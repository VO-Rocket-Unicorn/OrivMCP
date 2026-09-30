"""Abstract base for model usage plugins."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Tuple

from lib_oriv_telemetry._internal.typevars import T


class UsagePlugin(ABC, Generic[T]):
    """Defines how usage is measured and labelled for a model invocation."""

    name: str  # e.g. "llm", "ocr"

    @property
    @abstractmethod
    def metric_definitions(self) -> Dict[str, str]:
        """Return the canonical metric-name -> description map."""
        ...

    @abstractmethod
    def extract_metrics(self, usage: T) -> Dict[str, float]:
        """Convert a provider-specific usage object into numeric metrics."""
        ...

    @abstractmethod
    def span_attributes(self, usage: T) -> Dict[str, Any]:
        """Return attributes to attach to the active trace span."""
        ...

    @abstractmethod
    def get_model_details(self, usage: T) -> Tuple[str, str]:
        """Return ``(provider, model)`` for the given usage object.

        Must always return a tuple. Use ``"unknown"`` when a value cannot
        be determined.
        """
        ...

    @property
    @abstractmethod
    def counter_metric_definitions(self) -> Dict[str, str]:
        """Metrics that should be emitted as cumulative counters."""
        ...

    @property
    @abstractmethod
    def histogram_metric_definitions(self) -> Dict[str, str]:
        """Metrics that should be emitted as per-request histograms."""
        ...
