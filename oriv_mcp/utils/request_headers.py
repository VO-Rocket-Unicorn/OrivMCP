"""Read required values off the incoming MCP request.

What belongs here rather than in a tool argument: anything fixed for the
caller's session. A value the model cannot vary is a value it cannot get
wrong, and one it never has to be told.
"""

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import SecretStr

# The project a call is scoped to. Deliberately not named after any one
# service: a project is the caller's context, and which backend happens to
# serve it is not the caller's concern and may not stay the same one.
PROJECT_ID_HEADER = "X-Project-Id"
PROJECT_ID_HINT = (
    "The caller must supply the project id on that header. It is fixed for the "
    "session, which is why it is not a tool argument."
)


def _header_value(ctx: Context, header: str, hint: str) -> str:
    """Return a header's value, or fail the call with a message the model can act on.

    Header lookup is case-insensitive: streamable HTTP hands over Starlette's
    `Headers`, which folds case, but a transport that returns a plain dict
    would not.
    """
    headers = ctx.headers or {}
    value = headers.get(header) or headers.get(header.lower())
    if not value:
        raise ToolError(f"Missing the {header} request header. {hint}")
    return value


def require_header(ctx: Context, header: str, hint: str) -> str:
    """A required header that is not a credential."""
    return _header_value(ctx, header, hint)


def require_secret_header(ctx: Context, header: str, hint: str) -> SecretStr:
    """A required header that is a credential.

    Wrapped in `SecretStr` so the value cannot surface through a repr or a
    traceback's locals on the way to the service that needs it.
    """
    return SecretStr(_header_value(ctx, header, hint))
