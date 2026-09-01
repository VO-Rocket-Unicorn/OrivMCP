from pydantic import Field, SecretStr

from oriv_mcp.config.settings.base import EnvSettings


class SecretSettings(EnvSettings):
    """Credential material. `SecretStr` keeps values out of logs and reprs.

    Read a value with `.get_secret_value()` — only at the point of use, never
    into a variable that might be logged.
    """

    ontology_api_token: SecretStr | None = Field(
        default=None,
        description=(
            "Bearer token for the device-class / ontology API. None means the API "
            "is called unauthenticated."
        ),
    )
