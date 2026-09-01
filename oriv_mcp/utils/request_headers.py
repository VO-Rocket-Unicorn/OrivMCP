"""Read required values off the incoming MCP request."""

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import SecretStr


def require_secret_header(ctx: Context, header: str, hint: str) -> SecretStr:
    """Return a header's value, or fail the call with a message the model can act on.

    Header lookup is case-insensitive: streamable HTTP hands over Starlette's
    `Headers`, which folds case, but a transport that returns a plain dict
    would not.

    Wrapped in `SecretStr` so the value cannot surface through a repr or a
    traceback's locals on the way to the service that needs it.
    """
    headers = ctx.headers or {}
    value = headers.get(header) or headers.get(header.lower())
    if not value:
        raise ToolError(f"Missing the {header} request header. {hint}")
    return SecretStr(value)
