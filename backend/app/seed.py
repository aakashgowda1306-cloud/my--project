"""Load all synthetic lab data and Academy content into the database.

Safe to run repeatedly: every insert is an UPSERT keyed on a stable id.
Runs with the privileged (service) connection because it writes shared data.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

from .detections.rules import RULES, run_all
from .labdata import labs
from .labdata.events import generate_events

CONTENT_DIR = labs.REPO_ROOT / "educational-content"


def _j(value) -> str:
    return json.dumps(value, default=str)


def seed_events(conn: Connection) -> int:
    rows = generate_events()
    for r in rows:
        r["raw"] = _j(r["raw"])
    conn.execute(text("""
        insert into public.security_events (id, event_time, source, host, username, src_ip, dst_ip, dst_port,
            protocol, event_code, category, action, outcome, severity, process_name, command_line, message,
            raw, scenario_tag, dataset, is_synthetic)
        values (:id, :event_time, :source, :host, :username, cast(:src_ip as inet), cast(:dst_ip as inet),
            :dst_port, :protocol, :event_code, :category, :action, :outcome, :severity, :process_name,
            :command_line, :message, cast(:raw as jsonb), :scenario_tag, :dataset, :is_synthetic)
        on conflict (id) do update set event_time = excluded.event_time, source = excluded.source,
            host = excluded.host, username = excluded.username, src_ip = excluded.src_ip, dst_ip = excluded.dst_ip,
            dst_port = excluded.dst_port, protocol = excluded.protocol, event_code = excluded.event_code,
            category = excluded.category, action = excluded.action, outcome = excluded.outcome,
            severity = excluded.severity, process_name = excluded.process_name,
            command_line = excluded.command_line, message = excluded.message, raw = excluded.raw,
            scenario_tag = excluded.scenario_tag
    """), rows)
    return len(rows)


def seed_rules(conn: Connection) -> int:
    rows = []
    for r in RULES:
        m = r.metadata()
        m["parameters"] = _j(m["parameters"])
        rows.append(m)
    conn.execute(text("""
        insert into public.detection_rules (id, name, severity, mitre_technique_id, mitre_technique_name,
            mitre_tactic, data_sources, what_detected, why_it_matters, evidence_guidance, analyst_steps,
            defensive_response, parameters)
        values (:id, :name, :severity, :mitre_technique_id, :mitre_technique_name, :mitre_tactic, :data_sources,
            :what_detected, :why_it_matters, :evidence_guidance, :analyst_steps, :defensive_response,
            cast(:parameters as jsonb))
        on conflict (id) do update set name = excluded.name, severity = excluded.severity,
            mitre_technique_id = excluded.mitre_technique_id, mitre_technique_name = excluded.mitre_technique_name,
            mitre_tactic = excluded.mitre_tactic, data_sources = excluded.data_sources,
            what_detected = excluded.what_detected, why_it_matters = excluded.why_it_matters,
            evidence_guidance = excluded.evidence_guidance, analyst_steps = excluded.analyst_steps,
            defensive_response = excluded.defensive_response, parameters = excluded.parameters
    """), rows)
    return len(rows)


def load_events_from_db(conn: Connection) -> list[dict]:
    result = conn.execute(text("""
        select id, event_time, source, host, username, host(src_ip) as src_ip, host(dst_ip) as dst_ip, dst_port,
               protocol, event_code, category, action, outcome, severity, process_name, command_line, message, raw
        from public.security_events order by event_time, id"""))
    return [dict(r._mapping) for r in result]


def run_detections(conn: Connection) -> int:
    """Run every enabled rule over the stored events and upsert the alerts."""
    enabled = {r[0] for r in conn.execute(text("select id from public.detection_rules where enabled"))}
    alerts = [a for a in run_all(load_events_from_db(conn)) if a.rule_id in enabled]
    rows = [{**a.as_row(), "entity": _j(a.entity)} for a in alerts]
    if rows:
        conn.execute(text("""
            insert into public.generated_alerts (rule_id, alert_key, title, severity, entity, first_seen,
                last_seen, event_count, evidence_event_ids, summary)
            values (:rule_id, :alert_key, :title, :severity, cast(:entity as jsonb), :first_seen, :last_seen,
                :event_count, :evidence_event_ids, :summary)
            on conflict (alert_key) do update set title = excluded.title, severity = excluded.severity,
                entity = excluded.entity, summary = excluded.summary
        """), rows)
    return len(rows)


def seed_academy(conn: Connection) -> dict:
    catalogue = json.loads((CONTENT_DIR / "courses" / "catalogue.json").read_text())
    lab_ids = {e["slug"]: e["id"] for e in labs.lab_exercises()}
    counts = {"courses": 0, "lessons": 0, "questions": 0}
    for ci, course in enumerate(catalogue["courses"]):
        cid = labs.stable_id("course", course["slug"])
        conn.execute(text("""
            insert into public.courses (id, slug, title, summary, learning_path, level, department, order_index,
                is_published)
            values (:id, :slug, :title, :summary, :learning_path, :level, :department, :order_index, true)
            on conflict (id) do update set title = excluded.title, summary = excluded.summary,
                learning_path = excluded.learning_path, level = excluded.level, department = excluded.department,
                order_index = excluded.order_index, is_published = true
        """), {**{k: course[k] for k in ("slug", "title", "summary", "learning_path", "level", "department")},
               "id": cid, "order_index": ci})
        counts["courses"] += 1
        for mi, module in enumerate(course["modules"]):
            mid = labs.stable_id("module", f"{course['slug']}/{module['slug']}")
            conn.execute(text("""
                insert into public.modules (id, course_id, slug, title, summary, order_index)
                values (:id, :course_id, :slug, :title, :summary, :order_index)
                on conflict (id) do update set title = excluded.title, summary = excluded.summary,
                    order_index = excluded.order_index
            """), {"id": mid, "course_id": cid, "slug": module["slug"], "title": module["title"],
                   "summary": module.get("summary"), "order_index": mi})
            for li, lesson in enumerate(module["lessons"]):
                key = f"{course['slug']}/{lesson['slug']}"
                lid = labs.stable_id("lesson", key)
                body = (CONTENT_DIR / "lessons" / course["slug"] / f"{lesson['slug']}.md").read_text()
                conn.execute(text("""
                    insert into public.lessons (id, module_id, slug, title, summary, content_md, learning_outcome,
                        estimated_minutes, order_index)
                    values (:id, :module_id, :slug, :title, :summary, :content_md, :learning_outcome,
                        :estimated_minutes, :order_index)
                    on conflict (id) do update set title = excluded.title, summary = excluded.summary,
                        content_md = excluded.content_md, learning_outcome = excluded.learning_outcome,
                        estimated_minutes = excluded.estimated_minutes, order_index = excluded.order_index
                """), {"id": lid, "module_id": mid, "slug": lesson["slug"], "title": lesson["title"],
                       "summary": lesson["summary"], "content_md": body,
                       "learning_outcome": lesson["learning_outcome"],
                       "estimated_minutes": lesson["estimated_minutes"], "order_index": li})
                counts["lessons"] += 1

                if ex := lesson.get("exercise"):
                    lab = next(e for e in labs.lab_exercises() if e["slug"] == ex["lab"])
                    conn.execute(text("""
                        insert into public.exercises (id, lesson_id, lab_exercise_id, title, objective,
                            authorised_environment, expected_result, safety_restrictions, instructions_md)
                        values (:id, :lesson_id, :lab_id, :title, :objective, :env, :expected, :safety, :md)
                        on conflict (id) do update set title = excluded.title, instructions_md = excluded.instructions_md
                    """), {"id": labs.stable_id("exercise", key), "lesson_id": lid, "lab_id": lab_ids[ex["lab"]],
                           "title": ex["title"], "objective": lab["objective"],
                           "env": lab["authorised_environment"], "expected": lab["expected_result"],
                           "safety": lab["safety_restrictions"], "md": ex["instructions_md"]})

                qid = labs.stable_id("quiz", key)
                conn.execute(text("""
                    insert into public.quizzes (id, lesson_id, title, pass_mark) values (:id, :lesson_id, :title, 70)
                    on conflict (id) do update set title = excluded.title
                """), {"id": qid, "lesson_id": lid, "title": f"Check your understanding: {lesson['title']}"})
                for qi, q in enumerate(lesson["quiz"]):
                    if not 0 <= q["answer"] < len(q["options"]):
                        raise ValueError(f"{key} question {qi}: answer index out of range")
                    question_id = labs.stable_id("question", f"{key}/{qi}")
                    conn.execute(text("""
                        insert into public.questions (id, quiz_id, order_index, prompt, options)
                        values (:id, :quiz_id, :oi, :prompt, cast(:options as jsonb))
                        on conflict (id) do update set prompt = excluded.prompt, options = excluded.options
                    """), {"id": question_id, "quiz_id": qid, "oi": qi, "prompt": q["prompt"],
                           "options": _j(q["options"])})
                    conn.execute(text("""
                        insert into public.question_answer_keys (question_id, correct_option, explanation)
                        values (:id, :answer, :explanation)
                        on conflict (question_id) do update set correct_option = excluded.correct_option,
                            explanation = excluded.explanation
                    """), {"id": question_id, "answer": q["answer"], "explanation": q["explanation"]})
                    counts["questions"] += 1
    return counts


def seed_labs(conn: Connection) -> dict:
    exercises = labs.lab_exercises()
    for e in exercises:
        conn.execute(text("""
            insert into public.lab_exercises (id, slug, department, title, difficulty, objective,
                authorised_environment, expected_result, safety_restrictions, instructions_md, answer_fields)
            values (:id, :slug, :department, :title, :difficulty, :objective, :authorised_environment,
                :expected_result, :safety_restrictions, :instructions_md, cast(:answer_fields as jsonb))
            on conflict (id) do update set title = excluded.title, difficulty = excluded.difficulty,
                objective = excluded.objective, authorised_environment = excluded.authorised_environment,
                expected_result = excluded.expected_result, safety_restrictions = excluded.safety_restrictions,
                instructions_md = excluded.instructions_md, answer_fields = excluded.answer_fields
        """), {**e, "answer_fields": _j(e["answer_fields"])})
        conn.execute(text("""
            insert into public.lab_exercise_answer_keys (lab_exercise_id, expected, explanation)
            values (:id, cast(:expected as jsonb), :explanation)
            on conflict (lab_exercise_id) do update set expected = excluded.expected,
                explanation = excluded.explanation
        """), {"id": e["id"], "expected": _j(e["expected"]), "explanation": e["explanation"]})

    first_alert = {r.rule_id: r.id for r in conn.execute(text(
        "select distinct on (rule_id) rule_id, id from public.generated_alerts order by rule_id, first_seen desc"))}
    for inc in labs.incident_templates():
        conn.execute(text("""
            insert into public.incidents (id, owner_id, is_template, reference, title, category, severity,
                assigned_analyst, summary, related_alert_id, detected_at)
            values (:id, null, true, :reference, :title, :category, :severity, :assigned_analyst, :summary,
                :alert_id, :detected_at)
            on conflict (id) do update set title = excluded.title, summary = excluded.summary,
                category = excluded.category, severity = excluded.severity, related_alert_id = excluded.related_alert_id
        """), {**inc, "alert_id": first_alert.get(inc["related_rule"])})

    for ev in labs.evidence_items():
        conn.execute(text("""
            insert into public.evidence_items (id, owner_id, case_ref, label, evidence_type, description, file_name,
                size_bytes, sha256, md5, source_host, acquired_at, acquired_by, storage_path)
            values (:id, null, :case_ref, :label, :evidence_type, :description, :file_name, :size_bytes, :sha256,
                :md5, :source_host, :acquired_at, :acquired_by, :storage_path)
            on conflict (id) do update set size_bytes = excluded.size_bytes, sha256 = excluded.sha256,
                md5 = excluded.md5, description = excluded.description
        """), ev)
        has_custody = conn.execute(text("select 1 from public.evidence_custody_events where evidence_id = :id"),
                                   {"id": ev["id"]}).first()
        if not has_custody:
            conn.execute(text("""
                insert into public.evidence_custody_events (evidence_id, action, actor, location, occurred_at, notes)
                values (:id, :action, :actor, :location, :occurred_at, 'Simulated chain-of-custody record')
            """), [{"id": ev["id"], "action": a, "actor": who, "location": loc, "occurred_at": t}
                   for a, who, loc, t in ev["custody"]])

    for a in labs.achievements():
        conn.execute(text("""
            insert into public.achievements (id, code, title, description, icon, criteria)
            values (:id, :code, :title, :description, :icon, cast(:criteria as jsonb))
            on conflict (id) do update set title = excluded.title, description = excluded.description,
                icon = excluded.icon, criteria = excluded.criteria
        """), {**a, "criteria": _j(a["criteria"])})
    return {"lab_exercises": len(exercises), "incident_templates": len(labs.incident_templates()),
            "evidence_items": len(labs.evidence_items()), "achievements": len(labs.achievements())}


def seed_all(conn: Connection) -> dict:
    summary = {"events": seed_events(conn), "rules": seed_rules(conn)}
    summary["alerts"] = run_detections(conn)
    summary.update(seed_labs(conn))      # lab exercises first: lessons link to them
    summary.update(seed_academy(conn))
    return summary


def migration_files() -> list[Path]:
    return sorted((labs.REPO_ROOT / "database" / "migrations").glob("*.sql"))
