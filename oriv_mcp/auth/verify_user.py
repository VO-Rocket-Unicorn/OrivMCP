"""User credential verification — THE swap point.

Phase 1: hardcoded admin/admin.
Phase 2: rewrite the body of `verify_user` to delegate to Google/Microsoft OAuth.
Nothing else in the codebase should need to change.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    subject: str
    scopes: list[str]


async def verify_user(username: str, password: str) -> User | None:
    """Return a User on valid credentials, None otherwise."""
    if username == "admin" and password == "admin":
        return User(subject="admin", scopes=["read", "write"])
    return None
