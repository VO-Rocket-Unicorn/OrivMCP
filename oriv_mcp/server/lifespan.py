from contextlib import asynccontextmanager

from oriv_mcp.clients import device_class_client
from oriv_mcp.clients.transport import http_client
from oriv_mcp.config.logger_config import logger


async def _preflight() -> None:
    """Probe ODAS once at startup so a bad base URL surfaces here, not on the
    first tool call. Reported, never fatal — ODAS may simply come up later."""
    reachable, detail = await device_class_client.check_health()
    if reachable:
        logger.info("ODAS preflight: %s", detail)
    else:
        logger.error(
            "ODAS preflight FAILED: %s. Device-class tools will report the service "
            "as unavailable until this is fixed.",
            detail,
        )


@asynccontextmanager
async def lifespan(server):
    logger.info("Starting up the application...")
    await _preflight()
    try:
        yield
    finally:
        await http_client.aclose()
        logger.info("Shutting down the application...")
