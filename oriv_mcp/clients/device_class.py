"""Client for the device-class API. Contract: temp/device-class-api-spec.md."""

import httpx
from pydantic import SecretStr

from oriv_mcp.clients.base import ApiClient
from oriv_mcp.schemas.device_class import (
    GetDeviceClassOutput,
    ListDeviceClassesOutput,
    SearchDeviceClassesOutput,
)

SERVICE_LABEL = "device-class API"
BASE_URL_ENV_VAR = "ONTOLOGY_BASE_URL"

PARENT_ID_PARAM = "parent_id"
DEPTH_PARAM = "depth"
CURSOR_PARAM = "cursor"
QUERY_PARAM = "query"
LIMIT_PARAM = "limit"


class DeviceClassClient(ApiClient):
    """Read-only access to the device-class taxonomy."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        collection_url: str,
        search_url: str,
        token: SecretStr | None = None,
    ) -> None:
        super().__init__(
            http_client=http_client,
            service_label=SERVICE_LABEL,
            base_url_env_var=BASE_URL_ENV_VAR,
            token=token,
        )
        self._collection_url = collection_url
        self._search_url = search_url

    def _item_url(self, class_id: str) -> str:
        return f"{self._collection_url}/{class_id}"

    async def list_device_classes(
        self, parent_id: str | None, depth: int, cursor: str | None
    ) -> ListDeviceClassesOutput:
        return await self.get(
            self._collection_url,
            ListDeviceClassesOutput,
            {
                PARENT_ID_PARAM: parent_id,
                DEPTH_PARAM: depth,
                CURSOR_PARAM: cursor,
            },
        )

    async def search_device_classes(
        self, query: str, limit: int
    ) -> SearchDeviceClassesOutput:
        return await self.get(
            self._search_url,
            SearchDeviceClassesOutput,
            {QUERY_PARAM: query, LIMIT_PARAM: limit},
        )

    async def get_device_class(self, class_id: str) -> GetDeviceClassOutput:
        return await self.get(self._item_url(class_id), GetDeviceClassOutput)
