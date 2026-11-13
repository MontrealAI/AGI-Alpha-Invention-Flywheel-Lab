"""Independent versioned content-continuity guard for source-first accessibility.

The original Gate148 proves only structural invariants. This additive review
makes a stricter and *different* release decision: no automatic carry-forward
when ANY authored content changes. Identical authored content is not semantic
truth, WCAG conformance or assistive-technology acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from research.accessible_output148 import gate

SCHEMA = "agi-alpha/accessibility149/continuity-review-v1"
IGNORED_UNVERIFIED_FIELDS = frozenset({"model_label"})


def content_digest(record):
    """Exact authored-content equality, not a semantic equivalence oracle."""
    copy = dict(record)
    for field in IGNORED_UNVERIFIED_FIELDS:
        copy.pop(field, None)
    return hashlib.sha256(gate.canonical(copy)).hexdigest()


def inspect(baseline, candidate):
    """Require previously audited triplets; never promote unreviewed changes."""
    structural = gate.compare_bytes(baseline, candidate)
    a = gate.strict_load(baseline[0])
    b = gate.strict_load(candidate[0])
    digest_a, digest_b = content_digest(a), content_digest(b)
    changed = digest_a != digest_b
    return {
        "schema": SCHEMA,
        "document_id": structural["baseline"] and a["document_id"],
        "baseline_authored_content_sha256": digest_a,
        "candidate_authored_content_sha256": digest_b,
        "authored_content_changed": changed,
        "structural_gate": structural["verdict"],
        "continuity_verdict": (
            "HOLD_AUTHORED_CONTENT_CHANGED_REVIEW_REQUIRED"
            if changed else "PASS_EXACT_AUTHORED_CONTENT_CONTINUITY_ONLY"
        ),
        "automatic_content_carryforward": not changed,
        "model_identity_verified": False,
        "semantic_truth_verified": False,
        "screen_reader_tested": False,
        "wcag_conformance_verified": False,
        "customer_acceptance_verified": False,
        "commercial_benefit_verified": False,
        "deployment_authorized": False,
        "requires_independent_semantic_and_assistive_review": True,
    }


def read_triplet(path):
    root = Path(path)
    return tuple((root / name).read_bytes() for name in
                 ("RECORD.json", "DOCUMENT.html", "RECEIPT.json"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    result = inspect(read_triplet(args.baseline), read_triplet(args.candidate))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
