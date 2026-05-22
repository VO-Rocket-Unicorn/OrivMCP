from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import (
    TransportSecuritySettings,
)
from starlette.responses import JSONResponse

from oriv_mcp.server.bootstrap import (
    register_all_tools,
)
from oriv_mcp.config import settings
from oriv_mcp.server.lifespan import lifespan

mcp_app = FastMCP(
    name=settings.project_name,
    host=settings.host,
    port=settings.port,
    transport_security=TransportSecuritySettings(
        # IMPORTANT
        allowed_hosts=settings.allowed_hosts,
        # optional
        allowed_origins=settings.allowed_origins,
    ),
    lifespan=lifespan,
)


# Register once
register_all_tools()


app = mcp_app.streamable_http_app()


# Health check endpoint
async def health_check(request):
    return JSONResponse({"status": "ok"})


app.router.add_route(
    path="/health",
    endpoint=health_check,
    methods=["GET"],
)
