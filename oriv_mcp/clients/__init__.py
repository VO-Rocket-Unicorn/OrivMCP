"""Outbound clients for the services this server calls.

Each client is constructed here from settings — the clients themselves take
their URLs as arguments, so they stay testable without the environment.
Credentials are NOT held here: they arrive per request from the caller and are
passed into each call. Add a new service by adding a module and wiring it below.
"""

__version__ = "0.1.0"

from oriv_mcp.config import settings

from .architecture_selection import ArchitectureSelectionClient
from .base import ApiClient
from .device_class import DeviceClassClient
from .requirement import RequirementClient
from .transport import http_client

device_class_client = DeviceClassClient(
    http_client=http_client,
    collection_url=settings.urls.device_classes_url,
    search_url=settings.urls.device_classes_search_url,
    health_url=settings.urls.odas_health_url,
)

# Same host and same credential as the device-class client.
architecture_selection_client = ArchitectureSelectionClient(
    http_client=http_client,
    decision_trees_url=settings.urls.decision_trees_url,
    taxonomies_url=settings.urls.taxonomies_url,
    health_url=settings.urls.odas_health_url,
)

# Same host and same credential as the device-class client, so the startup
# probe that one runs covers this one too.
requirement_client = RequirementClient(
    http_client=http_client,
    projects_url=settings.urls.projects_url,
    requirements_path=settings.urls.requirements_path,
    ancestors_path=settings.urls.ancestors_path,
)

__all__ = [
    "ApiClient",
    "ArchitectureSelectionClient",
    "DeviceClassClient",
    "RequirementClient",
    "architecture_selection_client",
    "device_class_client",
    "http_client",
    "requirement_client",
]
