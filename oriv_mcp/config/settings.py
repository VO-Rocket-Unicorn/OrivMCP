from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from lib_oriv_telemetry.enums import EnvironmentEnum


class Settings(BaseSettings):
    """
    Application runtime configuration.
    Reads from environment variables with prefix: ORIV_MCP_
    """

    model_config = SettingsConfigDict(
        # env_prefix="ORIV_MCP_",
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
    environment: EnvironmentEnum = Field(
        default=EnvironmentEnum.PRODUCTION,
        description="Application environment (e.g., development, staging, production)",
    )
    log_file_path: str = Field(
        default="logs", description="File path for application logs"
    )

    allowed_hosts: list[str] = Field(
        default_factory=list, description="List of allowed hosts for CORS"
    )
    allowed_origins: list[str] = Field(
        default_factory=list, description="List of allowed origins for CORS"
    )

    # ---- urls ----
    code_generation_base_url: str = Field(
        ...,
        description="Base URL for the code generation service",
    )
    csas_base_url: str = Field(
        ...,
        description="Base URL for the CSAS service",
    )

    csas_origin: str = Field(
        default="oriv_mcp",
        description="Origin header value to use when making requests to CSAS. Set to 'localhost' if CSAS is running locally without CORS restrictions.",
    )

    otel_url: str = Field(
        ...,
        description="Endpoint URL for sending logs",
    )

    def get_simulation_schema_url(self, category: str) -> str:
        """Construct the URL to retrieve the simulation schema for a given category."""
        return f"{self.code_generation_base_url}/simulations/{category}/schema"

    @computed_field
    @property
    def component_list_url(self) -> str:
        return f"{self.csas_base_url}/api/v1/internal/components"

    @computed_field
    @property
    def upload_datasheet_url(self) -> str:
        return f"{self.csas_base_url}/api/v1/internal/files/pdf"

    @computed_field
    @property
    def create_component_url(self) -> str:
        """Construct the URL to create a new component."""
        return f"{self.csas_base_url}/api/v1/internal/components/extract"

    def check_component_creation_status_url(self, component_id: str) -> str:
        """Construct the URL to check the status of component creation."""
        return f"{self.csas_base_url}/api/v1/internal/components/{component_id}/status"

    def create_simulation_url(self, component_id: str) -> str:
        """Construct the URL to create a new simulation for a given component."""
        return f"{self.csas_base_url}/api/v1/internal/components/{component_id}/simulations/new"

    def start_code_generation_url(self, component_id: str, simulation_id: str) -> str:
        """Construct the URL to start code generation for a given simulation."""
        return f"{self.csas_base_url}/api/v1/internal/components/{component_id}/simulations/{simulation_id}/code/generate"

    def get_code_generation_status_url(
        self, component_id: str, simulation_id: str
    ) -> str:
        """Construct the URL to get code generation status for a given simulation."""
        return f"{self.csas_base_url}/api/v1/internal/components/{component_id}/simulations/{simulation_id}/code/status"

    def start_simulation_execution_url(
        self, component_id: str, simulation_id: str
    ) -> str:
        """Construct the URL to start simulation execution for a given simulation."""
        return f"{self.csas_base_url}/api/v1/internal/components/{component_id}/simulations/{simulation_id}/execute"

    def get_simulation_execution_status_url(
        self, component_id: str, simulation_id: str
    ) -> str:
        """Construct the URL to get simulation execution status for a given simulation."""
        return f"{self.csas_base_url}/api/v1/internal/components/{component_id}/simulations/{simulation_id}/execution/status"

    @computed_field
    @property
    def otel_logs_url(self) -> str:
        """Otel logs url"""
        return f"{self.otel_url}/v1/logs"

    @computed_field
    @property
    def otel_traces_url(self) -> str:
        """Otel traces url"""
        return f"{self.otel_url}/v1/traces"

    @computed_field
    @property
    def otel_metrics_url(self) -> str:
        """Otel metrics url"""
        return f"{self.otel_url}/v1/metrics"


# singleton instance
settings = Settings()  # type: ignore
