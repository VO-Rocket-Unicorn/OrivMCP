from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, Generic


from oriv_mcp.types.common import SpecType
from oriv_mcp.types.generics import T_Input, T_Output


class BasePrompt(ABC, Generic[T_Input, T_Output]):
    name: str
    description: str

    input_schema: type[T_Input]

    async def render(self, raw_input: dict[str, Any]) -> dict[str, Any]:
        # 1. validate input
        validated = self.input_schema(**raw_input)

        # 2. execute
        result = await self._render(input=validated)

        # 3. validate output
        if not isinstance(result, str):
            raise ValueError("Invalid output type")

        return result.model_dump()

    @abstractmethod
    async def _render(self, input: T_Input) -> T_Output: ...

    @cached_property
    def spec(self) -> SpecType:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": {},
        }
