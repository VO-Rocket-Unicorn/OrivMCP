from pydantic_settings import BaseSettings, SettingsConfigDict

from oriv_mcp.config.constants import ENV_FILE


class EnvSettings(BaseSettings):
    """Shared base for every settings group.

    Each group reads the same .env with flat variable names, so the grouping is
    a code-side concern only — no environment variable is renamed by it.
    """

    model_config = SettingsConfigDict(
        # env_prefix="ORIV_MCP_",
        env_file=ENV_FILE,
        extra="ignore",
    )
