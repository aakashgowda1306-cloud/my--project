"""Authentication, authorisation and Row Level Security.

The RLS tests talk to the database directly as the `authenticated` role, the
same way a browser holding the Supabase anon key could. They prove the data is
protected by the database itself, not only by the API code.
"""

import time

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db import service_connection, user_connection

from .conftest import register

API = "/api/v1"


# ---------------------------------------------------------------- authentication
def test_register_then_login(client, learner):
    r = client.post(f"{API}/auth/login", json={"email": learner["email"], "password": learner["password"]})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"


def test_wrong_password_and_unknown_email_get_same_message(client, learner):
    a = client.post(f"{API}/auth/login", json={"email": learner["email"], "password": "wrong-password!"})
    b = client.post(f"{API}/auth/login", json={"email": "nobody@example.com", "password": "wrong-password!"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_duplicate_registration_rejected(client, learner):
    r = client.post(f"{API}/auth/register", json={"email": learner["email"], "password": "another-long-pass",
                                                  "display_name": "Copy"})
    assert r.status_code == 409


def test_short_password_rejected(client):
    r = client.post(f"{API}/auth/register", json={"email": "short@example.com", "password": "short",
                                                  "display_name": "Shorty"})
    assert r.status_code == 422


def test_password_is_stored_hashed(learner):
    with service_connection() as conn:
        stored = conn.execute(text("select encrypted_password from auth.users where id = :id"),
                              {"id": learner["id"]}).scalar_one()
    assert stored != learner["password"] and stored.startswith("$2")


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer not-a-jwt"}, {"Authorization": "Basic abc"}])
def test_protected_routes_require_valid_token(client, headers):
    assert client.get(f"{API}/me", headers=headers).status_code in (401, 403)


def test_forged_and_expired_tokens_rejected(client, learner):
    from app.config import get_settings

    forged = jwt.encode({"sub": learner["id"], "role": "authenticated", "aud": "authenticated",
                         "exp": int(time.time()) + 600}, "attacker-guess-secret-attacker-guess", algorithm="HS256")
    expired = jwt.encode({"sub": learner["id"], "role": "authenticated", "aud": "authenticated",
                          "exp": int(time.time()) - 10}, get_settings().local_jwt_secret, algorithm="HS256")
    for token in (forged, expired):
        assert client.get(f"{API}/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_login_rate_limit(client):
    user = register(client, "Rate Limited")
    codes = [client.post(f"{API}/auth/login", json={"email": user["email"], "password": "wrong-password!"}).status_code
             for _ in range(11)]
    assert codes[:10] == [401] * 10 and codes[10] == 429


# ---------------------------------------------------------------- isolation between learners (via API)
def test_learner_cannot_read_another_learners_investigation(client, learner, other_learner):
    alert_id = client.get(f"{API}/siem/alerts", headers=learner["headers"]).json()[0]["id"]
    inv = client.post(f"{API}/investigations", json={"alert_id": alert_id}, headers=learner["headers"]).json()
    client.post(f"{API}/investigations/{inv['id']}/notes", json={"body": "private note"}, headers=learner["headers"])

    assert client.get(f"{API}/investigations/{inv['id']}", headers=other_learner["headers"]).status_code == 404
    assert client.get(f"{API}/investigations", headers=other_learner["headers"]).json() == []
    r = client.post(f"{API}/investigations/{inv['id']}/notes", json={"body": "intrusion"},
                    headers=other_learner["headers"])
    assert r.status_code == 404


def test_learner_cannot_read_or_modify_another_learners_incident(client, learner, other_learner):
    inc = client.get(f"{API}/incidents", headers=learner["headers"]).json()["items"][0]
    assert client.get(f"{API}/incidents/{inc['id']}", headers=other_learner["headers"]).status_code == 404
    r = client.patch(f"{API}/incidents/{inc['id']}", json={"severity": "low"}, headers=other_learner["headers"])
    assert r.status_code == 404


# ---------------------------------------------------------------- RLS directly in the database
def claims(user):
    return {"sub": user["id"], "role": "authenticated"}


def test_rls_hides_other_learners_rows(client, learner, other_learner):
    client.post(f"{API}/academy/lessons/{_first_lesson(client, learner)}/complete", headers=learner["headers"])
    with user_connection(claims(other_learner)) as conn:
        for table, col in (("lesson_progress", "user_id"), ("investigations", "user_id"),
                           ("incidents", "owner_id"), ("study_sessions", "user_id")):
            n = conn.execute(text(f"select count(*) from public.{table} where {col} = :id"),
                             {"id": learner["id"]}).scalar_one()
            assert n == 0, f"{table} leaked rows across learners"


def test_rls_blocks_writing_rows_for_someone_else(learner, other_learner):
    with pytest.raises(DBAPIError), user_connection(claims(other_learner)) as conn:
        conn.execute(text("insert into public.investigations (user_id, kind, case_ref, title) "
                          "values (:victim, 'forensic_case', 'X', 'forged')"), {"victim": learner["id"]})


@pytest.mark.parametrize("sql", [
    "select * from public.question_answer_keys",
    "select * from public.lab_exercise_answer_keys",
    "select scenario_tag from public.security_events",
    "insert into public.quiz_attempts (user_id, quiz_id, answers, correct_count, total_count, score_pct, passed) "
    "select auth.uid(), id, '{}', 1, 1, 100, true from public.quizzes limit 1",
    "insert into public.user_achievements (user_id, achievement_id) select auth.uid(), id from public.achievements limit 1",
    "insert into public.security_events (id, event_time, source, host, event_code, category, action, outcome, severity, message) "
    "values (99999, now(), 'linux', 'x', 'X', 'x', 'x', 'success', 'info', 'forged')",
    "select public.write_audit(auth.uid(), 'forged', 'x', null, '{}')",
    "select public.evaluate_achievements(auth.uid())",
])
def test_learner_cannot_touch_protected_data(learner, sql):
    with pytest.raises(DBAPIError) as exc, user_connection(claims(learner)) as conn:
        conn.execute(text(sql))
    assert exc.value.orig.sqlstate == "42501"  # insufficient_privilege


def test_learner_sees_no_audit_logs(learner):
    with user_connection(claims(learner)) as conn:
        assert conn.execute(text("select count(*) from public.audit_logs")).scalar_one() == 0


def test_self_promotion_to_admin_is_blocked(learner):
    with pytest.raises(DBAPIError) as exc, user_connection(claims(learner)) as conn:
        conn.execute(text("update public.profiles set role_id = 3 where id = auth.uid()"))
    assert "only administrators" in str(exc.value)


def test_chain_of_custody_is_append_only(learner):
    with user_connection(claims(learner)) as conn:
        # UPDATE is not granted at all, so Postgres refuses before RLS is even consulted.
        with pytest.raises(DBAPIError):
            conn.execute(text("update public.evidence_custody_events set actor = 'tampered'"))


def test_cannot_add_custody_record_to_shared_evidence(learner):
    with pytest.raises(DBAPIError), user_connection(claims(learner)) as conn:
        conn.execute(text("""insert into public.evidence_custody_events (evidence_id, action, actor, location,
                             occurred_at, recorded_by)
                             select id, 'released', 'me', 'x', now(), auth.uid() from public.evidence_items limit 1"""))


def test_cannot_forge_incident_stage_history(client, learner):
    inc = client.get(f"{API}/incidents", headers=learner["headers"]).json()["items"][0]
    with pytest.raises(DBAPIError), user_connection(claims(learner)) as conn:
        conn.execute(text("insert into public.incident_updates (incident_id, user_id, from_stage, to_stage) "
                          "values (:i, auth.uid(), 'alert_received', 'lessons_learned')"), {"i": inc["id"]})


def test_template_incidents_are_read_only(learner):
    with user_connection(claims(learner)) as conn:
        n = conn.execute(text("update public.incidents set title = 'x' where is_template")).rowcount
    assert n == 0


def test_anonymous_can_browse_catalogue_but_not_lessons():
    from app.db import get_engine

    with get_engine().begin() as conn:
        conn.execute(text("set local role anon"))
        assert conn.execute(text("select count(*) from public.courses")).scalar_one() == 3
        with pytest.raises(DBAPIError):
            conn.execute(text("select content_md from public.lessons"))


# ---------------------------------------------------------------- admin authorisation
def test_student_cannot_use_admin_routes(client, learner):
    for path in ("/admin/overview", "/admin/users", "/admin/audit-logs"):
        assert client.get(f"{API}{path}", headers=learner["headers"]).status_code == 403
    assert client.post(f"{API}/admin/detections/run", headers=learner["headers"]).status_code == 403


def test_admin_routes_and_audited_role_change(client, learner):
    admin = register(client, "Admin User")
    with service_connection() as conn:  # bootstrap the first admin out-of-band, as you would in production
        conn.execute(text("update public.profiles set role_id = 3 where id = :id"), {"id": admin["id"]})
    assert client.get(f"{API}/admin/overview", headers=admin["headers"]).json()["security_events"] == 352
    r = client.patch(f"{API}/admin/users/{learner['id']}/role", json={"role": "instructor"}, headers=admin["headers"])
    assert r.status_code == 200
    logs = client.get(f"{API}/admin/audit-logs", headers=admin["headers"]).json()
    assert any(entry["action"] == "profile.role_changed" and entry["entity_id"] == learner["id"] for entry in logs)
    assert client.post(f"{API}/admin/detections/run", headers=admin["headers"]).json()["alerts_upserted"] == 18


def _first_lesson(client, user):
    course = client.get(f"{API}/academy/courses/cybersecurity-fundamentals", headers=user["headers"]).json()
    return course["modules"][0]["lessons"][0]["id"]
