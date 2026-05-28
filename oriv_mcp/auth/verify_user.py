"""User credential verification — THE swap point.

Phase 1: hardcoded admin/admin.
Phase 2: rewrite the body of `verify_user` to delegate to Google/Microsoft OAuth.
Nothing else in the codebase should need to change.
"""

from pydantic import BaseModel, Field


class User(BaseModel):
    subject: str = Field(..., description="Unique identifier for the user")
    scopes: list[str] = Field(
        default_factory=list,
        description="List of scopes/permissions associated with the user",
    )


async def verify_user(username: str, password: str) -> User | None:
    """Return a User on valid credentials, None otherwise."""
    if username == "admin" and password == "admin":
        return User(subject="admin", scopes=["read", "write"])
    return None
