"""In-memory storage for the auth flow. Resets on process restart — dev only."""

from dataclasses import dataclass

from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl


@dataclass
class StoredAuthCode:
    code: str
    client_id: str
    redirect_uri: AnyUrl
    redirect_uri_provided_explicitly: bool
    code_challenge: str
    scopes: list[str]
    expires_at: float
    subject: str
    resource: str | None = None


@dataclass
class LoginSession:
    session_id: str
    client_id: str
    redirect_uri: AnyUrl
    redirect_uri_provided_explicitly: bool
    code_challenge: str
    scopes: list[str]
    state: str | None
    resource: str | None
    expires_at: float


clients: dict[str, OAuthClientInformationFull] = {}
auth_codes: dict[str, StoredAuthCode] = {}
login_sessions: dict[str, LoginSession] = {}
