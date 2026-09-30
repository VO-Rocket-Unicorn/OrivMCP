"""Custom span processors for telemetry pipelines."""

from typing import Optional

from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor


class LLMUsageSpanProcessor(SpanProcessor):
    """Span processor that records LLM token usage as metric histograms.

    Reads OpenInference span attributes emitted by LLM/agent instrumentations
    and converts them to four histograms:

    - ``llm_tokens_total``
    - ``llm_tokens_prompt``
    - ``llm_tokens_completion``
    - ``llm_latency_ms``
    """

    def __init__(self, meter) -> None:
        self._total_tokens = meter.create_histogram(
            name="llm_tokens_total",
            description="Total LLM tokens per request",
            unit="tokens",
        )
        self._prompt_tokens = meter.create_histogram(
            name="llm_tokens_prompt",
            description="LLM prompt tokens per request",
            unit="tokens",
        )
        self._completion_tokens = meter.create_histogram(
            name="llm_tokens_completion",
            description="LLM completion tokens per request",
            unit="tokens",
        )
        self._latency_ms = meter.create_histogram(
            name="llm_latency_ms",
            description="End-to-end LLM request latency",
            unit="ms",
        )

    def on_end(self, span: ReadableSpan) -> None:
        attrs = span.attributes or {}

        model_name = attrs.get("llm.model_name")
        provider = attrs.get("llm.provider")

        if not model_name and not attrs.get("llm.token_count.total"):
            return

        attributes = {
            "service": span.resource.attributes.get("service.name", "unknown"),
            "model_name": model_name or "unknown",
            "provider": provider or "unknown",
        }

        if span.start_time and span.end_time:
            latency_ms = (span.end_time - span.start_time) / 1_000_000
            self._latency_ms.record(latency_ms, attributes)

        total = self._as_int(attrs.get("llm.token_count.total"))
        prompt = self._as_int(attrs.get("llm.token_count.prompt"))
        completion = self._as_int(attrs.get("llm.token_count.completion"))

        if total:
            self._total_tokens.record(total, attributes)
        if prompt:
            self._prompt_tokens.record(prompt, attributes)
        if completion:
            self._completion_tokens.record(completion, attributes)

    def shutdown(self) -> None:
        pass

    @staticmethod
    def _as_int(value) -> Optional[int]:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None
