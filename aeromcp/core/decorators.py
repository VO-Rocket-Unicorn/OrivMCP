import asyncio
from functools import wraps
from typing import Callable, Coroutine, override

from aeromcp.capabilities.prompts.base import BasePrompt
from aeromcp.capabilities.resources.base import BaseResource
from aeromcp.capabilities.tools.base import BaseTool
from aeromcp.types.generics import T_Input, T_Output
from aeromcp.core.registry import tools, resources, prompts


FuncType = (
    Callable[[T_Input], T_Output] | Callable[[T_Input], Coroutine[T_Output, None, None]]
)


def tool(
    name: str,
    description: str,
    input_schema: type[T_Input],
    output_schema: type[T_Output],
):

    tool_name = name
    tool_description = description
    tool_input_schema = input_schema
    tool_output_schema = output_schema

    @wraps
    def wrapper(func: FuncType[T_Input, T_Output]):
        class FunctionTool(BaseTool):
            name: str = tool_name
            description: str = tool_description
            input_schema: type[T_Input] = tool_input_schema
            output_schema: type[T_Output] = tool_output_schema

            @override
            async def _run(self, input: T_Input) -> T_Output:

                result = func(input)

                if asyncio.iscoroutine(result):
                    result = await result

                if not isinstance(result, output_schema):
                    raise ValueError("Invalid output from tool")

                return result

        tools.register(FunctionTool())

    return wrapper


def resource(
    name: str,
    description: str,
    input_schema: type[T_Input],
    output_schema: type[T_Output],
):

    resource_name = name
    resource_description = description
    resource_input_schema = input_schema
    resource_output_schema = output_schema

    @wraps
    def wrapper(func: FuncType[T_Input, T_Output]):

        class FunctionResource(BaseResource):
            name: str = resource_name
            description: str = resource_description
            input_schema: type[T_Input] = resource_input_schema
            output_schema: type[T_Output] = resource_output_schema

            @override
            async def _get(self, input: T_Input) -> T_Output:

                result = func(input)

                if asyncio.iscoroutine(result):
                    result = await result

                if not isinstance(result, output_schema):
                    raise ValueError("Invalid output from tool")

                return result

        resources.register(FunctionResource())

    return wrapper


def prompt(
    name: str,
    description: str,
    input_schema: type[T_Input],
):

    resource_name = name
    resource_description = description
    resource_input_schema = input_schema

    @wraps
    def wrapper(func: FuncType[T_Input, T_Output]):

        class FunctionPrompt(BasePrompt):
            name: str = resource_name
            description: str = resource_description
            input_schema: type[T_Input] = resource_input_schema

            @override
            async def _render(self, input: T_Input) -> str:

                result = func(input)

                if asyncio.iscoroutine(result):
                    result = await result

                if not isinstance(result, str):
                    raise ValueError("Invalid output from tool")

                return result

        prompts.register(FunctionPrompt())

    return wrapper
