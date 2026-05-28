from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import (
    TransportSecuritySettings,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from oriv_mcp.auth.keys import load_or_generate_keypair
from oriv_mcp.auth.login_routes import login_get, login_post
from oriv_mcp.auth.provider import OrivOAuthProvider
from oriv_mcp.config import settings
from oriv_mcp.server.bootstrap import (
    register_all_tools,
)
from oriv_mcp.server.lifespan import lifespan

_key_material = load_or_generate_keypair(settings.keys_dir)
_provider = OrivOAuthProvider(_key_material)

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
    auth=AuthSettings(
        issuer_url=settings.auth_base_url,
        resource_server_url=settings.auth_base_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=settings.supported_scopes,
            default_scopes=settings.supported_scopes,
        ),
        required_scopes=["read"],
    ),
    auth_server_provider=_provider,
)


@mcp_app.custom_route("/login", methods=["GET"])
async def _login_get(request: Request) -> Response:
    return await login_get(request)


@mcp_app.custom_route("/login", methods=["POST"])
async def _login_post(request: Request) -> Response:
    return await login_post(request)


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
