from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from aeromcp.server.rpc_router import handle_rpc
from aeromcp.schemas.rpc import JSONRPCRequest, JSONRPCResponse
from aeromcp.core.bootstrap import register_all


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ---- startup ----
    register_all()

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AeroMCP",
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
