from pydantic import Field

from oriv_mcp.config.settings.base import EnvSettings


class HttpSettings(EnvSettings):
    """Outbound HTTP behaviour for the services this server calls."""

    http_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="Per-request timeout for outbound calls, in seconds.",
    )
    http_max_connections: int = Field(
        default=20,
        gt=0,
        description="Connection-pool ceiling for the shared HTTP client.",
    )
