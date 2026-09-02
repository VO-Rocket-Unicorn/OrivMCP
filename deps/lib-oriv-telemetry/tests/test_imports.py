"""Smoke tests that verify the public API is importable."""


def test_top_level_imports() -> None:
    from lib_oriv_telemetry import (
        EnvironmentEnum,
        LLMUsageSpanProcessor,
        LoggerOverrides,
        ModelObservability,
        OTELFormatter,
        ObservabilityRecord,
        Telemetry,
        UsagePlugin,
        create_logger,
        ensure_logger,
        setup_logger,
    )

    assert EnvironmentEnum.PRODUCTION == "production"
    assert all(
        sym is not None
        for sym in (
            LLMUsageSpanProcessor,
            LoggerOverrides,
            ModelObservability,
            OTELFormatter,
            ObservabilityRecord,
            Telemetry,
            UsagePlugin,
            create_logger,
            ensure_logger,
            setup_logger,
        )
    )


def test_logs_subpackage() -> None:
    from lib_oriv_telemetry.logs import (
        LoggerOverrides,
        OTELFormatter,
        create_logger,
        ensure_logger,
        setup_logger,
    )

    assert all(
        sym is not None
        for sym in (
            LoggerOverrides,
            OTELFormatter,
            create_logger,
            ensure_logger,
            setup_logger,
        )
    )


def test_tracing_subpackage() -> None:
    from lib_oriv_telemetry.tracing import LLMUsageSpanProcessor, Telemetry

    assert LLMUsageSpanProcessor is not None
    assert Telemetry is not None


def test_metrics_subpackage() -> None:
    from lib_oriv_telemetry.metrics import ModelObservability, ObservabilityRecord

    assert ModelObservability is not None
    assert ObservabilityRecord is not None


def test_instrumentation_subpackage() -> None:
    from lib_oriv_telemetry.instrumentation import UsagePlugin

    assert UsagePlugin is not None
