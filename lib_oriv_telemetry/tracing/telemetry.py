"""Process-wide telemetry initialization and tracing helpers."""

import inspect
import logging
import warnings
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, AsyncIterator, Callable, Dict, Optional

from opentelemetry import context, metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import extract
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from lib_oriv_telemetry._internal.singleton import SingletonMeta
from lib_oriv_telemetry.enums import EnvironmentEnum
from lib_oriv_telemetry.tracing.processors import LLMUsageSpanProcessor


class Telemetry(metaclass=SingletonMeta):
    """Process-wide singleton that wires OpenTelemetry providers.

    Initialises tracing, metrics, and logs providers against OTLP/gRPC
    endpoints, and exposes helpers to decorate functions or open scoped
    spans with context propagation.
    """

    def __init__(
        self,
        *,
        service_name: str,
        service_version: str,
        environment: EnvironmentEnum,
        trace_endpoint: Optional[str] = None,
        log_endpoint: Optional[str] = None,
        metric_endpoint: Optional[str] = None,
        timeout: float | None = None,
        headers: Optional[Dict[str, str]] = None,
        tracing_enabled: bool = True,
        should_log: bool = False,
        trace_llm_metrics: bool = True,
    ) -> None:
        self._service_name = service_name
        self._tracing_enabled = tracing_enabled
        self._headers = headers or {}
        self._should_log = should_log
        self._trace_llm_metrics = trace_llm_metrics

        self._resource = Resource.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": environment,
            }
        )

        self.tracer_provider: TracerProvider | None = None
        self.meter_provider: MeterProvider | None = None
        self.logger_provider: LoggerProvider | None = None
        self.logging_handler: LoggingHandler | None = None

        if metric_endpoint:
            self._init_metrics(metric_endpoint, timeout)

        if trace_endpoint and tracing_enabled:
            self._init_tracing(trace_endpoint, timeout)

        if log_endpoint:
            self._init_logging(log_endpoint, timeout)

    def _init_metrics(self, endpoint: str, timeout: Optional[float]) -> None:
        readers = []

        if self._should_log:
            readers.append(
                PeriodicExportingMetricReader(
                    ConsoleMetricExporter(),
                    export_interval_millis=5000,
                )
            )

        readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=endpoint,
                    timeout=timeout,
                    headers=self._headers,
                ),
                export_interval_millis=5000,
            )
        )

        if self._trace_llm_metrics:
            self._instrument_llm_libraries()

        provider = MeterProvider(
            resource=self._resource,
            metric_readers=readers,
        )

        metrics.set_meter_provider(provider)
        self.meter_provider = provider

    def _init_tracing(self, endpoint: str, timeout: Optional[float]) -> None:
        provider = TracerProvider(resource=self._resource)

        exporter = (
            OTLPSpanExporter(endpoint=endpoint, timeout=timeout, headers=self._headers)
            if endpoint
            else ConsoleSpanExporter()
        )

        meter = metrics.get_meter("llm-usage")
        provider.add_span_processor(LLMUsageSpanProcessor(meter))
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)
        self.tracer_provider = provider

    def _init_logging(self, endpoint: str, timeout: Optional[float]) -> None:
        provider = LoggerProvider(resource=self._resource)
        set_logger_provider(provider)

        exporter = OTLPLogExporter(
            endpoint=endpoint,
            timeout=timeout,
            headers=self._headers,
            insecure=True,
        )

        provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        self.logging_handler = LoggingHandler(logger_provider=provider)
        self.logging_handler.setLevel(logging.INFO)
        self.logger_provider = provider

    @staticmethod
    def _instrument_llm_libraries() -> None:
        missing: list[str] = []

        try:
            from openinference.instrumentation.litellm import LiteLLMInstrumentor

            LiteLLMInstrumentor().instrument()
        except ImportError:
            missing.append("litellm")

        try:
            from openinference.instrumentation.dspy import DSPyInstrumentor

            DSPyInstrumentor().instrument()
        except ImportError:
            missing.append("dspy")

        if missing:
            extras = ",".join(missing)
            warnings.warn(
                f"trace_llm_metrics=True but instrumentation extras are missing: "
                f"{', '.join(missing)}. "
                f"Install with: pip install lib-oriv-telemetry[{extras}]",
                stacklevel=3,
            )

    def get_tracer(self, name: Optional[str] = None):
        if not self._tracing_enabled:
            return trace.get_tracer_provider().get_tracer("noop")
        return trace.get_tracer(name or self._service_name or "default")

    def trace_method(
        self,
        func: Callable | None = None,
        *,
        tracer_name: Optional[str] = None,
    ):
        """Decorator that traces sync or async methods with named spans."""

        def decorator(f):
            if not self._tracing_enabled:
                return f

            tracer = self.get_tracer(tracer_name or f.__name__)

            async def async_wrapped(*args, **kwargs):
                span_name = self._span_name(f, args)
                with tracer.start_as_current_span(span_name) as span:
                    self._record_args(span, args, kwargs)
                    return await f(*args, **kwargs)

            def sync_wrapped(*args, **kwargs):
                span_name = self._span_name(f, args)
                with tracer.start_as_current_span(span_name) as span:
                    self._record_args(span, args, kwargs)
                    return f(*args, **kwargs)

            return (
                wraps(f)(async_wrapped)
                if inspect.iscoroutinefunction(f)
                else wraps(f)(sync_wrapped)
            )

        return decorator if func is None else decorator(func)

    @asynccontextmanager
    async def trace_context(
        self,
        *,
        span_name: str,
        headers: Optional[Dict[str, str]] = None,
        tracer_name: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[None]:
        """Async context manager that opens a span with optional context extraction."""
        if not self._tracing_enabled:
            yield
            return

        token = None
        if headers:
            token = context.attach(extract(headers))

        tracer = self.get_tracer(tracer_name)

        try:
            with tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, str(v))
                yield
        finally:
            if token is not None:
                context.detach(token)

    @staticmethod
    def _span_name(func, args):
        if args and hasattr(args[0], "__class__"):
            return f"{args[0].__class__.__name__}.{func.__name__}"
        return func.__name__

    @staticmethod
    def _record_args(span, args, kwargs):
        for idx, arg in enumerate(args):
            span.set_attribute(f"arg.{idx}", str(arg))
        for k, v in kwargs.items():
            span.set_attribute(f"arg.{k}", str(v))
