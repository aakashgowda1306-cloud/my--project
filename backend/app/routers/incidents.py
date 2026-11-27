"""Incident Response Centre: the 9-stage workflow, updates and reports."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..deps import get_db, one, one_or_404, rows

router = APIRouter(prefix="/incidents", tags=["incident-response"])

STAGES = ["alert_received", "triage", "investigation", "evidence_collection", "impact_assessment",
          "containment_planning", "recovery_planning", "resolution", "lessons_learned"]
STAGE_LABELS = {s: s.replace("_", " ").capitalize() for s in STAGES}
Stage = Literal["alert_received", "triage", "investigation", "evidence_collection", "impact_assessment",
                "containment_planning", "recovery_planning", "resolution", "lessons_learned"]
Severity = Literal["low", "medium", "high", "critical"]
Category = Literal["account_compromise", "malware", "phishing", "data_exposure", "unauthorised_access",
                   "policy_violation", "denial_of_service", "other"]
TEXT = Field(default=None, max_length=5000)


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category: Category
    severity: Severity
    summary: str = Field(min_length=3, max_length=5000)
    related_alert_id: int | None = None


class IncidentUpdate(BaseModel):
    severity: Severity | None = None
    category: Category | None = None
    assigned_analyst: str | None = Field(default=None, min_length=1, max_length=80)
    impact_assessment: str | None = TEXT
    containment_plan: str | None = TEXT
    recovery_plan: str | None = TEXT
    resolution_summary: str | None = TEXT
    lessons_learned: str | None = TEXT
    recommendations: str | None = TEXT


class Transition(BaseModel):
    to_stage: Stage
    note: str | None = Field(default=None, max_length=5000)


class Comment(BaseModel):
    note: str = Field(min_length=1, max_length=5000)


@router.get("")
def list_incidents(conn: Connection = Depends(get_db)) -> dict:
    conn.execute(text("select public.ensure_lab_workspace()"))
    items = rows(conn, """select id, reference, title, category, severity, stage, status, assigned_analyst,
                                 detected_at, resolved_at, updated_at
                          from public.incidents where owner_id = auth.uid() order by detected_at desc""")
    return {"stages": [{"key": s, "label": STAGE_LABELS[s], "position": i + 1} for i, s in enumerate(STAGES)],
            "items": items, "simulated": True}


@router.post("", status_code=201)
def create_incident(body: IncidentCreate, conn: Connection = Depends(get_db)) -> dict:
    count = conn.execute(text("select count(*) from public.incidents where owner_id = auth.uid()")).scalar_one()
    return one(conn, """insert into public.incidents (owner_id, reference, title, category, severity, summary,
                            related_alert_id, assigned_analyst)
                        values (auth.uid(), :ref, :title, :category, :severity, :summary, :alert, 'You')
                        returning *""",
               {"ref": f"INC-MY-{count + 1:03d}", "title": body.title, "category": body.category,
                "severity": body.severity, "summary": body.summary, "alert": body.related_alert_id})


@router.get("/{incident_id}")
def get_incident(incident_id: UUID, conn: Connection = Depends(get_db)) -> dict:
    inc = one_or_404(conn, "select * from public.incidents where id = :id and owner_id = auth.uid()",
                     {"id": incident_id}, what="Incident")
    inc["updates"] = rows(conn, "select * from public.incident_updates where incident_id = :id order by created_at, id",
                          {"id": incident_id})
    pos = STAGES.index(inc["stage"])
    inc["workflow"] = {"position": pos + 1, "total": len(STAGES),
                       "next_stage": STAGES[pos + 1] if pos + 1 < len(STAGES) else None,
                       "previous_stage": STAGES[pos - 1] if pos > 0 else None}
    return inc


@router.patch("/{incident_id}")
def update_incident(incident_id: UUID, body: IncidentUpdate, conn: Connection = Depends(get_db)) -> dict:
    changes = body.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(400, "Nothing to update")
    sets = ", ".join(f"{k} = :{k}" for k in changes)  # keys are fixed model fields
    updated = one(conn, f"update public.incidents set {sets} where id = :id and owner_id = auth.uid() returning *",
                  {**changes, "id": incident_id})
    if updated is None:
        raise HTTPException(404, "Incident not found")
    return updated


@router.post("/{incident_id}/transition")
def transition(incident_id: UUID, body: Transition, conn: Connection = Depends(get_db)) -> dict:
    one_or_404(conn, "select id from public.incidents where id = :id and owner_id = auth.uid()",
               {"id": incident_id}, what="Incident")
    # The database trigger enforces the rules (one step at a time, required documentation).
    row = one(conn, "select * from public.transition_incident(:id, :stage, :note)",
              {"id": incident_id, "stage": body.to_stage, "note": body.note})
    conn.execute(text("insert into public.study_sessions (user_id, activity, ref_id) values (auth.uid(), 'incident', :id)"),
                 {"id": incident_id})
    return row


@router.post("/{incident_id}/comments", status_code=201)
def comment(incident_id: UUID, body: Comment, conn: Connection = Depends(get_db)) -> dict:
    one_or_404(conn, "select id from public.incidents where id = :id and owner_id = auth.uid()",
               {"id": incident_id}, what="Incident")
    return one(conn, """insert into public.incident_updates (incident_id, user_id, note)
                        values (:id, auth.uid(), :note) returning *""", {"id": incident_id, "note": body.note})


@router.get("/{incident_id}/report", response_class=PlainTextResponse)
def report(incident_id: UUID, conn: Connection = Depends(get_db)) -> str:
    inc = get_incident(incident_id, conn)

    def section(title: str, body: str | None) -> str:
        return f"## {title}\n\n{body.strip() if body else '_Not yet recorded._'}\n"

    history = "\n".join(
        f"| {u['created_at']:%Y-%m-%d %H:%M} UTC | {STAGE_LABELS.get(u['from_stage'], '—') if u['from_stage'] else '—'} "
        f"| {STAGE_LABELS.get(u['to_stage'], 'Comment') if u['to_stage'] else 'Comment'} | {(u['note'] or '').replace('|', '/')} |"
        for u in inc["updates"]) or "| — | — | — | No updates yet |"
    return "\n".join([
        f"# Post-incident report — {inc['reference']}: {inc['title']}",
        "",
        "> SIMULATED EXERCISE — Cybersec Academy training scenario. Fictional organisation and data.",
        "",
        "| Field | Value |", "|---|---|",
        f"| Category | {inc['category'].replace('_', ' ')} |",
        f"| Severity | {inc['severity']} |",
        f"| Status | {inc['status']} (stage: {STAGE_LABELS[inc['stage']]}) |",
        f"| Assigned analyst | {inc['assigned_analyst']} |",
        f"| Detected | {inc['detected_at']:%Y-%m-%d %H:%M} UTC |",
        f"| Resolved | {inc['resolved_at']:%Y-%m-%d %H:%M} UTC |" if inc["resolved_at"] else "| Resolved | — |",
        "",
        section("Summary", inc["summary"]),
        section("Impact assessment", inc["impact_assessment"]),
        section("Containment plan", inc["containment_plan"]),
        section("Recovery plan", inc["recovery_plan"]),
        section("Resolution", inc["resolution_summary"]),
        section("Lessons learned", inc["lessons_learned"]),
        section("Recommendations", inc["recommendations"]),
        "## Timeline of updates\n", "| Time | From | To | Note |", "|---|---|---|---|", history, "",
    ])
