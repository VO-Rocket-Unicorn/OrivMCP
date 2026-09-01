"""Application configuration, grouped by concern.

Each group is its own `BaseSettings` reading the same flat `.env`, so grouping
changes how config is *addressed* in code (`settings.server.port`) without
renaming a single environment variable.
"""

from pydantic import BaseModel, Field

from .app import AppSettings
from .http import HttpSettings
from .secrets import SecretSettings
from .security import SecuritySettings
from .server import ServerSettings
from .urls import UrlSettings


class Settings(BaseModel):
    """The one global settings object, composed from its groups."""

    server: ServerSettings = Field(default_factory=ServerSettings)
    app: AppSettings = Field(default_factory=AppSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    http: HttpSettings = Field(default_factory=HttpSettings)
    urls: UrlSettings = Field(default_factory=UrlSettings)
    secrets: SecretSettings = Field(default_factory=SecretSettings)


# singleton instance
settings = Settings()

__all__ = [
    "AppSettings",
    "HttpSettings",
    "SecretSettings",
    "SecuritySettings",
    "ServerSettings",
    "Settings",
    "UrlSettings",
    "settings",
]
