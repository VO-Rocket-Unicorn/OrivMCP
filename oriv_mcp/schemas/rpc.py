from pydantic import BaseModel, Field
from typing import Any, Optional, Union


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCRequest(BaseModel):
    jsonrpc: str = Field(..., pattern="^2.0$")
    method: str
    params: Optional[dict[str, Any]] = None
    id: Optional[Union[int, str]] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None
    id: Optional[Union[int, str]] = None


class NamedInvocationParams(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class EmptyParams(BaseModel):
    pass
