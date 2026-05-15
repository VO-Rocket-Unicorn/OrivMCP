from typing import Dict, List

from oriv_mcp.capabilities.resources.base import BaseResource
from oriv_mcp.types.common import SpecType


class ResourceRegistry:
    def __init__(self) -> None:
        self._resources: Dict[str, BaseResource] = {}

    def register(self, resource: BaseResource) -> None:
        if resource.name in self._resources:
            raise ValueError(f"Resource '{resource.name}' already registered")

        self._resources[resource.name] = resource

    def get(self, name: str) -> BaseResource:
        try:
            return self._resources[name]
        except KeyError:
            raise ValueError(f"Resource '{name}' not found")

    def list(self) -> List[SpecType]:
        return [resource.spec for resource in self._resources.values()]
