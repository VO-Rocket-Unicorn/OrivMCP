from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application runtime configuration.
    Reads from environment variables with prefix: AEROMCP_
    """

    # ---- server ----
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    timeout_keep_alive: int = 5

    # ---- environment ----
    env: str = "dev"  # dev | prod

    model_config = SettingsConfigDict(
        env_prefix="AEROMCP_",
        env_file=".env",
        extra="ignore",
    )


# singleton instance
settings = Settings()
