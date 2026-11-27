"""Shared request dependencies and small query helpers."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.engine import Connection

from .db import user_connection
from .security import CurrentUser, get_current_user


def get_db(user: CurrentUser = Depends(get_current_user)) -> Iterator[Connection]:
    """One RLS-scoped transaction per request. Commits on success, rolls back on error."""
    with user_connection(user.claims) as conn:
        yield conn


def rows(conn: Connection, sql: str, params: dict | None = None) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params or {})]


def one(conn: Connection, sql: str, params: dict | None = None) -> dict | None:
    r = conn.execute(text(sql), params or {}).first()
    return dict(r._mapping) if r else None


def one_or_404(conn: Connection, sql: str, params: dict | None = None, what: str = "Resource") -> dict:
    r = one(conn, sql, params)
    if r is None:
        # 404 for both "does not exist" and "belongs to someone else": RLS hides the row,
        # and we do not reveal that it exists.
        raise HTTPException(404, f"{what} not found")
    return r


def require_admin(conn: Connection = Depends(get_db)) -> Connection:
    if not conn.execute(text("select public.is_admin()")).scalar_one():
        raise HTTPException(403, "Administrator role required")
    return conn
