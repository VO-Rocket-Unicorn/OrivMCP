from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application runtime configuration.
    Reads from environment variables with prefix: ORIV_MCP_
    """

    model_config = SettingsConfigDict(
        env_prefix="ORIV_MCP_",
        env_file=".env",
        extra="ignore",
    )

    # ---- server ----
    project_name: str = Field(
        default="OrivMCP", description="Project name for the MCP server"
    )
    host: str = Field(default="0.0.0.0", description="Host to run the server on")
    port: int = Field(default=8000, description="Port to run the server on")
    workers: int = Field(
        default=1, description="Number of worker processes for handling requests"
    )
    timeout_keep_alive: int = Field(
        default=5,
        description="Number of seconds to wait for the next request on a Keep-Alive connection",
    )

    # ---- environment ----
    env: str = Field(default="development", description="Application environment")

    allowed_hosts: list[str] = Field(
        default_factory=list, description="List of allowed hosts for CORS"
    )
    allowed_origins: list[str] = Field(
        default_factory=list, description="List of allowed origins for CORS"
    )


# singleton instance
settings = Settings()
