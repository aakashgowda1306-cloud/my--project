"""Cybersecurity Academy: catalogue, lessons, progress, quizzes, analytics."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..deps import get_db, one, one_or_404, rows

router = APIRouter(prefix="/academy", tags=["academy"])


class QuizSubmission(BaseModel):
    # {"<question uuid>": <selected option index>}
    answers: dict[UUID, int] = Field(min_length=1, max_length=50)


@router.get("/courses")
def list_courses(conn: Connection = Depends(get_db)) -> list[dict]:
    return rows(conn, """
        select c.id, c.slug, c.title, c.summary, c.learning_path, c.level, c.department,
               coalesce(cp.total_lessons, 0) as total_lessons, coalesce(cp.completed_lessons, 0) as completed_lessons,
               coalesce(cp.percent_complete, 0) as percent_complete,
               (select coalesce(sum(l.estimated_minutes), 0) from public.modules m
                  join public.lessons l on l.module_id = m.id where m.course_id = c.id) as estimated_minutes
        from public.courses c left join public.course_progress cp on cp.course_id = c.id
        order by c.order_index""")


@router.get("/courses/{slug}")
def get_course(slug: str, conn: Connection = Depends(get_db)) -> dict:
    course = one_or_404(conn, "select id, slug, title, summary, learning_path, level, department "
                              "from public.courses where slug = :s", {"s": slug}, what="Course")
    lessons = rows(conn, """
        select m.id as module_id, m.title as module_title, m.order_index as module_order,
               l.id, l.slug, l.title, l.summary, l.estimated_minutes, l.order_index,
               coalesce(lp.status, 'not_started') as status,
               (select max(qa.score_pct) from public.quiz_attempts qa join public.quizzes q on q.id = qa.quiz_id
                 where q.lesson_id = l.id and qa.user_id = auth.uid()) as best_quiz_score
        from public.modules m join public.lessons l on l.module_id = m.id
        left join public.lesson_progress lp on lp.lesson_id = l.id and lp.user_id = auth.uid()
        where m.course_id = :cid order by m.order_index, l.order_index""", {"cid": course["id"]})
    modules: dict = {}
    for les in lessons:
        mod = modules.setdefault(les["module_id"], {"id": les["module_id"], "title": les["module_title"], "lessons": []})
        mod["lessons"].append({k: les[k] for k in ("id", "slug", "title", "summary", "estimated_minutes",
                                                   "status", "best_quiz_score")})
    course["modules"] = list(modules.values())
    return course


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: UUID, conn: Connection = Depends(get_db)) -> dict:
    lesson = one_or_404(conn, """
        select l.id, l.slug, l.title, l.summary, l.content_md, l.learning_outcome, l.estimated_minutes,
               l.video_storyboard, c.slug as course_slug, c.title as course_title,
               coalesce(lp.status, 'not_started') as status
        from public.lessons l join public.modules m on m.id = l.module_id join public.courses c on c.id = m.course_id
        left join public.lesson_progress lp on lp.lesson_id = l.id and lp.user_id = auth.uid()
        where l.id = :id""", {"id": lesson_id}, what="Lesson")
    lesson["exercises"] = rows(conn, """
        select e.id, e.title, e.objective, e.authorised_environment, e.expected_result, e.safety_restrictions,
               e.instructions_md, le.slug as lab_slug
        from public.exercises e left join public.lab_exercises le on le.id = e.lab_exercise_id
        where e.lesson_id = :id order by e.order_index""", {"id": lesson_id})
    quiz = one(conn, "select id, title, pass_mark from public.quizzes where lesson_id = :id", {"id": lesson_id})
    if quiz:
        # Note: no answers here — learners cannot read question_answer_keys at all.
        quiz["questions"] = rows(conn, "select id, prompt, options from public.questions where quiz_id = :q "
                                       "order by order_index", {"q": quiz["id"]})
    lesson["quiz"] = quiz
    return lesson


@router.post("/lessons/{lesson_id}/start")
def start_lesson(lesson_id: UUID, conn: Connection = Depends(get_db)) -> dict:
    one_or_404(conn, "select id from public.lessons where id = :id", {"id": lesson_id}, what="Lesson")
    conn.execute(text("""
        insert into public.lesson_progress (user_id, lesson_id, status) values (auth.uid(), :id, 'in_progress')
        on conflict (user_id, lesson_id) do nothing"""), {"id": lesson_id})
    conn.execute(text("insert into public.study_sessions (user_id, activity, ref_id) values (auth.uid(), 'lesson', :id)"),
                 {"id": lesson_id})
    return {"lesson_id": str(lesson_id), "status": "in_progress"}


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: UUID, conn: Connection = Depends(get_db)) -> dict:
    one_or_404(conn, "select id from public.lessons where id = :id", {"id": lesson_id}, what="Lesson")
    conn.execute(text("""
        insert into public.lesson_progress (user_id, lesson_id, status, completed_at)
        values (auth.uid(), :id, 'completed', now())
        on conflict (user_id, lesson_id) do update set status = 'completed',
            completed_at = coalesce(public.lesson_progress.completed_at, now())"""), {"id": lesson_id})
    return {"lesson_id": str(lesson_id), "status": "completed"}


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: UUID, body: QuizSubmission, conn: Connection = Depends(get_db)) -> dict:
    answers = {str(k): v for k, v in body.answers.items()}
    return conn.execute(text("select public.submit_quiz_attempt(:q, cast(:a as jsonb))"),
                        {"q": quiz_id, "a": json.dumps(answers)}).scalar_one()


@router.get("/analytics")
def analytics(conn: Connection = Depends(get_db)) -> dict:
    return {
        "courses": rows(conn, """select c.title, cp.completed_lessons, cp.total_lessons, cp.percent_complete
                                 from public.course_progress cp join public.courses c on c.id = cp.course_id
                                 order by c.order_index"""),
        "quiz_history": rows(conn, """
            select qa.created_at, qa.score_pct, qa.passed, q.title
            from public.quiz_attempts qa join public.quizzes q on q.id = qa.quiz_id
            where qa.user_id = auth.uid() order by qa.created_at"""),
        "activity_by_day": rows(conn, """
            select (started_at at time zone 'UTC')::date as day, activity, count(*)::int as count
            from public.study_sessions where user_id = auth.uid()
            group by 1, 2 order by 1"""),
        "labs_by_department": rows(conn, """
            select e.department, count(distinct e.id)::int as total,
                   count(distinct s.lab_exercise_id) filter (where s.is_correct)::int as solved
            from public.lab_exercises e
            left join public.lab_submissions s on s.lab_exercise_id = e.id and s.user_id = auth.uid()
            group by e.department order by e.department"""),
    }
