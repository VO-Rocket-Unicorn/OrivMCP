from importlib.metadata import version

from lib_oriv_telemetry.tracing import Telemetry

from oriv_mcp.config import settings
from oriv_mcp.utils import path_helpers

telemetry = Telemetry(
    service_name=settings.project_name,
    service_version=version(path_helpers.get_package_name()),
    environment=settings.environment,
    log_endpoint=settings.log_endpoint,
    trace_endpoint=settings.trace_endpoint,
    metric_endpoint=settings.metric_endpoint,
)
