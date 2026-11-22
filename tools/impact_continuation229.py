"""Offline, *non-authoritative* change-impact scoping; no compliance verdicts.

Input contains synthetic/authorized structured metadata. SHA-256 is integrity
identification, never a signature or an authenticated source/provenance claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SCHEMA = "impact-continuation229/v1"
ID = re.compile(r"[a-zA-Z][a-zA-Z0-9._-]*\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class InvalidInput(ValueError):
    pass


def _valid_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise InvalidInput(f"{label}: required keys {sorted(keys)}")


def _identifier(value, label):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise InvalidInput(f"{label}: invalid ID")
    return value


def _digest(value, label):
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise InvalidInput(f"{label}: invalid sha256")
    return value


def _labels(value, label, *, universal=False):
    if not isinstance(value, list) or not value:
        raise InvalidInput(f"{label}: nonempty label list required")
    labels = []
    for v in value:
        if universal and v == "*":
            labels.append(v)
        else:
            labels.append(_identifier(v, label))
    if len(set(labels)) != len(labels) or ("*" in labels and len(labels) != 1):
        raise InvalidInput(f"{label}: duplicate or ambiguous wildcard")
    return sorted(labels)


def _requirements(items, label):
    if not isinstance(items, list):
        raise InvalidInput(f"{label}: array required")
    out = {}
    for raw in items:
        _valid_keys(raw, {"id", "version", "source_sha256", "applies_to", "controls"}, label)
        key = _identifier(raw["id"], f"{label}.id")
        if key in out:
            raise InvalidInput(f"{label}: duplicated requirement {key}")
        out[key] = {
            "id": key,
            "version": _identifier(raw["version"], f"{label}.{key}.version"),
            "source_sha256": _digest(raw["source_sha256"], f"{label}.{key}.source"),
            "applies_to": _labels(raw["applies_to"], f"{label}.{key}.applies", universal=True),
            "controls": _labels(raw["controls"], f"{label}.{key}.controls"),
        }
    return out


def _systems(items):
    if not isinstance(items, list):
        raise InvalidInput("systems: array required")
    out = {}
    for raw in items:
        _valid_keys(raw, {"id", "tags", "evidence_refs"}, "system")
        key = _identifier(raw["id"], "system.id")
        if key in out:
            raise InvalidInput(f"systems: duplicate {key}")
        if not isinstance(raw["evidence_refs"], list):
            raise InvalidInput(f"{key}.evidence_refs: array required")
        refs = {}
        for ref in raw["evidence_refs"]:
            _valid_keys(ref, {"control", "source_sha256"}, "evidence_ref")
            control = _identifier(ref["control"], "evidence_ref.control")
            if control in refs:
                raise InvalidInput(f"{key}: duplicate evidence control {control}")
            refs[control] = _digest(ref["source_sha256"], f"{key}.{control}.source")
        out[key] = {"id": key, "tags": _labels(raw["tags"], f"{key}.tags"),
                    "evidence_refs": [{"control": k, "source_sha256": refs[k]} for k in sorted(refs)]}
    return out


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _applies(requirement, system):
    if requirement is None:
        return False
    tags = requirement["applies_to"]
    return "*" in tags or bool(set(tags).intersection(system["tags"]))


def assess(payload):
    _valid_keys(payload, {"schema", "before", "after", "systems"}, "root")
    if payload["schema"] != SCHEMA:
        raise InvalidInput("schema: unsupported")
    old = _requirements(payload["before"], "before")
    new = _requirements(payload["after"], "after")
    systems = _systems(payload["systems"])
    # Semantic source-integrity guard: a frozen version cannot be changed in place.
    for rid in sorted(old.keys() & new.keys()):
        if old[rid]["version"] == new[rid]["version"] and old[rid] != new[rid]:
            raise InvalidInput(f"VERSION_CONTENT_COLLISION:{rid}")
    changes = []
    for rid in sorted(old.keys() | new.keys()):
        a, b = old.get(rid), new.get(rid)
        if a == b:
            continue
        kind = "added" if a is None else "retired" if b is None else "revised"
        changes.append({"id": rid, "kind": kind,
                        "old_version": a["version"] if a else None,
                        "new_version": b["version"] if b else None,
                        "old_source_sha256": a["source_sha256"] if a else None,
                        "new_source_sha256": b["source_sha256"] if b else None})
    index = defaultdict(set)
    for sid, system in systems.items():
        for tag in system["tags"]:
            index[tag].add(sid)
    reassessments = []
    for change in changes:
        rid = change["id"]
        a, b = old.get(rid), new.get(rid)
        candidate = set()
        for req in (a, b):
            if req is None:
                continue
            if "*" in req["applies_to"]:
                candidate.update(systems)
            else:
                for tag in req["applies_to"]:
                    candidate.update(index[tag])
        for sid in sorted(candidate):
            system = systems[sid]
            before_applies, after_applies = _applies(a, system), _applies(b, system)
            if not (before_applies or after_applies):
                continue
            controls = sorted(set(a["controls"] if before_applies else []) |
                              set(b["controls"] if after_applies else []))
            refs = {r["control"]: r["source_sha256"] for r in system["evidence_refs"]}
            reassessments.append({
                "system_id": sid, "requirement_id": rid,
                "change": change["kind"],
                "applied_before": before_applies, "applies_after": after_applies,
                "old_controls": a["controls"] if before_applies else [],
                "new_controls": b["controls"] if after_applies else [],
                "review_controls": controls,
                "linked_evidence": [{"control": c, "source_sha256": refs[c]} for c in controls if c in refs],
                "unlinked_controls": [c for c in controls if c not in refs],
                "state": "REASSESSMENT_REQUIRED_NO_COMPLIANCE_VERDICT",
            })
    normalized = {"schema": SCHEMA,
                  "before": [old[k] for k in sorted(old)],
                  "after": [new[k] for k in sorted(new)],
                  "systems": [systems[k] for k in sorted(systems)]}
    result = {"schema": SCHEMA, "input_sha256": sha(normalized),
              "source_claim": "STRUCTURED_INPUT_NOT_INDEPENDENTLY_AUTHENTICATED",
              "compliance_claim": "NONE", "changed_requirements": changes,
              "reassessments": reassessments, "changed_count": len(changes),
              "reassessment_count": len(reassessments),
              "unaffected_systems_count": len(systems) - len({r["system_id"] for r in reassessments})}
    result["result_sha256"] = sha(result)
    return result


def _reject_duplicates(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise InvalidInput(f"DUPLICATE_JSON_KEY:{key}")
        obj[key] = value
    return obj


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON file with structured synthetic/authorized inputs")
    parser.add_argument("--output", type=Path, help="Optional new output file; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        with args.input.open("r", encoding="utf-8") as f:
            payload = json.load(f, object_pairs_hook=_reject_duplicates)
        outcome = assess(payload)
        printable = json.dumps(outcome, sort_keys=True, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as f:
                f.write(printable)
        else:
            sys.stdout.write(printable)
        return 0
    except (OSError, InvalidInput, ValueError) as error:
        print(f"IMPACT229_REJECTED:{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
