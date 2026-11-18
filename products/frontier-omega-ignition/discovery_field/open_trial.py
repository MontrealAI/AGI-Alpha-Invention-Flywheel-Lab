"""Check a five-opportunity response on a fresh scientific-instrument handoff."""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import protocol

HERE = Path(__file__).resolve().parent
PACKET = "1f602ed003735be4377a66d44cdc75819c44fc967f14ba6f29625cb9d8ac553f"

# Independent of each proposal's chosen source. These reviewed domain cues
# route an open test for inspection; an ambiguous test is never certified.
USES = {
    "nomai": (r"\b(?:transients?|alerts?|supernovae?|SLSN[e]?)\b",
              r"\b(?:recover\w*|select\w*|coverage|triage|priorit\w*|feasible|visibility|target\w*|miss\w*)\b"),
    "cadbench": (r"\b(?:CAD|FreeCAD|parametric|drawing\w*|geometry|fixtures?)\b",
                 r"\b(?:edit\w*|regenerat\w*|dimension\w*|tolerance\w*|rebuild\w*|fit|geometry|metrology)\b"),
    "flash": (r"\b(?:proof\w*|prover|committed|commitment\w*|verifier)\b",
              r"\b(?:verify|verif\w*|tamper\w*|chang\w*|mismatch\w*|commit\w*|proving|CPU|latency)\b"),
    "ecmwf": (r"\b(?:weather|meteorolog\w*|forecast\w*|atmospher\w*)\b",
              r"\b(?:missing|gap\w*|omit\w*|station\w*|observations?|availability|prior|hold\w*|error\w*)\b"),
    "evolve-source": (r"\b(?:kernels?|optimization|optimisation|optimizer|algorithm\w*|parallel|numerical|batch\w*|candidate\w*)\b",
                      r"\b(?:search|throughput|parall\w*|cpu|benchmark\w*|error|evalua\w*|invariant\w*|recurr\w*|compute|rank\w*)\b"),
}


def packet():
    raw = (HERE / "open_mission.json").read_bytes()
    if protocol.digest(raw) != PACKET:
        raise ValueError("Registered open mission packet changed")
    value = json.loads(raw)
    for row in value["sources"]:
        record = protocol.sources()[row["source"]]
        if protocol.digest(row["fragment"].encode()) != record["excerpt_sha256"]:
            raise ValueError("Open mission source identity changed")
    return value


def prepared_packet():
    value = packet()
    inputs = {protocol.record_key(row["url"]): row for row in protocol.inputs()}
    for source in value["sources"]:
        fact = protocol.observe(inputs[source["source"]])
        source["independently_parsed_premise"] = {k: fact[k] for k in ("metric", "value", "scope")}
    return value


def score(response, withdrawn=()):
    if not isinstance(response, dict) or not isinstance(response.get("candidates"), list):
        return {"format": "failed", "rows": [], "registered_slots": 5}
    candidates = response["candidates"]
    if len(candidates) > 5:
        return {"format": "failed", "rows": [], "registered_slots": 5}
    rows = []
    lookup = {protocol.record_key(s["url"]): s for s in protocol.inputs()}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            rows.append({"source": None, "eligible_id": False, "binding": "invalid_candidate",
                         "action_domains": [], "is_material": None})
            continue
        key = candidate.get("source")
        signal = lookup.get(key) if isinstance(key, str) and key not in withdrawn else None
        if signal:
            signal = dict(signal, id=key)
        claim = {k: candidate[k] for k in ("source", "metric", "value", "scope", "unit") if k in candidate}
        # The original proposal's action, experiment and alternative are recorded separately.
        # The published-source contract asks what WAS observed, so polarity must be positive.
        claim["polarity"] = candidate.get("polarity", "asserted")
        observed = protocol.observe(signal) if signal else None
        fact_status = protocol.binding(claim, observed)
        bound = fact_status == "supported"
        prose = " ".join(item for item in (candidate.get("action"), candidate.get("test")) if isinstance(item, str))
        domains = [domain for domain, patterns in USES.items()
                   if all(re.search(pattern, prose, re.I) for pattern in patterns)]
        if not bound:
            material = False
        elif len(domains) != 1:
            material = None
        else:
            material = key == domains[0]
        status = fact_status if fact_status in {"supported", "rounded_consistent"} else (
            "unsupported_value_or_scope" if signal else "no_eligible_source")
        rows.append({"source": key, "eligible_id": bool(signal), "binding": status,
                     "action_domains": domains, "is_material": material})
    return {"format": "complete", "registered_slots": 5, "returned": len(candidates), "rows": rows}


def compare(response):
    original = score(response)
    counterfactuals = {}
    for key in sorted({r["source"] for r in original["rows"] if r["eligible_id"]}):
        counterfactuals[key] = [r["binding"] for r in score(response, withdrawn={key})["rows"]]
    # True-but-immaterial positive control. Substitute a genuine measurement
    # from a different registered domain, keeping the proposal/action/test intact.
    swap = None
    if original["rows"] and original["rows"][0].get("is_material") is True:
        first = response["candidates"][0]
        alternate = next(s for s in protocol.inputs() if protocol.record_key(s["url"]) != first["source"])
        other = protocol.record_key(alternate["url"])
        fact = protocol.observe(dict(alternate, id=other))
        changed = dict(first, **{k: fact[k] for k in ("source", "metric", "value", "scope")})
        swap = score({"candidates": [changed]})["rows"][0]
    return {"original": original, "withdrawal": counterfactuals, "true_but_unrelated_first_case": swap}
