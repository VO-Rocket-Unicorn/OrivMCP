"""Shared behaviour for outbound service clients.

A subclass supplies its URLs; this handles auth, transport failures, HTTP
status, and response validation, and turns every failure into a `ToolError`
whose message is safe and useful for a model to read.
"""

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, SecretStr, ValidationError

from oriv_mcp.config.logger_config import logger

ERROR_MESSAGE_KEY = "message"
AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer"
ABSOLUTE_URL_PREFIX = "http"


class ApiClient:
    """Issues GETs against one service and validates the result."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        service_label: str,
        base_url_env_var: str,
        token: SecretStr | None = None,
    ) -> None:
        self._http = http_client
        self._service_label = service_label
        self._base_url_env_var = base_url_env_var
        self._token = token

    # ---- messages ----
    @property
    def _unconfigured_message(self) -> str:
        return (
            f"The {self._service_label} is not configured: set "
            f"{self._base_url_env_var} in the environment. Until then this tool "
            "cannot return data."
        )

    @property
    def _unavailable_message(self) -> str:
        return (
            f"The {self._service_label} is unavailable. This is a service problem, "
            "not a bad request — retry shortly rather than changing the arguments."
        )

    @property
    def _malformed_message(self) -> str:
        return (
            f"The {self._service_label} returned a response that does not match the "
            "expected shape. Treat this as a service problem, not a bad request."
        )

    # ---- request ----
    def _headers(self) -> dict[str, str]:
        if self._token is None:
            return {}
        return {AUTHORIZATION_HEADER: f"{BEARER_PREFIX} {self._token.get_secret_value()}"}

    def _reject(self, response: httpx.Response) -> ToolError:
        """Pass the service's own 4xx message through — it tells the model what to fix."""
        try:
            message = response.json().get(ERROR_MESSAGE_KEY)
        except ValueError:
            message = None
        return ToolError(
            message
            or f"The {self._service_label} rejected the request ({response.status_code})."
        )

    async def get[TModel: BaseModel](
        self,
        url: str,
        model: type[TModel],
        params: dict[str, Any] | None = None,
    ) -> TModel:
        # A relative URL means the base URL setting is empty.
        if not url.startswith(ABSOLUTE_URL_PREFIX):
            raise ToolError(self._unconfigured_message)

        # httpx would serialise None into the query string, so drop those keys.
        query = {key: value for key, value in (params or {}).items() if value is not None}

        try:
            response = await self._http.get(url, params=query, headers=self._headers())
        except httpx.HTTPError as exc:
            logger.error("%s request to %s failed: %s", self._service_label, url, exc)
            raise ToolError(self._unavailable_message) from exc

        if response.is_client_error:
            raise self._reject(response)
        if response.is_server_error:
            logger.error(
                "%s returned %s for %s: %s",
                self._service_label,
                response.status_code,
                url,
                response.text[:500],
            )
            raise ToolError(self._unavailable_message)

        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            logger.error("%s response from %s did not validate: %s", self._service_label, url, exc)
            raise ToolError(self._malformed_message) from exc
