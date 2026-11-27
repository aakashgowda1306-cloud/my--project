"""Command-line tasks.  Run from the backend/ folder:

    python -m app.cli migrate --with-local-shim   # local Postgres only
    python -m app.cli migrate                     # Supabase (shim not needed)
    python -m app.cli seed                        # load synthetic data + run detections
    python -m app.cli detect                      # re-run detection rules only
    python -m app.cli status                      # show row counts
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text

from .db import service_connection
from .labdata.labs import REPO_ROOT
from .seed import migration_files, run_detections, seed_all

SHIM = REPO_ROOT / "database" / "local" / "00_supabase_local_shim.sql"


def migrate(with_shim: bool) -> None:
    with service_connection() as conn:
        conn.execute(text("create schema if not exists app_meta"))
        conn.execute(text("create table if not exists app_meta.schema_migrations "
                          "(name text primary key, applied_at timestamptz not null default now())"))
        applied = {r[0] for r in conn.execute(text("select name from app_meta.schema_migrations"))}
        files = ([SHIM] if with_shim else []) + migration_files()
        for f in files:
            if f.name in applied:
                print(f"  skip   {f.name} (already applied)")
                continue
            # Send the file through the raw driver cursor with NO parameters, so '%' characters
            # inside function bodies are not mistaken for query placeholders.
            with conn.connection.cursor() as cur:
                cur.execute(f.read_text())
            conn.execute(text("insert into app_meta.schema_migrations (name) values (:n)"), {"n": f.name})
            print(f"  apply  {f.name}")


def status() -> dict:
    tables = ["security_events", "detection_rules", "generated_alerts", "courses", "lessons", "questions",
              "lab_exercises", "incidents", "evidence_items", "achievements", "profiles"]
    with service_connection() as conn:
        return {t: conn.execute(text(f"select count(*) from public.{t}")).scalar_one() for t in tables}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("migrate", help="apply SQL migrations in order")
    m.add_argument("--with-local-shim", action="store_true", help="also apply the local Supabase auth shim")
    sub.add_parser("seed", help="load synthetic datasets and Academy content")
    sub.add_parser("detect", help="run detection rules and store alerts")
    sub.add_parser("status", help="print row counts")
    args = parser.parse_args(argv)

    if args.command == "migrate":
        migrate(args.with_local_shim)
    elif args.command == "seed":
        with service_connection() as conn:
            print(json.dumps(seed_all(conn), indent=2))
    elif args.command == "detect":
        with service_connection() as conn:
            print(f"alerts upserted: {run_detections(conn)}")
    elif args.command == "status":
        print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
