import logging

from lib_oriv_telemetry.enums import EnvironmentEnum
from pydantic import Field, computed_field

from oriv_mcp.config.settings.base import EnvSettings
from oriv_mcp.utils.path_helpers import get_repo_root

LOGS_DIRECTORY_NAME = "logs"


class AppSettings(EnvSettings):
    """Environment the process runs in, and where it writes and reads on disk."""

    environment: EnvironmentEnum = Field(
        default=EnvironmentEnum.PRODUCTION,
        description="Application environment (e.g., development, staging, production)",
    )
    log_file_path: str = Field(
        default_factory=lambda: str(get_repo_root() / LOGS_DIRECTORY_NAME),
        description="File path for application logs",
    )

    @computed_field
    @property
    def log_level(self) -> int:
        """Determine log level based on environment."""
        return (
            logging.DEBUG
            if self.environment == EnvironmentEnum.SANDBOX
            else logging.INFO
        )
