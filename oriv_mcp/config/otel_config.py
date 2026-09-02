from importlib.metadata import version

from lib_oriv_telemetry.tracing import Telemetry

from oriv_mcp.config import settings
from oriv_mcp.utils import path_helpers

telemetry = Telemetry(
    service_name=settings.server.project_name,
    service_version=version(path_helpers.get_package_name()),
    environment=settings.app.environment,
    log_endpoint=settings.urls.otel_logs_url,
    trace_endpoint=settings.urls.otel_traces_url,
    metric_endpoint=settings.urls.otel_metrics_url,
)
