"""Read-only, source-pinned crosswalk: 57 authored research dossiers -> canonical proposals.

This module NEVER opens a Reservoir, account, journal, or network connection. The
canonical reservoir's sole integration owner must separately review each proposal
and any semantic overlap before accepting it. A proposed problem is not a buyer.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from .core import canonical, exact, parse, regular_file, sha, sources, title, validate_problem

STUDY_COMMIT = "41b1b61f17f455189123bbde82497ed8150a7710"
OPP_GIT_BLOB = "ff3deec66229252efca80fed42cbffcdfc243c2c"
SIGNAL_GIT_BLOB = "d3b7133a4453e57732235c5f6dc8266989a51fa6"
STUDY_URL = ("https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/"
             "blob/" + STUDY_COMMIT + "/frontier_omega/opportunities.json")
SOURCE_FIELDS = {"id", "engine", "title", "buyer", "blocked_problem", "deliverable",
                 "acceptance_test", "strongest_complete_alternative",
                 "frontier_signal_ids", "first_discriminating_test",
                 "pilot_quote_usd_hypothesis", "pilot_quote_status",
                 "crossing_threshold", "ordinal_hypotheses", "initial_state",
                 "technical_old_vs_new", "observed_paid_demand",
                 "strict_unattended_autonomy", "customer_authority", "note"}
OPP_ROOT = {"schema", "as_of", "definition", "baseline_cutoff", "currency",
            "pricing_policy", "dimension_policy", "results"}
SIGNAL_ROOT = {"schema", "as_of", "baseline_cutoff", "status", "signals"}
SIGNAL_FIELDS = {"id", "date", "title", "url", "type", "access", "implication",
                 "verified_corpus_date", "reproduced_by_alpha"}
THRESHOLD_FIELDS = {"minimum_matched_cases", "minimum_acceptance_fraction",
                    "max_complete_cost_per_accepted_usd", "max_p95_turnaround_hours"}
ORDINAL_FIELDS = {"buyer_urgency", "autonomy_fit", "acceptance_clarity",
                  "repeatability", "differentiation", "capital_intensity",
                  "sales_friction"}
ENGINES = {"MIGRATE", "PROVE", "OPERATE", "TRUST", "ENGINEER", "DISCOVER", "COMPUTE"}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def pin_input(data: bytes, expected: str) -> None:
    if git_blob(data) != expected:
        raise ValueError("RESEARCH_SOURCE_BLOB_CHANGED")


def review_proposals(opportunities: dict, signals: dict) -> dict:
    """Validate the *source study* and emit immutable, UNIMPORTED canonical drafts."""
    exact(opportunities, OPP_ROOT)
    exact(signals, SIGNAL_ROOT)
    if (opportunities["schema"] != "frontier-omega-opportunities/v1"
            or signals["schema"] != "frontier-omega-signals/v1"
            or opportunities["as_of"] != "2026-11-16"
            or signals["as_of"] != opportunities["as_of"]
            or opportunities["baseline_cutoff"] != "2026-10-12"
            or signals["baseline_cutoff"] != opportunities["baseline_cutoff"]
            or opportunities["currency"] != "USD"):
        raise ValueError("INCOMPATIBLE_STUDY_VERSION_OR_DATE")
    for k in ("definition", "pricing_policy", "dimension_policy"):
        title(opportunities[k])
    title(signals["status"])
    if type(signals["signals"]) is not list or len(signals["signals"]) != 12:
        raise ValueError("EXPECTED_PINNED_SIGNAL_COHORT")
    source_signals = {}
    for signal in signals["signals"]:
        exact(signal, SIGNAL_FIELDS)
        sid = signal["id"]
        if type(sid) is not str or not re.fullmatch(r"S[0-9]{3}", sid) or sid in source_signals:
            raise ValueError("DUPLICATE_OR_INVALID_SIGNAL_ID")
        for key in ("title", "type", "access", "implication"):
            title(signal[key])
        if signal["date"] > opportunities["as_of"] or signal["date"] < "2026-01-01":
            raise ValueError("OUT_OF_WINDOW_SIGNAL")
        if signal["verified_corpus_date"] != opportunities["as_of"] or signal["reproduced_by_alpha"] is not False:
            raise ValueError("SOURCE_CLAIM_CHANGED")
        sources([signal["url"]])
        source_signals[sid] = signal
    if type(opportunities["results"]) is not list or len(opportunities["results"]) != 57:
        raise ValueError("EXPECTED_PINNED_57_STUDY_CASES")
    seen = set()
    converted = []
    index = []
    for record in opportunities["results"]:
        exact(record, SOURCE_FIELDS)
        rid = record["id"]
        if type(rid) is not str or not re.fullmatch(r"O[0-9]{3}", rid) or rid in seen:
            raise ValueError("DUPLICATE_OR_INVALID_STUDY_ID")
        seen.add(rid)
        if record["engine"] not in ENGINES:
            raise ValueError("UNKNOWN_STUDY_ENGINE")
        for k in ("title", "buyer", "blocked_problem", "deliverable",
                  "acceptance_test", "strongest_complete_alternative",
                  "first_discriminating_test", "note"):
            title(record[k])
        if (record["pilot_quote_status"] != "UNTESTED_PRICE_HYPOTHESIS_NOT_A_CUSTOMER_OFFER"
                or record["initial_state"] != "WATCH_NO_MATCHED_BENCHMARK"
                or record["technical_old_vs_new"] != "NOT_TESTED"
                or record["observed_paid_demand"] != "NONE"
                or record["strict_unattended_autonomy"] != "NOT_DEMONSTRATED"
                or record["customer_authority"] != "REQUIRES_CONTRACT_AND_ACCESS"):
            raise ValueError("UNAUTHORIZED_STUDY_CLAIM_PROMOTION")
        if type(record["pilot_quote_usd_hypothesis"]) is not int or record["pilot_quote_usd_hypothesis"] < 0:
            raise ValueError("INVALID_UNTESTED_QUOTE")
        exact(record["crossing_threshold"], THRESHOLD_FIELDS)
        threshold = record["crossing_threshold"]
        if (type(threshold["minimum_matched_cases"]) is not int or threshold["minimum_matched_cases"] < 1
                or type(threshold["minimum_acceptance_fraction"]) not in (float, int)
                or not 0 < threshold["minimum_acceptance_fraction"] <= 1
                or any(type(threshold[k]) not in (int, float) or threshold[k] < 0
                       for k in ("max_complete_cost_per_accepted_usd", "max_p95_turnaround_hours"))):
            raise ValueError("INVALID_PROPOSED_TEST_THRESHOLD")
        exact(record["ordinal_hypotheses"], ORDINAL_FIELDS)
        if any(type(v) is not int or not 1 <= v <= 5 for v in record["ordinal_hypotheses"].values()):
            raise ValueError("INVALID_EDITOR_PRIOR")
        refs = record["frontier_signal_ids"]
        if type(refs) is not list or not refs or len(refs) != len(set(refs)) or any(s not in source_signals for s in refs):
            raise ValueError("UNBOUND_DATED_SOURCE_SIGNAL")
        # Preserve study membership and source identity; do not claim a buyer, price, or verified capability.
        urls = list(dict.fromkeys([STUDY_URL] + [source_signals[s]["url"] for s in refs]))
        problem = {
            "schema": "frontier-omega/problem/v1",
            "id": "study-" + rid.lower() + "-20261116",
            "title": record["title"],
            "beneficiary": record["buyer"],
            "outcome": record["deliverable"],
            "acceptance": record["acceptance_test"],
            "blocker": record["blocked_problem"],
            "tags": [record["engine"].lower(), "research-study"],
            "demand": {
                "status": "HYPOTHESIS",
                "basis": ("Authored study " + rid + " dated 2026-11-16 at pinned commit "
                          + STUDY_COMMIT + ". No observed buyer, price agreement or consent."),
                "ceiling_microUSD": None,
                "deadline": None,
                "terms_sha256": None,
                "consent_verification": "NOT_VERIFIED",
            },
            "alternatives": [
                {"name": "Described complete incumbent", "route": record["strongest_complete_alternative"],
                 "unknowns": "No verified matched complete cost, delivery, availability or quote."},
                {"name": "No purchase", "route": "The beneficiary may decline, defer, or self-service.",
                 "unknowns": "Voluntary buyer choice and opportunity cost not measured."},
            ],
            "source_urls": urls,
            "next_test": record["first_discriminating_test"],
        }
        validate_problem(problem)
        converted.append(problem)
        index.append({"study_id": rid, "candidate_id": problem["id"],
                      "study_record_sha256": sha(record), "candidate_sha256": sha(problem),
                      "semantic_overlap_review_required": True})
    return {
        "schema": "frontier-omega/research-crosswalk-proposals/v1",
        "study_commit": STUDY_COMMIT,
        "source_git_blobs": {"opportunities": OPP_GIT_BLOB, "signals": SIGNAL_GIT_BLOB},
        "case_count": len(converted),
        "signal_count": len(source_signals),
        "candidate_problems": converted,
        "index": index,
        "disposition": "READ_ONLY_UNIMPORTED_REVIEW_ONLY",
        "canonical_reservoir_modified": False,
        "financial_authority": "NONE",
        "actual_buyers_or_paid_outcomes_established": False,
        "caveat": ("Original untested quote hypotheses, ordinal priors and experimental thresholds "
                   "remain in the immutable source study, not in canonical buyer terms. "
                   "An original integration owner must review semantic overlap and provenance before "
                   "any separate canonical import. No automatic account or queue writes."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opportunities", required=True)
    p.add_argument("--signals", required=True)
    args = p.parse_args(argv)
    opportunity_bytes = regular_file(args.opportunities).read_bytes()
    signal_bytes = regular_file(args.signals).read_bytes()
    pin_input(opportunity_bytes, OPP_GIT_BLOB)
    pin_input(signal_bytes, SIGNAL_GIT_BLOB)
    report = review_proposals(parse(opportunity_bytes), parse(signal_bytes))
    report["source_sha256"] = {
        "opportunities": hashlib.sha256(opportunity_bytes).hexdigest(),
        "signals": hashlib.sha256(signal_bytes).hexdigest(),
    }
    sys.stdout.buffer.write(canonical(report) + b"\n")


if __name__ == "__main__":
    main()
