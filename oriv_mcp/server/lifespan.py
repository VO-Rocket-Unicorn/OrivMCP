from contextlib import asynccontextmanager

from oriv_mcp.clients.transport import http_client
from oriv_mcp.config.logger_config import logger


@asynccontextmanager
async def lifespan(server):
    logger.info("Starting up the application...")
    try:
        yield
    finally:
        await http_client.aclose()
        logger.info("Shutting down the application...")
