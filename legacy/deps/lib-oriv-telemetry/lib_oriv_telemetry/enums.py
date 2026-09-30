"""Public enumerations exposed by lib-oriv-telemetry."""

from enum import StrEnum


class EnvironmentEnum(StrEnum):
    """Deployment environment identifier.

    Values follow the OpenTelemetry ``deployment.environment``
    semantic convention (lowercase string).
    """

    SANDBOX = "sandbox"
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
