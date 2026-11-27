"""Local-mode registration and login.

In AUTH_MODE=supabase these endpoints are disabled: the frontend talks to
Supabase Auth directly and only sends us the resulting access token.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text

from ..config import Settings, get_settings
from ..db import service_connection
from ..security import hash_password, issue_local_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=2, max_length=60)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — the literal word "bearer", not a secret
    expires_in: int


# Simple in-memory limiter: max 10 failed logins per (client IP, email) per 15 minutes.
# Limitation (documented in docs/DEVELOPMENT_TRACKER.md): memory is per process, so on
# serverless hosting each instance counts separately. Supabase Auth has its own limits.
_FAILED: dict[tuple[str, str], deque] = defaultdict(deque)
MAX_FAILURES, WINDOW_SECONDS = 10, 15 * 60


def _too_many_failures(key: tuple[str, str]) -> bool:
    q, now = _FAILED[key], time.monotonic()
    while q and now - q[0] > WINDOW_SECONDS:
        q.popleft()
    return len(q) >= MAX_FAILURES


def _local_only(settings: Settings) -> None:
    if settings.auth_mode != "local":
        raise HTTPException(404, "Use Supabase Auth in this environment")


@router.get("/config")
def auth_config(settings: Settings = Depends(get_settings)) -> dict:
    return {"mode": settings.auth_mode, "min_password_length": settings.min_password_length}


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, settings: Settings = Depends(get_settings)) -> TokenOut:
    _local_only(settings)
    email = body.email.lower()
    with service_connection() as conn:
        exists = conn.execute(text("select 1 from auth.users where lower(email) = :e"), {"e": email}).first()
        if exists:
            raise HTTPException(409, "An account with this email already exists")
        # The on_auth_user_created trigger creates the matching profile row.
        user_id = conn.execute(text("""
            insert into auth.users (email, encrypted_password, raw_user_meta_data)
            values (:e, :p, jsonb_build_object('display_name', cast(:n as text))) returning id
        """), {"e": email, "p": hash_password(body.password), "n": body.display_name.strip()}).scalar_one()
    token, ttl = issue_local_token(str(user_id), email, settings)
    return TokenOut(access_token=token, expires_in=ttl)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, settings: Settings = Depends(get_settings)) -> TokenOut:
    _local_only(settings)
    email = body.email.lower()
    key = (request.client.host if request.client else "unknown", email)
    if _too_many_failures(key):
        raise HTTPException(429, "Too many failed sign-in attempts. Try again in 15 minutes.")
    with service_connection() as conn:
        row = conn.execute(text("select id, encrypted_password from auth.users where lower(email) = :e"),
                           {"e": email}).first()
    if not verify_password(body.password, row.encrypted_password if row else None):
        _FAILED[key].append(time.monotonic())
        # Same message for "no such user" and "wrong password" (prevents account enumeration).
        raise HTTPException(401, "Incorrect email or password")
    _FAILED.pop(key, None)
    token, ttl = issue_local_token(str(row.id), email, settings)
    return TokenOut(access_token=token, expires_in=ttl)
