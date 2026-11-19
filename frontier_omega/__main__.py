"""FRONTIER Ω: a cost-aware, source-bound living opportunity inventory.

No paid API calls, private-data collection, production actions or sales authority.
A technical crossing is only a reported result pending receipt-level audit.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
CUTOFF = date.fromisoformat("2026-10-12")
DIMENSIONS = (
    "buyer_urgency", "autonomy_fit", "acceptance_clarity", "repeatability",
    "differentiation", "capital_intensity", "sales_friction",
)
COST_CATEGORIES = (
    "model_compute", "software_tools", "human_work", "independent_verification",
    "retries_failures", "acquisition", "onboarding", "support_maintenance",
    "overhead", "financing", "refunds_disputes", "residual_obligations",
)
WATCH_SOURCES = {
    "openai_releases": "https://openai.com/news/product-releases/",
    "anthropic_news": "https://www.anthropic.com/news",
    "google_deepmind": "https://deepmind.google/blog/",
}
# A changed page is not a newly available capability. Never execute page content.
WATCH_HOSTS = {urlparse(v).hostname for v in WATCH_SOURCES.values()}
MAX_BODY = 1_000_000


class InventoryError(ValueError):
    pass


def read_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(root: Path = ROOT):
    catalog = read_json(root / "opportunities.json")
    source_data = read_json(root / "signals.json")
    if catalog.get("schema") != "frontier-omega-opportunities/v1":
        raise InventoryError("Unexpected opportunity schema")
    if source_data.get("schema") != "frontier-omega-signals/v1":
        raise InventoryError("Unexpected signal schema")
    signals = {s["id"]: s for s in source_data["signals"]}
    if len(signals) != len(source_data["signals"]):
        raise InventoryError("Duplicate signal IDs")
    for signal in source_data["signals"]:
        if not urlparse(signal["url"]).scheme == "https":
            raise InventoryError("Signal URL is not HTTPS")
        date.fromisoformat(signal["date"])
    opportunities = catalog["results"]
    ids = set()
    for o in opportunities:
        if o["id"] in ids:
            raise InventoryError("Duplicate opportunity ID: " + o["id"])
        ids.add(o["id"])
        for key in ("id", "engine", "title", "buyer", "blocked_problem",
                    "deliverable", "acceptance_test", "strongest_complete_alternative",
                    "first_discriminating_test"):
            if not isinstance(o.get(key), str) or not o[key].strip():
                raise InventoryError(o["id"] + ": missing " + key)
        if o["engine"] not in {"MIGRATE", "PROVE", "OPERATE", "TRUST", "ENGINEER", "DISCOVER", "COMPUTE"}:
            raise InventoryError(o["id"] + ": unknown engine")
        if not o["frontier_signal_ids"] or any(x not in signals for x in o["frontier_signal_ids"]):
            raise InventoryError(o["id"] + ": unknown/missing source signal")
        if o["initial_state"] != "WATCH_NO_MATCHED_BENCHMARK" or o["observed_paid_demand"] != "NONE":
            raise InventoryError(o["id"] + ": seed cannot claim a verified crossing or revenue")
        if o["pilot_quote_status"] != "UNTESTED_PRICE_HYPOTHESIS_NOT_A_CUSTOMER_OFFER":
            raise InventoryError(o["id"] + ": price cannot be presented as observed")
        if type(o["pilot_quote_usd_hypothesis"]) not in (int, float) or o["pilot_quote_usd_hypothesis"] <= 0:
            raise InventoryError(o["id"] + ": invalid proposed pilot price")
        d = o["ordinal_hypotheses"]
        if set(d) != set(DIMENSIONS) or any(type(d[k]) is not int or not 1 <= d[k] <= 5 for k in DIMENSIONS):
            raise InventoryError(o["id"] + ": ordinal dimensions must be integers 1..5")
        t = o["crossing_threshold"]
        if type(t["minimum_matched_cases"]) is not int or t["minimum_matched_cases"] <= 0:
            raise InventoryError(o["id"] + ": min cases invalid")
        if not 0 < t["minimum_acceptance_fraction"] <= 1:
            raise InventoryError(o["id"] + ": target acceptance invalid")
        if t["max_complete_cost_per_accepted_usd"] <= 0 or t["max_p95_turnaround_hours"] <= 0:
            raise InventoryError(o["id"] + ": invalid cost/time ceiling")
    return opportunities, signals


def score(o):
    """Editorial triage, not expected profit or objective market probability."""
    d = o["ordinal_hypotheses"]
    return (4*d["buyer_urgency"] + 3*d["autonomy_fit"] +
            4*d["acceptance_clarity"] + 3*d["repeatability"] +
            3*d["differentiation"] - 2*d["capital_intensity"] -
            2*d["sales_friction"])


def rank(opportunities):
    return sorted(opportunities, key=lambda o: (-score(o), o["id"]))


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _run(run, o):
    if type(run) is not dict:
        raise InventoryError("Benchmark run must be an object")
    if type(run.get("cases")) is not int or run["cases"] < o["crossing_threshold"]["minimum_matched_cases"]:
        raise InventoryError("Too few matched cases")
    if type(run.get("accepted")) is not int or not 0 <= run["accepted"] <= run["cases"]:
        raise InventoryError("Invalid acceptance numerator")
    if type(run.get("p95_turnaround_hours")) not in (int, float) or run["p95_turnaround_hours"] < 0:
        raise InventoryError("Missing/invalid p95 time")
    costs = run.get("costs_usd")
    if type(costs) is not dict or set(costs) != set(COST_CATEGORIES):
        raise InventoryError("All full-lifecycle cost categories required")
    if any(type(v) not in (int, float) or v < 0 for v in costs.values()):
        raise InventoryError("Cost categories must be finite nonnegative numbers")
    if any(v != v or v == float("inf") for v in costs.values()):
        raise InventoryError("Non-finite costs")
    complete_cost = sum(costs.values())
    cost_per_accepted = complete_cost / run["accepted"] if run["accepted"] else float("inf")
    threshold = o["crossing_threshold"]
    passed = (run["accepted"] / run["cases"] >= threshold["minimum_acceptance_fraction"]
              and cost_per_accepted <= threshold["max_complete_cost_per_accepted_usd"]
              and run["p95_turnaround_hours"] <= threshold["max_p95_turnaround_hours"])
    return {
        "pass": passed, "cases": run["cases"], "accepted": run["accepted"],
        "acceptance_fraction": round(run["accepted"] / run["cases"], 5),
        "complete_cost_usd": round(complete_cost, 2),
        "complete_cost_per_accepted_usd": round(cost_per_accepted, 2) if run["accepted"] else None,
        "p95_turnaround_hours": run["p95_turnaround_hours"],
    }


def assess_one(o, evidence):
    """Detect a *reported* before/after threshold crossing; do not certify receipts."""
    if evidence.get("opportunity_id") != o["id"]:
        raise InventoryError("Opportunity ID mismatch")
    if evidence.get("synthetic") is True:
        return {"opportunity_id": o["id"], "stage": "SYNTHETIC_REHEARSAL_ONLY"}
    if evidence.get("synthetic") is not False:
        raise InventoryError("Explicit synthetic flag required")
    if not _sha(evidence.get("task_suite_sha256")):
        raise InventoryError("Exact task-suite SHA256 required")
    if evidence.get("same_frozen_suite") is not True:
        raise InventoryError("New and old runs must use the same frozen suite")
    baseline, current = evidence["baseline"], evidence["current"]
    old_date, new_date = date.fromisoformat(baseline["date"]), date.fromisoformat(current["date"])
    if not old_date < CUTOFF <= new_date:
        raise InventoryError("Original baseline before Oct 12 and fresh run afterward required")
    if baseline["cases"] != current["cases"]:
        raise InventoryError("Matched case counts required")
    old, new = _run(baseline, o), _run(current, o)
    if not new["pass"]:
        stage = "BLOCKED_CURRENT_BELOW_ACCEPTANCE_COST_OR_TIME_GATE"
    elif old["pass"]:
        stage = "QUALIFIED_BUT_NO_NEW_FIVE_WEEK_CROSSING"
    else:
        stage = "REPORTED_NEW_TECHNICAL_CROSSING_AUDIT_REQUIRED"
    review = evidence.get("review", {})
    if stage.startswith("REPORTED_NEW") and (review.get("independent_verifier") is not True
         or not str(review.get("report_url", "")).startswith("https://")):
        stage = "UNINDEPENDENT_CROSSING_REPORT_NEEDS_VERIFIER"
    sale = evidence.get("sale")
    if stage == "REPORTED_NEW_TECHNICAL_CROSSING_AUDIT_REQUIRED" and sale:
        if (sale.get("buyer_accepted") is True and sale.get("collected") is True
                and sale.get("all_residual_obligations_costed") is True
                and type(sale.get("actual_collected_usd")) in (int, float)
                and sale["actual_collected_usd"] > new["complete_cost_usd"]
                and str(sale.get("receipt_url", "")).startswith("https://")):
            stage = "REPORTED_PAID_OUTCOME_AUDIT_REQUIRED"
    return {
        "opportunity_id": o["id"], "stage": stage, "old": old, "current": new,
        "fresh_reproduction": "NOT_INDEPENDENTLY_PERFORMED_BY_THIS_CLI",
        "commercial_status": "UNVERIFIED_EXTERNALLY",
        "warning": "JSON fields and URLs are not evidence by themselves. Auditor must inspect actual artifacts, receipts, payments and permissions.",
    }


def assess(opportunities, evidence_rows):
    by_id = {o["id"]: o for o in opportunities}
    seen, reports = set(), []
    for row in evidence_rows:
        oid = row.get("opportunity_id")
        if oid in seen or oid not in by_id:
            raise InventoryError("Duplicate or unknown opportunity in evaluation input")
        seen.add(oid)
        reports.append(assess_one(by_id[oid], row))
    return reports


def watch_diff(old_hashes, new_hashes):
    changes = []
    for name, value in new_hashes.items():
        prior = old_hashes.get(name)
        if prior is None:
            changes.append({"source": name, "event": "INITIAL_OBSERVATION_NOT_A_NEW_RELEASE"})
        elif prior != value:
            changes.append({"source": name, "event": "PAGE_BYTES_CHANGED_REVIEW_REQUIRED"})
    return changes


class _OnlyAllowedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urlparse(newurl)
        if p.scheme != "https" or p.hostname not in WATCH_HOSTS or p.port not in (None, 443):
            raise InventoryError("Redirect outside allowlisted official hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch_hash(url):
    p = urlparse(url)
    if p.scheme != "https" or p.hostname not in WATCH_HOSTS or p.port not in (None, 443):
        raise InventoryError("Unsupported source URL")
    opener = build_opener(_OnlyAllowedRedirect())
    req = Request(url, headers={"User-Agent": "AGI-Alpha-Frontier-Omega-SourceWatch/1.0", "Accept": "text/html,application/xml,text/xml"})
    with opener.open(req, timeout=12) as response:
        raw = response.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise InventoryError("Source body exceeds bounded monitoring limit")
        return hashlib.sha256(raw).hexdigest()


def watch(state_file: Path, output_file: Path):
    previous = read_json(state_file) if state_file.exists() else {"hashes": {}}
    old_hashes = previous.get("hashes", {})
    if not isinstance(old_hashes, dict):
        raise InventoryError("Invalid previous monitoring state")
    hashes = dict(old_hashes)
    errors = {}
    for source, url in WATCH_SOURCES.items():
        try:
            hashes[source] = _fetch_hash(url)
        except Exception as exc:
            errors[source] = type(exc).__name__ + ": " + str(exc)[:200]
    changes = watch_diff(old_hashes, {k: v for k, v in hashes.items() if k not in errors})
    stamp = datetime.now(timezone.utc).isoformat()
    out = {"schema": "frontier-omega-watch/v1", "checked_at_utc": stamp,
           "sources": WATCH_SOURCES, "events": changes, "failures": errors,
           "qualification": "SOURCE_CHANGE_ONLY_NO_CAPABILITY_OR_COMMERCIAL_PROMOTION"}
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    state_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = state_file.with_suffix(".next")
    temporary.write_text(json.dumps({"hashes": hashes, "updated_at_utc": stamp}, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, state_file)
    return out


def export_csv(opportunities, stream):
    fields = ("id", "engine", "title", "buyer", "blocked_problem", "deliverable",
              "acceptance_test", "strongest_complete_alternative",
              "first_discriminating_test", "pilot_quote_usd_hypothesis", "priority_score",
              "initial_state")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for o in rank(opportunities):
        writer.writerow({**o, "priority_score": score(o)})


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="FRONTIER Ω living buyer-problem inventory; source changes never imply successful crossings")
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("validate")
    ranked = subs.add_parser("rank")
    ranked.add_argument("--limit", type=int, default=15)
    ranked.add_argument("--json", action="store_true")
    subs.add_parser("export-csv")
    evaluated = subs.add_parser("assess")
    evaluated.add_argument("--evidence", type=Path, required=True, help="JSON list of separately obtained benchmark records")
    watching = subs.add_parser("watch")
    watching.add_argument("--state", type=Path, required=True)
    watching.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    opportunities, signals = validate()
    if args.command == "validate":
        print(json.dumps({"valid": True, "opportunities": len(opportunities),
                          "signals": len(signals), "paid_outcomes": 0,
                          "technical_crossings": "NOT_ESTABLISHED"}))
    elif args.command == "rank":
        rows = [{"id": o["id"], "engine": o["engine"], "title": o["title"],
                 "triage_score_not_roi": score(o), "pilot_price_hypothesis_usd": o["pilot_quote_usd_hypothesis"],
                 "stage": o["initial_state"], "next_test": o["first_discriminating_test"]}
                for o in rank(opportunities)[:args.limit]]
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            for r in rows:
                print(f'{r["id"]} [{r["engine"]}] ({r["triage_score_not_roi"]}) {r["title"]}: {r["next_test"]}')
    elif args.command == "export-csv":
        export_csv(opportunities, sys.stdout)
    elif args.command == "assess":
        input_rows = read_json(args.evidence)
        if not isinstance(input_rows, list):
            raise InventoryError("Evidence root must be an array")
        print(json.dumps(assess(opportunities, input_rows), indent=2))
    elif args.command == "watch":
        print(json.dumps(watch(args.state, args.out), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (InventoryError, KeyError, TypeError, OSError) as error:
        print("FRONTIER Ω validation failed: " + str(error), file=sys.stderr)
        sys.exit(2)
