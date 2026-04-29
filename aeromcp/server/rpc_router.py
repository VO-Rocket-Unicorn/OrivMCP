from typing import Any, Callable, Awaitable, Dict, Type

from aeromcp.core.registry import tools, resources, prompts
from aeromcp.schemas.rpc import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    NamedInvocationParams,
    EmptyParams,
)


# JSON-RPC standard error codes
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class HandlerSpec:
    def __init__(
        self,
        params_model: Type,
        handler: Callable[[Any], Awaitable[Any]],
    ):
        self.params_model = params_model
        self.handler = handler


# ---- Handlers ----


async def tools_list(_: EmptyParams):
    return {"tools": tools.list()}


async def tools_call(params: NamedInvocationParams):
    tool = tools.get(params.name)
    return {"output": tool.run(params.arguments)}


async def resources_list(_: EmptyParams):
    return {"resources": resources.list()}


async def resources_get(params: NamedInvocationParams):
    resource = resources.get(params.name)
    return {"output": resource.get(params.arguments)}


async def prompts_list(_: EmptyParams):
    return {"prompts": prompts.list()}


async def prompts_get(params: NamedInvocationParams):
    prompt = prompts.get(params.name)
    return {"output": prompt.render(params.arguments)}


RPC_HANDLERS: Dict[str, HandlerSpec] = {
    "tools.list": HandlerSpec(EmptyParams, tools_list),
    "tools.call": HandlerSpec(NamedInvocationParams, tools_call),
    "resources.list": HandlerSpec(EmptyParams, resources_list),
    "resources.get": HandlerSpec(NamedInvocationParams, resources_get),
    "prompts.list": HandlerSpec(EmptyParams, prompts_list),
    "prompts.get": HandlerSpec(NamedInvocationParams, prompts_get),
}


# ---- Main router ----


async def handle_rpc(payload: JSONRPCRequest) -> JSONRPCResponse:
    if payload.jsonrpc != "2.0":
        return JSONRPCResponse(
            error=JSONRPCError(
                code=INVALID_PARAMS,
                message="Invalid JSON-RPC version",
            ),
            id=payload.id,
        )

    method = payload.method
    raw_params = payload.params or {}

    try:
        spec = RPC_HANDLERS.get(method)

        if spec is None:
            return JSONRPCResponse(
                error=JSONRPCError(
                    code=METHOD_NOT_FOUND,
                    message=f"Method '{method}' not found",
                ),
                id=payload.id,
            )

        # strict param validation
        params_obj = spec.params_model(**raw_params)

        result = await spec.handler(params_obj)

        return JSONRPCResponse(
            result=result,
            id=payload.id,
        )

    except Exception as e:
        return JSONRPCResponse(
            error=JSONRPCError(
                code=INTERNAL_ERROR,
                message=str(e),
                data={"method": method},
            ),
            id=payload.id,
        )
