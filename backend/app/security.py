"""Authentication helpers.

* Passwords (local mode only) are hashed with bcrypt — never stored in plain text.
* Access tokens are JWTs with the same claim shape Supabase uses
  (`sub` = user id, `role` = "authenticated", `email`), so the rest of the
  system does not care which auth mode issued them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    claims: dict


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        # Still spend the time a real check would take, so response timing does not
        # reveal whether an email address is registered.
        bcrypt.checkpw(b"timing-equaliser", bcrypt.hashpw(b"x", bcrypt.gensalt(rounds=12)))
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def issue_local_token(user_id: str, email: str, settings: Settings) -> tuple[str, int]:
    ttl = settings.local_jwt_ttl_minutes * 60
    now = datetime.now(UTC)
    claims = {"sub": user_id, "email": email, "role": "authenticated", "aud": "authenticated",
              "iss": "cybersec-academy-local", "iat": now, "exp": now + timedelta(seconds=ttl)}
    return jwt.encode(claims, settings.local_jwt_secret, algorithm="HS256"), ttl


def decode_token(token: str, settings: Settings) -> dict:
    secret = settings.local_jwt_secret if settings.auth_mode == "local" else settings.supabase_jwt_secret
    return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated",
                      options={"require": ["sub", "exp"]})


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_token(creds.credentials, settings)
    except jwt.PyJWTError:
        # Do not echo the library's message: it can help an attacker tune forged tokens.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    if claims.get("role") != "authenticated":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Token role not allowed")
    return CurrentUser(id=claims["sub"], email=claims.get("email"), claims=claims)
