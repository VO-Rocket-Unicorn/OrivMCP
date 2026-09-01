from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import (
    TransportSecuritySettings,
)
from starlette.responses import JSONResponse
from starlette.routing import Route

from oriv_mcp.config import settings
from oriv_mcp.config.settings import ROOT_PATH
from oriv_mcp.server.bootstrap import (
    register_all_tools,
)

HEALTH_PATH = "/health"

mcp_app = MCPServer(
    name=settings.project_name,
)


# Register once
register_all_tools()


app = mcp_app.streamable_http_app(
    streamable_http_path=settings.mcp_path,
    transport_security=TransportSecuritySettings(
        # IMPORTANT
        allowed_hosts=settings.allowed_hosts,
        # optional
        allowed_origins=settings.allowed_origins,
    ),
)


# Starlette matches routes exactly, so a client pointed at the bare base URL
# (POST /) would 404. Alias the same ASGI endpoint at the root.
if settings.mcp_path != ROOT_PATH:
    mcp_route = next(
        route
        for route in app.router.routes
        if getattr(route, "path", None) == settings.mcp_path
    )
    app.router.routes.append(Route(ROOT_PATH, endpoint=mcp_route.endpoint))


# Health check endpoint
async def health_check(request):
    return JSONResponse({"status": "ok"})


app.router.add_route(
    path=HEALTH_PATH,
    endpoint=health_check,
    methods=["GET"],
)
