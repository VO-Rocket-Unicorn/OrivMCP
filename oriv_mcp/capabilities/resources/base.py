from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, Generic


from oriv_mcp.types.common import SpecType
from oriv_mcp.types.generics import T_Input, T_Output


class BaseResource(ABC, Generic[T_Input, T_Output]):
    name: str
    description: str

    input_schema: type[T_Input]
    output_schema: type[T_Output]

    async def get(self, raw_input: dict[str, Any]) -> dict[str, Any]:
        # 1. validate input
        validated = self.input_schema(**raw_input)

        # 2. execute
        result = await self._get(input=validated)

        # 3. validate output
        if not isinstance(result, self.output_schema):
            raise ValueError("Invalid output type")

        return result.model_dump()

    @abstractmethod
    async def _get(self, input: T_Input) -> T_Output: ...

    @cached_property
    def spec(self) -> SpecType:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
        }
