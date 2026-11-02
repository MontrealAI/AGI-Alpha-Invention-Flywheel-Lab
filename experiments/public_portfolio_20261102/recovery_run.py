"""Execution-only recovery of interrupted R2 accounts; never a new business seed.

The financial function and native implementation are unchanged. A disposable
verification replay reconstructs its lost local scheduler up to the exact
authenticated original prefix, then only the original owner appends its suffix.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import tempfile
import threading
import time
import types

from commercial.ledger import canonical, digest
from connected_enterprise.finance import JournalAccount
from experiments.public_portfolio_20261102 import economics, qualification_run
from experiments.public_portfolio_20261102.native import BusinessAccount


EXPECTED_NATIVE_SOURCE = "bb74d40f7a84ca155189f908c091db32b27093e203e0d63696f327a9a2492901"
AMENDMENT = economics.PREFIX + "RECOVERY_AMENDMENT_R2_001.json"


def _normalized_entry(entry):
    value = copy.deepcopy(entry)
    # The temporary verifier has its OWN disposable local key. Its proof
    # signatures, and therefore this aggregate export hash, must differ. Native
    # proof bodies/actions, every request, plan, receipt and other attempt field
    # remain exact. Nothing from that key or verifier becomes live authority.
    if isinstance(value.get("attempt"), dict):
        value["attempt"].pop("account_record_sha256", None)
    return value


def _semantic_record(record):
    result = copy.deepcopy(record)
    for proof in result.get("action_proofs", {}).values():
        proof.pop("signature", None)
    result["connected_journal"]["entries"] = [
        _normalized_entry(row) for row in result["connected_journal"]["entries"]
    ]
    result.pop("connected_journal_sha256", None)
    return result


def _assert_public_prefix(output, checkpoint, *, after_continuation=False):
    checked = {}
    for case in checkpoint["public_prefix_commitments"]:
        for name, expected in case["public_prefix_files"].items():
            # Interrupted cases may append their missing account/result files;
            # every preexisting manifest and all COMPLETE39 evidence stay exact.
            if after_continuation and case["reservation_status"] != "COMPLETE" and name != "manifest.json":
                continue
            path = output / "public" / case["case_id"] / name
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if path.is_symlink() or actual != expected:
                raise ValueError("RECOVERY_ORIGINAL_PUBLIC_PREFIX_CHANGED:" + case["case_id"] + "/" + name)
            checked[case["case_id"] + "/" + name] = actual
    return {"checked_files": len(checked), "file_commitments_sha256": digest(checked),
            "original_complete_cases_read_only": True,
            "original_43_manifests_unchanged": True}


class PrefixRelay:
    """Hold the original writer while reconstructing only its historical prefix.

    Constructor/reopen uses the original JournalAccount's authenticated pending
    intent recovery. Every historical operation executes on a disposable replay,
    never again on the original account. A complete exact native-prefix match is
    required before the first new live request.
    """

    def __init__(self, root, manifest, path, *, opening, working, contract,
                 receipt, live_factory=JournalAccount):
        self._mutex = threading.RLock()
        self._live = self._replay = None
        self._temporary = None
        self._switched = False
        self._receipt = receipt
        self._closed = False
        try:
            # No key, wallet, capital, journal or authority is copied.
            self._live = live_factory(root, manifest, path, opening=opening,
                                      working=working, contract=contract)
            self._original = self._live.export()
            if self._original["connected_journal"]["source"]["sha256"] != EXPECTED_NATIVE_SOURCE:
                raise ValueError("RECOVERY_ORIGINAL_SOURCE_REQUIRED")
            self._entries = self._original["connected_journal"]["entries"]
            if any(row["status"] not in {"COMPLETE", "REJECTED"} for row in self._entries):
                raise ValueError("ORIGINAL_NATIVE_PENDING_RECOVERY_MUST_COMPLETE")
            self._receipt.update({
                "source_sha256": EXPECTED_NATIVE_SOURCE,
                "authenticated_original_record_sha256": digest(self._original),
                "original_native_actions_sha256": self._original["ledger"]["actions_sha256"],
                "original_native_action_count": len(self._original["ledger"]["actions"]),
                "original_journal_entry_count": len(self._entries),
                "original_summary_microUSD": copy.deepcopy(self._original["ledger"]["summary"]),
                "temporary_replay_scope": "NONBUSINESS_VERIFICATION_ONLY_NOT_A_FUNDING_SOURCE",
                "historical_requests_reexecuted_on_original": 0,
                "prefix_matched": False,
            })
            self._temporary = tempfile.TemporaryDirectory(
                prefix="r2-nonbusiness-prefix-replay-", dir=Path(path).parent.parent.parent / "control")
            self._replay = JournalAccount(root, manifest, Path(self._temporary.name) / "replay.sqlite",
                                          opening=opening, working=working, contract=contract)
        except BaseException:
            self.close()
            raise

    def _verify_replay(self):
        record = self._replay.export()
        entries = record["connected_journal"]["entries"]
        if len(entries) > len(self._entries):
            raise ValueError("RECOVERY_REPLAY_MAY_NOT_PASS_ORIGINAL_PREFIX")
        for index, row in enumerate(entries):
            if _normalized_entry(row) != _normalized_entry(self._entries[index]):
                raise ValueError("RECOVERY_HISTORICAL_JOURNAL_REQUEST_OR_RESULT_MISMATCH:" + str(index))
        actions = record["ledger"]["actions"]
        if actions != self._original["ledger"]["actions"][:len(actions)]:
            raise ValueError("RECOVERY_EXACT_NATIVE_ACTION_PREFIX_REQUIRED")
        return record

    def _current(self):
        if self._closed:
            raise ValueError("RECOVERY_RELAY_CLOSED")
        if not self._switched:
            record = self._verify_replay()
            if len(record["connected_journal"]["entries"]) == len(self._entries):
                if _semantic_record(record) != _semantic_record(self._original):
                    raise ValueError("RECOVERY_FULL_PREFIX_STATE_AND_OBLIGATIONS_MISMATCH")
                if self._live.export() != self._original:
                    raise ValueError("RECOVERY_ORIGINAL_CHANGED_DURING_RECONSTRUCTION")
                self._receipt["prefix_matched"] = True
                self._receipt["matched_native_actions_sha256"] = record["ledger"]["actions_sha256"]
                self._receipt["matched_controller_snapshot_sha256"] = digest(record["snapshot"])
                self._receipt["matched_semantic_record_sha256"] = digest(_semantic_record(record))
                self._replay.close()
                self._replay = None
                self._temporary.cleanup()
                self._temporary = None
                self._switched = True
        return self._live if self._switched else self._replay

    def execute(self, op, args, day):
        with self._mutex:
            target = self._current()
            result = target.execute(op, args, day)
            if not self._switched:
                self._verify_replay()
            return result

    def spend(self, ident, kind, amount, day, work, expected_net, allow_seed=False):
        with self._mutex:
            target = self._current()
            result = target.spend(ident, kind, amount, day, work, expected_net,
                                  allow_seed=allow_seed)
            if not self._switched:
                self._verify_replay()
            return result

    def cost(self, ident, amount, day):
        # Use the unchanged frozen financial implementation, routing its execute
        # call through the relay (also covers the middle of a begin operation).
        return JournalAccount.cost(self, ident, amount, day)

    def advance_financial(self, day):
        # Its self.execute calls switch individually, including multiple maturity
        # actions in the same advance call. Never use future live state to decide
        # a historical refusal or historical order.
        return JournalAccount.advance_financial(self, day)

    def _assert_current(self):
        return self._current()._assert_current()

    @property
    def _account(self):
        return self._current()._account

    def export(self):
        return self._current().export()

    def snapshot(self):
        return self._current().snapshot()

    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = []
        for account in (self._replay, self._live):
            if account is not None:
                try:
                    account.close()
                except BaseException as error:
                    errors.append(error)
        if self._temporary is not None:
            self._temporary.cleanup()
        if errors:
            raise errors[0]


class _ExistingCasePath(type(Path())):
    """Narrow exception for the already-owned case directory, not a reset."""
    permitted_private = None

    def mkdir(self, mode=0o777, parents=False, exist_ok=False):
        if self == self.permitted_private:
            if self.is_symlink() or not self.is_dir():
                raise ValueError("RECOVERY_ORIGINAL_PRIVATE_DIRECTORY_REQUIRED")
            return None
        return super().mkdir(mode=mode, parents=parents, exist_ok=exist_ok)


def recover_case(root, output, products, protocol, route, scenario, *, receipt_path=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    case_id = route + "-" + scenario["id"]
    folder, private = output / "public" / case_id, output / "private" / case_id
    if (folder / "RESULT.json").exists():
        raise ValueError("COMPLETE_CASE_IS_READ_ONLY_NOT_A_RECOVERY_TARGET")
    if not (private / "account.sqlite.connected-journal.json").is_file():
        raise ValueError("RECOVERY_REQUIRES_ORIGINAL_AUTHENTICATED_NATIVE_ACCOUNT")
    manifest = economics.prepare_manifest(root, [p for p in products if p["route"] == route], case_id)
    if json.loads((folder / "manifest.json").read_text()) != manifest:
        raise ValueError("RECOVERY_EXACT_ORIGINAL_MANIFEST_REQUIRED")
    receipt = {"schema": "public-portfolio/same-account-interruption-recovery/v1",
               "case_id": case_id, "status": "RECONSTRUCTING",
               "financial_function_sha256": hashlib.sha256((root / economics.PREFIX / "economics.py").read_bytes()).hexdigest(),
               "recovery_driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "original_financial_source_unchanged": True,
               "original_authority_preserved": True, "new_business_account_created": False,
               "capital_copied_or_added_microUSD": 0,
               "pending_recovery": "Only original JournalAccount authenticated idempotent pending-intent recovery on reopen",
               "signature_comparison": "Temporary proof signatures and attempt aggregate account_record_sha256 differ by disposable verifier key; proof bodies/native actions/other fields must be exact. No temporary authority is adopted."}
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.perf_counter()

    class RecoveredBusinessAccount(BusinessAccount):
        def __init__(self, root, manifest, path, *, opening, working=0, contract):
            self.root, self.manifest = Path(root).resolve(), copy.deepcopy(manifest)
            self.account = PrefixRelay(root, manifest, path, opening=opening, working=working,
                                       contract=contract, receipt=receipt)

    permitted = {folder / name for name in ("manifest.json", "account.public.json", "aggregation.json")}

    def equal_existing_save(path, value):
        path = Path(path)
        if path in permitted and path.exists():
            if path.is_symlink() or path.read_bytes() != canonical(value) + b"\n":
                raise ValueError("RECOVERY_EXISTING_PUBLIC_ARTIFACT_MUST_BE_IDENTICAL:" + path.name)
            return None
        return economics._save(path, value)

    # Same code object and branch logic; only account I/O and the existing
    # immutable output guard are supplied by this explicit execution adapter.
    financial_function = types.FunctionType(
        economics._run_case.__code__,
        {**economics._run_case.__globals__, "BusinessAccount": RecoveredBusinessAccount,
         "_save": equal_existing_save}, economics._run_case.__name__,
        economics._run_case.__defaults__, economics._run_case.__closure__)
    path_type = type("OwnedRecoveryPath", (_ExistingCasePath,), {"permitted_private": private})
    try:
        state = financial_function(root, path_type(output), products, protocol, route, scenario)
        if not receipt["prefix_matched"]:
            raise ValueError("RECOVERY_COMPLETION_REQUIRES_EXACT_PREFIX_MATCH")
        receipt.update({"status": "COMPLETE", "final_native_actions_sha256":
                        json.loads((folder / "account.public.json").read_text())["ledger"]["actions_sha256"],
                        "result_sha256": hashlib.sha256((folder / "RESULT.json").read_bytes()).hexdigest()})
        return state, receipt
    except BaseException as error:
        receipt.update({"status": "FAILED_NO_AUTOMATIC_RETRY", "error_type": type(error).__name__,
                        "error": str(error)[:2000]})
        raise
    finally:
        after = resource.getrusage(resource.RUSAGE_SELF)
        receipt["actual_recovery_resources"] = {
            "wall_seconds": time.perf_counter() - started,
            "user_cpu_seconds": after.ru_utime - before.ru_utime,
            "system_cpu_seconds": after.ru_stime - before.ru_stime,
            "worker_high_water_rss_kib": after.ru_maxrss,
            "scope": "Includes disposable verification reconstruction and same-account continuation; original interrupted process usage is unknown, not zero"}
        if receipt_path is not None:
            economics._save(receipt_path, receipt)


def _recovery_worker(root_string, output_string, products, protocol, plan, expected_driver_sha256):
    root, output = Path(root_string), Path(output_string)
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != expected_driver_sha256:
        raise ValueError("PROSPECTIVE_RECOVERY_DRIVER_CHANGED_BEFORE_OWNER_REOPEN")
    reservation = output / "control" / "reservations" / (plan["case_id"] + ".json")
    original = json.loads(reservation.read_text())
    if original["status"] != "RUNNING" or original["planned_index"] != plan["index"]:
        raise ValueError("RECOVERY_EXACT_INTERRUPTED_RESERVATION_REQUIRED")
    qualification_run._replace(reservation, {**original, "status": "RECOVERING_SAME_ACCOUNT",
                                             "recovery_worker_pid": os.getpid()})
    try:
        state, receipt = recover_case(root, output, products, protocol, plan["route"], plan["scenario"],
                                     receipt_path=output / "public" / plan["case_id"] / "RECOVERY_001.json")
        qualification_run._replace(reservation, {**original, "status": "COMPLETE",
                                                 "recovery": receipt})
        return {"ok": True, "case_id": plan["case_id"], "planned_index": plan["index"],
                "result": economics._compact(state), "recovery": receipt}
    except BaseException as error:
        qualification_run._replace(reservation, {**original, "status": "RECOVERY_FAILED",
                                                 "error_type": type(error).__name__, "error": str(error)[:2000]})
        return {"ok": False, "case_id": plan["case_id"], "error_type": type(error).__name__,
                "error": str(error)[:2000], "no_automatic_retry": True}


def run(root, output, *, publication_sha):
    root, output = Path(root).resolve(), Path(output).resolve()
    if len(publication_sha) != 40 or any(c not in "0123456789abcdef" for c in publication_sha):
        raise ValueError("PROSPECTIVE_PUBLICATION_COMMIT_REQUIRED")
    amendment = json.loads((root / AMENDMENT).read_text())
    original_amendment = json.loads((root / qualification_run.AMENDMENT).read_text())
    qualification_run._assert_math(root, original_amendment)
    protocol = json.loads((output / "public" / "protocol.json").read_text())
    if protocol != json.loads((root / economics.PROTOCOL).read_text()):
        raise ValueError("ORIGINAL_REGISTERED_PROTOCOL_REQUIRED")
    plans = qualification_run.planned_cases(protocol)
    if json.loads((output / "control" / "PLANNED_CASES.json").read_text()) != plans:
        raise ValueError("ORIGINAL_110_CASE_PLAN_REQUIRED")
    if (output / "public" / "RESULTS.json").exists():
        raise ValueError("COMPLETE_CAMPAIGN_IS_READ_ONLY")
    checkpoint = json.loads((output / "public" / "HOST_INTERRUPTION_CHECKPOINT.json").read_text())
    prefix_before = _assert_public_prefix(output, checkpoint)
    products = json.loads((root / economics.PREFIX / "PRODUCTS.json").read_text())
    if isinstance(products, dict):
        products = products["products"]
    identity = json.loads((output / "public" / "RUN_IDENTITY.json").read_text())
    if hashlib.sha256((root / economics.PREFIX / "PRODUCTS.json").read_bytes()).hexdigest() != identity["products_file_sha256"]:
        raise ValueError("RECOVERY_ORIGINAL_APPROVED_PRODUCTS_REQUIRED")
    completed, interrupted, unstarted = [], [], []
    for plan in plans:
        reservation = output / "control" / "reservations" / (plan["case_id"] + ".json")
        if reservation.exists():
            registered = json.loads(reservation.read_text())
            if registered["case_id"] != plan["case_id"] or registered["planned_index"] != plan["index"]:
                raise ValueError("ORIGINAL_EXCLUSIVE_PLAN_RESERVATION_REQUIRED")
            if registered["status"] == "COMPLETE":
                state = json.loads((output / "public" / plan["case_id"] / "RESULT.json").read_text())
                completed.append((plan["index"], economics._compact(state)))
            elif registered["status"] == "RUNNING":
                interrupted.append(plan)
            else:
                raise ValueError("ACTUAL_FAILURE_IS_NOT_AUTOMATICALLY_RETRIED:" + plan["case_id"])
        else:
            if (output / "private" / plan["case_id"]).exists() or (output / "public" / plan["case_id"]).exists():
                raise ValueError("UNRESERVED_EXISTING_ACCOUNT_REFUSED")
            unstarted.append(plan)
    observed = {"complete": len(completed), "interrupted": [p["case_id"] for p in interrupted],
                "never_started": len(unstarted)}
    if observed != amendment["expected_interruption_state"]:
        raise ValueError("RECOVERY_AMENDMENT_OBSERVED_STATE_MUST_MATCH")
    stage = {"schema": "public-portfolio/r2-recovery-stage/v1", "status": "RUNNING",
             "publication_sha": publication_sha,
             "amendment_sha256": hashlib.sha256((root / AMENDMENT).read_bytes()).hexdigest(),
             "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "original_observed_state": observed, "original_interrupted_process_resources": None,
             "original_public_prefix_check_before": prefix_before,
             "original_interrupted_cause": "Not observed; prior process/session is absent and saved running reservations remain",
             "scope": "Continuation of same R2 accounts and original unscheduled plan, not a new financial campaign"}
    economics._save(output / "public" / "RECOVERY_STAGE_001.json", stage)
    resources, failures, recoveries = [], [], []
    allocation = qualification_run.resource_allocation()
    started = time.perf_counter()
    # Recover all original interrupted accounts before commissioning any new one.
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=allocation["workers"], mp_context=context) as pool:
        futures = {pool.submit(_recovery_worker, str(root), str(output), products, protocol, plan, stage["driver_sha256"]): plan
                   for plan in interrupted}
        for future in concurrent.futures.as_completed(futures):
            plan = futures[future]
            try:
                result = future.result()
            except BaseException as error:
                result = {"ok": False, "case_id": plan["case_id"], "error_type": type(error).__name__, "error": str(error)[:2000]}
            if result["ok"]:
                completed.append((plan["index"], result["result"]))
                recoveries.append(result["recovery"])
                print("RECOVERED " + plan["case_id"], flush=True)
            else:
                failures.append(result)
                print("RECOVERY_FAILED " + plan["case_id"], flush=True)
        next_index = 0
        running = {}
        while running or (next_index < len(unstarted) and not failures):
            while len(running) < allocation["workers"] and next_index < len(unstarted) and not failures:
                plan = unstarted[next_index]
                economics._save(output / "control" / "reservations" / (plan["case_id"] + ".json"),
                                {"schema": "public-portfolio/exclusive-r2-case-reservation/v1",
                                 "case_id": plan["case_id"], "planned_index": plan["index"],
                                 "status": "RESERVED", "no_prior_account_or_cash_imported": True})
                future = pool.submit(qualification_run._worker, str(root), str(output), products,
                                     protocol, original_amendment, plan)
                running[future] = plan
                next_index += 1
                print("START " + plan["case_id"], flush=True)
            if not running:
                break
            done, _ = concurrent.futures.wait(running, return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                plan = running.pop(future)
                try:
                    result = future.result()
                except BaseException as error:
                    result = {"ok": False, "case_id": plan["case_id"], "error_type": type(error).__name__, "error": str(error)[:2000]}
                if result["ok"]:
                    completed.append((plan["index"], result["result"]))
                    resources.append(result["resources"])
                    print("DONE " + plan["case_id"] + " collected=" + str(result["result"]["accepted_and_collected_orders"]), flush=True)
                else:
                    failures.append(result)
                    print("FAILED " + plan["case_id"], flush=True)
    summary = json.loads((output / "public" / "RUN_IDENTITY.json").read_text())
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != stage["driver_sha256"]:
        raise ValueError("PROSPECTIVE_RECOVERY_DRIVER_CHANGED_DURING_EXECUTION")
    summary.update({"cases": [row for _, row in sorted(completed)], "completed_businesses": len(completed),
                    "failed_businesses": len(failures), "recovery_stage": stage,
                    "target_1b_count": sum(row["target_1b"] for _, row in completed),
                    "target_3b_count": sum(row["target_3b"] for _, row in completed)})
    summary["original_public_prefix_check_after"] = _assert_public_prefix(output, checkpoint, after_continuation=True)
    telemetry = {"schema": "public-portfolio/actual-r2-recovery-stage-resources/v1",
                 "wall_seconds_this_stage": time.perf_counter() - started,
                 "original_interrupted_process_resources": None, "resource_allocation": allocation,
                 "previous_complete_case_resources": [json.loads(p.read_text()) for p in sorted((output / "public").glob("*/RESOURCES.json")) if p.parent.name not in {r["case_id"] for r in resources}],
                 "new_complete_case_resources": resources, "same_account_recovery_resources": recoveries,
                 "actual_model_tokens": None, "actual_host_model_billing": None,
                 "scope": "Known per-case/stage measurements; no fabricated total for lost original process and interrupted work"}
    economics._save(output / "public" / "RECOVERY_TELEMETRY_001.json", telemetry)
    if failures or len(completed) != len(plans):
        summary["status"] = "CHECKPOINT"
        economics._save(output / "public" / "RECOVERY_CHECKPOINT_001.json", {"registered_cases": len(plans), "completed_case_ids": [r["case_id"] for _, r in completed], "failures": failures, "no_retry_no_reset_no_pooled_cash": True})
        economics._save(output / "public" / "RECOVERY_PARTIAL_RESULTS_001.json", summary)
        return summary
    summary["working_capital_pairs"] = []
    for route in economics.ROUTES:
        pair = {row["scenario"]: row for row in summary["cases"] if row["route"] == route and row["scenario"].startswith("working-capital-")}
        aware, greedy = pair["working-capital-aware"], pair["working-capital-greedy"]
        if aware["matched_world_sha256"] != greedy["matched_world_sha256"]:
            raise ValueError("R2_MATCHED_WORKING_CAPITAL_WORLD_CHANGED")
        summary["working_capital_pairs"].append({"route": route, "matched_world_sha256": aware["matched_world_sha256"], "aware_minus_greedy_profit_microUSD": aware["profit_microUSD"] - greedy["profit_microUSD"], "aware_minus_greedy_collected_orders": aware["accepted_and_collected_orders"] - greedy["accepted_and_collected_orders"]})
    summary["status"] = "COMPLETE"
    economics._save(output / "public" / "RESULTS.json", summary)
    economics._write_report(output, protocol, summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--publication-sha", required=True)
    args = parser.parse_args()
    result = run(args.root, args.output, publication_sha=args.publication_sha)
    print(json.dumps({"status": result["status"], "completed": result["completed_businesses"], "failed": result["failed_businesses"]}))
    raise SystemExit(0 if result["status"] == "COMPLETE" else 2)
