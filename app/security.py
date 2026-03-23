from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Callable
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings
from app.models import UserProfile

_http_bearer = HTTPBearer(auto_error=False)

_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_ITERATIONS,
    )
    return (
        f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}$"
        f"{_b64url_encode(salt)}${_b64url_encode(digest)}"
    )


def verify_password(stored_password_hash: str, password: str) -> bool:
    try:
        scheme, iteration_raw, salt_raw, digest_raw = stored_password_hash.split("$", 3)
        if scheme != _PASSWORD_SCHEME:
            return False
        iterations = int(iteration_raw)

        salt = _b64url_decode_bytes(salt_raw)
        expected = _b64url_decode_bytes(digest_raw)
    except (ValueError, TypeError):
        return False

    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(expected, candidate)


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    secret: str,
    expire_minutes: int,
) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "uid": user_id,
        "role": role,
        "jti": uuid4().hex,
        "iat": now,
        "exp": now + (expire_minutes * 60),
    }

    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(f"{encoded_header}.{encoded_payload}", secret)
    return f"{encoded_header}.{encoded_payload}.{signature}"


def decode_access_token(token: str, *, secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format",
        )

    encoded_header, encoded_payload, signature = parts
    expected_signature = _sign(f"{encoded_header}.{encoded_payload}", secret)

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
        )

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        ) from exc

    try:
        exp = int(payload.get("exp", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token expiry",
        ) from exc

    if exp < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    return payload


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
) -> UserProfile:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )

    payload = decode_access_token(
        credentials.credentials,
        secret=request.app.state.settings.jwt_secret,
    )

    username = payload.get("sub")
    role = payload.get("role")
    jti = payload.get("jti")
    uid = payload.get("uid")

    if not username or not role or not jti or uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    auth_service = request.app.state.auth_service
    if auth_service.is_access_token_revoked(str(jti)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
        )

    user = auth_service.get_user_profile_by_id(int(uid))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not active",
        )

    request.state.auth_user = user
    request.state.access_token_payload = payload
    return user


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return dependency


def require_permissions(*required_permissions: str) -> Callable:
    def dependency(
        request: Request,
        user: UserProfile = Depends(get_current_user),
    ) -> UserProfile:
        auth_service = request.app.state.auth_service
        if not auth_service.user_has_permissions(user.id, list(required_permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    return _b64url_encode(digest.digest())


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(encoded: str) -> str:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding).decode("utf-8")


def _b64url_decode_bytes(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    return base64.urlsafe_b64decode(encoded + padding)


def validate_security_settings(settings: Settings) -> None:
    if settings.environment == "development":
        return

    if settings.jwt_secret == "change-this-secret":
        raise RuntimeError(
            "AQ_JWT_SECRET must be changed for non-development environments."
        )

    if settings.enable_demo_users:
        raise RuntimeError(
            "AQ_ENABLE_DEMO_USERS must be false for non-development environments."
        )

    if not settings.auth_users.strip():
        raise RuntimeError(
            "AQ_AUTH_USERS must define at least one user for non-development environments."
        )
