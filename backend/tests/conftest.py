"""Test setup: a throwaway database, migrated and seeded once per test run.

The test database name must end in "_test"; we refuse to drop anything else.
"""

from __future__ import annotations

import os
import secrets
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BASE_URL = os.environ.get("TEST_DATABASE_URL",
                          "postgresql+psycopg://postgres:postgres@localhost:5432/cybersec_academy_test")
url = make_url(BASE_URL)
assert url.database and url.database.endswith("_test"), "Refusing to run tests against a non-test database"

os.environ.update({
    "DATABASE_URL": BASE_URL,
    "AUTH_MODE": "local",
    "LOCAL_JWT_SECRET": secrets.token_urlsafe(48),
    "ENVIRONMENT": "test",
    "CORS_ORIGINS": "http://localhost:3000",
})


@pytest.fixture(scope="session", autouse=True)
def database():
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as c:
        c.execute(text(f'drop database if exists "{url.database}" with (force)'))
        c.execute(text(f'create database "{url.database}"'))
    admin_engine.dispose()

    from app import cli
    from app.db import service_connection
    from app.seed import seed_all

    cli.migrate(with_shim=True)
    with service_connection() as conn:
        seed_all(conn)
    yield


@pytest.fixture(scope="session")
def client(database):
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def register(client, name: str = "Test Learner") -> dict:
    email = f"learner-{uuid.uuid4().hex[:10]}@example.com"
    password = "a-long-test-password"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "display_name": name})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/v1/me", headers=headers).json()
    return {"email": email, "password": password, "token": token, "headers": headers, "id": me["id"]}


@pytest.fixture
def learner(client):
    return register(client, "Learner A")


@pytest.fixture
def other_learner(client):
    return register(client, "Learner B")
