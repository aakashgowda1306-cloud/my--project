"""The signed-in learner: profile, onboarding, dashboard, achievements."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..deps import get_db, one_or_404, rows

router = APIRouter(prefix="/me", tags=["me"])

PROFILE_SQL = """
    select p.id, p.display_name, r.name as role, p.experience_level, p.learning_goal,
           p.onboarding_completed, p.created_at
    from public.profiles p join public.roles r on r.id = p.role_id
    where p.id = auth.uid()"""


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=60)
    experience_level: Literal["beginner", "intermediate", "advanced"] | None = None
    learning_goal: str | None = Field(default=None, max_length=280)
    onboarding_completed: bool | None = None


@router.get("")
def get_me(conn: Connection = Depends(get_db)) -> dict:
    # First visit: give the learner their own copy of the fictional incidents.
    conn.execute(text("select public.ensure_lab_workspace()"))
    profile = one_or_404(conn, PROFILE_SQL, what="Profile")
    profile["streak_days"] = conn.execute(text("select public.my_streak()")).scalar_one()
    return profile


@router.patch("")
def update_me(body: ProfileUpdate, conn: Connection = Depends(get_db)) -> dict:
    # Only fields the learner sent are changed. role_id is deliberately not accepted here,
    # and the database trigger would reject a self-promotion anyway.
    changes = body.model_dump(exclude_none=True)
    if changes:
        assignments = ", ".join(f"{k} = :{k}" for k in changes)  # keys come from the model, not the client
        conn.execute(text(f"update public.profiles set {assignments} where id = auth.uid()"), changes)
    return one_or_404(conn, PROFILE_SQL, what="Profile")


@router.get("/dashboard")
def dashboard(conn: Connection = Depends(get_db)) -> dict:
    conn.execute(text("select public.ensure_lab_workspace()"))
    courses = rows(conn, """
        select c.slug, c.title, c.department, cp.total_lessons, cp.completed_lessons, cp.percent_complete
        from public.course_progress cp join public.courses c on c.id = cp.course_id order by c.order_index""")
    total_lessons = sum(c["total_lessons"] for c in courses)
    done_lessons = sum(c["completed_lessons"] for c in courses)
    stats = rows(conn, """
        select
          (select count(distinct quiz_id) from public.quiz_attempts where user_id = auth.uid() and passed) as quizzes_passed,
          (select count(*) from public.quiz_attempts where user_id = auth.uid()) as quiz_attempts,
          (select round(avg(score_pct), 1) from public.quiz_attempts where user_id = auth.uid()) as avg_quiz_score,
          (select count(distinct lab_exercise_id) from public.lab_submissions where user_id = auth.uid() and is_correct) as labs_solved,
          (select count(*) from public.lab_exercises) as labs_total,
          (select count(*) from public.investigations where user_id = auth.uid() and status not like 'closed_%') as investigations_open,
          (select count(*) from public.investigations where user_id = auth.uid() and status like 'closed_%') as investigations_closed,
          (select count(*) from public.incidents where owner_id = auth.uid() and status = 'open') as incidents_open,
          (select count(*) from public.incidents where owner_id = auth.uid() and status = 'resolved') as incidents_resolved,
          (select count(*) from public.user_achievements where user_id = auth.uid()) as achievements_earned,
          (select count(*) from public.achievements) as achievements_total
    """)[0]
    recent = rows(conn, """
        select activity, ref_id, started_at from public.study_sessions
        where user_id = auth.uid() order by started_at desc limit 10""")
    next_lesson = rows(conn, """
        select l.id, l.title, c.slug as course_slug, c.title as course_title, l.estimated_minutes
        from public.lessons l join public.modules m on m.id = l.module_id join public.courses c on c.id = m.course_id
        left join public.lesson_progress lp on lp.lesson_id = l.id and lp.user_id = auth.uid()
        where coalesce(lp.status, 'not_started') <> 'completed'
        order by c.order_index, m.order_index, l.order_index limit 1""")
    return {
        "streak_days": conn.execute(text("select public.my_streak()")).scalar_one(),
        "lessons": {"completed": done_lessons, "total": total_lessons,
                    "percent": round(100 * done_lessons / total_lessons, 1) if total_lessons else 0.0},
        "courses": courses, "stats": stats, "recent_activity": recent,
        "next_lesson": next_lesson[0] if next_lesson else None,
    }


@router.get("/achievements")
def achievements(conn: Connection = Depends(get_db)) -> list[dict]:
    return rows(conn, """
        select a.code, a.title, a.description, a.icon, a.criteria, ua.awarded_at,
               (ua.awarded_at is not null) as earned
        from public.achievements a
        left join public.user_achievements ua on ua.achievement_id = a.id and ua.user_id = auth.uid()
        order by earned desc, a.title""")
