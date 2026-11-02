"""Independent disposable checks; never reads a campaign account or key."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from commercial.ledger import digest
from connected_enterprise import finance
from connected_enterprise.finance import JournalAccount, audit_journal
from experiments.public_portfolio_20261102 import recovery_fast, service


def run():
    checks = {}
    usd = 1_000_000
    with tempfile.TemporaryDirectory(prefix="independent-fast-recovery-nonbusiness-") as temporary:
        out = Path(temporary)
        (out / "control").mkdir()
        path = out / "private" / "case" / "account.sqlite"
        path.parent.mkdir(parents=True)
        manifest = service.prepare_manifest(ROOT, [], "independent-fast-recovery-nonbusiness")
        settings = {"opening": 100 * usd, "working": 0,
                    "contract": "NONBUSINESS-INDEPENDENT-FAST-REVIEW"}
        work = {"kind": "explicit disposable verification fixture"}
        with JournalAccount(ROOT, manifest, path, **settings) as original:
            original.cost("first", 10 * usd, 0)
            original.spend("second", "verification", 5 * usd, 1, work, 1, allow_seed=True)
            prefix = original.export()
        receipt = {}
        relay = recovery_fast.FastPrefixRelay(ROOT, manifest, path, receipt=receipt, **settings)
        try:
            relay.cost("first", 10 * usd, 0)
            try:
                relay.spend("second", "verification", 6 * usd, 1, work, 1, allow_seed=True)
            except ValueError as error:
                checks["changed_historical_request_refused"] = "REQUEST_PLAN_FUNDING" in str(error)
            else:
                checks["changed_historical_request_refused"] = False
            checks["bad_reconstruction_did_not_change_original"] = relay._live.export() == prefix
        finally:
            relay.close()
        receipt = {}
        relay = recovery_fast.FastPrefixRelay(ROOT, manifest, path, receipt=receipt, **settings)
        try:
            relay.cost("first", 10 * usd, 0)
            relay.spend("second", "verification", 5 * usd, 1, work, 1, allow_seed=True)
            changed = copy.deepcopy(relay.source)
            changed["sha256"] = "0" * 64
            with patch.object(finance, "source_identity", return_value=changed):
                try:
                    relay.cost("third", 7 * usd, 2)
                except ValueError as error:
                    checks["changed_source_refused_at_append_boundary"] = "SOURCE_CHANGED" in str(error)
                else:
                    checks["changed_source_refused_at_append_boundary"] = False
            checks["source_rejection_preserved_original"] = relay._live.export() == prefix
            relay.cost("third", 7 * usd, 2)
            final = relay.export()
            checks["exact_original_action_prefix_preserved"] = final["ledger"]["actions"][:len(prefix["ledger"]["actions"])] == prefix["ledger"]["actions"]
            checks["exact_entire_original_export_matched"] = receipt["matched_exact_record_sha256"] == digest(prefix)
            checks["only_one_missing_action_appended"] = len(final["ledger"]["actions"]) == len(prefix["ledger"]["actions"]) + 1
            checks["original_capital_cash_expenses_conserved"] = (final["ledger"]["config"]["opening"] == 100 * usd and final["ledger"]["summary"]["cash"] == 78 * usd and final["ledger"]["summary"]["expenses"] == 22 * usd)
            checks["full_canonical_native_replay"] = audit_journal(final, root=ROOT, manifest=manifest)["accepted"]
            checks["no_historical_original_execution"] = receipt["historical_requests_reexecuted_on_original"] == 0
        finally:
            relay.close()
        receipt = {}
        relay = recovery_fast.FastPrefixRelay(ROOT, manifest, path, receipt=receipt, **settings)
        try:
            relay.cost("first", 10 * usd, 0)
            relay.spend("second", "verification", 5 * usd, 1, work, 1, allow_seed=True)
            relay.cost("third", 7 * usd, 2)
            checks["second_reconstruction_adds_no_duplicate"] = relay.export() == final and receipt["prefix_matched"]
        finally:
            relay.close()
    return {"schema": "public-portfolio/independent-fast-recovery-checks/v3",
            "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "fast_recovery_source_sha256": hashlib.sha256(Path(recovery_fast.__file__).read_bytes()).hexdigest(),
            "checks": checks, "passed": all(checks.values()),
            "scope": "Independent disposable NONBUSINESS fixture only. No original campaign account, key, wallet or cash was read, copied, reopened or changed. The in-memory source fault is reverted before cleanup; actual source files stay unchanged."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("INDEPENDENT_CHECK_RESULT_MUST_NOT_BE_OVERWRITTEN")
    result = run()
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "checks": len(result["checks"])}))
    raise SystemExit(0 if result["passed"] else 1)
