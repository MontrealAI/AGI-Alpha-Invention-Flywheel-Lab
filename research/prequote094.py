"""Read-only value-of-prequote-information frontier; never a native spending authority.

All probability grid points are uncalibrated hypotheses. The only observed inputs
are five previously exposed simulated native-account summaries.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "campaign/omega-paid-reach-20261104/PAIRED_EVIDENCE.json"
SOURCE_SHA256 = "b646d9ec901f6c71ff6ebe2ee6717387b55f47aa9f60a623a2b2c16cfc3acbcb"
CASES = ("central", "weak", "copycat", "no_demand", "failed_activation")
EXPECTED_DELTAS = (205112000, -7160000, -7160000, -7160000, -5000000)
OPENING = 100000000000
USD = 1000000
GRIDS = {
    "central_prior": (Fraction(0), Fraction(1, 10), Fraction(1, 2), Fraction(1)),
    "sensitivity": (Fraction(0), Fraction(1, 2), Fraction(1)),
    "false_positive_rate": (Fraction(0), Fraction(1, 10), Fraction(1)),
    "screen_cost_usd": (0, 1, 10),
}


def unique(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("DUPLICATE_JSON_KEY")
        d[k] = v
    return d


def integer(n):
    if type(n) is not int:
        raise ValueError("INTEGER_REQUIRED")
    return n


def source_cases(raw: bytes, expected_sha: str = SOURCE_SHA256):
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("SOURCE_SHA256_MISMATCH")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda z: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    if (data.get("schema") != "omega/earned-paid-reach-paired-evidence/v1"
            or data.get("window_days") != [0, 365]
            or data.get("end_day_exclusive") is not True
            or integer(data["opening_microUSD_each"]) != OPENING
            or type(data.get("actual_revenue_usd")) is not int
            or data["actual_revenue_usd"] != 0
            or data.get("actual_complete_lifecycle_cost_usd") is not None
            or type(data.get("pairs")) is not dict
            or set(data["pairs"]) != set(CASES)):
        raise ValueError("FROZEN_SCOPE_CHANGED")
    results = {}
    for case, expected in zip(CASES, EXPECTED_DELTAS):
        row = data["pairs"][case]
        ledgers = []
        for arm in ("organic", "pilot"):
            r = row[arm]
            if (r.get("native_audit_accepted") is not True
                    or not r.get("audit_receipt_sha256")
                    or not r.get("artifact_file_sha256")):
                raise ValueError("UNVERIFIED_NATIVE_EXPORT:" + case + ":" + arm)
            f = r["financial_microUSD"]
            costs = r["incurred_expense_breakdown_microUSD"]
            if any(integer(v) < 0 for v in costs.values()) or sum(costs.values()) != integer(f["incurred_expenses_including_tax"]):
                raise ValueError("INCORRECT_COSTS:" + case + ":" + arm)
            if (integer(f["recognized_revenue"]) + integer(f["recovery_income"]) -
                    integer(f["incurred_expenses_including_tax"]) != integer(f["profit_after_modeled_tax"])):
                raise ValueError("INCORRECT_PROFIT:" + case + ":" + arm)
            if (OPENING + integer(f["collections"]) + integer(f["recovery_income"]) -
                    integer(f["cash_expenses_paid"]) != integer(f["cash"])):
                raise ValueError("INCORRECT_CASH:" + case + ":" + arm)
            reserves = ("tail_reserve", "working_capital", "custody_reserve", "custody_restricted", "reserved_investment")
            if integer(f["cash"]) - sum(integer(f[k]) for k in reserves) != integer(f["available_cash"]):
                raise ValueError("INCORRECT_PROTECTION:" + case + ":" + arm)
            ledgers.append(f)
        a, b = ledgers
        delta = integer(b["profit_after_modeled_tax"]) - integer(a["profit_after_modeled_tax"])
        if delta != expected:
            raise ValueError("FROZEN_RESULT_CHANGED:" + case)
        comp = row["comparison"]["pilot_minus_organic_financial_microUSD"]
        for field in ("profit_after_modeled_tax", "cash", "available_cash", "collections",
                      "recognized_revenue", "incurred_expenses_including_tax", "tail_reserve"):
            if integer(b[field]) - integer(a[field]) != integer(comp[field]):
                raise ValueError("COMPARISON_MISMATCH:" + case + ":" + field)
        results[case] = {
            "pilot_minus_organic_aftertax_microUSD": delta,
            "organic_aftertax_profit_microUSD": integer(a["profit_after_modeled_tax"]),
            "pilot_aftertax_profit_microUSD": integer(b["profit_after_modeled_tax"]),
            "native_pair_previously_audited": True,
        }
    return results


def as_fraction(f):
    return {"numerator": f.numerator, "denominator": f.denominator}


def choose_policy(p: Fraction, tpr: Fraction, fpr: Fraction, screen_cost_microUSD: int,
                  good: int = EXPECTED_DELTAS[0], loss: int = max(-v for v in EXPECTED_DELTAS[1:])):
    """Exact finite-game maximum. Strong competitor may ignore or invert the signal."""
    if not all(isinstance(x, Fraction) and 0 <= x <= 1 for x in (p, tpr, fpr)):
        raise ValueError("INVALID_PROBABILITY")
    if integer(screen_cost_microUSD) < 0 or good <= 0 or loss < 0:
        raise ValueError("INVALID_MODEL")
    c = Fraction(screen_cost_microUSD)
    values = {
        "NO_NEW_CHANNEL": Fraction(0),
        "UNSCREENED_PILOT": p * good - (1 - p) * loss,
        "SCREEN_BUY_POSITIVE": p * tpr * good - (1 - p) * fpr * loss - c,
        "SCREEN_BUY_NEGATIVE": p * (1 - tpr) * good - (1 - p) * (1 - fpr) * loss - c,
    }
    maximum = max(values.values())
    precedence = ("NO_NEW_CHANNEL", "UNSCREENED_PILOT", "SCREEN_BUY_POSITIVE", "SCREEN_BUY_NEGATIVE")
    chosen = next(name for name in precedence if values[name] == maximum)
    oracle = p * good
    if maximum > oracle:
        raise ValueError("ORACLE_BOUND_VIOLATED")
    return {
        "finite_game_optimal_policy_HYPOTHETICAL": chosen,
        "worst_adverse_conditional_assumption_microUSD": loss,
        "policy_payoffs_microUSD_exact": {k: as_fraction(v) for k, v in values.items()},
        "best_payoff_microUSD_exact": as_fraction(maximum),
        "unattainable_perfect_oracle_upper_microUSD_exact": as_fraction(oracle),
        "known_signal_calibration": False,
        "authorize_purchase": False,
    }


def certify(raw: bytes, expected_sha: str = SOURCE_SHA256):
    cases = source_cases(raw, expected_sha)
    good = cases["central"]["pilot_minus_organic_aftertax_microUSD"]
    loss = max(-r["pilot_minus_organic_aftertax_microUSD"] for k, r in cases.items() if k != "central")
    if (good, loss) != (205112000, 7160000):
        raise ValueError("FROZEN_DATA_CHANGED")
    rows = []
    wins = {k: 0 for k in ("NO_NEW_CHANNEL", "UNSCREENED_PILOT", "SCREEN_BUY_POSITIVE", "SCREEN_BUY_NEGATIVE")}
    for p in GRIDS["central_prior"]:
        for tpr in GRIDS["sensitivity"]:
            for fpr in GRIDS["false_positive_rate"]:
                for cost_usd in GRIDS["screen_cost_usd"]:
                    choice = choose_policy(p, tpr, fpr, cost_usd * USD, good, loss)
                    wins[choice["finite_game_optimal_policy_HYPOTHETICAL"]] += 1
                    rows.append({
                        "central_prior_UNCALIBRATED": as_fraction(p),
                        "sensitivity_UNCALIBRATED": as_fraction(tpr),
                        "false_positive_rate_UNCALIBRATED": as_fraction(fpr),
                        "screen_cost_usd_UNCALIBRATED": cost_usd,
                        **choice,
                    })
    assert len(rows) == 108
    return {
        "schema": "agi-alpha/prequote094-conditional-information/v1",
        "source_sha256": expected_sha,
        "source_commit": "4abbb85893c9c073ca092db4ad858f7bb156dc35",
        "source_window_days": [0, 365],
        "historical_simulated_account_count": 10, "new_native_account_count": 0,
        "cases": cases, "registered_grid_size": len(rows), "registered_grid": rows,
        "illustrative_winner_counts_not_evidence_of_demand": wins,
        "maximin_unscreened_incremental_microUSD": min(r["pilot_minus_organic_aftertax_microUSD"] for r in cases.values()),
        "maximin_organic_incremental_microUSD": 0,
        "strongest_no_information_robust_policy": "NO_NEW_CHANNEL",
        "perfect_classifier_min_incremental_before_signal_cost_microUSD": 0,
        "perfect_classifier_adverse_any_positive_cost_causes_loss": True,
        "real_world_signal_exists": None, "prior_type_frequencies": None,
        "signal_quality_measurements": None, "supplier_willingness_and_outside_option": None,
        "competent_human_and_AI_complete_offer_costs": None,
        "actual_annual_profit_usd": None, "actual_new_revenue_usd": 0,
        "target_3b_achieved": False, "decision": "NO_NEW_CHANNEL_COMMITMENT",
        "causal_scope": "FROZEN_EXPOSED_NATIVE_OUTCOME_BOUNDS_AND_UNCALIBRATED_BAYESIAN_HYPOTHESES_ONLY",
        "audit_boundary": "THE_CURRENT_PRIVATE_ACCOUNT_AUTHORITY_WAS_NOT_ACCESSED_OR_CHANGED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.resolve() == args.source.resolve():
        raise ValueError("SOURCE_OVERWRITE_FORBIDDEN")
    result = certify(args.source.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
