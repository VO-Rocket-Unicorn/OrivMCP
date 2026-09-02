"""Logging formatters that enrich records with OpenTelemetry context."""

import logging
from typing import Optional

from opentelemetry.trace import get_current_span


class OTELFormatter(logging.Formatter):
    """Logging formatter that injects OpenTelemetry trace and span IDs.

    Records the active span's ``trace_id`` and ``span_id`` (as zero-padded
    hex strings) onto every log record, falling back to all-zero IDs when
    no span is active.

    Args:
        fmt: Logging format string. Defaults to ``DEFAULT_FMT``.
        datefmt: Date format string.
    """

    DEFAULT_FMT = (
        "%(asctime)s %(levelname)s [%(name)s] "
        "[%(module)s.%(funcName)s:%(lineno)d] "
        "[%(spanId)s - %(traceId)s] %(message)s"
    )

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt=fmt or self.DEFAULT_FMT, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        span = get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            record.traceId = format(span_context.trace_id, "032x")
            record.spanId = format(span_context.span_id, "016x")
        else:
            record.traceId = "0" * 32
            record.spanId = "0" * 16
        return super().format(record)
