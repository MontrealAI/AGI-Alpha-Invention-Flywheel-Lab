"""Selective, source-scoped review queue for explicitly modeled governance changes.

Research-only: normalized caller metadata is not authenticated. This program
does NOT assert compliance, legally sufficient oversight or actual cost savings.
The independent exhaustive oracle is in tests, not this implementation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import impact_continuation229 as prior
from tools import bidirectional_impact230 as conservative

SCHEMA = "selective-impact232/v1"


def _refmap(system, controls):
    refs = {} if system is None else {
        item["control"]: item["source_sha256"]
        for item in system["evidence_refs"]
    }
    return {control: refs.get(control) for control in controls}


def assess(payload):
    prior._valid_keys(payload, {"schema", "before", "after"}, "root")
    if payload["schema"] != SCHEMA:
        raise prior.InvalidInput("schema: unsupported")
    old_req, old_sys = conservative._snapshot(payload["before"], "before")
    new_req, new_sys = conservative._snapshot(payload["after"], "after")
    for rid in sorted(old_req.keys() & new_req.keys()):
        if old_req[rid]["version"] == new_req[rid]["version"] and old_req[rid] != new_req[rid]:
            raise prior.InvalidInput("VERSION_CONTENT_COLLISION:" + rid)

    normalized = {
        "before": {"requirements": [old_req[k] for k in sorted(old_req)],
                   "systems": [old_sys[k] for k in sorted(old_sys)]},
        "after": {"requirements": [new_req[k] for k in sorted(new_req)],
                  "systems": [new_sys[k] for k in sorted(new_sys)]},
    }
    control_result = conservative.assess({
        "schema": conservative.SCHEMA, **normalized
    })
    conservative_pairs = {
        (entry["requirement_id"], entry["system_id"])
        for entry in control_result["reviews"]
    }
    reviews = []
    for rid in sorted(old_req.keys() | new_req.keys()):
        r0, r1 = old_req.get(rid), new_req.get(rid)
        for sid in sorted(old_sys.keys() | new_sys.keys()):
            s0, s1 = old_sys.get(sid), new_sys.get(sid)
            was = s0 is not None and prior._applies(r0, s0)
            now = s1 is not None and prior._applies(r1, s1)
            if not (was or now):
                continue
            old_controls = r0["controls"] if was else []
            new_controls = r1["controls"] if now else []
            old_refs = _refmap(s0, old_controls)
            new_refs = _refmap(s1, new_controls)
            reasons = []
            if r0 != r1:
                reasons.append("requirement_changed")
            if was != now:
                reasons.append("applicability_changed")
            if (s0 is None) != (s1 is None):
                reasons.append("system_added_or_retired")
            if old_refs != new_refs:
                reasons.append("required_evidence_changed")
            if reasons:
                if (rid, sid) not in conservative_pairs:
                    raise prior.InvalidInput("SELECTIVE_NOT_IN_CONSERVATIVE:" + rid + ":" + sid)
                reviews.append({
                    "requirement_id": rid, "system_id": sid,
                    "reasons": reasons, "applied_before": was,
                    "applies_after": now,
                    "old_required_evidence": old_refs,
                    "new_required_evidence": new_refs,
                    "state": "REVIEW_NEEDED_UNDER_DECLARED_MODEL_NO_COMPLIANCE_VERDICT",
                })
    selected = {(x["requirement_id"], x["system_id"]) for x in reviews}
    suppressed = [
        {"requirement_id": rid, "system_id": sid,
         "reason": "UNRELATED_SYSTEM_FIELD_ONLY_UNDER_DECLARED_MODEL"}
        for rid, sid in sorted(conservative_pairs - selected)
    ]
    result = {
        "schema": SCHEMA,
        "input_sha256": prior.sha({"schema": SCHEMA, **normalized}),
        "source_claim": "CALLER_SUPPLIED_STRUCTURED_DATA_NOT_AUTHENTICATED",
        "compliance_claim": "NONE",
        "scope": "EXPLICIT_TAG_APPLICABILITY_AND_REQUIRED_CONTROL_EVIDENCE_ONLY",
        "reviews": reviews,
        "review_count": len(reviews),
        "conservative_review_count": len(conservative_pairs),
        "suppressed_conservative_reviews": suppressed,
        "suppressed_count": len(suppressed),
        "economic_savings_USD": None,
    }
    result["result_sha256"] = prior.sha(result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, help="new output only; never overwrite")
    args = parser.parse_args(argv)
    try:
        with args.input.open("r", encoding="utf-8") as stream:
            payload = json.load(stream, object_pairs_hook=prior._reject_duplicates)
        result = assess(payload)
        output = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(output)
        else:
            sys.stdout.write(output)
        return 0
    except (OSError, ValueError) as error:
        print("SELECTIVE232_REJECTED:" + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
