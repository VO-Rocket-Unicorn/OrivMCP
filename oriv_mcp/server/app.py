from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import (
    TransportSecuritySettings,
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
