from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from oriv_mcp.server.rpc_router import handle_rpc
from oriv_mcp.schemas.rpc import (
    JSONRPCRequest,
    JSONRPCResponse,
)
from oriv_mcp.core.bootstrap import register_all
from oriv_mcp.server.stdio_server import stdio_loop


@asynccontextmanager
async def lifespan(app: FastAPI):

    # ----------------------------
    # Startup
    # ----------------------------

    register_all()

    # Start STDIO listener task
    stdio_task = asyncio.create_task(stdio_loop())

    app.state.stdio_task = stdio_task

    yield

    # ----------------------------
    # Shutdown
    # ----------------------------

    stdio_task.cancel()

    try:
        await stdio_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="oriv-mcp",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/rpc", response_model=JSONRPCResponse)
    async def rpc_endpoint(payload: JSONRPCRequest):
        response = await handle_rpc(payload)

        return JSONResponse(content=response.model_dump())

    return app


app = create_app()
