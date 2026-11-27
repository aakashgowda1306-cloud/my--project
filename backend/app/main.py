"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload     (from the backend/ folder)
API docs:     http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from .config import get_settings
from .routers import academy, admin, auth, incidents, labs_routes, me, soc_siem

log = logging.getLogger("cybersec_academy")

# Map PostgreSQL error codes raised by our SQL functions/triggers to HTTP responses.
SQLSTATE_TO_HTTP = {
    "42501": 403,  # insufficient_privilege (RLS / permission / our own checks)
    "22023": 400,  # invalid_parameter_value (e.g. invalid incident transition)
    "P0002": 404,  # no_data_found
    "23505": 409,  # unique_violation
    "23514": 400,  # check_violation
    "23503": 400,  # foreign_key_violation
    "22P02": 400,  # invalid_text_representation (bad uuid, etc.)
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Cybersec Academy API",
        version="0.1.0",
        description="Defensive cybersecurity learning platform. All lab data is synthetic.",
        docs_url="/docs" if settings.environment != "production" else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # we use Bearer tokens, not cookies
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DBAPIError)
    async def db_errors(request: Request, exc: DBAPIError):
        code = getattr(exc.orig, "sqlstate", None)
        status = SQLSTATE_TO_HTTP.get(code)
        if status is None:
            log.exception("Unhandled database error")
            return JSONResponse({"detail": "Internal server error"}, status_code=500)
        # Our own RAISE messages are written for learners; driver messages for other codes are shortened.
        diag = getattr(exc.orig, "diag", None)
        message = (diag.message_primary if diag else None) or "Request rejected by the database"
        return JSONResponse({"detail": message}, status_code=status)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok", "auth_mode": settings.auth_mode, "environment": settings.environment}

    for r in (auth.router, me.router, academy.router, soc_siem.router, labs_routes.router,
              incidents.router, admin.router):
        app.include_router(r, prefix=settings.api_prefix)
    return app


app = create_app()
