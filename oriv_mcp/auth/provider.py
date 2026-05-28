import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from oriv_mcp.auth.keys import KeyMaterial, decode_access_token, mint_access_token
from oriv_mcp.auth.storage import (
    LoginSession,
    auth_codes,
    clients,
    login_sessions,
)
from oriv_mcp.config import settings


class OrivOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """OAuth Authorization Server provider for FastMCP.

    Routes the /authorize step through our local Jinja2 login page, then mints
    RS256 JWT access tokens. Verification (load_access_token) decodes the JWT
    against the same key material.
    """

    def __init__(self, key_material: KeyMaterial):
        self._key_material = key_material

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        assert client_info.client_id is not None
        clients[client_info.client_id] = client_info

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        assert client.client_id is not None
        session_id = secrets.token_urlsafe(24)
        login_sessions[session_id] = LoginSession(
            session_id=session_id,
            client_id=client.client_id,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            code_challenge=params.code_challenge,
            scopes=params.scopes or [],
            state=params.state,
            resource=params.resource,
            expires_at=time.time() + settings.login_session_ttl_seconds,
        )
        base = settings.auth_base_url.rstrip("/")
        return f"{base}/login?session={session_id}"

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> AuthorizationCode | None:
        stored = auth_codes.get(authorization_code)
        if stored is None or stored.client_id != client.client_id:
            return None
        return AuthorizationCode(
            code=stored.code,
            scopes=stored.scopes,
            expires_at=stored.expires_at,
            client_id=stored.client_id,
            code_challenge=stored.code_challenge,
            redirect_uri=stored.redirect_uri,
            redirect_uri_provided_explicitly=stored.redirect_uri_provided_explicitly,
            resource=stored.resource,
        )

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        stored = auth_codes.pop(authorization_code.code, None)
        if stored is None:
            raise TokenError(
                error="invalid_grant",
                error_description="authorization code already used",
            )
        assert client.client_id is not None

        token, _ = mint_access_token(
            key_material=self._key_material,
            subject=stored.subject,
            client_id=client.client_id,
            scopes=stored.scopes,
            issuer=settings.auth_base_url,
            audience=settings.auth_base_url,
            ttl_seconds=settings.access_token_ttl_seconds,
        )

        return OAuthToken(
            access_token=token,
            token_type="Bearer",
            expires_in=settings.access_token_ttl_seconds,
            scope=" ".join(stored.scopes) if stored.scopes else None,
        )

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> RefreshToken | None:
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        raise TokenError(
            error="unsupported_grant_type",
            error_description="refresh tokens are not enabled",
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_access_token(
                token,
                key_material=self._key_material,
                issuer=settings.auth_base_url,
                audience=settings.auth_base_url,
            )
        except Exception:
            return None
        scope_claim = payload.get("scope") or ""
        return AccessToken(
            token=token,
            client_id=payload.get("azp", ""),
            scopes=scope_claim.split() if scope_claim else [],
            expires_at=int(payload["exp"]),
        )

    async def revoke_token(self, token) -> None:
        return None
