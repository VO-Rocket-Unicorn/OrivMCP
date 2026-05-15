import uvicorn

from oriv_mcp.server.app import (
    mcp_app,
)

from oriv_mcp.server.bootstrap import (
    register_all_tools,
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
