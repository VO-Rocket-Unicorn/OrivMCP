__version__ = "0.1.0"

from oriv_mcp.config import settings

from .store import (
    DeviceClassTaxonomy,
    IndexEntry,
    UnknownDeviceClassError,
    load_taxonomy,
)

# Loaded once at startup; the taxonomy is read-only for the process lifetime.
taxonomy = load_taxonomy(settings.device_classes_path)

__all__ = [
    "DeviceClassTaxonomy",
    "IndexEntry",
    "UnknownDeviceClassError",
    "load_taxonomy",
    "taxonomy",
]
