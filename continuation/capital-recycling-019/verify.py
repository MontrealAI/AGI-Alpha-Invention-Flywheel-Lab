"""Independent compact verifier for the published capital-recycling result."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "continuation/capital-recycling-019"
RESULT = json.loads((BASE / "RESULT.json").read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_summary(summary):
    assert summary["profit"] == summary["revenue"] + summary["recoveryIncome"] - summary["expenses"]
    assert summary["cash"] == 500_000_000 + summary["collections"] + summary["recoveryIncome"] - summary["expensePaid"]
    expected_available = max(
        0,
        summary["cash"] - summary["payables"] - summary["custodyReserve"]
        - summary["tailReserve"] - summary["workingCapital"]
        - summary["reservedInvestment"],
    )
    assert summary["available"] == expected_available
    assert 0 <= summary["unrestrictedEarned"] <= summary["available"]


def main():
    assert RESULT["adoption"] == "DECLINE_AS_OPERATIONAL_CURRENT_ACCOUNT_MECHANISM"
    assert RESULT["account_boundary"]["refused"] is True
    assert "MANDATORY_WRITER_ACCOUNT_FACADE" in RESULT["account_boundary"]["error"]
    assert RESULT["restart_and_writer_probe"]["same_actions_sha256"]
    assert RESULT["restart_and_writer_probe"]["same_summary"]
    assert RESULT["restart_and_writer_probe"]["audit_accepted"]
    assert RESULT["restart_and_writer_probe"]["concurrent_writer"]["refused"]
    arms = [RESULT["permanent"], *RESULT["prospective"].values()]
    for arm in arms:
        check_summary(arm["summary"])
        assert arm["audit_accepted"]
        for row in arm["funding_lineage"]:
            funding = row["funding"]
            if funding["funding"] == "PRIOR_UNRESTRICTED_EARNINGS":
                assert funding["before"]["unrestrictedEarned"] >= funding["amount"]
                assert funding["reserved"]["reservedInvestment"] >= funding["amount"]
            settlement = row["settlement"]
            if "residual_cap" in settlement:
                assert 0 <= settlement["claim"] <= settlement["residual_cap"]
    matched = RESULT["matched_central_assertion"]
    assert matched["same_seed"] == 500_000_000
    assert matched["same_working"] == 100_000_000
    assert matched["incremental_settled"] == matched["prospective_settled"] - matched["permanent_settled"]
    assert matched["incremental_profit"] == matched["prospective_profit"] - matched["permanent_profit"]
    assert matched["incremental_settled"] == 13
    assert matched["incremental_profit"] == 2_037_981_000
    assert RESULT["prospective"]["high_friction"]["summary"]["profit"] < 0
    for name in ("full_provider_default", "fully_correlated_dispute"):
        assert RESULT["prospective"][name]["accepted_settled"] == 0
        assert RESULT["prospective"][name]["stopped"]["reason"] == "EARNED_RESIDUAL_RESERVE_UNAVAILABLE"
        assert RESULT["prospective"][name]["summary"]["tailReserve"] == 200_200_000
    files = [
        "enterprise/contract012.py",
        "enterprise/contract019.py",
        "continuation/capital-recycling-019/run_experiment.py",
        "continuation/capital-recycling-019/RESULT.json",
        "continuation/capital-recycling-019/ALLOCATION.json",
    ]
    integrity = {name: sha(ROOT / name) for name in files}
    report = {
        "accepted": True,
        "independent_implementation": True,
        "same_author_model_host": True,
        "not_external_certification": True,
        "checked_arms": len(arms),
        "checked_lineage_records": sum(len(x["funding_lineage"]) for x in arms),
        "source_sha256": integrity,
    }
    (BASE / "VERIFY_RESULT.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
