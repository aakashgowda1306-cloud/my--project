"""The 10 defensive detection scenarios.

Each rule answers the five analyst questions required by the platform:
  1. what was detected  2. why it matters  3. what evidence supports it
  4. what to investigate  5. the appropriate defensive response
"""

from __future__ import annotations

import ipaddress
import re
from datetime import timedelta

from .engine import AlertCandidate, Rule, bursts, group_by

# Synthetic threat-intelligence list (documentation range only).
THREAT_INTEL_NETS = [ipaddress.ip_network("203.0.113.0/24")]
HUMAN_EXCLUDED = ("svc_", "root", "www-data", "system")
USER_WRITABLE = re.compile(r"(\\users\\public\\|\\appdata\\|\\temp\\|/tmp/|/dev/shm/)", re.IGNORECASE)
ENCODED_PS = re.compile(r"\s-(e|ec|en|enc|encodedcommand)\s", re.IGNORECASE)
OFFICE_PARENTS = {"winword.exe", "excel.exe", "powerpnt.exe", "outlook.exe"}
SHELLS = {"powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe", "mshta.exe"}


def _is_failed_auth(e: dict) -> bool:
    return e["category"] == "authentication" and e["outcome"] == "failure"


def _is_human(user: str | None) -> bool:
    return bool(user) and not user.lower().startswith(HUMAN_EXCLUDED)


# ---------------------------------------------------------------------------
# Rule logic
# ---------------------------------------------------------------------------
def _brute_force(events, p):
    alerts = []
    failures = [e for e in events if _is_failed_auth(e)]
    for (user, src), group in group_by(failures, lambda e: (e["username"], e["src_ip"])).items():
        for burst in bursts(group, timedelta(minutes=p["window_minutes"])):
            if len(burst) >= p["threshold"]:
                alerts.append(AlertCandidate(
                    "CSA-DET-001", f"Repeated failed logins for '{user}' from {src}", "medium",
                    {"username": user, "src_ip": src, "host": burst[0]["host"]}, burst,
                    f"{len(burst)} failed authentications for {user} from {src} within "
                    f"{p['window_minutes']} minutes on {burst[0]['host']}."))
    return alerts


def _password_spray(events, p):
    alerts = []
    failures = [e for e in events if _is_failed_auth(e)]
    for src, group in group_by(failures, lambda e: e["src_ip"]).items():
        for burst in bursts(group, timedelta(minutes=p["window_minutes"])):
            users = sorted({e["username"] for e in burst})
            if len(users) >= p["distinct_accounts"]:
                alerts.append(AlertCandidate(
                    "CSA-DET-002", f"Password spraying from {src} against {len(users)} accounts", "high",
                    {"src_ip": src, "accounts": users}, burst,
                    f"One source ({src}) failed to sign in as {len(users)} different accounts in "
                    f"{p['window_minutes']} minutes: {', '.join(users)}."))
    return alerts


def _success_after_failures(events, p):
    alerts = []
    window = timedelta(minutes=p["window_minutes"])
    auth = [e for e in events if e["category"] == "authentication"]
    for (user, src), group in group_by(auth, lambda e: (e["username"], e["src_ip"])).items():
        for i, e in enumerate(group):
            if e["outcome"] != "success":
                continue
            prior = [f for f in group[:i] if f["outcome"] == "failure"
                     and e["event_time"] - f["event_time"] <= window]
            if len(prior) >= p["min_failures"]:
                alerts.append(AlertCandidate(
                    "CSA-DET-003", f"Successful login for '{user}' after {len(prior)} failures", "high",
                    {"username": user, "src_ip": src, "host": e["host"]}, prior + [e],
                    f"{user} signed in successfully from {src} after {len(prior)} failed attempts — "
                    "the password may have been guessed."))
    return alerts


def _privileged_group_change(events, p):
    privileged = {g.lower() for g in p["privileged_groups"]}
    return [
        AlertCandidate(
            "CSA-DET-004", f"'{e['username']}' added to privileged group {e['raw'].get('TargetGroup')}", "high",
            {"username": e["username"], "group": e["raw"].get("TargetGroup"),
             "changed_by": e["raw"].get("SubjectUser"), "host": e["host"]}, [e],
            f"{e['raw'].get('SubjectUser')} added {e['username']} to {e['raw'].get('TargetGroup')} on {e['host']}.")
        for e in events
        if e["event_code"] in p["event_codes"] and str(e["raw"].get("TargetGroup", "")).lower() in privileged
    ]


def _unusual_connection(events, p):
    def suspicious(e):
        if e["source"] != "network" or e["raw"].get("direction") != "outbound" or not e["dst_ip"]:
            return False
        ip = ipaddress.ip_address(str(e["dst_ip"]))
        return any(ip in n for n in THREAT_INTEL_NETS) or e["dst_port"] in p["suspicious_ports"]

    alerts = []
    hits = [e for e in events if suspicious(e)]
    for (origin, dst, port), group in group_by(
            hits, lambda e: (e["raw"].get("origin_host"), str(e["dst_ip"]), e["dst_port"])).items():
        for burst in bursts(group, timedelta(minutes=p["window_minutes"])):
            alerts.append(AlertCandidate(
                "CSA-DET-005", f"Outbound connections from {origin} to {dst}:{port}", "high",
                {"origin_host": origin, "dst_ip": dst, "dst_port": port}, burst,
                f"{len(burst)} outbound connection(s) from {origin} to {dst}:{port}, a non-standard port / "
                "address on the threat-intelligence list. Regular intervals can indicate beaconing."))
    return alerts


def _suspicious_service(events, p):
    return [
        AlertCandidate(
            "CSA-DET-006", f"Service '{e['raw'].get('ServiceName')}' installed from a user-writable path",
            "critical", {"host": e["host"], "service": e["raw"].get("ServiceName"), "image_path": e["command_line"]},
            [e], f"A new service on {e['host']} runs {e['command_line']}. Legitimate services are normally "
            "installed under Program Files or System32.")
        for e in events if e["event_code"] == "7045" and USER_WRITABLE.search(e["command_line"] or "")
    ]


def _suspicious_scheduled_task(events, p):
    return [
        AlertCandidate(
            "CSA-DET-007", f"Scheduled task / cron entry runs from a user-writable path on {e['host']}", "high",
            {"host": e["host"], "username": e["username"], "command": e["command_line"]}, [e],
            f"{e['username']} created a recurring job on {e['host']} that runs {e['command_line']}.")
        for e in events
        if e["event_code"] in ("4698", "4702", "CRON_EDIT") and USER_WRITABLE.search(e["command_line"] or "")
    ]


def _defence_impairment(events, p):
    labels = {"4719": "Audit policy changed", "1102": "Security audit log cleared",
              "SSHD_CONFIG_CHANGE": "SSH server configuration modified"}
    return [
        AlertCandidate(
            "CSA-DET-008", f"{labels[e['event_code']]} on {e['host']}",
            "critical" if e["event_code"] == "1102" else "high",
            {"host": e["host"], "username": e["username"], "event_code": e["event_code"]}, [e],
            f"{labels[e['event_code']]} by {e['username']} on {e['host']}: {e['message']}")
        for e in events if e["event_code"] in labels
    ]


def _off_hours_access(events, p):
    return [
        AlertCandidate(
            "CSA-DET-009", f"Off-hours sign-in by '{e['username']}' at {e['event_time']:%H:%M} UTC", "medium",
            {"username": e["username"], "src_ip": e["src_ip"], "host": e["host"]}, [e],
            f"{e['username']} signed in to {e['host']} from {e['src_ip']} at {e['event_time']:%Y-%m-%d %H:%M} UTC, "
            f"outside the usual {p['start_hour']:02d}:00–{p['end_hour']:02d}:00 working window.")
        for e in events
        if e["category"] == "authentication" and e["outcome"] == "success" and _is_human(e["username"])
        and not (p["start_hour"] <= e["event_time"].hour < p["end_hour"])
        and e["event_time"].hour < p["night_end_hour"]
    ]


def _suspicious_process(events, p):
    alerts = []
    for e in events:
        if e["event_code"] != "4688":
            continue
        cmd = e["command_line"] or ""
        parent = str(e["raw"].get("ParentProcessName", "")).lower()
        reasons = []
        if ENCODED_PS.search(f" {cmd} "):
            reasons.append("encoded PowerShell command")
        if parent in OFFICE_PARENTS and (e["process_name"] or "").lower() in SHELLS:
            reasons.append(f"Office application ({parent}) started a shell")
        if "certutil" in cmd.lower() and "-urlcache" in cmd.lower():
            reasons.append("certutil used to download a file")
        if reasons:
            alerts.append(AlertCandidate(
                "CSA-DET-010", f"Suspicious {e['process_name']} execution on {e['host']}", "high",
                {"host": e["host"], "username": e["username"], "process": e["process_name"], "indicators": reasons},
                [e], f"Indicators: {'; '.join(reasons)}. Command line: {cmd[:160]}"))
    return alerts


# ---------------------------------------------------------------------------
# Rule catalogue
# ---------------------------------------------------------------------------
RULES: list[Rule] = [
    Rule("CSA-DET-001", "Repeated failed login activity", "medium", "T1110", "Brute Force", "Credential Access",
         ["windows", "linux", "authentication"],
         "Many failed sign-ins for the same account from the same source in a short time.",
         "Attackers guess passwords automatically. A burst of failures is often the first visible sign. "
         "It can also simply be a user who forgot a password — triage decides which.",
         "The failed-authentication events: count, time span, account, source IP and target host.",
         "Is the source internal or external? Is the account real or a default name like 'root'? "
         "Did any attempt succeed afterwards (see CSA-DET-003)? Is the source on a threat-intel list?",
         "Block or rate-limit the source, enforce account lockout and MFA, disable password SSH logins, "
         "and contact the user if the source is their own device.",
         {"threshold": 5, "window_minutes": 10}, _brute_force),
    Rule("CSA-DET-002", "Password spraying (one source, many accounts)", "high", "T1110.003", "Password Spraying",
         "Credential Access", ["authentication", "windows", "linux"],
         "One source failing to sign in as many different accounts within a short window.",
         "Spraying tries one common password against many accounts to avoid per-account lockouts.",
         "Failed sign-ins from one IP, the list of distinct accounts targeted, and timing.",
         "Which accounts were targeted, and do they share a pattern (e.g. VPN users)? Any later success from "
         "that source? Is the source known?",
         "Block the source, require MFA on the targeted service, check targeted accounts for weak passwords.",
         {"distinct_accounts": 4, "window_minutes": 15}, _password_spray),
    Rule("CSA-DET-003", "Successful login after repeated failures", "high", "T1078", "Valid Accounts",
         "Initial Access", ["authentication", "windows", "linux"],
         "A successful sign-in for an account shortly after several failures from the same source.",
         "This pattern suggests a password was guessed correctly — the attacker may now hold a valid account.",
         "The failed attempts, the successful sign-in, the source IP and what the session did next.",
         "Contact the user to confirm. Review all activity by this account after the success (privilege changes, "
         "new processes, outbound connections).",
         "Reset the password, revoke active sessions, enforce MFA, and scope everything the account did.",
         {"min_failures": 4, "window_minutes": 15}, _success_after_failures),
    Rule("CSA-DET-004", "Account added to a privileged group", "high", "T1098", "Account Manipulation",
         "Persistence", ["windows"],
         "An account was added to an administrative group such as Domain Admins or Backup Operators.",
         "Privileged groups grant control of systems. Unapproved membership changes are a classic way to "
         "keep or expand access.",
         "The group-change event: who was added, to which group, by whom, and any change-ticket reference.",
         "Is there an approved change ticket? Did the account add itself? Is this account involved in other alerts?",
         "If unapproved: remove the membership, disable the account, and investigate how it obtained the right to "
         "make the change. If approved: close as expected activity and note the ticket.",
         {"event_codes": ["4728", "4732", "4756"],
          "privileged_groups": ["Domain Admins", "Enterprise Admins", "Administrators", "Backup Operators"]},
         _privileged_group_change),
    Rule("CSA-DET-005", "Unusual outbound network connection", "high", "T1571", "Non-Standard Port",
         "Command and Control", ["network"],
         "Outbound connections to an address on the threat-intel list or to a non-standard port.",
         "Malware often 'calls home' on unusual ports. Repeated, evenly spaced connections suggest automated "
         "beaconing rather than a person browsing.",
         "Firewall records: origin host, destination IP and port, number of connections and their timing.",
         "Which process on the origin host made the connection? Did other hosts contact the same address? "
         "What happened on the host just before the first connection?",
         "Block the destination at the firewall, isolate the origin host, and collect evidence from it.",
         {"suspicious_ports": [4444, 1337, 31337, 6667], "window_minutes": 60}, _unusual_connection),
    Rule("CSA-DET-006", "Service installed from a user-writable location", "critical", "T1543.003",
         "Create or Modify System Process: Windows Service", "Persistence", ["windows"],
         "A new Windows service whose program lives in a public or temporary folder.",
         "Services start automatically with high privileges. Legitimate software installs to Program Files; "
         "a service in C:\\Users\\Public is a strong persistence indicator.",
         "The service-installation event: service name, image path, host and the installing account.",
         "Hash the executable and compare it with known software. Which account installed it, and how did it get "
         "the rights to do so?",
         "Stop and disable the service, preserve the executable as evidence, and isolate the host.",
         {}, _suspicious_service),
    Rule("CSA-DET-007", "Suspicious scheduled task or cron job", "high", "T1053.005", "Scheduled Task/Job",
         "Persistence", ["windows", "linux"],
         "A scheduled task or cron entry that runs a program or script from a user-writable/temporary path.",
         "Scheduled jobs let attackers re-run code automatically. Hidden scripts in Temp or /tmp are a common sign.",
         "The task-creation or crontab event: job name, command, schedule, host and account.",
         "Read the referenced script (from preserved evidence). Who created the job? Do other hosts have it?",
         "Remove the job, preserve the script, and investigate how the account was used.",
         {}, _suspicious_scheduled_task),
    Rule("CSA-DET-008", "Security configuration weakened or logs cleared", "high", "T1562", "Impair Defenses",
         "Defense Evasion", ["windows", "linux"],
         "Audit policy changes, cleared security logs, or modified security-sensitive configuration.",
         "Attackers disable logging to hide their activity. Clearing the audit log is almost never routine.",
         "The configuration-change event: what changed, who changed it, host, and any change-ticket reference.",
         "Was there an approved change? What happened immediately before the change (the activity being hidden)?",
         "Restore the configuration, forward logs to a central SIEM so clearing a host does not erase them, and "
         "treat unapproved changes as part of an incident.",
         {}, _defence_impairment),
    Rule("CSA-DET-009", "Sign-in outside normal working hours", "medium", "T1078", "Valid Accounts",
         "Initial Access", ["windows", "linux", "authentication"],
         "A person (not a service account) signed in during the night.",
         "Stolen accounts are often used when the real owner is asleep. It can also be legitimate travel or "
         "on-call work — this alert needs context.",
         "The successful sign-in: account, time, source IP, target host and logon type.",
         "Is the user travelling or on call? Is the source normal for them? What did the session do?",
         "Confirm with the user/manager. If unexpected: reset credentials, end sessions, review activity.",
         {"start_hour": 7, "end_hour": 19, "night_end_hour": 5}, _off_hours_access),
    Rule("CSA-DET-010", "Suspicious process execution indicators", "high", "T1059.001",
         "Command and Scripting Interpreter: PowerShell", "Execution", ["windows"],
         "Processes showing known abuse indicators: encoded PowerShell, Office spawning a shell, certutil downloads.",
         "These techniques let attackers run hidden code using built-in Windows tools ('living off the land').",
         "Process-creation events: process, parent process, full command line, user and host.",
         "Decode any encoded command (safely, as text). What document or parent started it? Any network activity "
         "from the host afterwards?",
         "Isolate the host, preserve the document and command line, block the macro/LOLBin behaviour by policy.",
         {}, _suspicious_process),
]

RULES_BY_ID = {r.id: r for r in RULES}


def run_all(events: list[dict]) -> list[AlertCandidate]:
    alerts: list[AlertCandidate] = []
    for rule in RULES:
        alerts.extend(rule.run(events))
    return alerts
