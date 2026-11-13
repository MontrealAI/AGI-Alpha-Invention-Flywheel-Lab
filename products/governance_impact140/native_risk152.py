"""Native, offline *synthetic* data/model/output quality signals, never compliance approval.

Governance research dependency 152: first-party measurements from raw authored rows.
No third-party evaluators, network, signing keys, private data or original native accounts.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "agi-alpha/native-risk152/input-v1"
RESULT_SCHEMA = "agi-alpha/native-risk152/result-v1"
REQUIRED_THRESHOLDS = {
    "max_missing_label_rate", "min_accuracy", "max_tpr_gap",
    "max_flip_rate", "max_claimed_violation_rate", "min_group_positives",
}
SCORE_NAMES = (
    "missing_label_rate", "accuracy", "tpr_gap",
    "flip_rate", "claimed_violation_rate",
)
DECIMAL = re.compile(r"(?:0(?:\.[0-9]+)?|1(?:\.0+)?)\Z")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _ratio(x: Fraction):
    return {"numerator": x.numerator, "denominator": x.denominator}


def _require_exact_dict(value, fields, code):
    if type(value) is not dict or set(value) != fields:
        raise ValueError(code)


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 160


def _decimal(value):
    if type(value) is not str or DECIMAL.fullmatch(value) is None:
        raise ValueError("INVALID_EXACT_THRESHOLD")
    return Fraction(value)


def _bit(value, optional=False):
    if optional and value is None:
        return None
    if type(value) is not int or value not in (0, 1):
        raise ValueError("INVALID_BINARY_OBSERVATION")
    return value


def evaluate(data):
    """Compute conservative exact metrics from explicit authored observations.

    A threshold signal is *not* a conformity/compliance or real-world performance
    verdict. Missing source observations remain unqualified; claims aren't verified.
    """
    _require_exact_dict(data, {"schema", "system_id", "thresholds", "rows"},
                        "INVALID_NATIVE_RISK_INPUT_SCHEMA")
    if data["schema"] != SCHEMA or not _nonempty(data["system_id"]):
        raise ValueError("INVALID_NATIVE_RISK_IDENTITY")
    thresholds = data["thresholds"]
    _require_exact_dict(thresholds, REQUIRED_THRESHOLDS,
                        "INVALID_NATIVE_RISK_THRESHOLDS")
    limits = {name: _decimal(thresholds[name]) for name in REQUIRED_THRESHOLDS
              if name != "min_group_positives"}
    minimum = thresholds["min_group_positives"]
    if type(minimum) is not int or not 1 <= minimum <= 1000000:
        raise ValueError("INVALID_MIN_GROUP_POSITIVES")
    rows = data["rows"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("NONEMPTY_NATIVE_RISK_ROWS_REQUIRED")
    normalized = []
    ids = set()
    ignored_reviews = 0
    for row in rows:
        if type(row) is not dict or not {"case_id", "truth", "prediction", "group",
                                         "repeat_prediction", "claimed_violation"} <= set(row) \
                or not set(row) <= {"case_id", "truth", "prediction", "group",
                                       "repeat_prediction", "claimed_violation", "claimed_review"}:
            raise ValueError("INVALID_NATIVE_RISK_ROW_SCHEMA")
        ident = row["case_id"]
        if not _nonempty(ident) or ident in ids:
            raise ValueError("DUPLICATE_OR_INVALID_CASE_ID")
        ids.add(ident)
        _bit(row["truth"], optional=True)
        _bit(row["prediction"])
        _bit(row["repeat_prediction"], optional=True)
        group = row["group"]
        if group is not None and not _nonempty(group):
            raise ValueError("INVALID_GROUP_LABEL")
        if type(row["claimed_violation"]) is not bool:
            raise ValueError("INVALID_UNVERIFIED_POLICY_FLAG")
        if "claimed_review" in row:
            if not _nonempty(row["claimed_review"]):
                raise ValueError("INVALID_UNTRUSTED_REVIEW_CLAIM")
            ignored_reviews += 1
        normalized.append(dict(row))
    normalized.sort(key=lambda row: row["case_id"])
    n = len(normalized)
    incomplete_truth = sum(row["truth"] is None for row in normalized)
    incomplete_repeat = sum(row["repeat_prediction"] is None for row in normalized)
    violations = sum(row["claimed_violation"] for row in normalized)
    flips = sum(row["prediction"] != row["repeat_prediction"]
                for row in normalized if row["repeat_prediction"] is not None)
    correct = sum(row["truth"] == row["prediction"] for row in normalized
                  if row["truth"] is not None)
    # Count every observed group, including groups without positive labels.
    # Otherwise unsupported groups vanish and TPR clearance can be fabricated.
    group_counts = {group: 0 for group in sorted({
        row["group"] for row in normalized if row["group"] is not None
    })}
    group_hits = dict.fromkeys(group_counts, 0)
    for row in normalized:
        if row["truth"] == 1 and row["group"] is not None:
            g = row["group"]
            group_counts[g] += 1
            group_hits[g] += (row["prediction"] == 1)
    group_supported = (incomplete_truth == 0 and all(row["group"] is not None for row in normalized)
                       and len(group_counts) >= 2
                       and all(v >= minimum for v in group_counts.values()))
    group_gap = None
    if group_supported:
        rates = [Fraction(group_hits[g], group_counts[g]) for g in group_counts]
        group_gap = max(rates) - min(rates)
    measurements = {
        "missing_label_rate": Fraction(incomplete_truth, n),
        "accuracy": Fraction(correct, n) if incomplete_truth == 0 else None,
        "tpr_gap": group_gap,
        "flip_rate": Fraction(flips, n) if incomplete_repeat == 0 else None,
        "claimed_violation_rate": Fraction(violations, n),
    }
    directions = {
        "missing_label_rate": ("max_missing_label_rate", "max"),
        "accuracy": ("min_accuracy", "min"),
        "tpr_gap": ("max_tpr_gap", "max"),
        "flip_rate": ("max_flip_rate", "max"),
        "claimed_violation_rate": ("max_claimed_violation_rate", "max"),
    }
    signals = {}
    for metric in SCORE_NAMES:
        limit_name, direction = directions[metric]
        observed = measurements[metric]
        within = None if observed is None else (observed >= limits[limit_name] if direction == "min"
                                                  else observed <= limits[limit_name])
        signals[metric] = {
            "observed": _ratio(observed) if observed is not None else None,
            "threshold": _ratio(limits[limit_name]),
            "signal": "UNABLE_TO_DETERMINE" if within is None else
                      "WITHIN_UNVERIFIED_SYNTHETIC_THRESHOLD" if within else
                      "ADVERSE_SYNTHETIC_THRESHOLD",
        }
    report = {
        "schema": RESULT_SCHEMA,
        "scope": "SYNTHETIC_FIRST_PARTY_CALCULATION_ONLY",
        "system_id": data["system_id"],
        "source_input_sha256": digest({**data, "rows": normalized}),
        "case_count": n,
        "observed_denominators": {
            "labeled_cases": n-incomplete_truth, "unlabeled_cases": incomplete_truth,
            "repeat_known_cases": n-incomplete_repeat, "repeat_unknown_cases": incomplete_repeat,
            "positive_cases_per_group": dict(sorted(group_counts.items())),
            "correct_labeled_cases": correct, "claimed_violation_cases": violations,
            "repeated_disagreement_cases": flips,
        },
        "signals": signals,
        "ignored_untrusted_review_claim_count": ignored_reviews,
        "claimed_violation_status": "UNAUTHENTICATED_INPUT_ASSERTION_NOT_SAFETY_TEST",
        "group_metric_scope": "GROUP_TPR_GAP_NOT_FAIRNESS_PROOF",
        "authorization": "NO_REVIEW_NO_COMPLIANCE_NO_REAL_WORLD_PERFORMANCE",
        "limitation": "Only binary labeled examples; no independently authenticated ground truth, policy flags, evaluator, or source",
    }
    report["receipt_sha256"] = digest(report)
    return report


def verify_receipt(report, *, anchored_receipt_sha256, anchored_input_sha256):
    """Fail closed without separately held integrity anchors (not identity authority)."""
    if (not isinstance(anchored_receipt_sha256, str) or not isinstance(anchored_input_sha256, str)
        or not re.fullmatch(r"[0-9a-f]{64}", anchored_receipt_sha256)
        or not re.fullmatch(r"[0-9a-f]{64}", anchored_input_sha256)):
        raise ValueError("INDEPENDENT_ANCHORS_REQUIRED")
    if type(report) is not dict or report.get("source_input_sha256") != anchored_input_sha256:
        raise ValueError("INPUT_ANCHOR_MISMATCH")
    copied = {k: v for k, v in report.items() if k != "receipt_sha256"}
    if digest(copied) != anchored_receipt_sha256 or report.get("receipt_sha256") != anchored_receipt_sha256:
        raise ValueError("RECEIPT_ANCHOR_MISMATCH")
    return True


def _no_duplicates(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    source = Path(args.input)
    dest = Path(args.output)
    if source.resolve() == dest.resolve():
        raise ValueError("INPUT_OUTPUT_MUST_DIFFER")
    raw = source.read_bytes().decode("utf-8", errors="strict")
    data = json.loads(raw, object_pairs_hook=_no_duplicates,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("INVALID_JSON_CONSTANT")))
    result = evaluate(data)
    with dest.open("x", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return result


if __name__ == "__main__":
    main()
