from contextlib import asynccontextmanager
from oriv_mcp.config.http_config import http_client


@asynccontextmanager
async def lifespan(app):
    try:
        # Code to run on startup
        print("Starting up the application...")
        yield
    finally:
        await http_client.aclose()  # Close the HTTP client on shutdown
        # Code to run on shutdown
        print("Shutting down the application...")
