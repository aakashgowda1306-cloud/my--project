"""End-to-end feature tests through the API: Academy, SOC/SIEM, Forensics, Network, Incident Response."""

import hashlib

import pytest
from sqlalchemy import text

from app.db import service_connection
from app.labdata.labs import EVIDENCE_DIR

API = "/api/v1"


def answer_key(quiz_id):
    with service_connection() as conn:
        return {str(r.id): r.correct_option for r in conn.execute(text(
            "select q.id, k.correct_option from public.questions q join public.question_answer_keys k "
            "on k.question_id = q.id where q.quiz_id = :q"), {"q": quiz_id})}


# ---------------------------------------------------------------- Academy
def test_lesson_has_content_quiz_without_answers(client, learner):
    courses = client.get(f"{API}/academy/courses", headers=learner["headers"]).json()
    assert len(courses) == 3 and all(c["total_lessons"] > 0 for c in courses)
    lesson_id = client.get(f"{API}/academy/courses/computer-networking-basics",
                           headers=learner["headers"]).json()["modules"][0]["lessons"][0]["id"]
    lesson = client.get(f"{API}/academy/lessons/{lesson_id}", headers=learner["headers"]).json()
    assert "## " in lesson["content_md"] and lesson["learning_outcome"]
    assert lesson["exercises"][0]["safety_restrictions"] and lesson["exercises"][0]["authorised_environment"]
    for q in lesson["quiz"]["questions"]:
        assert set(q) == {"id", "prompt", "options"}  # no correct answer leaked


def test_quiz_grading_progress_and_achievements(client, learner):
    h = learner["headers"]
    course = client.get(f"{API}/academy/courses/cybersecurity-fundamentals", headers=h).json()
    lessons = [les["id"] for m in course["modules"] for les in m["lessons"]]
    quiz = client.get(f"{API}/academy/lessons/{lessons[0]}", headers=h).json()["quiz"]
    key = answer_key(quiz["id"])

    wrong = {qid: (opt + 1) % 3 for qid, opt in key.items()}
    r = client.post(f"{API}/academy/quizzes/{quiz['id']}/submit", json={"answers": wrong}, headers=h).json()
    assert r["correct_count"] == 0 and r["passed"] is False and float(r["score_pct"]) == 0

    r = client.post(f"{API}/academy/quizzes/{quiz['id']}/submit", json={"answers": key}, headers=h).json()
    assert r["correct_count"] == r["total_count"] == 3 and r["passed"] is True
    assert all(item["explanation"] for item in r["results"])

    client.post(f"{API}/academy/lessons/{lessons[0]}/start", headers=h)
    client.post(f"{API}/academy/lessons/{lessons[0]}/complete", headers=h)
    progress = {c["slug"]: c for c in client.get(f"{API}/academy/courses", headers=h).json()}
    fundamentals = progress["cybersecurity-fundamentals"]
    assert fundamentals["completed_lessons"] == 1
    assert float(fundamentals["percent_complete"]) == round(100 / fundamentals["total_lessons"], 1)

    earned = {a["code"] for a in client.get(f"{API}/me/achievements", headers=h).json() if a["earned"]}
    assert {"first-lesson", "first-quiz", "perfect-score"} <= earned
    dash = client.get(f"{API}/me/dashboard", headers=h).json()
    assert dash["streak_days"] == 1 and dash["stats"]["quizzes_passed"] == 1 and dash["lessons"]["completed"] == 1


def test_completing_a_lesson_twice_is_idempotent(client, learner):
    h = learner["headers"]
    lesson_id = client.get(f"{API}/academy/courses/soc-operations-and-log-analysis",
                           headers=h).json()["modules"][0]["lessons"][0]["id"]
    for _ in range(2):
        assert client.post(f"{API}/academy/lessons/{lesson_id}/complete", headers=h).status_code == 200
    assert client.get(f"{API}/me/dashboard", headers=h).json()["lessons"]["completed"] == 1


def test_profile_onboarding_update(client, learner):
    r = client.patch(f"{API}/me", json={"experience_level": "intermediate", "learning_goal": "Become a SOC analyst",
                                        "onboarding_completed": True}, headers=learner["headers"]).json()
    assert r["onboarding_completed"] and r["experience_level"] == "intermediate" and r["role"] == "student"


# ---------------------------------------------------------------- SOC / SIEM
def test_soc_overview_metrics_are_computed_from_data(client, learner):
    d = client.get(f"{API}/soc/overview", headers=learner["headers"]).json()
    with service_connection() as conn:
        events = conn.execute(text("select count(*) from public.security_events")).scalar_one()
        crit = conn.execute(text("select count(*) from public.generated_alerts where severity = 'critical'")).scalar_one()
    assert d["events"]["total"] == events == sum(d["events"]["by_severity"].values())
    assert d["alerts"]["total"] == 18 and d["alerts"]["by_severity"]["critical"] == crit
    assert d["alerts"]["open"] == 18 and d["alerts"]["resolved"] == 0
    assert sum(r["count"] for r in d["alerts"]["by_rule"]) == 18
    assert sum(b["count"] for b in d["timeline"]) == events
    assert d["incidents"] == {"open": 4, "resolved": 0}


def test_event_search_filters_and_pagination(client, learner):
    h = learner["headers"]
    r = client.get(f"{API}/siem/events", params={"q": "203.0.113.45", "source": "linux"}, headers=h).json()
    assert r["total"] == 12 and all(e["outcome"] == "failure" for e in r["items"])
    r = client.get(f"{API}/siem/events", params={"severity": ["critical"]}, headers=h).json()
    assert r["total"] == 2
    page1 = client.get(f"{API}/siem/events", params={"page_size": 10, "sort": "asc"}, headers=h).json()
    page2 = client.get(f"{API}/siem/events", params={"page_size": 10, "page": 2, "sort": "asc"}, headers=h).json()
    assert page1["items"][-1]["id"] < page2["items"][0]["id"] and page1["total"] == 352
    assert "scenario_tag" not in page1["items"][0]


def test_search_input_is_treated_as_data_not_sql(client, learner):
    r = client.get(f"{API}/siem/events", params={"q": "' or 1=1 --"}, headers=learner["headers"])
    assert r.status_code == 200 and r.json()["total"] == 0


def test_run_rule_live_and_alert_detail(client, learner):
    h = learner["headers"]
    run = client.post(f"{API}/siem/rules/CSA-DET-002/run", headers=h).json()
    assert run["match_count"] == 1 and len(run["matches"][0]["entity"]["accounts"]) == 6
    alert = client.get(f"{API}/siem/alerts", params={"rule_id": "CSA-DET-006"}, headers=h).json()[0]
    detail = client.get(f"{API}/siem/alerts/{alert['id']}", headers=h).json()
    assert detail["rule"]["mitre_technique_id"] == "T1543.003" and len(detail["evidence"]) == 1


def test_investigation_lifecycle_requires_summary_to_close(client, learner):
    h = learner["headers"]
    alert = client.get(f"{API}/siem/alerts", params={"rule_id": "CSA-DET-004"}, headers=h).json()[0]
    inv = client.post(f"{API}/investigations", json={"alert_id": alert["id"]}, headers=h).json()
    again = client.post(f"{API}/investigations", json={"alert_id": alert["id"]}, headers=h).json()
    assert again["id"] == inv["id"]  # one investigation per alert per learner
    assert client.patch(f"{API}/investigations/{inv['id']}", json={"status": "closed_benign"}, headers=h).status_code == 400
    r = client.patch(f"{API}/investigations/{inv['id']}",
                     json={"status": "closed_benign", "summary": "Approved change CHG-1042."}, headers=h)
    assert r.status_code == 200
    overview = client.get(f"{API}/soc/overview", headers=h).json()
    assert overview["alerts"]["resolved"] == 1 and overview["alerts"]["open"] == 17
    earned = {a["code"] for a in client.get(f"{API}/me/achievements", headers=h).json() if a["earned"]}
    assert "first-triage" in earned


# ---------------------------------------------------------------- Labs, forensics, network
@pytest.mark.parametrize("slug,answers,correct", [
    ("network-subnet-24", {"network_address": "10.20.4.0", "broadcast_address": "10.20.4.255", "usable_hosts": "254"}, True),
    ("network-subnet-26", {"network_address": "172.16.8.128", "broadcast_address": "172.16.8.191", "usable_hosts": "62"}, True),
    ("siem-bruteforce-source", {"src_ip": " 203.0.113.45 ", "username": "ROOT"}, True),  # whitespace/case tolerant
    ("siem-bruteforce-source", {"src_ip": "203.0.113.80", "username": "root"}, False),
])
def test_lab_grading(client, learner, slug, answers, correct):
    r = client.post(f"{API}/labs/{slug}/submit", json={"answers": answers}, headers=learner["headers"]).json()
    assert r["is_correct"] is correct
    assert (r["explanation"] is not None) is correct  # explanation only revealed when solved
    if not correct:
        assert 0 < r["score"] < r["max_score"]  # partial credit: one of two fields right


def test_every_lab_declares_safety_boundary(client, learner):
    labs = client.get(f"{API}/labs", headers=learner["headers"]).json()
    assert len(labs) == 10
    for lab in labs:
        full = client.get(f"{API}/labs/{lab['slug']}", headers=learner["headers"]).json()
        for field in ("objective", "authorised_environment", "expected_result", "safety_restrictions"):
            assert full[field]


def test_evidence_hashes_match_files_and_content_served(client, learner):
    h = learner["headers"]
    items = client.get(f"{API}/forensics/evidence", headers=h).json()
    assert len(items) == 5
    for item in items:
        data = (EVIDENCE_DIR / item["file_name"]).read_bytes()
        assert item["sha256"] == hashlib.sha256(data).hexdigest() and item["size_bytes"] == len(data)
    sync = next(i for i in items if i["file_name"] == "sync.ps1.txt")
    content = client.get(f"{API}/forensics/evidence/{sync['id']}/content", headers=h).text
    assert hashlib.sha256(content.encode()).hexdigest() == sync["sha256"]
    detail = client.get(f"{API}/forensics/evidence/{sync['id']}", headers=h).json()
    assert [c["action"] for c in detail["chain_of_custody"]] == ["collected", "hashed", "transferred", "stored"]


def test_hash_demo_and_subnet_calculator(client, learner):
    h = learner["headers"]
    assert client.post(f"{API}/forensics/hash", json={"text": "abc"}, headers=h).json()["sha256"] == \
           hashlib.sha256(b"abc").hexdigest()
    s = client.post(f"{API}/network/subnet-calculator", json={"cidr": "172.16.8.130/26"}, headers=h).json()
    assert (s["network_address"], s["broadcast_address"], s["usable_hosts"]) == ("172.16.8.128", "172.16.8.191", 62)
    assert client.post(f"{API}/network/subnet-calculator", json={"cidr": "nonsense"}, headers=h).status_code == 422


def test_forensic_timeline_and_network_data(client, learner):
    h = learner["headers"]
    t = client.get(f"{API}/forensics/timeline", params={"username": "m.okafor"}, headers=h).json()
    times = [e["event_time"] for e in t["items"]]
    assert t["count"] >= 10 and times == sorted(times)
    assert len(client.get(f"{API}/network/topology", headers=h).json()["nodes"]) == 15
    traffic = client.get(f"{API}/network/traffic", headers=h).json()
    assert sum(1 for e in traffic["items"] if e["dst_port"] == 4444) == 5


# ---------------------------------------------------------------- Incident response workflow
def test_incident_workflow_enforces_order_and_documentation(client, learner):
    h = learner["headers"]
    inc = next(i for i in client.get(f"{API}/incidents", headers=h).json()["items"] if i["reference"] == "INC-SIM-001")
    url = f"{API}/incidents/{inc['id']}"

    def move(stage, note=None):
        return client.post(f"{url}/transition", json={"to_stage": stage, "note": note}, headers=h)

    assert move("investigation").status_code == 400          # cannot skip triage
    for stage in ("triage", "investigation", "evidence_collection", "impact_assessment"):
        assert move(stage, f"moved to {stage}").status_code == 200
    r = move("containment_planning")
    assert r.status_code == 400 and "impact assessment" in r.json()["detail"]
    client.patch(url, json={"impact_assessment": "Domain admin rights obtained; DC and ws-fin-02 affected."}, headers=h)
    assert move("containment_planning").status_code == 200
    assert move("impact_assessment").status_code == 200       # one step back for rework is allowed
    assert move("containment_planning").status_code == 200
    client.patch(url, json={"containment_plan": "Disable m.okafor, isolate ws-fin-02, block 203.0.113.0/24.",
                            "recovery_plan": "Reset credentials, remove task and service, restore audit policy.",
                            "resolution_summary": "Attacker access removed; systems verified clean."}, headers=h)
    for stage in ("recovery_planning", "resolution"):
        assert move(stage).status_code == 200
    detail = client.get(url, headers=h).json()
    assert detail["status"] == "resolved" and detail["resolved_at"] is not None
    client.patch(url, json={"lessons_learned": "Enforce MFA on VPN; alert on self-added admin rights."}, headers=h)
    assert move("lessons_learned").status_code == 200

    detail = client.get(url, headers=h).json()
    stage_changes = [u for u in detail["updates"] if u["to_stage"]]
    assert len(stage_changes) == 10 and stage_changes[0]["note"] == "moved to triage"
    report = client.get(f"{url}/report", headers=h).text
    assert "SIMULATED EXERCISE" in report and "Enforce MFA" in report and "## Timeline of updates" in report
    earned = {a["code"] for a in client.get(f"{API}/me/achievements", headers=h).json() if a["earned"]}
    assert "incident-closer" in earned


def test_incident_comments_and_creation(client, learner):
    h = learner["headers"]
    created = client.post(f"{API}/incidents", json={"title": "Escalated from triage", "category": "malware",
                                                    "severity": "high", "summary": "From CSA-DET-010"}, headers=h)
    assert created.status_code == 201 and created.json()["stage"] == "alert_received"
    c = client.post(f"{API}/incidents/{created.json()['id']}/comments", json={"note": "Opened case"}, headers=h)
    assert c.status_code == 201 and c.json()["to_stage"] is None
