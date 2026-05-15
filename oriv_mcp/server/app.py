import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import (
    TransportSecuritySettings,
)

from oriv_mcp.server.bootstrap import (
    register_all_tools,
)

mcp_app = FastMCP(
    "AeroMCP",
    host="0.0.0.0",
    port=8000,
    transport_security=TransportSecuritySettings(
        # IMPORTANT
        allowed_hosts=[
            "progeny-certainly-dating.ngrok-free.dev",
            "127.0.0.1",
            "localhost",
        ],
        # optional
        allowed_origins=[
            "https://progeny-certainly-dating.ngrok-free.dev",
        ],
    ),
)


# Register once
register_all_tools()


app = mcp_app.streamable_http_app()


if __name__ == "__main__":

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        # proxy_headers=True,
        forwarded_allow_ips="*",
    )
