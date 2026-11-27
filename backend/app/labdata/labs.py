"""Lab exercises, fictional incidents, forensic evidence, achievements and the
network topology. All content is synthetic and stays inside the platform."""

from __future__ import annotations

import hashlib
import ipaddress
import uuid
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = REPO_ROOT / "labs" / "forensics" / "evidence"
NS = uuid.UUID("6b1f1c1e-2c3d-4b8e-9a51-0c5ac0de2026")  # namespace for stable ids


def stable_id(kind: str, key: str) -> str:
    """Same input -> same UUID, so re-seeding updates rows instead of duplicating them."""
    return str(uuid.uuid5(NS, f"{kind}:{key}"))


PLATFORM_ENV = "The synthetic {dept} dataset inside Cybersec Academy only (no external systems)."
STANDARD_SAFETY = ("Work only with the simulated data shown in the platform. Do not run commands against, "
                   "scan, or connect to any real system or address, including the documentation-range IPs.")


def _subnet_key(cidr_host: str) -> dict:
    iface = ipaddress.ip_interface(cidr_host)
    net = iface.network
    return {"network_address": str(net.network_address), "broadcast_address": str(net.broadcast_address),
            "usable_hosts": str(net.num_addresses - 2)}


def lab_exercises() -> list[dict]:
    """Each exercise: public definition + hidden answer key + explanation."""
    sync_hash = hashlib.sha256((EVIDENCE_DIR / "sync.ps1.txt").read_bytes()).hexdigest()
    items = [
        # --- SIEM ---
        dict(slug="siem-bruteforce-source", department="siem", difficulty="beginner",
             title="Identify the brute-force source",
             objective="Use search and filters to isolate repeated failed SSH logins and identify the attacker "
                       "and targeted account.",
             expected_result="The source IP address and the account name that were targeted on lnx-bastion-01.",
             instructions_md="Open the **SIEM Event Explorer**. Filter `source = linux` and `outcome = failure`. "
                             "Look at the host `lnx-bastion-01.corp.example`. Which IP made the attempts, and "
                             "for which account?",
             answer_fields=[{"name": "src_ip", "label": "Source IP"}, {"name": "username", "label": "Targeted account"}],
             expected={"src_ip": "203.0.113.45", "username": "root"},
             explanation="12 'Failed password for root' events from 203.0.113.45 arrived about 18 seconds apart — "
                         "too fast and regular for a person. 'root' is a default account attackers always try."),
        dict(slug="siem-spray-count", department="siem", difficulty="beginner",
             title="Measure a password spray",
             objective="Distinguish password spraying from brute force by counting distinct targeted accounts.",
             expected_result="The number of distinct accounts targeted by 203.0.113.80.",
             instructions_md="Search for `203.0.113.80`. Count how many **different** usernames it tried.",
             answer_fields=[{"name": "account_count", "label": "Distinct accounts"}],
             expected={"account_count": "6"},
             explanation="Six accounts, one attempt each, within about six minutes: one password tried against "
                         "many accounts is the signature of spraying."),
        dict(slug="siem-correlate-account", department="siem", difficulty="intermediate",
             title="Correlate the compromised account",
             objective="Correlate several alerts by a shared entity to reconstruct an attack chain.",
             expected_result="The single account involved in the privilege change, the scheduled task and the "
                             "service installation.",
             instructions_md="Open the alerts for CSA-DET-004, CSA-DET-006 and CSA-DET-007. Which account links them?",
             answer_fields=[{"name": "username", "label": "Account"}],
             expected={"username": "m.okafor"},
             explanation="m.okafor signs in after failures (CSA-DET-003), adds itself to Domain Admins, creates a "
                         "hidden scheduled task, installs a service and clears logs — one account, one story."),
        # --- SOC ---
        dict(slug="soc-triage-approved-change", department="soc", difficulty="beginner",
             title="Separate expected activity from a real threat",
             objective="Practise triage: use context (change tickets) to classify an alert as expected activity.",
             expected_result="The change-ticket number that makes one CSA-DET-004 alert expected activity.",
             instructions_md="Two alerts fired for privileged group changes. Read both. One has an approved change "
                             "ticket. Enter it.",
             answer_fields=[{"name": "change_ticket", "label": "Change ticket"}],
             expected={"change_ticket": "CHG-1042"},
             explanation="r.svensson was added to Backup Operators by admin.ops under approved ticket CHG-1042. "
                         "The other change has no ticket and the account added itself — that one is suspicious."),
        # --- Forensics ---
        dict(slug="forensics-verify-hash", department="forensics", difficulty="beginner",
             title="Verify an evidence hash",
             objective="Understand integrity verification: compute a SHA-256 hash and compare it with the "
                       "recorded value.",
             expected_result="The full SHA-256 hash (64 hex characters) of sync.ps1.txt.",
             instructions_md="Open evidence item **sync.ps1.txt** in the Forensics Lab and use the built-in hash "
                             "calculator (it hashes the file inside your browser). Paste the result.",
             answer_fields=[{"name": "sha256", "label": "SHA-256"}],
             expected={"sha256": sync_hash},
             explanation="If even one byte of the file changed, the hash would be completely different. Matching "
                         "hashes show the evidence is unchanged since acquisition."),
        dict(slug="forensics-log-cleared-time", department="forensics", difficulty="beginner",
             title="Timeline: when were the logs cleared?",
             objective="Reconstruct a timeline from exported event records.",
             expected_result="The UTC time (HH:MM) when the audit log on srv-dc-01 was cleared.",
             instructions_md="Open **security_events_srv-dc-01.txt** and find event 1102.",
             answer_fields=[{"name": "time_utc", "label": "Time (HH:MM, UTC)"}],
             expected={"time_utc": "03:25"},
             explanation="Event 1102 at 03:25 UTC came five minutes after the audit policy was weakened (03:20): "
                         "first stop recording, then erase what was recorded."),
        # --- Network ---
        dict(slug="network-subnet-24", department="network", difficulty="beginner",
             title="Subnetting: a /24 network",
             objective="Calculate network address, broadcast address and usable hosts for a /24.",
             expected_result="Correct network, broadcast and usable host count for 10.20.4.27/24.",
             instructions_md="Host **ws-fin-02** has address `10.20.4.27/24`. Calculate the network address, "
                             "broadcast address and number of usable host addresses.",
             answer_fields=[{"name": "network_address", "label": "Network address"},
                            {"name": "broadcast_address", "label": "Broadcast address"},
                            {"name": "usable_hosts", "label": "Usable hosts"}],
             expected=_subnet_key("10.20.4.27/24"),
             explanation="/24 leaves 8 host bits: 2^8 = 256 addresses, minus the network and broadcast addresses "
                         "= 254 usable."),
        dict(slug="network-subnet-26", department="network", difficulty="intermediate",
             title="Subnetting: a /26 network",
             objective="Apply subnetting when the boundary is not on a dot.",
             expected_result="Correct network, broadcast and usable host count for 172.16.8.130/26.",
             instructions_md="Calculate the network, broadcast and usable hosts for `172.16.8.130/26`.",
             answer_fields=[{"name": "network_address", "label": "Network address"},
                            {"name": "broadcast_address", "label": "Broadcast address"},
                            {"name": "usable_hosts", "label": "Usable hosts"}],
             expected=_subnet_key("172.16.8.130/26"),
             explanation="/26 = blocks of 64 in the last octet (0, 64, 128, 192). 130 falls in 128–191, "
                         "so 62 usable hosts."),
        dict(slug="network-beacon-hunt", department="network", difficulty="intermediate",
             title="Find the beaconing host",
             objective="Analyse pre-generated firewall records to spot regular, automated outbound traffic.",
             expected_result="The internal host and destination port involved in beaconing.",
             instructions_md="In the Network Lab traffic view, look for connections that repeat at a regular "
                             "interval to an unusual port.",
             answer_fields=[{"name": "host", "label": "Origin host"}, {"name": "dst_port", "label": "Destination port"}],
             expected={"host": "ws-fin-02.corp.example", "dst_port": "4444"},
             explanation="Five connections exactly 60 seconds apart to port 4444 — machine-like regularity on a port "
                         "with no business purpose."),
        # --- Incident response ---
        dict(slug="ir-classify-incident", department="incident_response", difficulty="beginner",
             title="Classify an incident",
             objective="Assign category and severity using the impact of what happened.",
             expected_result="Category and severity for INC-SIM-001.",
             instructions_md="Read INC-SIM-001 in the Incident Response Centre. A valid account was taken over and "
                             "used to gain Domain Admin rights. Choose its category and severity.",
             answer_fields=[{"name": "category", "label": "Category"}, {"name": "severity", "label": "Severity"}],
             expected={"category": "account_compromise", "severity": "critical"},
             explanation="An attacker holding domain-administrator rights can control every system: critical "
                         "account compromise."),
    ]
    for it in items:
        it["id"] = stable_id("lab", it["slug"])
        it["authorised_environment"] = PLATFORM_ENV.format(dept=it["department"].replace("_", " "))
        it["safety_restrictions"] = STANDARD_SAFETY
    return items


def incident_templates() -> list[dict]:
    """Fictional incidents copied into each learner's workspace."""
    base = [
        ("INC-SIM-001", "Compromised VPN account used to gain Domain Admin", "account_compromise", "critical",
         "CSA-DET-003", "2026-11-20T22:09:00Z",
         "After six failed VPN sign-ins from 203.0.113.45, m.okafor signed in successfully. Within 25 minutes the "
         "account added itself to Domain Admins, followed by persistence and log clearing."),
        ("INC-SIM-002", "Brute-force attempts against the SSH bastion", "unauthorised_access", "medium",
         "CSA-DET-001", "2026-11-17T02:14:00Z",
         "12 failed root logins from 203.0.113.45 against lnx-bastion-01 in about 3 minutes. No success observed."),
        ("INC-SIM-003", "Hidden encoded PowerShell launched from a Word document", "malware", "high",
         "CSA-DET-010", "2026-11-20T22:44:00Z",
         "WINWORD.EXE on ws-fin-02 started powershell.exe with -W Hidden -enc. Outbound port-4444 traffic began "
         "four minutes later."),
        ("INC-SIM-004", "Password spraying against the VPN portal", "unauthorised_access", "high",
         "CSA-DET-002", "2026-11-18T01:40:00Z",
         "203.0.113.80 attempted one sign-in each against six accounts in six minutes."),
    ]
    return [
        dict(id=stable_id("incident", ref), reference=ref, title=title, category=cat, severity=sev,
             related_rule=rule, detected_at=datetime.fromisoformat(ts.replace("Z", "+00:00")), summary=summary,
             assigned_analyst="Unassigned (simulated SOC queue)")
        for ref, title, cat, sev, rule, ts, summary in base
    ]


def evidence_items() -> list[dict]:
    spec = [
        ("auth_excerpt_lnx-bastion-01.log", "log_file", "lnx-bastion-01.corp.example", "CASE-SIM-002",
         "SSH authentication log excerpt from the bastion host."),
        ("vpn_gateway_export.csv", "log_file", "vpn-gw-01.corp.example", "CASE-SIM-001",
         "VPN portal sign-in export for m.okafor."),
        ("security_events_srv-dc-01.txt", "log_file", "srv-dc-01.corp.example", "CASE-SIM-001",
         "Summary export of Windows Security events from the domain controller."),
        ("task_OneDriveSyncHelper.xml", "configuration", "ws-fin-02.corp.example", "CASE-SIM-001",
         "Exported scheduled-task definition found on ws-fin-02."),
        ("sync.ps1.txt", "document", "ws-fin-02.corp.example", "CASE-SIM-001",
         "Harmless stand-in for the script referenced by the scheduled task."),
    ]
    out = []
    for name, etype, host, case, desc in spec:
        data = (EVIDENCE_DIR / name).read_bytes()
        out.append(dict(
            id=stable_id("evidence", name), case_ref=case, label=name, evidence_type=etype, description=desc,
            file_name=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
            md5=hashlib.md5(data, usedforsecurity=False).hexdigest(), source_host=host,
            acquired_at=datetime(2026, 11, 21, 9, 0, tzinfo=UTC), acquired_by="T. Ncube (simulated IR analyst)",
            storage_path=f"labs/forensics/evidence/{name}",
            custody=[
                ("collected", "T. Ncube (simulated)", f"{host} (live response)", datetime(2026, 11, 21, 9, 0, tzinfo=UTC)),
                ("hashed", "T. Ncube (simulated)", "IR workstation ir-ws-01", datetime(2026, 11, 21, 9, 5, tzinfo=UTC)),
                ("transferred", "T. Ncube → P. Duarte (simulated)", "Evidence locker EL-3",
                 datetime(2026, 11, 21, 10, 30, tzinfo=UTC)),
                ("stored", "P. Duarte (simulated)", "Evidence locker EL-3", datetime(2026, 11, 21, 10, 35, tzinfo=UTC)),
            ]))
    return out


ACHIEVEMENTS = [
    ("first-lesson", "First Steps", "Complete your first lesson.", "footprints", "lessons_completed", 1),
    ("five-lessons", "Steady Learner", "Complete five lessons.", "book-open", "lessons_completed", 5),
    ("first-quiz", "Knowledge Check", "Pass your first quiz.", "check-circle", "quizzes_passed", 1),
    ("perfect-score", "Flawless", "Score 100% on a quiz.", "star", "perfect_quizzes", 1),
    ("first-lab", "Hands-On", "Solve your first lab exercise.", "flask-conical", "labs_solved", 1),
    ("lab-specialist", "Lab Specialist", "Solve five different lab exercises.", "award", "labs_solved", 5),
    ("first-triage", "Triage Analyst", "Close your first alert investigation.", "shield-check", "investigations_closed", 1),
    ("incident-closer", "Incident Closer", "Take an incident all the way to lessons learned.", "flag",
     "incidents_resolved", 1),
    ("streak-3", "On a Roll", "Learn on 3 consecutive days.", "flame", "streak_days", 3),
    ("streak-7", "Week Warrior", "Learn on 7 consecutive days.", "calendar-check", "streak_days", 7),
]


def achievements() -> list[dict]:
    return [dict(id=stable_id("achievement", code), code=code, title=t, description=d, icon=i,
                 criteria={"metric": m, "threshold": n}) for code, t, d, i, m, n in ACHIEVEMENTS]


NETWORK_TOPOLOGY = {
    "key": "corp-example-v1",
    "description": "Fictional ExampleCorp network used by every lab. Not a real network.",
    "nodes": [
        {"id": "internet", "label": "Internet (simulated)", "type": "cloud", "zone": "external"},
        {"id": "fw-edge-01", "label": "fw-edge-01", "type": "firewall", "zone": "edge", "ip": "10.0.0.1"},
        {"id": "vpn-gw-01", "label": "vpn-gw-01", "type": "vpn", "zone": "dmz", "ip": "10.0.10.5"},
        {"id": "lnx-web-01", "label": "lnx-web-01", "type": "server", "zone": "dmz", "ip": "10.10.1.11"},
        {"id": "lnx-bastion-01", "label": "lnx-bastion-01", "type": "server", "zone": "dmz", "ip": "10.10.1.5"},
        {"id": "core-sw-01", "label": "core-sw-01", "type": "switch", "zone": "internal", "ip": "10.10.0.2"},
        {"id": "srv-dc-01", "label": "srv-dc-01", "type": "server", "zone": "servers", "ip": "10.10.0.10"},
        {"id": "srv-file-01", "label": "srv-file-01", "type": "server", "zone": "servers", "ip": "10.10.0.20"},
        {"id": "srv-app-02", "label": "srv-app-02", "type": "server", "zone": "servers", "ip": "10.10.0.32"},
        {"id": "lnx-db-01", "label": "lnx-db-01", "type": "database", "zone": "servers", "ip": "10.10.1.12"},
        {"id": "ws-fin-01", "label": "ws-fin-01", "type": "workstation", "zone": "users", "ip": "10.20.4.20"},
        {"id": "ws-fin-02", "label": "ws-fin-02", "type": "workstation", "zone": "users", "ip": "10.20.4.27"},
        {"id": "ws-hr-01", "label": "ws-hr-01", "type": "workstation", "zone": "users", "ip": "10.20.4.34"},
        {"id": "ws-eng-03", "label": "ws-eng-03", "type": "workstation", "zone": "users", "ip": "10.20.4.41"},
        {"id": "ws-eng-04", "label": "ws-eng-04", "type": "workstation", "zone": "users", "ip": "10.20.4.48"},
    ],
    "links": [
        ["internet", "fw-edge-01"], ["fw-edge-01", "vpn-gw-01"], ["fw-edge-01", "lnx-web-01"],
        ["fw-edge-01", "lnx-bastion-01"], ["fw-edge-01", "core-sw-01"], ["core-sw-01", "srv-dc-01"],
        ["core-sw-01", "srv-file-01"], ["core-sw-01", "srv-app-02"], ["core-sw-01", "lnx-db-01"],
        ["core-sw-01", "ws-fin-01"], ["core-sw-01", "ws-fin-02"], ["core-sw-01", "ws-hr-01"],
        ["core-sw-01", "ws-eng-03"], ["core-sw-01", "ws-eng-04"],
    ],
}

# A TCP three-way handshake + HTTP request, as packets, for the packet-structure demo.
PACKET_WALKTHROUGH = [
    {"step": 1, "title": "SYN", "src": "10.20.4.27:51514", "dst": "10.10.1.11:80", "flags": ["SYN"], "seq": 1000,
     "ack": None, "explain": "The client asks to open a connection and picks a starting sequence number."},
    {"step": 2, "title": "SYN-ACK", "src": "10.10.1.11:80", "dst": "10.20.4.27:51514", "flags": ["SYN", "ACK"],
     "seq": 5000, "ack": 1001, "explain": "The server agrees, picks its own sequence number, and acknowledges 1000+1."},
    {"step": 3, "title": "ACK", "src": "10.20.4.27:51514", "dst": "10.10.1.11:80", "flags": ["ACK"], "seq": 1001,
     "ack": 5001, "explain": "The client confirms. The connection is now established."},
    {"step": 4, "title": "HTTP GET", "src": "10.20.4.27:51514", "dst": "10.10.1.11:80", "flags": ["PSH", "ACK"],
     "seq": 1001, "ack": 5001, "payload": "GET /api/products HTTP/1.1\r\nHost: lnx-web-01.corp.example\r\n\r\n",
     "explain": "Plain HTTP: anyone on the path can read this text. HTTPS would encrypt it inside TLS."},
]
