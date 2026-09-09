"""Client for the AI decision-tree walk and its taxonomy resolution."""

from urllib.parse import quote

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import SecretStr

from oriv_mcp.clients.base import ApiClient
from oriv_mcp.clients.odas import BASE_URL_ENV_VAR, CREDENTIAL_HINT
from oriv_mcp.schemas.architecture_selection import (
    ArchitectureDetail,
    DecisionNode,
    DecisionTree,
    DecisionTreeNodeResponse,
    TaxonomyLookupResponse,
)

SERVICE_LABEL = "architecture-selection API"

# Device-class keys carry a dot (e.g. "adc.sar") and may carry a colon, like
# device-class ids do — left intact rather than percent-encoded, which a
# server that does not decode path params would then fail to match.
ID_SAFE_CHARACTERS = ":"

BY_PARAM = "by"
BY_AI_VALUE = "ai"
ARCHITECTURE_NAME_FIELD = "architecture_name"


class ArchitectureSelectionClient(ApiClient):
    """Read-only access to AI decision trees and their taxonomy resolution."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        decision_trees_url: str,
        taxonomies_url: str,
        health_url: str,
    ) -> None:
        super().__init__(
            http_client=http_client,
            service_label=SERVICE_LABEL,
            base_url_env_var=BASE_URL_ENV_VAR,
            credential_hint=CREDENTIAL_HINT,
        )
        self._decision_trees_url = decision_trees_url
        self._taxonomies_url = taxonomies_url
        self._health_url = health_url

    async def check_health(self) -> tuple[bool, str]:
        return await super().check_health(self._health_url)

    def _decision_tree_url(self, device_class_key: str) -> str:
        return f"{self._decision_trees_url}/{quote(device_class_key, safe=ID_SAFE_CHARACTERS)}"

    def _decision_tree_node_url(self, device_class_key: str, node_id: str) -> str:
        return (
            f"{self._decision_tree_url(device_class_key)}/nodes/"
            f"{quote(node_id, safe=ID_SAFE_CHARACTERS)}"
        )

    def _taxonomy_url(self, device_class_key: str) -> str:
        return f"{self._taxonomies_url}/{quote(device_class_key, safe=ID_SAFE_CHARACTERS)}"

    async def get_decision_tree(self, token: SecretStr, device_class_key: str) -> DecisionTree:
        return await self.get(
            self._decision_tree_url(device_class_key),
            DecisionTree,
            token,
            {BY_PARAM: BY_AI_VALUE},
        )

    async def get_decision_tree_node(
        self, token: SecretStr, device_class_key: str, node_id: str
    ) -> DecisionNode:
        response = await self.get(
            self._decision_tree_node_url(device_class_key, node_id),
            DecisionTreeNodeResponse,
            token,
            {BY_PARAM: BY_AI_VALUE},
        )
        return response.node

    async def resolve_architecture(
        self, token: SecretStr, device_class_key: str, architecture_name: str
    ) -> ArchitectureDetail:
        response = await self.get(
            self._taxonomy_url(device_class_key),
            TaxonomyLookupResponse,
            token,
            {ARCHITECTURE_NAME_FIELD: architecture_name},
        )
        if not response.leaves:
            raise ToolError(
                f"No architecture resolved for '{architecture_name}' under device "
                f"class '{device_class_key}'."
            )
        return response.leaves[0]
