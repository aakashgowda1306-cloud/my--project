"""Synthetic dataset validation and detection-engine correctness."""

import ipaddress
import re
from collections import Counter

import pytest
from sqlalchemy import text

from app.detections.rules import RULES, RULES_BY_ID, run_all
from app.labdata.events import generate_events

ALLOWED_NETS = [ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",          # RFC 1918 private
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]     # RFC 5737 documentation

# rule -> (expected alert count, scenario tags that must appear in its evidence)
EXPECTED = {
    "CSA-DET-001": (3, {"S1-bruteforce-ssh", "S1b-user-lockout", "S3-success-after-failures"}),
    "CSA-DET-002": (1, {"S2-password-spray"}),
    "CSA-DET-003": (1, {"S3-success-after-failures"}),
    "CSA-DET-004": (2, {"S4-privilege-escalation", "S4b-approved-change"}),
    "CSA-DET-005": (1, {"S5-c2-beacon"}),
    "CSA-DET-006": (1, {"S6-suspicious-service"}),
    "CSA-DET-007": (2, {"S7-scheduled-task", "S7b-cron"}),
    "CSA-DET-008": (3, {"S8-audit-policy", "S8-log-cleared", "S8b-approved-hardening"}),
    "CSA-DET-009": (2, {"S9-offhours-rdp", "S9b-travelling-user"}),
    "CSA-DET-010": (2, {"S10-encoded-powershell", "S10b-lolbin-download"}),
}


@pytest.fixture(scope="module")
def events():
    return generate_events()


def test_dataset_has_at_least_300_events(events):
    assert len(events) >= 300


def test_dataset_is_deterministic(events):
    again = generate_events()
    assert [(e["id"], e["event_time"], e["message"]) for e in again] == \
           [(e["id"], e["event_time"], e["message"]) for e in events]


def test_ids_are_unique_and_sequential(events):
    assert [e["id"] for e in events] == list(range(1, len(events) + 1))


def test_every_event_is_marked_synthetic_and_uses_fictional_hosts(events):
    assert all(e["is_synthetic"] and e["dataset"] == "synthetic-v1" for e in events)
    assert all(e["host"].endswith(".corp.example") for e in events)


def test_only_private_or_documentation_ip_addresses(events):
    for e in events:
        for field in ("src_ip", "dst_ip"):
            if e[field]:
                ip = ipaddress.ip_address(e[field])
                assert any(ip in n for n in ALLOWED_NETS), f"event {e['id']} uses non-reserved IP {ip}"


def test_dataset_covers_all_log_sources(events):
    assert set(Counter(e["source"] for e in events)) == {"windows", "linux", "application", "authentication", "network"}


@pytest.mark.parametrize("rule_id", sorted(EXPECTED))
def test_each_rule_fires_expected_number_of_times(events, rule_id):
    expected_count, expected_tags = EXPECTED[rule_id]
    alerts = RULES_BY_ID[rule_id].run(events)
    assert len(alerts) == expected_count
    seen_tags = {e["scenario_tag"] for a in alerts for e in a.events}
    assert seen_tags == expected_tags


def test_no_alert_is_built_from_baseline_noise(events):
    for alert in run_all(events):
        assert all(e["scenario_tag"] for e in alert.events), f"{alert.rule_id} fired on benign baseline events"


def test_near_miss_three_typos_do_not_alert(events):
    # s.chen mistypes three times then succeeds: below CSA-DET-001 (5) and CSA-DET-003 (4) thresholds.
    for rule in ("CSA-DET-001", "CSA-DET-003"):
        assert not [a for a in RULES_BY_ID[rule].run(events) if a.entity.get("username") == "s.chen"]


def test_ten_rules_with_complete_analyst_guidance():
    assert len(RULES) == 10
    for r in RULES:
        assert re.fullmatch(r"T\d{4}(\.\d{3})?", r.mitre_technique_id)
        for field in ("what_detected", "why_it_matters", "evidence_guidance", "analyst_steps", "defensive_response"):
            assert len(getattr(r, field)) > 30, f"{r.id}.{field} is too thin"


def test_alert_keys_are_unique(events):
    keys = [a.alert_key for a in run_all(events)]
    assert len(keys) == len(set(keys))


def test_database_counts_match_generator(events):
    from app.db import service_connection

    with service_connection() as conn:
        assert conn.execute(text("select count(*) from public.security_events")).scalar_one() == len(events)
        assert conn.execute(text("select count(*) from public.generated_alerts")).scalar_one() == \
               sum(c for c, _ in EXPECTED.values())


def test_rerunning_detections_is_idempotent():
    from app.db import service_connection
    from app.seed import run_detections

    with service_connection() as conn:
        run_detections(conn)
        run_detections(conn)
        assert conn.execute(text("select count(*) from public.generated_alerts")).scalar_one() == 18
