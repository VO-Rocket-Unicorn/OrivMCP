import sys

# sys.path.insert(0, "D:/VO/AI/OrivMCP")
# sys.path.insert(0, "/Users/sebinsaju/Documents/ORIV/OrivMCP")


from oriv_mcp.server.bootstrap import register_all_tools

from oriv_mcp.server.app import mcp_app

# Register all tools onto the same mcp_app instance

register_all_tools()


if __name__ == "__main__":

    mcp_app.run(transport="stdio")
