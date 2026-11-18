"""Reconstruct one authorized evidence decision against public source records."""
import argparse
import hashlib
import importlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.path.insert(0, str(PRODUCT))

PROFILES = {
    "ztf-persistence": {
        "beneficiary": "Archival observer reviewing the two ZTF26acbezdh notices",
        "question": "Does the first eligible same-reference ZTF repeat confirm the registered change in positive difference light?",
        "acceptance": "Public program 1, same band, detector and reference, eligible time, original packet and two-sigma and 0.2 mag thresholds.",
        "units": "PSF difference magnitude and formal uncertainty in mag",
        "time_rule": "Right-open event-time cutoff. Receipt-clock replay also requires the frozen sources to have arrived.",
        "routes": ["fink", "alerce"], "acquisition": "Use the retained notice first, then the alternative archive and original packet.",
        "alternative": "Direct ALeRCE TAP and ZTF Avro lookup",
        "actions": {"persisted": "deliver_persistence_measurement", "reversed": "escalate_reversal", "not_reproduced": "close_unconfirmed_change"},
        "adapter": "action_study.ztf"},
    "gw-status": {
        "beneficiary": "Archival observer maintaining a shadow alert review list",
        "question": "Should this LVK public alert remain on the shadow review list at the selected time?",
        "acceptance": "Eligible public actual-event packets, correct event identity, source order and uninterrupted status history.",
        "units": "Publisher alert type, serial and UTC time",
        "time_rule": "Use the selected publisher-issue or demonstrable local-receipt clock.",
        "routes": ["first_notice", "status_history"], "acquisition": "Inspect the original notification, then acquire status revisions if needed.",
        "alternative": "Conventional GCN text bulletin lookup and latest-packet SQL",
        "actions": {"active": "retain_shadow_review", "retracted": "withdraw_shadow_review"}, "adapter": "action_study.observing.adapter"},
    "engineering-qualification": {
        "beneficiary": "MONTREAL.AI selecting the next coding-agent configuration to qualify",
        "question": "Which registered configuration merits the next trial when every benchmark repository receives equal weight?",
        "acceptance": "Pinned 500-issue roster, fixed paired systems, equally weighted repositories and a sign forced by the feasible allocations.",
        "units": "Difference in repository-mean resolved fractions (A minus B)",
        "time_rule": "Frozen public submission and roster revisions. Scope limits the number of repository splits revealed.",
        "routes": ["pooled", "repository_outcomes"], "acquisition": "Try the published totals before reading repository-level outcomes.",
        "alternative": "Complete conventional grouped SQL census",
        "actions": {"A": "qualify_A_next", "B": "qualify_B_next", "tie": "defer_tied_qualification"},
        "adapter": "action_study.qualification_choice.adapter"},
}
FALLBACK = {"pending": "continue_monitoring", "incomplete": "request_missing_evidence",
            "unavailable": "defer_until_access", "contradictory": "escalate_to_review",
            "not_observed_within_qualified_coverage": "close_covered_search"}
NEGATIVE = "not_observed_within_qualified_coverage"


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else encoded(data)).hexdigest()


def instant(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value):
        raise ValueError("Use a full UTC timestamp ending in Z.")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def adapter(profile):
    return importlib.import_module(PROFILES[profile]["adapter"])


def example(profile):
    return {"profile": profile, "scope": adapter(profile).example_scope(), "sources": PROFILES[profile]["routes"].copy()}


def validate(mission):
    if not isinstance(mission, dict) or set(mission) - {"profile", "scope", "sources", "crosscheck"}:
        raise ValueError("Provide a profile, its exact scope and the permitted source routes.")
    profile = mission.get("profile")
    if not isinstance(profile, str) or profile not in PROFILES or not isinstance(mission.get("scope"), dict):
        raise ValueError("Unknown decision profile or invalid scope.")
    scope, routes = mission["scope"], mission.get("sources")
    if not isinstance(routes, list) or any(not isinstance(x, str) or x not in PROFILES[profile]["routes"] for x in routes) or len(set(routes)) != len(routes):
        raise ValueError("Select distinct registered source routes for this purpose.")
    if type(mission.get("crosscheck", False)) is not bool:
        raise ValueError("crosscheck must be a boolean.")
    if profile == "ztf-persistence":
        if set(scope) != {"band", "as_of", "clock"} or scope["band"] not in ("g", "r") or scope["clock"] not in ("event", "received"):
            raise ValueError("Choose a registered g/r notice and an event or receipt clock.")
        instant(scope["as_of"])
    elif profile == "gw-status":
        if set(scope) != {"event", "as_of", "clock"} or not isinstance(scope["event"], str) or not re.fullmatch(r"S\d{6}[a-z]{1,4}", scope["event"]) or scope["clock"] not in ("issued", "received"):
            raise ValueError("Choose an LVK superevent ID and an issue or receipt clock.")
        instant(scope["as_of"])
    elif set(scope) != {"max_repositories"} or type(scope["max_repositories"]) is not int or not 0 <= scope["max_repositories"] <= 12:
        raise ValueError("Choose an integer repository budget from zero to twelve.")
    return PROFILES[profile]


def anchored(evidence):
    for row in evidence:
        if not isinstance(row, dict) or not row.get("publisher") or not (row.get("record_id") or row.get("id")):
            continue
        for source in [row, *row.get("sources", [])]:
            if (isinstance(source, dict) and str(source.get("url", source.get("source_url", ""))).startswith("https://")
                    and re.fullmatch("[0-9a-f]{64}", str(source.get("sha256", "")))):
                return True
    return False


def checked_attempt(raw, rules):
    if not isinstance(raw, dict) or not isinstance(raw.get("reason"), str) or not raw["reason"].strip() or not isinstance(raw.get("evidence"), list):
        raise ValueError("A source returned an incomplete evidence record.")
    state, finding = raw.get("state"), raw.get("finding")
    if state == "observed":
        if finding not in rules["actions"] or not anchored(raw["evidence"]) or not all(isinstance(row, dict) and row for row in raw["evidence"]):
            raise ValueError("A scientific finding requires original source evidence and a registered meaning.")
    elif state not in FALLBACK or finding is not None:
        raise ValueError("Invalid uncertainty state or unsupported action.")
    if state == NEGATIVE:
        c = raw.get("coverage", {})
        if (not isinstance(c, dict) or not all(isinstance(c.get(k), str) and c[k].strip() for k in ("population", "interval", "authority"))
                or type(c.get("expected")) is not int or c["expected"] <= 0 or type(c.get("inspected")) is not int
                or c["inspected"] != c["expected"] or type(c.get("matches")) is not int or c["matches"] != 0
                or not anchored(raw["evidence"])):
            raise ValueError("Absence requires an evidenced complete census of the specified population and interval.")
    return raw


def adjudicate(attempts, rules):
    positives = {(a["state"], a["finding"]) for a in attempts if a["state"] in ("observed", NEGATIVE)}
    if any(a["state"] == "contradictory" for a in attempts) or len(positives) > 1:
        state, finding = "contradictory", None
    elif positives:
        state, finding = positives.pop()
    else:
        state = next((s for s in ("incomplete", "pending", "unavailable") if any(a["state"] == s for a in attempts)), "unavailable")
        finding = None
    return {"state": state, "finding": finding, "action": rules["actions"][finding] if state == "observed" else FALLBACK[state],
            "authority": "recommend_only"}


def case(mission):
    rules = validate(mission)
    source = adapter(mission["profile"])
    attempts = []
    for route in rules["routes"]:
        if route not in mission["sources"]:
            continue
        result = checked_attempt(source.inspect_source(mission["scope"], route), rules)
        if mission["profile"] == "gw-status" and route == "status_history" and result["state"] == "observed" and result["finding"] == "active":
            # The adapter already reconciled an uninterrupted serial prefix against the qualified public index.
            rows = result["evidence"]
            coverage = {"authority": rows[0]["publisher"] if "publisher" in rows[0] else "LVK public VOEvent stream",
                        "population": mission["scope"]["event"] + " indexed public issuer revisions",
                        "interval": rows[0]["issued_utc"] + " through " + mission["scope"]["as_of"],
                        "expected": rows[-1]["serial"], "inspected": len(rows), "matches": sum(r["notice_type"] == "Retraction" for r in rows)}
            absence = checked_attempt({"state": NEGATIVE, "finding": None, "evidence": rows, "coverage": coverage,
                                       "reason": "Zero retraction packets in the reconciled publisher prefix."}, rules)
            result = dict(result, retraction_search={"state": absence["state"], "coverage": coverage})
        attempts.append(dict(result, route=route))
        if result["state"] == "contradictory" or (result["state"] in ("observed", NEGATIVE) and not mission.get("crosscheck")):
            break
    from action_study.pack import computation_files
    files = computation_files(mission["profile"], mission["sources"])
    binding = {path: digest(content) for path, content in sorted(files.items())}
    receipt = {"schema": "frontier.evidence-action/1", "mission": mission, "mission_sha256": digest(mission),
               "contract_sha256": digest(rules), "source_sha256": digest(binding), "attempts": attempts,
               "decision": adjudicate(attempts, rules)}
    return dict(receipt, sha256=digest(receipt))


def verify(receipt, mission=None, expect=None):
    original = case(receipt["mission"] if mission is None else mission)
    if receipt != original or (expect is not None and expect != original["sha256"]):
        raise ValueError("Mission, source or decision differs. Requalify this decision.")
    return original["sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("example")
    show.add_argument("profile", choices=PROFILES)
    run = commands.add_parser("decide")
    run.add_argument("mission", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("receipt", type=Path)
    check.add_argument("--mission", type=Path)
    check.add_argument("--expect")
    args = parser.parse_args()
    if args.command == "example":
        result = example(args.profile)
    elif args.command == "decide":
        result = case(json.loads(args.mission.read_bytes()))
    else:
        result = {"verified": verify(json.loads(args.receipt.read_bytes()), json.loads(args.mission.read_bytes()) if args.mission else None, args.expect)}
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
