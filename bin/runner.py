import uvicorn

from oriv_mcp.config import settings


def run():
    """
    Starts the FastAPI application using Uvicorn.
    This function launches the FastAPI server with host and log level
    determined by the environment configuration.

    - In PRODUCTION: binds to 0.0.0.0 and uses INFO logging level.
    - In other environments: binds to 127.0.0.1 and uses DEBUG logging level.
    """

    uvicorn.run(
        app="oriv_mcp.server.app:app",
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        timeout_keep_alive=settings.server.timeout_keep_alive,
    )


if __name__ == "__main__":
    run()
