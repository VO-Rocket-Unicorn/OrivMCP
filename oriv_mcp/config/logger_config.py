from lib_oriv_telemetry.logs import create_logger
from lib_oriv_telemetry.enums import EnvironmentEnum

from oriv_mcp.config import settings
from oriv_mcp.config.otel_config import telemetry
from oriv_mcp.utils import path_helpers


logger = create_logger(
    name=settings.server.project_name,
    environment=settings.app.environment,
    level=settings.app.log_level,
    log_file_path=str(path_helpers.get_repo_root() / (settings.app.log_file_path))
    if settings.app.environment != EnvironmentEnum.SANDBOX
    else None,
    console_log=settings.app.environment == EnvironmentEnum.SANDBOX,
    handlers=[telemetry.logging_handler]
    if (settings.app.environment != EnvironmentEnum.SANDBOX and telemetry.logging_handler)
    else None,
)
