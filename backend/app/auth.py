"""Shared-password gate.

This is deliberately not a user system: there are no accounts and no per-user
data isolation. It exists so the deployment isn't open to anyone who finds the
URL. Everyone who knows the password sees the same agents and conversations.

Tokens are HMAC-SHA256 signed with the stdlib — no dependency, no hand-rolled
crypto. A token is `<expiry>.<signature>`; verification recomputes the signature
and compares in constant time, then checks the expiry.
"""

import base64
import hashlib
import hmac
import secrets
import time

from fastapi import Depends, HTTPException, Request

from app.config import settings

TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days — this is a gate, not a bank


def _secret() -> bytes:
    # The password doubles as the signing key. Rotating the password therefore
    # invalidates every outstanding token, which is the behaviour you want.
    return settings.app_password.encode()


def _sign(payload: str) -> str:
    digest = hmac.new(_secret(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue_token() -> str:
    expiry = str(int(time.time()) + TOKEN_TTL_SECONDS)
    return f"{expiry}.{_sign(expiry)}"


def token_is_valid(token: str) -> bool:
    try:
        expiry, signature = token.split(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(expiry)):
        return False
    try:
        return int(expiry) > time.time()
    except ValueError:
        return False


def check_password(candidate: str) -> bool:
    # Constant-time so the comparison can't be timed character by character.
    return secrets.compare_digest(candidate, settings.app_password)


def auth_enabled() -> bool:
    """No password configured means the gate is off — so a fresh checkout still
    runs locally without ceremony."""
    return bool(settings.app_password)


async def require_auth(request: Request) -> None:
    if not auth_enabled():
        return

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token_is_valid(token):
        raise HTTPException(401, "Not authenticated")


async def require_internal_key(request: Request) -> None:
    """Gates worker-to-backend calls. Always enforced, even with no key
    configured — unlike require_auth, an unset key means "reject everything,"
    not "gate disabled," because this endpoint sits on the public backend URL."""
    key = request.headers.get("x-internal-key", "")
    if not settings.internal_api_key or not secrets.compare_digest(key, settings.internal_api_key):
        raise HTTPException(401, "Not authenticated")


# Applied to every data router; the login and health routes stay open.
AuthDep = Depends(require_auth)
InternalAuthDep = Depends(require_internal_key)
