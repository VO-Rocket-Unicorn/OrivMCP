from pydantic import Field, field_validator

from oriv_mcp.config.constants import ROOT_PATH
from oriv_mcp.config.settings.base import EnvSettings

# A Host/Origin entry without a port only matches a request that carries no
# port either, so every bare entry is paired with this wildcard form.
PORT_WILDCARD_SUFFIX = ":*"
SCHEME_SEPARATOR = "://"


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


def normalize_host_entry(entry: str) -> list[str]:
    """Reduce an entry to Host-header form: no scheme, no path, plus wildcard."""
    host = entry.strip()
    if SCHEME_SEPARATOR in host:
        host = host.split(SCHEME_SEPARATOR, 1)[1]
    return _expand_host(host.split(ROOT_PATH, 1)[0])


def normalize_origin_entry(entry: str) -> list[str]:
    """Reduce an entry to Origin-header form: scheme://host, no path, plus wildcard."""
    origin = entry.strip()
    if SCHEME_SEPARATOR not in origin:
        return normalize_host_entry(origin)
    scheme, rest = origin.split(SCHEME_SEPARATOR, 1)
    return [
        f"{scheme}{SCHEME_SEPARATOR}{host}"
        for host in _expand_host(rest.split(ROOT_PATH, 1)[0])
    ]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


class SecuritySettings(EnvSettings):
    """Transport-security allowlists for DNS-rebinding protection."""

    allowed_hosts: list[str] = Field(
        default_factory=list,
        description=(
            "Allowed Host header values. Entries are normalized: scheme and path are "
            "stripped, and a ':*' port wildcard is added for any entry without an "
            "explicit port."
        ),
    )
    allowed_origins: list[str] = Field(
        default_factory=list,
        description=(
            "Allowed Origin header values. Entries are normalized: path is stripped, "
            "and a ':*' port wildcard is added for any entry without an explicit port."
        ),
    )

    @field_validator("allowed_hosts", mode="after")
    @classmethod
    def normalize_allowed_hosts(cls, hosts: list[str]) -> list[str]:
        return _dedupe([h for entry in hosts for h in normalize_host_entry(entry)])

    @field_validator("allowed_origins", mode="after")
    @classmethod
    def normalize_allowed_origins(cls, origins: list[str]) -> list[str]:
        return _dedupe([o for entry in origins for o in normalize_origin_entry(entry)])
