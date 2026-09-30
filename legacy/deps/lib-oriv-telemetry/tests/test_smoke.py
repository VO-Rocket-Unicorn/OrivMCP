"""End-to-end smoke tests using a fake usage plugin."""

from typing import Any, Dict, Tuple

import pytest

from lib_oriv_telemetry import (
    EnvironmentEnum,
    LoggerOverrides,
    ModelObservability,
    ObservabilityRecord,
    Telemetry,
    UsagePlugin,
    create_logger,
)


class _FakeUsage:
    """Minimal usage object used by FakeUsagePlugin."""

    def __init__(self, tokens: int, model: str = "fake-1") -> None:
        self.tokens = tokens
        self.model = model


class FakeUsagePlugin(UsagePlugin[_FakeUsage]):
    """In-memory usage plugin for tests; no external deps."""

    name = "fake"

    @property
    def metric_definitions(self) -> Dict[str, str]:
        return {"fake_tokens_total": "Fake tokens"}

    @property
    def counter_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    @property
    def histogram_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    def extract_metrics(self, usage: _FakeUsage) -> Dict[str, float]:
        return {"fake_tokens_total": usage.tokens}

    def span_attributes(self, usage: _FakeUsage) -> Dict[str, Any]:
        return {"fake.tokens": usage.tokens, "fake.model": usage.model}

    def get_model_details(self, usage: _FakeUsage) -> Tuple[str, str]:
        return "fake-provider", usage.model


def test_create_logger_no_file() -> None:
    logger = create_logger(
        name="lib_oriv_telemetry.test_smoke",
        environment=EnvironmentEnum.SANDBOX,
        reuse_existing=False,
    )
    assert logger.name == "lib_oriv_telemetry.test_smoke"
    assert logger.level == 10  # DEBUG, because SANDBOX


def test_logger_overrides_defaults() -> None:
    overrides = LoggerOverrides()
    assert "uvicorn" in overrides.combined_loggers
    assert overrides.console_log is True


def test_telemetry_construction_without_endpoints() -> None:
    """No endpoints means no providers are configured but construction succeeds."""
    Telemetry._instances.pop(Telemetry, None)  # reset singleton
    tel = Telemetry(
        service_name="smoke-test",
        service_version="0.0.0",
        environment=EnvironmentEnum.SANDBOX,
    )
    assert tel.tracer_provider is None
    assert tel.meter_provider is None
    assert tel.logger_provider is None


def test_telemetry_singleton() -> None:
    Telemetry._instances.pop(Telemetry, None)
    a = Telemetry(
        service_name="smoke", service_version="0", environment=EnvironmentEnum.SANDBOX
    )
    b = Telemetry(
        service_name="other", service_version="9", environment=EnvironmentEnum.PRODUCTION
    )
    assert a is b


def test_model_observability_build_record() -> None:
    obs = ModelObservability(plugin=FakeUsagePlugin())
    record = obs.build_record(
        usage=_FakeUsage(tokens=42),
        latency_seconds=0.123,
        extra_attributes={"tenant": "acme"},
    )
    assert isinstance(record, ObservabilityRecord)
    assert record.model_provider == "fake-provider"
    assert record.model_name == "fake-1"
    assert record.model_type == "fake"
    assert record.metrics == {"fake_tokens_total": 42}
    assert record.span_attributes["fake.tokens"] == 42
    assert record.extra_attributes == {"tenant": "acme"}


def test_model_observability_emit_does_not_raise() -> None:
    obs = ModelObservability(plugin=FakeUsagePlugin())
    record = obs.build_record(usage=_FakeUsage(tokens=7), latency_seconds=0.01)
    obs.emit(record)


@pytest.mark.asyncio
async def test_model_observability_observe_context() -> None:
    obs = ModelObservability(plugin=FakeUsagePlugin())
    async with obs.observe() as submit:
        submit(_FakeUsage(tokens=3))


@pytest.mark.asyncio
async def test_model_observability_observe_without_submit_records_nothing() -> None:
    obs = ModelObservability(plugin=FakeUsagePlugin())
    async with obs.observe():
        pass
