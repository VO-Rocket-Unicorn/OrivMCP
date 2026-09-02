"""Shared behaviour for outbound service clients.

A subclass supplies its URLs; this handles auth, transport failures, the
response envelope, HTTP status, and validation, turning every failure into a
`ToolError` whose message is safe and useful for a model to read.
"""

from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, SecretStr, ValidationError

from oriv_mcp.config.logger_config import logger

AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer"
ABSOLUTE_URL_PREFIX = "http"

# Every response is wrapped: {respcode, payload, message, traceId}. The data
# the tools care about — and, on a 400/404, the actionable error text — live
# under `payload`; `respcode` is not load-bearing, HTTP status is.
PAYLOAD_KEY = "payload"
MESSAGE_KEY = "message"
TRACE_ID_KEY = "traceId"

UNAUTHORIZED_STATUS = 401


class ApiClient:
    """Issues GETs against one service and validates the result."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        service_label: str,
        base_url_env_var: str,
        credential_hint: str,
    ) -> None:
        self._http = http_client
        self._service_label = service_label
        self._base_url_env_var = base_url_env_var
        self._credential_hint = credential_hint

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

    # ---- envelope ----
    @staticmethod
    def _envelope(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    @staticmethod
    def _payload(envelope: dict[str, Any]) -> dict[str, Any]:
        payload = envelope.get(PAYLOAD_KEY)
        return payload if isinstance(payload, dict) else {}

    @classmethod
    def _error_text(cls, envelope: dict[str, Any]) -> str | None:
        """`payload.message` is the actionable one; the envelope's is the fallback."""
        return cls._payload(envelope).get(MESSAGE_KEY) or envelope.get(MESSAGE_KEY)

    # ---- request ----
    def _headers(self, token: SecretStr) -> dict[str, str]:
        """The caller's token reaches the service as a standard bearer credential."""
        return {AUTHORIZATION_HEADER: f"{BEARER_PREFIX} {token.get_secret_value()}"}

    def _reject(self, response: httpx.Response) -> ToolError:
        envelope = self._envelope(response)
        trace_id = envelope.get(TRACE_ID_KEY)
        message = self._error_text(envelope)

        if response.status_code == UNAUTHORIZED_STATUS:
            # A 401 carries no payload, and the caller — not this server — owns
            # the credential, so say which one to fix.
            message = message or f"The {self._service_label} rejected the credential."
            message = f"{message} {self._credential_hint}"
        elif not message:
            message = (
                f"The {self._service_label} rejected the request "
                f"({response.status_code})."
            )

        if trace_id:
            logger.error(
                "%s returned %s (traceId=%s)",
                self._service_label,
                response.status_code,
                trace_id,
            )
        return ToolError(message)

    async def check_health(self, url: str) -> tuple[bool, str]:
        """Probe a service's health endpoint.

        Never raises and never sends a credential: this runs at startup, where
        there is no caller and no token, and a dead dependency must not stop
        this server from booting.
        """
        if not url.startswith(ABSOLUTE_URL_PREFIX):
            return False, f"{self._base_url_env_var} is not set"
        try:
            response = await self._http.get(url)
        except httpx.HTTPError as exc:
            return False, f"unreachable at {url} ({exc})"
        if response.is_success:
            return True, f"reachable at {url}"
        return False, f"{url} returned HTTP {response.status_code}"

    async def get[TModel: BaseModel](
        self,
        url: str,
        model: type[TModel],
        token: SecretStr,
        params: dict[str, Any] | None = None,
    ) -> TModel:
        # A relative URL means the base URL setting is empty.
        if not url.startswith(ABSOLUTE_URL_PREFIX):
            raise ToolError(self._unconfigured_message)

        # httpx would serialise None into the query string, so drop those keys.
        query = {key: value for key, value in (params or {}).items() if value is not None}

        try:
            response = await self._http.get(url, params=query, headers=self._headers(token))
        except httpx.HTTPError as exc:
            logger.error("%s request to %s failed: %s", self._service_label, url, exc)
            raise ToolError(self._unavailable_message) from exc

        if response.is_client_error:
            raise self._reject(response)
        if response.is_server_error:
            envelope = self._envelope(response)
            logger.error(
                "%s returned %s for %s (traceId=%s): %s",
                self._service_label,
                response.status_code,
                url,
                envelope.get(TRACE_ID_KEY),
                response.text[:500],
            )
            raise ToolError(self._unavailable_message)

        try:
            return model.model_validate(self._payload(self._envelope(response)))
        except (ValueError, ValidationError) as exc:
            logger.error("%s response from %s did not validate: %s", self._service_label, url, exc)
            raise ToolError(self._malformed_message) from exc
