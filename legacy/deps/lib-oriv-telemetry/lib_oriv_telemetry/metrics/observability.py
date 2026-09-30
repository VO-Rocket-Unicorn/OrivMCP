"""Provider-agnostic observability helper for model invocations.

Wraps any model call (LLM, OCR, embeddings, etc.) and emits metrics + span
attributes according to the metric identities declared by a
:class:`~lib_oriv_telemetry.instrumentation.base.UsagePlugin`.
"""

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, Generic, Optional

from opentelemetry import metrics, trace
from pydantic import BaseModel, Field

from lib_oriv_telemetry._internal.typevars import T
from lib_oriv_telemetry.instrumentation.base import UsagePlugin


class ObservabilityRecord(BaseModel):
    """Serializable observability payload for a single model invocation."""

    model_provider: str = Field(
        ...,
        description="Name of the model provider (e.g., mistral, openai, anthropic).",
        examples=["mistral"],
    )
    model_name: str = Field(
        ...,
        description="Identifier of the model used to process the request.",
        examples=["ocr-large"],
    )
    model_type: str = Field(
        ...,
        description="Logical model category (e.g., llm, ocr, embeddings).",
        examples=["ocr"],
    )
    latency_seconds: float = Field(
        ...,
        ge=0,
        description="End-to-end request latency measured in seconds.",
        examples=[0.842],
    )
    metrics: Dict[str, int | float] = Field(
        ...,
        description="Aggregated numeric usage metrics extracted from the response.",
        examples=[{"ocr_pages_total": 4, "ocr_document_bytes_total": 102400}],
    )
    span_attributes: Dict[str, Any] = Field(
        ...,
        description="Span attributes to attach to the active OpenTelemetry span.",
        examples=[{"ocr.pages": 4, "ocr.model": "ocr-large"}],
    )
    extra_attributes: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metric/span dimensions (e.g., request_id, tenant_id).",
        examples=[{"request_id": "abc-123"}],
    )


class ModelObservability(Generic[T]):
    """Generic observability helper for model invocations.

    Design principles:

    - Metric names are defined exclusively by the plugin.
    - No suffixes, prefixes, or semantic assumptions are applied.
    - Counters and histograms are created strictly from plugin-declared metadata.
    - Observability is pure infrastructure.
    """

    def __init__(self, *, plugin: UsagePlugin[T]) -> None:
        """Initialize OpenTelemetry instruments based on plugin-defined metrics.

        The plugin declares:

        - ``counter_metric_definitions``: cumulative metrics
        - ``histogram_metric_definitions``: per-request metrics
        """
        self._plugin = plugin
        meter = metrics.get_meter(f"oriv.{plugin.name}")

        self._requests_total = meter.create_counter(
            name=f"{plugin.name}_requests_total",
            description=f"Total number of {plugin.name.upper()} requests",
        )

        self._counters = {
            metric_name: meter.create_counter(
                name=f"{plugin.name}_{metric_name}",
                description=description,
            )
            for metric_name, description in plugin.counter_metric_definitions.items()
        }

        self._latency_seconds = meter.create_histogram(
            name=f"{plugin.name}_request_latency_seconds",
            description=f"{plugin.name.upper()} request latency",
            unit="s",
        )

        self._histograms = {
            metric_name: meter.create_histogram(
                name=f"{plugin.name}_{metric_name}_per_request",
                description=description,
            )
            for metric_name, description in plugin.histogram_metric_definitions.items()
        }

    def build_record(
        self,
        *,
        usage: T,
        latency_seconds: float,
        extra_attributes: Optional[Dict[str, Any]] = None,
    ) -> ObservabilityRecord:
        """Construct an :class:`ObservabilityRecord` from a usage object."""
        provider, model = self._plugin.get_model_details(usage)

        return ObservabilityRecord(
            model_provider=provider,
            model_name=model,
            model_type=self._plugin.name,
            latency_seconds=latency_seconds,
            metrics=self._plugin.extract_metrics(usage),
            span_attributes=self._plugin.span_attributes(usage),
            extra_attributes=extra_attributes or {},
        )

    def emit(self, record: ObservabilityRecord) -> None:
        """Emit metrics and trace attributes for a completed model invocation."""
        metric_attrs: Dict[str, Any] = {
            "service": record.model_type,
            "model_provider": record.model_provider,
            "model_name": record.model_name,
            **record.extra_attributes,
        }

        self._requests_total.add(1, attributes=metric_attrs)

        for metric_name, counter in self._counters.items():
            value = record.metrics.get(metric_name)
            if isinstance(value, (int, float)):
                counter.add(value, attributes=metric_attrs)

        self._latency_seconds.record(
            record.latency_seconds,
            attributes=metric_attrs,
        )

        for metric_name, histogram in self._histograms.items():
            value = record.metrics.get(metric_name)
            if isinstance(value, (int, float)):
                histogram.record(value, attributes=metric_attrs)

        span = trace.get_current_span()
        if not span.is_recording():
            return

        span.set_attribute("model.provider", record.model_provider)
        span.set_attribute("model.name", record.model_name)
        span.set_attribute("model.type", record.model_type)
        span.set_attribute("model.latency_seconds", record.latency_seconds)

        for key, value in record.span_attributes.items():
            span.set_attribute(key, value)

    @asynccontextmanager
    async def observe(
        self,
        extra_attributes: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Callable[[T], T]]:
        """Async context manager for observing a single model invocation.

        Yields a ``submit`` callable; pass the model's usage object to it to
        record metrics and span attributes when the context exits. If
        ``submit`` is never called, nothing is recorded.
        """
        start = time.perf_counter()
        usage: Optional[T] = None

        def submit(value: T) -> T:
            """Capture the usage object produced by the model invocation."""
            nonlocal usage
            usage = value
            return value

        try:
            yield submit
        finally:
            if usage is not None:
                record = self.build_record(
                    usage=usage,
                    latency_seconds=time.perf_counter() - start,
                    extra_attributes=extra_attributes,
                )
                self.emit(record)
