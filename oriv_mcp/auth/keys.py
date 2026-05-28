import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey


@dataclass(frozen=True)
class KeyMaterial:
    private_key: RSAPrivateKey
    public_key: RSAPublicKey
    private_pem: bytes
    public_pem: bytes
    kid: str


def load_or_generate_keypair(keys_dir: Path) -> KeyMaterial:
    keys_dir.mkdir(parents=True, exist_ok=True)
    private_pem_path = keys_dir / "private.pem"
    public_pem_path = keys_dir / "public.pem"

    if private_pem_path.exists() and public_pem_path.exists():
        private_key = serialization.load_pem_private_key(
            private_pem_path.read_bytes(), password=None
        )
        public_key = serialization.load_pem_public_key(public_pem_path.read_bytes())
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
