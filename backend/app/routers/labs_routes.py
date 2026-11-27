"""Lab exercises (all departments), Digital Forensics Lab and Network Security Lab."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..deps import get_db, one_or_404, rows
from ..labdata.labs import EVIDENCE_DIR, NETWORK_TOPOLOGY, PACKET_WALKTHROUGH
from .soc_siem import EVENT_COLUMNS

router = APIRouter(tags=["labs"])
RFC1918 = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")


class LabSubmission(BaseModel):
    answers: dict[str, str] = Field(min_length=1, max_length=10)


# ---------------------------------------------------------------------------
# Lab exercises
# ---------------------------------------------------------------------------
@router.get("/labs")
def list_labs(department: str | None = Query(default=None, max_length=40), conn: Connection = Depends(get_db)):
    return rows(conn, """
        select e.id, e.slug, e.department, e.title, e.difficulty, e.objective,
               exists (select 1 from public.lab_submissions s where s.lab_exercise_id = e.id
                       and s.user_id = auth.uid() and s.is_correct) as solved
        from public.lab_exercises e where (cast(:d as text) is null or e.department = :d)
        order by e.department, e.difficulty, e.title""", {"d": department})


@router.get("/labs/{slug}")
def get_lab(slug: str, conn: Connection = Depends(get_db)) -> dict:
    lab = one_or_404(conn, "select * from public.lab_exercises where slug = :s", {"s": slug}, what="Lab exercise")
    lab["submissions"] = rows(conn, """select id, score, max_score, is_correct, feedback, created_at
        from public.lab_submissions where lab_exercise_id = :id order by created_at desc limit 5""", {"id": lab["id"]})
    return lab


@router.post("/labs/{slug}/submit")
def submit_lab(slug: str, body: LabSubmission, conn: Connection = Depends(get_db)) -> dict:
    lab = one_or_404(conn, "select id from public.lab_exercises where slug = :s", {"s": slug}, what="Lab exercise")
    return conn.execute(text("select public.submit_lab_answer(:id, cast(:a as jsonb))"),
                        {"id": lab["id"], "a": json.dumps(body.answers)}).scalar_one()


# ---------------------------------------------------------------------------
# Digital forensics
# ---------------------------------------------------------------------------
@router.get("/forensics/evidence")
def list_evidence(conn: Connection = Depends(get_db)) -> list[dict]:
    return rows(conn, """select id, case_ref, label, evidence_type, file_name, size_bytes, sha256, md5, source_host,
                                acquired_at, acquired_by, is_synthetic, owner_id is null as shared
                         from public.evidence_items order by case_ref, label""")


@router.get("/forensics/evidence/{evidence_id}")
def get_evidence(evidence_id: str, conn: Connection = Depends(get_db)) -> dict:
    item = one_or_404(conn, "select * from public.evidence_items where id = cast(:id as uuid)",
                      {"id": evidence_id}, what="Evidence")
    item["chain_of_custody"] = rows(conn, """select action, actor, location, notes, occurred_at
        from public.evidence_custody_events where evidence_id = :id order by occurred_at, id""", {"id": item["id"]})
    return item


@router.get("/forensics/evidence/{evidence_id}/content", response_class=PlainTextResponse)
def evidence_content(evidence_id: str, conn: Connection = Depends(get_db)) -> str:
    item = one_or_404(conn, "select file_name, storage_path, owner_id from public.evidence_items "
                            "where id = cast(:id as uuid)", {"id": evidence_id}, what="Evidence")
    if item["owner_id"] is not None:
        raise HTTPException(404, "Content is only stored for shared lab evidence")
    # Only files from the fixed evidence folder can be served; the name comes from the database row,
    # and we still verify it resolves inside EVIDENCE_DIR (blocks path traversal).
    path = (EVIDENCE_DIR / item["file_name"]).resolve()
    if path.parent != EVIDENCE_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Evidence file not available")
    return path.read_text(encoding="utf-8")


class HashRequest(BaseModel):
    text: str = Field(max_length=100_000)


@router.post("/forensics/hash")
def hash_demo(body: HashRequest) -> dict:
    """Hashing demonstration. (The web app also hashes files locally in the browser.)"""
    data = body.text.encode("utf-8")
    return {"bytes": len(data), "md5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
            "sha1": hashlib.sha1(data, usedforsecurity=False).hexdigest(), "sha256": hashlib.sha256(data).hexdigest(),
            "note": "MD5 and SHA-1 are shown for comparison only; they are broken for security use. Use SHA-256."}


@router.get("/forensics/timeline")
def forensic_timeline(
    conn: Connection = Depends(get_db),
    username: str | None = Query(default=None, max_length=100),
    host: str | None = Query(default=None, max_length=100),
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    if not (username or host):
        raise HTTPException(422, "Filter by username and/or host to build a timeline")
    items = rows(conn, f"""
        select {EVENT_COLUMNS} from public.security_events
        where (cast(:u as text) is null or username = :u or raw->>'SubjectUser' = :u)
          and (cast(:h as text) is null or host ilike :hl or raw->>'origin_host' ilike :hl)
          and (cast(:s as timestamptz) is null or event_time >= :s)
          and (cast(:e as timestamptz) is null or event_time <= :e)
          and severity <> 'info'
        order by event_time""", {"u": username, "h": host, "hl": f"%{host}%" if host else None, "s": start, "e": end})
    return {"simulated": True, "count": len(items), "items": items}


# ---------------------------------------------------------------------------
# Network security lab
# ---------------------------------------------------------------------------
@router.get("/network/topology")
def topology() -> dict:
    return {**NETWORK_TOPOLOGY, "simulated": True}


@router.get("/network/packets")
def packets() -> dict:
    return {"simulated": True, "steps": PACKET_WALKTHROUGH}


@router.get("/network/traffic")
def traffic(conn: Connection = Depends(get_db)) -> dict:
    items = rows(conn, f"select {EVENT_COLUMNS} from public.security_events where source = 'network' "
                       "order by event_time")
    return {"simulated": True, "count": len(items), "items": items}


class SubnetRequest(BaseModel):
    cidr: str = Field(max_length=18, examples=["10.20.4.27/24"])


@router.post("/network/subnet-calculator")
def subnet_calculator(body: SubnetRequest) -> dict:
    """Pure arithmetic on the address you type — no network traffic is sent anywhere."""
    try:
        iface = ipaddress.IPv4Interface(body.cidr.strip())
    except ValueError:
        raise HTTPException(422, "Enter an IPv4 address with prefix, e.g. 10.20.4.27/24") from None
    net = iface.network
    usable = max(net.num_addresses - 2, 0) if net.prefixlen < 31 else net.num_addresses
    return {"address": str(iface.ip), "prefix": net.prefixlen, "netmask": str(net.netmask),
            "network_address": str(net.network_address), "broadcast_address": str(net.broadcast_address),
            "usable_hosts": usable,
            "is_rfc1918_private": any(iface.ip in ipaddress.ip_network(n) for n in RFC1918),
            "binary_mask": ".".join(f"{int(o):08b}" for o in str(net.netmask).split("."))}
