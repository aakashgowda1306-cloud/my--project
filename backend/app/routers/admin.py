"""Administrator dashboard endpoints. Every route requires the admin role."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..db import service_connection
from ..deps import one, require_admin, rows
from ..seed import run_detections

router = APIRouter(prefix="/admin", tags=["admin"])


class RoleChange(BaseModel):
    role: Literal["student", "instructor", "admin"]


@router.get("/overview")
def overview(conn: Connection = Depends(require_admin)) -> dict:
    return one(conn, """select
        (select count(*) from public.profiles) as users,
        (select count(*) from public.profiles where created_at > now() - interval '7 days') as new_users_7d,
        (select count(*) from public.lesson_progress where status = 'completed') as lessons_completed,
        (select count(*) from public.quiz_attempts) as quiz_attempts,
        (select round(avg(score_pct), 1) from public.quiz_attempts) as avg_quiz_score,
        (select count(*) from public.lab_submissions) as lab_submissions,
        (select count(*) from public.security_events) as security_events,
        (select count(*) from public.generated_alerts) as generated_alerts,
        (select count(*) from public.incidents where not is_template) as learner_incidents""")


@router.get("/users")
def users(conn: Connection = Depends(require_admin)) -> list[dict]:
    return rows(conn, """select p.id, p.display_name, r.name as role, p.experience_level, p.created_at,
                                (select count(*) from public.lesson_progress lp where lp.user_id = p.id
                                   and lp.status = 'completed') as lessons_completed
                         from public.profiles p join public.roles r on r.id = p.role_id order by p.created_at desc""")


@router.patch("/users/{user_id}/role")
def change_role(user_id: UUID, body: RoleChange, conn: Connection = Depends(require_admin)) -> dict:
    updated = one(conn, """update public.profiles set role_id = (select id from public.roles where name = :r)
                           where id = :id returning id, role_id""", {"r": body.role, "id": user_id})
    if updated is None:
        raise HTTPException(404, "User not found")
    return {"id": str(updated["id"]), "role": body.role}


@router.get("/audit-logs")
def audit_logs(conn: Connection = Depends(require_admin), limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
    return rows(conn, "select * from public.audit_logs order by created_at desc limit :l", {"l": limit})


@router.post("/detections/run")
def rerun_detections(conn: Connection = Depends(require_admin)) -> dict:
    # Admin verified above through RLS-scoped connection; writing shared alerts needs the service connection.
    admin_id = conn.execute(text("select auth.uid()")).scalar_one()
    with service_connection() as svc:
        count = run_detections(svc)
        svc.execute(text("select public.write_audit(:a, 'detections.run', 'generated_alerts', null, "
                         "jsonb_build_object('alerts', cast(:c as int)))"), {"a": admin_id, "c": count})
    return {"alerts_upserted": count}
