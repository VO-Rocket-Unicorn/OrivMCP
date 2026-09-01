from pathlib import Path
import logging

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from lib_oriv_telemetry.enums import EnvironmentEnum

# A Host/Origin entry without a port only matches a request that carries no
# port either, so every bare entry is paired with this wildcard form.
PORT_WILDCARD_SUFFIX = ":*"
SCHEME_SEPARATOR = "://"
DEFAULT_MCP_PATH = "/mcp"
ROOT_PATH = "/"


def _has_explicit_port(host: str) -> bool:
    """True if `host` pins a port. Bracketed IPv6 literals carry inner colons."""
    if host.startswith("["):
        closing = host.find("]")
        return closing != -1 and ":" in host[closing + 1 :]
    return ":" in host


def _expand_host(host: str) -> list[str]:
    """Pair a bare host with its port-wildcard form; leave pinned ports alone."""
    if not host or host.endswith(PORT_WILDCARD_SUFFIX) or _has_explicit_port(host):
        return [host] if host else []
    return [host, f"{host}{PORT_WILDCARD_SUFFIX}"]


def _normalize_host_entry(entry: str) -> list[str]:
    """Reduce an entry to Host-header form: no scheme, no path, plus wildcard."""
    host = entry.strip()
    if SCHEME_SEPARATOR in host:
        host = host.split(SCHEME_SEPARATOR, 1)[1]
    return _expand_host(host.split(ROOT_PATH, 1)[0])


def _normalize_origin_entry(entry: str) -> list[str]:
    """Reduce an entry to Origin-header form: scheme://host, no path, plus wildcard."""
    origin = entry.strip()
    if SCHEME_SEPARATOR not in origin:
        return _normalize_host_entry(origin)
    scheme, rest = origin.split(SCHEME_SEPARATOR, 1)
    return [
        f"{scheme}{SCHEME_SEPARATOR}{host}"
        for host in _expand_host(rest.split(ROOT_PATH, 1)[0])
    ]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


class Settings(BaseSettings):
    """
    Application runtime configuration.
    Reads from environment variables with prefix: ORIV_MCP_
    """

    model_config = SettingsConfigDict(
        # env_prefix="ORIV_MCP_",
        env_file=".env",
        extra="ignore",
    )

    # ---- server ----
    project_name: str = Field(
        default="OrivMCP", description="Project name for the MCP server"
    )
    host: str = Field(default="0.0.0.0", description="Host to run the server on")
    port: int = Field(default=8000, description="Port to run the server on")
    workers: int = Field(
        default=1, description="Number of worker processes for handling requests"
    )
    timeout_keep_alive: int = Field(
        default=5,
        description="Number of seconds to wait for the next request on a Keep-Alive connection",
    )
    device_classes_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2]
        / "temp"
        / "device_classes.json",
        description="Device-class taxonomy JSON, loaded into memory once at startup.",
    )
    mcp_path: str = Field(
        default=DEFAULT_MCP_PATH,
        description="Path the streamable HTTP MCP endpoint is served from. The endpoint is also aliased at '/' so clients given a bare base URL still connect.",
    )

    # ---- environment ----
    environment: EnvironmentEnum = Field(
        default=EnvironmentEnum.PRODUCTION,
        description="Application environment (e.g., development, staging, production)",
    )
    log_file_path: str = Field(
        default_factory=lambda: str(Path(__file__).resolve().parents[2] / "logs"),
        description="File path for application logs",
    )

    @computed_field
    @property
    def log_level(self) -> int:
        """Determine log level based on environment."""
        return (
            logging.DEBUG
            if self.environment == EnvironmentEnum.SANDBOX
            else logging.INFO
        )

    allowed_hosts: list[str] = Field(
        default_factory=list,
        description="Allowed Host header values. Entries are normalized: scheme and path are stripped, and a ':*' port wildcard is added for any entry without an explicit port.",
    )
    allowed_origins: list[str] = Field(
        default_factory=list,
        description="Allowed Origin header values. Entries are normalized: path is stripped, and a ':*' port wildcard is added for any entry without an explicit port.",
    )

    @field_validator("allowed_hosts", mode="after")
    @classmethod
    def normalize_allowed_hosts(cls, hosts: list[str]) -> list[str]:
        return _dedupe([h for entry in hosts for h in _normalize_host_entry(entry)])

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def normalize_allowed_origins(cls, origins: list[str]) -> list[str]:
        return _dedupe([o for entry in origins for o in _normalize_origin_entry(entry)])

    # ---- telemetry ----
    otel_url: str = Field(
        ...,
        description="Endpoint URL for sending logs",
    )

    @computed_field
    @property
    def otel_logs_url(self) -> str:
        """Otel logs url"""
        return f"{self.otel_url}/v1/logs"

    @computed_field
    @property
    def otel_traces_url(self) -> str:
        """Otel traces url"""
        return f"{self.otel_url}/v1/traces"

    @computed_field
    @property
    def otel_metrics_url(self) -> str:
        """Otel metrics url"""
        return f"{self.otel_url}/v1/metrics"


# singleton instance
settings = Settings()  # type: ignore
