"""Offline, source-grounded opportunity study for a governed MONTREAL.AI mission."""
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MATRIX = ROOT.parent / "flagship" / "runs.csv"


def _read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def default_mission():
    """Return a fresh copy of the public coding-pilot mandate."""
    return _read("mission.json")


def load_atlas():
    return _read("atlas.json")


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _matrix_witness(expected_hash):
    """Establish the observable resource. A bibliography entry cannot satisfy this test."""
    try:
        raw = MATRIX.read_bytes()
    except OSError:
        return {"available": False, "reason": "The registered local run matrix is unavailable."}
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_hash:
        return {"available": False, "sha256": actual_hash, "reason": "The projected matrix differs from its registered bytes."}
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    cells = {(r["task"], r["model"], r["harness"]) for r in rows}
    tasks = {task for task, _, _ in cells}
    pairs = {(model, harness) for _, model, harness in cells}
    complete = (len(cells) == len(rows) == len(tasks) * len(pairs) == 1800
                and len(tasks) == 100 and len(pairs) == 18)
    return {"available": complete, "sha256": actual_hash, "rows": len(rows),
            "tasks": len(tasks), "configurations": len(pairs),
            "reason": "Complete matched rows with registered identity." if complete else "Incomplete matched panel."}


def _labels(value, field):
    if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
        raise ValueError(f"{field} must contain an array of nonempty property or permission names")
    if len(set(value)) != len(value):
        raise ValueError(f"{field} contains duplicate entries")
    return set(value)


def _candidate(offer, props, required, granted, missing_sources=()):
    result = {key: offer[key] for key in ("id", "title", "value", "method", "tradeoff", "test", "effort", "source_ids")}
    result["satisfied"] = sorted(required & props)
    result["missing"] = sorted(required - props)
    result["permissions_missing"] = sorted(set(offer["permissions"]) - granted)
    result["unavailable_sources"] = sorted(missing_sources)
    result["eligible"] = not any(result[k] for k in ("missing", "permissions_missing", "unavailable_sources"))
    return result


def investigate(mission, atlas=None, previous=None):
    """Join a bounded authored source map to mission requirements; never grant permissions.

    Historical cutoffs use publication dates from observations made on the study date.
    A changed ambition or acceptance contract starts a new watch. This function reads
    public local files and returns evidence, never an accepted customer artifact.
    """
    if not isinstance(mission, dict):
        raise ValueError("a structured mission is required")
    for key in ("question", "purpose", "beneficiary", "as_of"):
        if not isinstance(mission.get(key), str) or not mission[key].strip():
            raise ValueError(f"mission requires {key}")
    required = _labels(mission.get("requires"), "requires")
    granted = _labels(mission.get("permissions"), "permissions")
    if not required:
        raise ValueError("at least one measurable requirement is needed")
    cutoff = date.fromisoformat(mission["as_of"])
    atlas = load_atlas() if atlas is None else atlas
    observed = date.fromisoformat(atlas["observed_on"])
    if cutoff > observed:
        raise ValueError("requested cutoff exceeds the date of the last source observations")
    sources = {s["id"]: s for s in atlas["sources"] if date.fromisoformat(s["published"]) <= cutoff}
    relevant = [o for o in atlas["offers"] if o["question"] == mission["question"]]
    candidates = []
    for offer in relevant:
        missing_sources = set(offer["source_ids"]) - sources.keys()
        if missing_sources:
            continue
        candidates.append(_candidate(offer, set(offer["properties"]), required, granted))
    resources, challengers = {}, []
    for resource in atlas["resources"]:
        if resource["question"] != mission["question"]:
            continue
        source = sources.get(resource["source_id"])
        if source is None:
            continue
        witness = _matrix_witness(source["projection_sha256"]) if resource["id"] == "public-run-matrix" else {
            "available": False, "reason": "No verifier is registered for these data."}
        resources[resource["id"]] = witness
        for trans in atlas["transformations"]:
            if trans["input_format"] != resource["format"]:
                continue
            props = set(resource["properties"] + trans["produces"]) if witness["available"] else set()
            offer = dict(trans, source_ids=[source["id"]])
            challenger = _candidate(offer, props, required, granted,
                                    [] if witness["available"] else [resource["id"]])
            challenger["resource_id"] = resource["id"]
            challengers.append(challenger)
    eligible = [c for c in candidates + challengers if c["eligible"]]
    if len(eligible) == 1:
        winner = eligible[0]
        decision = {"status": "select", "candidate_id": winner["id"],
                    "reason": "This route alone meets every specified property with the available evidence and permissions."}
    elif eligible:
        decision = {"status": "compare", "candidate_id": None,
                    "reason": "Several routes meet the contract. Compare their complete outcome and cost before selecting.",
                    "eligible": [c["id"] for c in eligible]}
    else:
        decision = {"status": "defer", "candidate_id": None,
                    "reason": "No supported route satisfies the current evidence and permission requirements."}
    mission_id = _digest(mission)
    evidence_id = _digest({"sources": sources, "resources": resources})
    state = "initial"
    if previous is not None:
        if previous["mission_sha256"] != mission_id:
            state = "new-mission"
        elif previous["evidence_sha256"] == evidence_id and previous["atlas_sha256"] == _digest(atlas):
            state = "unchanged"
        elif previous["decision"]["status"] == "defer" and decision["status"] == "select":
            state = "reopened"
        elif previous["decision"]["status"] == "select" and decision["status"] == "defer":
            state = "suspended"
        else:
            state = "reassessed"
    return {"schema": 1, "purpose": mission["purpose"], "beneficiary": mission["beneficiary"],
            "question": mission["question"], "required": sorted(required), "as_of": mission["as_of"],
            "observed_on": atlas["observed_on"], "mission_sha256": mission_id, "atlas_sha256": _digest(atlas),
            "evidence_sha256": evidence_id, "source_ids": sorted(sources),
            "sources": [{k: s[k] for k in ("id", "title", "url", "published", "publisher", "observation", "scope")}
                        for s in sources.values()], "witnesses": resources,
            "candidates": candidates, "challengers": challengers, "decision": decision, "watch": state,
            "previous_evidence_sha256": previous["evidence_sha256"] if previous is not None else None,
            "limits": "Authored source inventory and bounded replay. Publication dates do not establish previous impossibility. No model, deployment, inference billing or buyer transaction."}
