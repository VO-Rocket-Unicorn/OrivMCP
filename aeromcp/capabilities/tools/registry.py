from typing import Dict, List

from aeromcp.capabilities.tools.base import BaseTool
from aeromcp.types.common import SpecType


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")

        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError:
            raise ValueError(f"Tool '{name}' not found")

    def list(self) -> List[SpecType]:
        return [tool.spec for tool in self._tools.values()]
