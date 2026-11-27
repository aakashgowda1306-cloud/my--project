"""Tiny, readable detection engine.

A *rule* is a Python function that receives a list of events (dicts) and
returns AlertCandidate objects. Rules never modify events and never touch the
database, so they are easy to unit-test and safe to run inside a web request.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class AlertCandidate:
    rule_id: str
    title: str
    severity: str
    entity: dict
    events: list[dict]
    summary: str

    @property
    def first_seen(self) -> datetime:
        return min(e["event_time"] for e in self.events)

    @property
    def last_seen(self) -> datetime:
        return max(e["event_time"] for e in self.events)

    @property
    def evidence_event_ids(self) -> list[int]:
        return sorted(e["id"] for e in self.events)

    @property
    def alert_key(self) -> str:
        """Stable identity: same rule + same evidence => same alert (idempotent re-runs)."""
        return f"{self.rule_id}:{self.evidence_event_ids[0]}:{len(self.events)}"

    def as_row(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "alert_key": self.alert_key,
            "title": self.title,
            "severity": self.severity,
            "entity": self.entity,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "event_count": len(self.events),
            "evidence_event_ids": self.evidence_event_ids,
            "summary": self.summary,
        }


@dataclass
class Rule:
    id: str
    name: str
    severity: str
    mitre_technique_id: str
    mitre_technique_name: str
    mitre_tactic: str
    data_sources: list[str]
    what_detected: str
    why_it_matters: str
    evidence_guidance: str
    analyst_steps: str
    defensive_response: str
    parameters: dict
    logic: Callable[[list[dict], dict], list[AlertCandidate]] = field(repr=False)

    def run(self, events: Iterable[dict]) -> list[AlertCandidate]:
        ordered = sorted(events, key=lambda e: (e["event_time"], e["id"]))
        return self.logic(ordered, self.parameters)

    def metadata(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k != "logic"}


def group_by(events: Iterable[dict], key: Callable[[dict], object]) -> dict[object, list[dict]]:
    groups: dict[object, list[dict]] = defaultdict(list)
    for e in events:
        groups[key(e)].append(e)
    return groups


def bursts(events: list[dict], window: timedelta) -> list[list[dict]]:
    """Split time-ordered events into bursts: a new burst starts when the gap
    from the burst's FIRST event exceeds `window`."""
    out: list[list[dict]] = []
    for e in events:
        if out and e["event_time"] - out[-1][0]["event_time"] <= window:
            out[-1].append(e)
        else:
            out.append([e])
    return out
