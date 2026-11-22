"""Research-only bidirectional registered-system and policy change-impact scoping.

Never a legal/compliance finding. SHA-256 binds structured caller data but does
not authenticate its source or imply authority. No live systems are accessed.

Retains the exact upstream IMPACT229 canonical parsers and validation. Extends
the scope of events to changes in the registered system / evidence inventory.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Standalone script entry point must also resolve the repository package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import impact_continuation229 as prior

SCHEMA = "bidirectional-impact230/v1"


def _snapshot(raw, label):
    prior._valid_keys(raw, {"requirements", "systems"}, label)
    return (prior._requirements(raw["requirements"], label + ".requirements"),
            prior._systems(raw["systems"]))


def _change_kind(old, new):
    if old is None:
        return "added"
    if new is None:
        return "retired"
    return "revised"


def _evidence(system, controls):
    refs = {} if system is None else {
        ref["control"]: ref["source_sha256"] for ref in system["evidence_refs"]
    }
    return {
        "linked": [{"control": key, "source_sha256": refs[key]}
                   for key in controls if key in refs],
        "unlinked": [key for key in controls if key not in refs],
    }


def assess(payload):
    prior._valid_keys(payload, {"schema", "before", "after"}, "root")
    if payload["schema"] != SCHEMA:
        raise prior.InvalidInput("schema: unsupported")
    old_req, old_sys = _snapshot(payload["before"], "before")
    new_req, new_sys = _snapshot(payload["after"], "after")
    for rid in sorted(old_req.keys() & new_req.keys()):
        a, b = old_req[rid], new_req[rid]
        if a["version"] == b["version"] and a != b:
            raise prior.InvalidInput("VERSION_CONTENT_COLLISION:" + rid)

    changed_requirements = [
        {"id": rid, "kind": _change_kind(old_req.get(rid), new_req.get(rid)),
         "old_sha256": prior.sha(old_req[rid]) if rid in old_req else None,
         "new_sha256": prior.sha(new_req[rid]) if rid in new_req else None}
        for rid in sorted(old_req.keys() | new_req.keys())
        if old_req.get(rid) != new_req.get(rid)
    ]
    changed_systems = [
        {"id": sid, "kind": _change_kind(old_sys.get(sid), new_sys.get(sid)),
         "old_sha256": prior.sha(old_sys[sid]) if sid in old_sys else None,
         "new_sha256": prior.sha(new_sys[sid]) if sid in new_sys else None}
        for sid in sorted(old_sys.keys() | new_sys.keys())
        if old_sys.get(sid) != new_sys.get(sid)
    ]
    changed_req_ids = {item["id"] for item in changed_requirements}
    changed_sys_ids = {item["id"] for item in changed_systems}
    reviews = []

    # Deliberately ordinary O(requirements * systems) baseline-shaped scan:
    # no claim of discovery, algorithmic superiority or time-saving.
    for rid in sorted(old_req.keys() | new_req.keys()):
        a, b = old_req.get(rid), new_req.get(rid)
        for sid in sorted(old_sys.keys() | new_sys.keys()):
            x, y = old_sys.get(sid), new_sys.get(sid)
            applied_before = x is not None and prior._applies(a, x)
            applied_after = y is not None and prior._applies(b, y)
            if not (applied_before or applied_after):
                continue
            requirement_changed = rid in changed_req_ids
            system_changed = sid in changed_sys_ids
            if not (requirement_changed or system_changed):
                continue
            controls_before = a["controls"] if applied_before else []
            controls_after = b["controls"] if applied_after else []
            evidence_before = _evidence(x, controls_before)
            evidence_after = _evidence(y, controls_after)
            reviews.append({
                "requirement_id": rid, "system_id": sid,
                "cause": [word for word, yes in (
                    ("requirement_change", requirement_changed),
                    ("system_or_evidence_change", system_changed)) if yes],
                "applied_before": applied_before,
                "applies_after": applied_after,
                "old_controls": controls_before,
                "new_controls": controls_after,
                "old_evidence": evidence_before,
                "new_evidence": evidence_after,
                "system_retired": x is not None and y is None,
                "requirement_retired": a is not None and b is None,
                "state": "REVIEW_REQUIRED_NO_COMPLIANCE_VERDICT",
            })

    normalized = {
        "schema": SCHEMA,
        "before": {"requirements": [old_req[k] for k in sorted(old_req)],
                   "systems": [old_sys[k] for k in sorted(old_sys)]},
        "after": {"requirements": [new_req[k] for k in sorted(new_req)],
                  "systems": [new_sys[k] for k in sorted(new_sys)]},
    }
    result = {
        "schema": SCHEMA,
        "input_sha256": prior.sha(normalized),
        "source_claim": "CALLER_SUPPLIED_STRUCTURED_DATA_NOT_AUTHENTICATED",
        "compliance_claim": "NONE",
        "changed_requirements": changed_requirements,
        "changed_systems": changed_systems,
        "reviews": reviews,
        "changed_requirement_count": len(changed_requirements),
        "changed_system_count": len(changed_systems),
        "review_count": len(reviews),
    }
    result["result_sha256"] = prior.sha(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="Create-only JSON result")
    args = parser.parse_args(argv)
    try:
        with args.input.open("r", encoding="utf-8") as stream:
            payload = json.load(stream, object_pairs_hook=prior._reject_duplicates)
        result = assess(payload)
        text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except (ValueError, OSError) as error:
        print("BIDIRECTIONAL230_REJECTED:" + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
