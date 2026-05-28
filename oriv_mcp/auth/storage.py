"""In-memory storage for the auth flow. Resets on process restart — dev only."""

from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl, BaseModel, Field


class StoredAuthCode(BaseModel):
    code: str = Field(..., description="Opaque authorization code value")
    client_id: str = Field(..., description="OAuth client this code was issued to")
    redirect_uri: AnyUrl = Field(..., description="Redirect URI from the /authorize request")
    redirect_uri_provided_explicitly: bool = Field(
        ..., description="Whether the client explicitly passed redirect_uri"
    )
    code_challenge: str = Field(..., description="PKCE S256 challenge to verify at /token")
    scopes: list[str] = Field(default_factory=list, description="Scopes granted with this code")
    expires_at: float = Field(..., description="Unix timestamp when the code expires")
    subject: str = Field(..., description="Authenticated user identifier (becomes JWT 'sub')")
    resource: str | None = Field(default=None, description="RFC 8707 resource indicator, if any")


class LoginSession(BaseModel):
    session_id: str = Field(..., description="Opaque session id passed to the login page")
    client_id: str = Field(..., description="OAuth client requesting authorization")
    redirect_uri: AnyUrl = Field(..., description="Where to redirect after a successful login")
    redirect_uri_provided_explicitly: bool = Field(
        ..., description="Whether the client explicitly passed redirect_uri"
    )
    code_challenge: str = Field(..., description="PKCE S256 challenge to carry to the auth code")
    scopes: list[str] = Field(default_factory=list, description="Scopes requested by the client")
    state: str | None = Field(default=None, description="OAuth state parameter to round-trip")
    resource: str | None = Field(default=None, description="RFC 8707 resource indicator, if any")
    expires_at: float = Field(..., description="Unix timestamp when the session expires")


clients: dict[str, OAuthClientInformationFull] = {}
auth_codes: dict[str, StoredAuthCode] = {}
login_sessions: dict[str, LoginSession] = {}
