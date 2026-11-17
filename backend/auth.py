from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import HTTPException, Request

COOKIE_NAME = "rr_session"
SESSION_TTL = 12 * 60 * 60


def _password() -> str:
    return os.getenv("APP_PASSWORD", "royals2027")


def _secret() -> bytes:
    return os.getenv("APP_SECRET", "rr-scout-dev-secret").encode("utf-8")


def _sign(payload: bytes) -> str:
    return hmac.new(_secret(), payload, hashlib.sha256).hexdigest()


def password_ok(password: str) -> bool:
    return hmac.compare_digest(str(password).encode("utf-8"), _password().encode("utf-8"))


def issue_token() -> str:
    payload = json.dumps({"sub": "scout", "exp": int(time.time()) + SESSION_TTL}).encode("utf-8")
    return f"{base64.urlsafe_b64encode(payload).decode('ascii')}.{_sign(payload)}"


def token_valid(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    encoded, signature = token.rsplit(".", 1)
    try:
        payload = base64.urlsafe_b64decode(encoded.encode("ascii"))
    except Exception:
        return False
    if not hmac.compare_digest(_sign(payload), signature):
        return False
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        return False
    exp = data.get("exp")
    return isinstance(exp, int) and exp > time.time()


def is_authenticated(request: Request) -> bool:
    return token_valid(request.cookies.get(COOKIE_NAME))


def require_auth(request: Request) -> None:
    if not is_authenticated(request):
        raise HTTPException(
            status_code=401,
            detail="Sign in required to change or download data.",
        )
