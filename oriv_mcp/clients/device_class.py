"""Client for the device-class API. Contract: temp/device-class-api-spec.md."""

from urllib.parse import quote

import httpx
from pydantic import SecretStr

from oriv_mcp.clients.base import ApiClient
from oriv_mcp.clients.odas import BASE_URL_ENV_VAR, CREDENTIAL_HINT
from oriv_mcp.schemas.device_class import (
    GetDeviceClassOutput,
    ListDeviceClassesOutput,
    SearchDeviceClassesOutput,
)

SERVICE_LABEL = "device-class API"

# Node ids carry a colon (`group:<slug>`, `class:<key>`). Colons are legal in a
# path segment, so they are left intact rather than percent-encoded, which a
# server that does not decode path params would then fail to match.
ID_SAFE_CHARACTERS = ":"

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
        health_url: str,
    ) -> None:
        super().__init__(
            http_client=http_client,
            service_label=SERVICE_LABEL,
            base_url_env_var=BASE_URL_ENV_VAR,
            credential_hint=CREDENTIAL_HINT,
        )
        self._collection_url = collection_url
        self._search_url = search_url
        self._health_url = health_url

    async def check_health(self) -> tuple[bool, str]:
        return await super().check_health(self._health_url)

    def _item_url(self, class_id: str) -> str:
        return f"{self._collection_url}/{quote(class_id, safe=ID_SAFE_CHARACTERS)}"

    async def list_device_classes(
        self, token: SecretStr, parent_id: str | None, depth: int, cursor: str | None
    ) -> ListDeviceClassesOutput:
        return await self.get(
            self._collection_url,
            ListDeviceClassesOutput,
            token,
            {
                PARENT_ID_PARAM: parent_id,
                DEPTH_PARAM: depth,
                CURSOR_PARAM: cursor,
            },
        )

    async def search_device_classes(
        self, token: SecretStr, query: str, limit: int
    ) -> SearchDeviceClassesOutput:
        return await self.get(
            self._search_url,
            SearchDeviceClassesOutput,
            token,
            {QUERY_PARAM: query, LIMIT_PARAM: limit},
        )

    async def get_device_class(
        self, token: SecretStr, class_id: str
    ) -> GetDeviceClassOutput:
        return await self.get(self._item_url(class_id), GetDeviceClassOutput, token)
