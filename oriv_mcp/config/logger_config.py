from lib_oriv_telemetry.logs import create_logger
from lib_oriv_telemetry.enums import EnvironmentEnum

from oriv_mcp.config import settings


logger = create_logger(
    name=settings.project_name,
    environment=settings.environment,
    log_file_path=settings.log_file_path
    if settings.environment != EnvironmentEnum.SANDBOX
    else None,
    console_log=settings.environment == EnvironmentEnum.SANDBOX,
)
