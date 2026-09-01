from oriv_mcp.config.settings.base import EnvSettings


class SecretSettings(EnvSettings):
    """Credential material read from the environment.

    Empty by design: ODAS credentials arrive per request on the
    `X-ODAS-Token` header rather than from a process-wide service account, so
    there is no ODAS token to configure here. Any future environment-held
    secret belongs in this group, as a `SecretStr` so it cannot surface
    through a repr.
    """
