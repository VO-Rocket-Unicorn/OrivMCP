from pydantic import Field

from oriv_mcp.config.constants import DEFAULT_MCP_PATH
from oriv_mcp.config.settings.base import EnvSettings


class ServerSettings(EnvSettings):
    """How the process identifies itself, binds, and serves MCP."""

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
    mcp_path: str = Field(
        default=DEFAULT_MCP_PATH,
        description=(
            "Path the streamable HTTP MCP endpoint is served from. The endpoint is "
            "also aliased at '/' so clients given a bare base URL still connect."
        ),
    )
