from oriv_mcp.server.bootstrap import register_all_tools
from oriv_mcp.server.app import mcp_app

# Register all tools onto the same mcp_app instance

register_all_tools()


if __name__ == "__main__":
    mcp_app.run(transport="stdio")
