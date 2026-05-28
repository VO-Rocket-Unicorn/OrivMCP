import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.templating import Jinja2Templates

from oriv_mcp.auth.storage import StoredAuthCode, auth_codes, login_sessions
from oriv_mcp.auth.verify_user import verify_user
from oriv_mcp.config import settings

_templates_dir = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


async def login_get(request: Request) -> Response:
    session_id = request.query_params.get("session")
    session = login_sessions.get(session_id) if session_id else None
    if session is None or session.expires_at < time.time():
        return Response("invalid or expired session", status_code=400)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"session_id": session_id, "error": None},
    )


async def login_post(request: Request) -> Response:
    form = await request.form()
    session_id = form.get("session")
    username = str(form.get("username") or "")
    password = str(form.get("password") or "")

    session = login_sessions.get(session_id) if session_id else None
    if session is None or session.expires_at < time.time():
        return Response("invalid or expired session", status_code=400)

    user = await verify_user(username, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"session_id": session_id, "error": "Invalid credentials"},
            status_code=401,
        )

    code = secrets.token_urlsafe(32)
    auth_codes[code] = StoredAuthCode(
        code=code,
        client_id=session.client_id,
        redirect_uri=session.redirect_uri,
        redirect_uri_provided_explicitly=session.redirect_uri_provided_explicitly,
        code_challenge=session.code_challenge,
        scopes=session.scopes or user.scopes,
        expires_at=time.time() + settings.auth_code_ttl_seconds,
        subject=user.subject,
        resource=session.resource,
    )
    login_sessions.pop(session_id, None)

    query = {"code": code}
    if session.state:
        query["state"] = session.state
    redirect_uri = str(session.redirect_uri)
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        url=f"{redirect_uri}{sep}{urlencode(query)}",
        status_code=302,
    )
