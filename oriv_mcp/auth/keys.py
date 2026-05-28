import base64
import hashlib
import secrets
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from pydantic import BaseModel, ConfigDict, Field


class KeyMaterial(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    private_key: RSAPrivateKey = Field(..., description="RSA private key for signing JWTs")
    public_key: RSAPublicKey = Field(..., description="RSA public key for verifying JWTs")
    private_pem: bytes = Field(..., description="PEM-encoded private key bytes")
    public_pem: bytes = Field(..., description="PEM-encoded public key bytes")
    kid: str = Field(..., description="Stable key id derived from the public key bytes")


def load_or_generate_keypair(keys_dir: Path) -> KeyMaterial:
    keys_dir.mkdir(parents=True, exist_ok=True)
    private_pem_path = keys_dir / "private.pem"
    public_pem_path = keys_dir / "public.pem"

    if private_pem_path.exists() and public_pem_path.exists():
        loaded_private = serialization.load_pem_private_key(
            private_pem_path.read_bytes(), password=None
        )
        loaded_public = serialization.load_pem_public_key(public_pem_path.read_bytes())
        if not isinstance(loaded_private, RSAPrivateKey) or not isinstance(
            loaded_public, RSAPublicKey
        ):
            raise RuntimeError(
                f"Expected RSA keypair in {keys_dir}, got "
                f"{type(loaded_private).__name__}/{type(loaded_public).__name__}"
            )
        private_key: RSAPrivateKey = loaded_private
        public_key: RSAPublicKey = loaded_public
    else:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = private_key.public_key()
        private_pem_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        public_pem_path.write_bytes(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    kid = hashlib.sha256(public_pem).hexdigest()[:16]

    return KeyMaterial(
        private_key=private_key,
        public_key=public_key,
        private_pem=private_pem,
        public_pem=public_pem,
        kid=kid,
    )


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def build_jwks(key_material: KeyMaterial) -> dict:
    numbers = key_material.public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": key_material.kid,
                "n": _b64url_uint(numbers.n),
                "e": _b64url_uint(numbers.e),
            }
        ]
    }


def mint_access_token(
    *,
    key_material: KeyMaterial,
    subject: str,
    client_id: str,
    scopes: list[str],
    issuer: str,
    audience: str,
    ttl_seconds: int,
) -> tuple[str, int]:
    now = int(time.time())
    exp = now + ttl_seconds
    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "azp": client_id,
        "scope": " ".join(scopes),
        "iat": now,
        "exp": exp,
        "jti": secrets.token_urlsafe(16),
    }
    token = jwt.encode(
        payload,
        key_material.private_pem,
        algorithm="RS256",
        headers={"kid": key_material.kid},
    )
    return token, exp


def decode_access_token(
    token: str,
    *,
    key_material: KeyMaterial,
    issuer: str,
    audience: str,
) -> dict:
    return jwt.decode(
        token,
        key_material.public_pem,
        algorithms=["RS256"],
        issuer=issuer,
        audience=audience,
        options={"require": ["iss", "sub", "aud", "exp", "iat"]},
    )
