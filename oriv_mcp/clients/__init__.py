"""Outbound clients for the services this server calls.

Each client is constructed here from settings — the clients themselves take
their URLs and credentials as arguments, so they stay testable without the
environment. Add a new service by adding a module and wiring it below.
"""

__version__ = "0.1.0"

from oriv_mcp.config import settings

from .base import ApiClient
from .device_class import DeviceClassClient
from .transport import http_client

device_class_client = DeviceClassClient(
    http_client=http_client,
    collection_url=settings.urls.device_classes_url,
    search_url=settings.urls.device_classes_search_url,
    token=settings.secrets.ontology_api_token,
)

__all__ = [
    "ApiClient",
    "DeviceClassClient",
    "device_class_client",
    "http_client",
]
