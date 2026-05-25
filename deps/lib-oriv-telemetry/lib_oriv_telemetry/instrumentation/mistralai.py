"""Usage plugin for Mistral OCR responses.

Requires the ``mistral`` extra::

    pip install lib-oriv-telemetry[mistral]
"""

from typing import Any, Dict, Tuple, override

try:
    from mistralai.client import models
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "mistralai is required for lib_oriv_telemetry.instrumentation.mistralai. "
        "Install with: pip install lib-oriv-telemetry[mistral]"
    ) from exc

from lib_oriv_telemetry.instrumentation.base import UsagePlugin


class OCRUsagePlugin(UsagePlugin[models.OCRResponse]):
    """Usage plugin for collecting OCR metrics from Mistral OCR responses."""

    name = "ocr"
    PROVIDER = "mistral"

    @property
    @override
    def metric_definitions(self) -> Dict[str, str]:
        return {
            "ocr_pages_total": "Total OCR pages processed",
            "ocr_document_bytes_total": "Total OCR document size in bytes",
        }

    @property
    def counter_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    @property
    def histogram_metric_definitions(self) -> Dict[str, str]:
        return self.metric_definitions

    @override
    def extract_metrics(self, response: models.OCRResponse) -> Dict[str, int]:
        usage = response.usage_info
        doc_bytes = usage.doc_size_bytes or 0

        return {
            "ocr_pages_total": usage.pages_processed,
            "ocr_document_bytes_total": doc_bytes,
        }

    @override
    def span_attributes(self, response: models.OCRResponse) -> Dict[str, Any]:
        usage = response.usage_info
        doc_bytes = usage.doc_size_bytes or 0

        return {
            "ocr.provider": self.PROVIDER,
            "ocr.pages": usage.pages_processed,
            "ocr.document_bytes": doc_bytes,
            "ocr.model": response.model,
        }

    @override
    def get_model_details(self, response: models.OCRResponse) -> Tuple[str, str]:
        return self.PROVIDER, response.model
