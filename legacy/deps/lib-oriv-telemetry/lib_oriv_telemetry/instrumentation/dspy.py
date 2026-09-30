"""Usage plugin for DSPy LLM predictions.

Requires the ``dspy`` extra::

    pip install lib-oriv-telemetry[dspy]
"""

from typing import Any, Dict, Tuple, override

try:
    from dspy.primitives.prediction import Prediction
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "DSPy is required for lib_oriv_telemetry.instrumentation.dspy. "
        "Install with: pip install lib-oriv-telemetry[dspy]"
    ) from exc

from lib_oriv_telemetry.instrumentation.base import UsagePlugin


class DSPyPredictionUsagePlugin(UsagePlugin[Prediction]):
    """Usage plugin that extracts LLM token usage from DSPy predictions."""

    name = "llm"

    PROVIDER: str = "dspy"

    def __init__(self, use_mock: bool = False) -> None:
        """Args:
        use_mock: If ``True`` returns random mock data instead of
            extracting real usage. Useful for local development.
        """
        self._use_mock = use_mock
        super().__init__()

    @property
    def metric_definitions(self) -> Dict[str, str]:
        return {
            "llm_prompt_tokens_total": "Total LLM prompt tokens",
            "llm_completion_tokens_total": "Total LLM completion tokens",
            "llm_total_tokens_total": "Total LLM tokens",
        }

    @property
    def counter_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    @property
    def histogram_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    @override
    def extract_metrics(self, response: Prediction) -> Dict[str, int]:
        if self._use_mock:
            return self._mock_data()

        _, usage = self._get_usage_with_model(response)

        prompt = int(usage.get("prompt_tokens", 0))
        completion = int(usage.get("completion_tokens", 0))
        total = int(usage.get("total_tokens", prompt + completion))

        return {
            "llm_prompt_tokens_total": prompt,
            "llm_completion_tokens_total": completion,
            "llm_total_tokens_total": total,
        }

    @override
    def span_attributes(self, response: Prediction) -> Dict[str, Any]:
        model, usage = self._get_usage_with_model(response)

        prompt = int(usage.get("prompt_tokens", 0))
        completion = int(usage.get("completion_tokens", 0))
        total = int(usage.get("total_tokens", prompt + completion))

        attributes: Dict[str, str | int] = {
            "llm.provider": self.PROVIDER,
            "llm.usage.prompt_tokens": prompt,
            "llm.usage.completion_tokens": completion,
            "llm.usage.total_tokens": total,
        }

        if model:
            attributes["llm.model"] = model

        return attributes

    @override
    def get_model_details(self, response: Prediction) -> Tuple[str, str]:
        model, _ = self._get_usage_with_model(response)
        return self.PROVIDER, model or "unknown"

    def _get_usage_with_model(
        self, response: Prediction
    ) -> Tuple[str | None, Dict[str, int]]:
        """Extract model name and token usage from a DSPy Prediction.

        DSPy returns usage shaped as::

            {"model/name": {"prompt_tokens": ..., "completion_tokens": ..., "total_tokens": ...}}
        """
        try:
            usage_map = response.get_lm_usage() or {}
        except Exception:
            return None, {}

        if not usage_map:
            return None, {}

        model, usage = next(iter(usage_map.items()))
        return model, usage

    @staticmethod
    def _mock_data() -> Dict[str, int]:
        import random

        prompt = random.randint(1, 5000)
        completion = random.randint(1, 5000)
        return {
            "llm_prompt_tokens_total": prompt,
            "llm_completion_tokens_total": completion,
            "llm_total_tokens_total": prompt + completion,
        }
