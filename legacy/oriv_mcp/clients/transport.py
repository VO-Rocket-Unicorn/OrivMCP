"""The one pooled HTTP transport every outbound client shares.

Closed by the server lifespan on shutdown, so connections are not leaked
between reloads.
"""

from httpx import AsyncClient, Limits, Timeout

from oriv_mcp.config import settings

http_client = AsyncClient(
    timeout=Timeout(settings.http.http_timeout_seconds),
    limits=Limits(max_connections=settings.http.http_max_connections),
)
