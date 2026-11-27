"""Database access.

The most important idea in this file: every request from a signed-in learner
runs inside a transaction where we

  1. store the learner's JWT claims in `request.jwt.claims`, and
  2. switch to the low-privilege `authenticated` role.

Postgres Row Level Security then filters every query to that learner's rows,
exactly as it does for Supabase's own API. A bug in an endpoint therefore
cannot leak another learner's data.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

from .config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@contextmanager
def user_connection(claims: dict) -> Iterator[Connection]:
    """A transaction that runs as role `authenticated` with the learner's claims."""
    with get_engine().begin() as conn:
        # set_config(..., true) = "local to this transaction"; it is reset at COMMIT/ROLLBACK,
        # so a pooled connection never carries one learner's identity into the next request.
        conn.execute(text("select set_config('request.jwt.claims', :claims, true)"),
                     {"claims": json.dumps(claims)})
        conn.execute(text("set local role authenticated"))
        yield conn


@contextmanager
def service_connection() -> Iterator[Connection]:
    """Privileged transaction for trusted server-side jobs only (seeding, detection runs,
    local-mode account creation). Never use it with learner-controlled filters."""
    with get_engine().begin() as conn:
        yield conn
