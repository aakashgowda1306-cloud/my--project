"""SOC Operations Centre, SIEM Investigation Lab and alert investigations.

Every number on the SOC dashboard is computed from the database at request
time — nothing is hard-coded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..deps import get_db, one, one_or_404, rows
from ..detections.rules import RULES_BY_ID

router = APIRouter(tags=["soc", "siem"])

EVENT_COLUMNS = """id, event_time, source, host, username, host(src_ip) as src_ip, host(dst_ip) as dst_ip, dst_port,
    protocol, event_code, category, action, outcome, severity, process_name, command_line, message, raw,
    dataset, is_synthetic"""
Severity = Literal["info", "low", "medium", "high", "critical"]
InvestigationStatus = Literal["new", "in_progress", "escalated", "closed_true_positive",
                              "closed_false_positive", "closed_benign"]


# ---------------------------------------------------------------------------
# SOC overview
# ---------------------------------------------------------------------------
@router.get("/soc/overview")
def soc_overview(conn: Connection = Depends(get_db)) -> dict:
    events_by_sev = {r["severity"]: r["count"] for r in rows(conn, """
        select severity, count(*)::int as count from public.security_events group by severity""")}
    alerts_by_sev = {r["severity"]: r["count"] for r in rows(conn, """
        select severity, count(*)::int as count from public.generated_alerts group by severity""")}
    # "Open" means the learner has not closed an investigation for the alert yet.
    triage = rows(conn, """
        select coalesce(i.status, 'new') as status, count(*)::int as count
        from public.generated_alerts a
        left join public.investigations i on i.alert_id = a.id and i.user_id = auth.uid()
        group by 1""")
    triage_map = {r["status"]: r["count"] for r in triage}
    closed = sum(v for k, v in triage_map.items() if k.startswith("closed_"))
    incidents = {r["status"]: r["count"] for r in rows(conn, """
        select status, count(*)::int as count from public.incidents where owner_id = auth.uid() group by status""")}
    return {
        "dataset": "synthetic-v1",
        "simulated": True,
        "events": {"total": sum(events_by_sev.values()), "by_severity": events_by_sev,
                   "by_source": {r["source"]: r["count"] for r in rows(conn, """
                       select source, count(*)::int as count from public.security_events group by source""")}},
        "alerts": {"total": sum(alerts_by_sev.values()), "by_severity": alerts_by_sev,
                   "open": sum(alerts_by_sev.values()) - closed, "resolved": closed, "by_status": triage_map,
                   "by_rule": rows(conn, """
                       select r.id as rule_id, r.name, r.mitre_technique_id, count(a.id)::int as count
                       from public.detection_rules r left join public.generated_alerts a on a.rule_id = r.id
                       group by r.id, r.name, r.mitre_technique_id order by r.id""")},
        "incidents": {"open": incidents.get("open", 0), "resolved": incidents.get("resolved", 0)},
        "timeline": rows(conn, """
            select date_trunc('hour', event_time) as bucket, severity, count(*)::int as count
            from public.security_events group by 1, 2 order by 1"""),
        "recent_alerts": rows(conn, """
            select a.id, a.rule_id, a.title, a.severity, a.first_seen, a.event_count,
                   coalesce(i.status, 'new') as triage_status
            from public.generated_alerts a
            left join public.investigations i on i.alert_id = a.id and i.user_id = auth.uid()
            order by a.first_seen desc limit 8"""),
        "top_hosts": rows(conn, """
            select host, count(*)::int as events,
                   count(*) filter (where severity in ('high', 'critical'))::int as high_or_critical
            from public.security_events group by host order by high_or_critical desc, events desc limit 6"""),
    }


# ---------------------------------------------------------------------------
# SIEM event explorer
# ---------------------------------------------------------------------------
@router.get("/siem/events")
def search_events(
    conn: Connection = Depends(get_db),
    q: str | None = Query(default=None, max_length=100, description="Free-text search in message/host/user/IP"),
    source: Literal["windows", "linux", "application", "authentication", "network"] | None = None,
    severity: list[Severity] | None = Query(default=None),
    outcome: Literal["success", "failure", "unknown"] | None = None,
    host: str | None = Query(default=None, max_length=100),
    username: str | None = Query(default=None, max_length=100),
    event_code: str | None = Query(default=None, max_length=40),
    start: datetime | None = None,
    end: datetime | None = None,
    sort: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
) -> dict:
    # Every filter is a bound parameter (:name) — user input is never pasted into SQL text.
    where, params = ["true"], {}
    if q:
        where.append("(message ilike :q or host ilike :q or username ilike :q or host(src_ip) like :q_raw "
                     "or host(dst_ip) like :q_raw or event_code ilike :q)")
        params["q"] = f"%{q}%"
        params["q_raw"] = f"%{q}%"
    for name, value in (("source", source), ("outcome", outcome), ("event_code", event_code),
                        ("username", username)):
        if value:
            where.append(f"{name} = :{name}")
            params[name] = value
    if host:
        where.append("host ilike :host")
        params["host"] = f"%{host}%"
    if severity:
        where.append("severity = any(:severity)")
        params["severity"] = severity
    if start:
        where.append("event_time >= :start")
        params["start"] = start
    if end:
        where.append("event_time <= :end")
        params["end"] = end
    clause = " and ".join(where)
    total = conn.execute(text(f"select count(*) from public.security_events where {clause}"), params).scalar_one()
    items = rows(conn, f"""select {EVENT_COLUMNS} from public.security_events where {clause}
                           order by event_time {sort}, id {sort} limit :limit offset :offset""",
                 {**params, "limit": page_size, "offset": (page - 1) * page_size})
    return {"total": total, "page": page, "page_size": page_size, "items": items, "simulated": True}


@router.get("/siem/events/{event_id}")
def get_event(event_id: int, conn: Connection = Depends(get_db)) -> dict:
    return one_or_404(conn, f"select {EVENT_COLUMNS} from public.security_events where id = :id",
                      {"id": event_id}, what="Event")


@router.get("/siem/rules")
def list_rules(conn: Connection = Depends(get_db)) -> list[dict]:
    return rows(conn, """select r.*, (select count(*)::int from public.generated_alerts a where a.rule_id = r.id)
                         as alert_count from public.detection_rules r order by r.id""")


@router.get("/siem/rules/{rule_id}")
def get_rule(rule_id: str, conn: Connection = Depends(get_db)) -> dict:
    return one_or_404(conn, "select * from public.detection_rules where id = :id", {"id": rule_id}, what="Rule")


@router.post("/siem/rules/{rule_id}/run")
def run_rule(rule_id: str, conn: Connection = Depends(get_db)) -> dict:
    """Run a detection rule live over the dataset (read-only — nothing is stored)."""
    rule = RULES_BY_ID.get(rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    events = rows(conn, f"select {EVENT_COLUMNS} from public.security_events order by event_time, id")
    matches = rule.run(events)
    return {"rule_id": rule_id, "events_scanned": len(events), "match_count": len(matches),
            "matches": [{"title": m.title, "severity": m.severity, "entity": m.entity, "summary": m.summary,
                         "first_seen": m.first_seen, "last_seen": m.last_seen,
                         "evidence_event_ids": m.evidence_event_ids} for m in matches]}


@router.get("/siem/alerts")
def list_alerts(
    conn: Connection = Depends(get_db),
    severity: list[Literal["low", "medium", "high", "critical"]] | None = Query(default=None),
    rule_id: str | None = Query(default=None, max_length=20),
    status: InvestigationStatus | None = None,
) -> list[dict]:
    where, params = ["true"], {}
    if severity:
        where.append("a.severity = any(:sev)")
        params["sev"] = severity
    if rule_id:
        where.append("a.rule_id = :rule")
        params["rule"] = rule_id
    if status:
        where.append("coalesce(i.status, 'new') = :status")
        params["status"] = status
    return rows(conn, f"""
        select a.id, a.rule_id, r.name as rule_name, r.mitre_technique_id, a.title, a.severity, a.entity,
               a.first_seen, a.last_seen, a.event_count, a.summary,
               coalesce(i.status, 'new') as triage_status, i.id as investigation_id
        from public.generated_alerts a join public.detection_rules r on r.id = a.rule_id
        left join public.investigations i on i.alert_id = a.id and i.user_id = auth.uid()
        where {' and '.join(where)} order by a.first_seen desc""", params)


@router.get("/siem/alerts/{alert_id}")
def get_alert(alert_id: int, conn: Connection = Depends(get_db)) -> dict:
    alert = one_or_404(conn, "select * from public.generated_alerts where id = :id", {"id": alert_id}, what="Alert")
    alert["rule"] = one(conn, "select * from public.detection_rules where id = :r", {"r": alert["rule_id"]})
    alert["evidence"] = rows(conn, f"select {EVENT_COLUMNS} from public.security_events where id = any(:ids) "
                                   "order by event_time", {"ids": alert["evidence_event_ids"]})
    alert["investigation"] = one(conn, "select * from public.investigations where alert_id = :id", {"id": alert_id})
    return alert


# ---------------------------------------------------------------------------
# Investigations (private to each learner through RLS)
# ---------------------------------------------------------------------------
class InvestigationCreate(BaseModel):
    alert_id: int | None = None
    case_ref: str | None = Field(default=None, max_length=40)
    title: str | None = Field(default=None, min_length=3, max_length=160)


class InvestigationUpdate(BaseModel):
    status: InvestigationStatus | None = None
    summary: str | None = Field(default=None, max_length=5000)


class NoteCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    evidence_id: UUID | None = None


@router.get("/investigations")
def list_investigations(conn: Connection = Depends(get_db)) -> list[dict]:
    return rows(conn, """
        select i.*, (select count(*)::int from public.investigation_notes n where n.investigation_id = i.id) as note_count
        from public.investigations i order by i.updated_at desc""")


@router.post("/investigations", status_code=201)
def create_investigation(body: InvestigationCreate, conn: Connection = Depends(get_db)) -> dict:
    if body.alert_id is not None:
        alert = one_or_404(conn, "select id, title from public.generated_alerts where id = :id",
                           {"id": body.alert_id}, what="Alert")
        existing = one(conn, "select * from public.investigations where alert_id = :id", {"id": body.alert_id})
        if existing:
            return existing
        return one(conn, """insert into public.investigations (user_id, kind, alert_id, title, status)
                            values (auth.uid(), 'alert_triage', :a, :t, 'in_progress') returning *""",
                   {"a": alert["id"], "t": body.title or f"Triage: {alert['title']}"[:160]})
    if not body.case_ref:
        raise HTTPException(422, "Provide alert_id (alert triage) or case_ref (forensic case)")
    return one(conn, """insert into public.investigations (user_id, kind, case_ref, title, status)
                        values (auth.uid(), 'forensic_case', :c, :t, 'in_progress') returning *""",
               {"c": body.case_ref, "t": body.title or f"Forensic case {body.case_ref}"})


@router.get("/investigations/{inv_id}")
def get_investigation(inv_id: UUID, conn: Connection = Depends(get_db)) -> dict:
    inv = one_or_404(conn, "select * from public.investigations where id = :id", {"id": inv_id}, what="Investigation")
    inv["notes"] = rows(conn, "select * from public.investigation_notes where investigation_id = :id "
                              "order by created_at", {"id": inv_id})
    return inv


@router.patch("/investigations/{inv_id}")
def update_investigation(inv_id: UUID, body: InvestigationUpdate, conn: Connection = Depends(get_db)) -> dict:
    changes = body.model_dump(exclude_none=True)
    if changes.get("status", "").startswith("closed_") and not (changes.get("summary") or one(
            conn, "select 1 from public.investigations where id = :id and coalesce(summary, '') <> ''", {"id": inv_id})):
        raise HTTPException(400, "Write an investigation summary before closing (it justifies your verdict)")
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        updated = one(conn, f"update public.investigations set {sets} where id = :id returning *", {**changes, "id": inv_id})
        if updated is None:
            raise HTTPException(404, "Investigation not found")
        if updated["status"].startswith("closed_"):
            conn.execute(text("insert into public.study_sessions (user_id, activity, ref_id) "
                              "values (auth.uid(), 'investigation', :id)"), {"id": inv_id})
        return updated
    return one_or_404(conn, "select * from public.investigations where id = :id", {"id": inv_id}, what="Investigation")


@router.post("/investigations/{inv_id}/notes", status_code=201)
def add_note(inv_id: UUID, body: NoteCreate, conn: Connection = Depends(get_db)) -> dict:
    one_or_404(conn, "select id from public.investigations where id = :id", {"id": inv_id}, what="Investigation")
    return one(conn, """insert into public.investigation_notes (investigation_id, user_id, evidence_id, body)
                        values (:i, auth.uid(), :e, :b) returning *""",
               {"i": inv_id, "e": body.evidence_id, "b": body.body})
