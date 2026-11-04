"""Governance090: offline, public-fixture requirement-change witness.

NOT a compliance certifier, identity/authentication service, government connector, or
contract-ready system. It never reads or writes native financial accounts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VERDICTS = {"MET", "PARTIAL", "NOT_MET", "NOT_APPLICABLE", "UNDETERMINED"}


def canonical(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(data: Any) -> str:
    return hashlib.sha256(canonical(data)).hexdigest()


def strict_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("DUPLICATE_JSON_KEY:" + str(k))
        result[k] = v
    return result


def read_strict(path: str | Path) -> dict:
    v = json.loads(Path(path).read_text(encoding="utf-8"),
                   object_pairs_hook=strict_object,
                   parse_constant=lambda x: (_ for _ in ()).throw(ValueError("NONFINITE:" + x)))
    if not isinstance(v, dict):
        raise ValueError("OBJECT_REQUIRED")
    return v


def _indexed(items: list, allowed: set[str], kind: str) -> dict[str, dict]:
    if type(items) is not list:
        raise ValueError("INVALID_" + kind)
    d = {}
    for v in items:
        if type(v) is not dict or set(v) != allowed or type(v.get("id")) is not str or not v["id"]:
            raise ValueError("INVALID_" + kind)
        if v["id"] in d:
            raise ValueError("DUPLICATE_" + kind)
        d[v["id"]] = v
    return d


def _requirements(rows: list) -> dict[str, dict]:
    rs = _indexed(rows, {"id", "text", "status"}, "REQUIREMENT")
    for r in rs.values():
        if type(r["text"]) is not str or r["status"] not in ("active", "retired"):
            raise ValueError("INVALID_REQUIREMENT")
    return rs


def _check_links(controls: dict, systems: dict, requirements: dict) -> None:
    for c in controls.values():
        if type(c["requirements"]) is not list or len(set(c["requirements"])) != len(c["requirements"]):
            raise ValueError("INVALID_CONTROL_LINKS")
        if not all(type(x) is str and x in requirements for x in c["requirements"]):
            raise ValueError("UNKNOWN_REQUIREMENT")
    for s in systems.values():
        if type(s["controls"]) is not list or len(set(s["controls"])) != len(s["controls"]):
            raise ValueError("INVALID_SYSTEM_LINKS")
        if not all(type(x) is str and x in controls for x in s["controls"]):
            raise ValueError("UNKNOWN_CONTROL")


def full_scan_impacts(systems: dict, controls: dict, changed: set[str]) -> list[str]:
    """Competent ordinary exhaustive traversal, independent of the reverse index."""
    return sorted(sid for sid, s in systems.items()
                  if any(any(req in changed for req in controls[c]["requirements"])
                         for c in s["controls"]))


def verify_chain(events: list[dict], expected_tip: str) -> bool:
    if type(expected_tip) is not str or len(expected_tip) != 64:
        raise ValueError("EXPECTED_TIP_REQUIRED")
    head = "0" * 64
    for seq, item in enumerate(events):
        if type(item) is not dict or set(item) != {"seq", "previous", "payload", "hash"}:
            raise ValueError("JOURNAL_SCHEMA")
        if type(item["seq"]) is not int or item["seq"] != seq or item["previous"] != head:
            raise ValueError("JOURNAL_ORDER")
        if item["hash"] != digest({"seq": seq, "previous": head, "payload": item["payload"]}):
            raise ValueError("JOURNAL_CONTENT")
        head = item["hash"]
    if head != expected_tip:
        raise ValueError("JOURNAL_TIP_CHANGED")
    return True


class ImpactRegistry:
    def __init__(self, specification: dict):
        if type(specification) is not dict or set(specification) != {"tenant", "requirements", "controls", "systems", "reviewers"}:
            raise ValueError("SPEC_SCHEMA")
        self.tenant = specification["tenant"]
        if type(self.tenant) is not str or not self.tenant:
            raise ValueError("INVALID_TENANT")
        self.requirements = _requirements(specification["requirements"])
        self.controls = _indexed(specification["controls"], {"id", "requirements"}, "CONTROL")
        self.systems = _indexed(specification["systems"], {"id", "controls"}, "SYSTEM")
        _check_links(self.controls, self.systems, self.requirements)
        self.reviewers = specification["reviewers"]
        if type(self.reviewers) is not dict or not all(type(k) is str and type(v) is dict and set(v) == {"tenant", "roles"} and type(v["roles"]) is list and all(type(role) is str for role in v["roles"]) for k, v in self.reviewers.items()):
            raise ValueError("REVIEWER_SCHEMA")
        self.events = []
        self.tip = "0" * 64
        self.reverse_controls = {req: set() for req in self.requirements}
        self.reverse_systems = {c: set() for c in self.controls}
        for cid, c in self.controls.items():
            for req in c["requirements"]:
                self.reverse_controls[req].add(cid)
        for sid, s in self.systems.items():
            for cid in s["controls"]:
                self.reverse_systems[cid].add(sid)
        self._append({"kind": "genesis", "tenant": self.tenant, "spec_sha256": digest(specification)})

    def _append(self, payload: dict) -> None:
        seq = len(self.events)
        event = {"seq": seq, "previous": self.tip, "payload": payload}
        event["hash"] = digest(event)
        self.events.append(event)
        self.tip = event["hash"]

    def update(self, incoming: list[dict]) -> dict:
        new = _requirements(incoming)
        # All requirement IDs are retained as tombstones; deletion is never silently interpreted
        # as removal of a governance obligation. Retire it explicitly instead.
        if set(new) != set(self.requirements):
            raise ValueError("REQUIREMENT_SET_CHANGE_REQUIRES_EXPLICIT_MIGRATION")
        changed = {r for r in new if new[r] != self.requirements[r]}
        impact = sorted({sid for req in changed for cid in self.reverse_controls[req]
                         for sid in self.reverse_systems[cid]})
        before = digest(list(self.requirements.values()))
        self.requirements = new
        after = digest(list(new.values()))
        if changed:
            self._append({"kind": "update", "tenant": self.tenant, "changed": sorted(changed),
                          "impacted": impact, "before_sha256": before, "after_sha256": after})
        return {"tenant": self.tenant, "changed_requirements": sorted(changed),
                "affected_systems": impact, "ordinary_full_scan": full_scan_impacts(self.systems, self.controls, changed),
                "old_sha256": before, "new_sha256": after}

    def review(self, *, actor: str, tenant: str, system: str, control: str,
               requirement: str, verdict: str, evidence_sha256: str,
               annotation: str) -> None:
        member = self.reviewers.get(actor)
        if tenant != self.tenant or member is None or member["tenant"] != tenant or "reviewer" not in member["roles"]:
            raise ValueError("REVIEWER_NOT_AUTHORIZED_IN_TENANT")
        if system not in self.systems or control not in self.systems[system]["controls"] or requirement not in self.controls[control]["requirements"]:
            raise ValueError("MAPPING_NOT_FOUND")
        req = self.requirements[requirement]
        if req["status"] != "active":
            raise ValueError("RETIRED_REQUIREMENT")
        if verdict not in VERDICTS:
            raise ValueError("INVALID_VERDICT")
        if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64 or any(x not in "0123456789abcdef" for x in evidence_sha256):
            raise ValueError("INVALID_EVIDENCE_DIGEST")
        if not isinstance(annotation, str):
            raise ValueError("INVALID_ANNOTATION")
        self._append({"kind": "review", "tenant": tenant, "actor": actor,
                      "system": system, "control": control, "requirement": requirement,
                      "requirement_sha256": digest(req), "verdict": verdict,
                      "evidence_sha256": evidence_sha256, "annotation": annotation})

    def evaluate(self) -> dict:
        # A review is valid only within the uninterrupted policy revision epoch.
        # A->B->A (or active->retired->active) must not resurrect a prior MET
        # merely because the old content SHA-256 has reappeared.
        latest_change_seq = {rid: -1 for rid in self.requirements}
        for event in self.events:
            payload = event["payload"]
            if payload.get("kind") == "update":
                for rid in payload["changed"]:
                    latest_change_seq[rid] = event["seq"]

        # A competent chronological replay control. Do not alter stored reviews:
        # history is permanent; its past authorization is simply not current.
        # Indexing reviews also avoids rescanning the full journal for every link.
        current_reviews = {}
        for event in self.events:
            payload = event["payload"]
            if payload.get("kind") != "review":
                continue
            rid = payload["requirement"]
            if event["seq"] <= latest_change_seq[rid]:
                continue
            if payload["requirement_sha256"] != digest(self.requirements[rid]):
                continue
            current_reviews[(payload["system"], payload["control"], rid)] = event

        result = {}
        for sid, s in sorted(self.systems.items()):
            findings = []
            for cid in sorted(s["controls"]):
                for rid in sorted(self.controls[cid]["requirements"]):
                    req = self.requirements[rid]
                    if req["status"] != "active":
                        findings.append({"control": cid, "requirement": rid, "status": "RETIRED_REVIEW_REQUIRED", "event_hash": None})
                        continue
                    recent = current_reviews.get((sid, cid, rid))
                    findings.append({"control": cid, "requirement": rid,
                                     "status": recent["payload"]["verdict"] if recent else "UNDETERMINED",
                                     "event_hash": recent["hash"] if recent else None})
            result[sid] = {"findings": findings,
                           "all_controls_met": bool(findings) and all(f["status"] == "MET" for f in findings)}
        return {"tenant": self.tenant, "systems": result, "journal_tip": self.tip,
                "qualified_compliance": False,
                "scope": "DETERMINISTIC_LOCAL_REVIEW_ASSERTIONS_NOT_LEGAL_COMPLIANCE"}

    def audit(self, expected_tip: str) -> bool:
        return verify_chain(self.events, expected_tip)


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    registry = ImpactRegistry(read_strict(args.spec))
    impact = registry.update(read_strict(args.revision)["requirements"])
    if impact["affected_systems"] != impact["ordinary_full_scan"]:
        raise ValueError("IMPACT_DISAGREES_WITH_ORDINARY_FULL_SCAN")
    path = Path(args.output)
    if path.exists():
        raise FileExistsError("OUTPUT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = {"impact": impact, "assessment": registry.evaluate(), "journal": registry.events,
               "journal_tip": registry.tip, "evidence_level": "UNQUALIFIED_PUBLIC_FIXTURE"}
    path.write_bytes(canonical(content) + b"\n")
    print(json.dumps({"output": str(path), "affected": impact["affected_systems"],
                      "journal_tip": registry.tip}, sort_keys=True))


if __name__ == "__main__":
    cli()
