"""One-pass read-only native prefix reconstruction for same-account recovery.

Original ownership, journal authentication and full audit run once on reopen.
Historical requests use the frozen financial methods and a pure native verifier;
no historical operation is appended to the original account a second time.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import types

from adaptive_enterprise.account import Account
from commercial.ledger import _ADAPTIVE_ACCOUNT_CAPABILITY, canonical, digest
from commercial.single_writer import SingleWriterExchange
from connected_enterprise.finance import JournalAccount, _native_snapshot
from experiments.public_portfolio_20261102 import economics, qualification_run, recovery_run

AMENDMENT = economics.PREFIX + "FAST_RECOVERY_AMENDMENT_R2_002.json"
STAGE = "FAST_RECOVERY_STAGE_002.json"
_RECOVERY_IO_FUNCTION = recovery_run.recover_case


class FastPrefixRelay:
    def __init__(self, root, manifest, path, *, opening, working, contract, receipt,
                 live_factory=JournalAccount):
        self.root, self.manifest = Path(root), copy.deepcopy(manifest)
        self._mutex = threading.RLock()
        self._live = self._pure = self._temporary = None
        self._closed = self._switched = False
        self._cursor = 0
        self._receipt = receipt
        try:
            self._live = live_factory(root, manifest, path, opening=opening, working=working, contract=contract)
            self._original = self._live.export()
            self.source = self._original["connected_journal"]["source"]
            if self.source["sha256"] != recovery_run.EXPECTED_NATIVE_SOURCE:
                raise ValueError("FAST_RECOVERY_ORIGINAL_SOURCE_REQUIRED")
            self._entries = self._original["connected_journal"]["entries"]
            if any(row["status"] not in {"COMPLETE", "REJECTED"} for row in self._entries):
                raise ValueError("AUTHENTICATED_PENDING_RECOVERY_MUST_FINISH")
            self._temporary = tempfile.TemporaryDirectory(prefix="r2-pure-native-readonly-", dir=Path(path).parent.parent.parent / "control")
            self._pure = SingleWriterExchange(Path(self._temporary.name) / "replay.sqlite", root=root,
                manifest=manifest, opening=opening, working=working, contract=contract, durable=False,
                _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY)
            relay = self
            class HistoricalSnapshotAccount:
                filesystem = relay._original["snapshot"]["filesystem"]
                _owner = relay._pure
                def _assert_owner(self):
                    relay._historical_guard()
                def snapshot(self):
                    return Account.snapshot(self)
                def export(self):
                    return {k: v for k, v in relay._prefix_record().items()
                            if k not in {"connected_journal", "connected_journal_sha256"}}
            self._historical_account = HistoricalSnapshotAccount()
            receipt.update({"source_sha256": self.source["sha256"],
                "authenticated_original_record_sha256": digest(self._original),
                "original_native_actions_sha256": self._original["ledger"]["actions_sha256"],
                "original_native_action_count": len(self._original["ledger"]["actions"]),
                "original_journal_entry_count": len(self._entries),
                "original_summary_microUSD": copy.deepcopy(self._original["ledger"]["summary"]),
                "temporary_replay_scope": "PURE_NATIVE_NONBUSINESS_READ_ONLY_VERIFICATION_NOT_A_FUNDING_SOURCE",
                "historical_requests_reexecuted_on_original": 0, "prefix_matched": False,
                "signature_comparison": "Exact original exported proof data are read-only metadata; no private key or signer copied. Complete record equality has no normalized/ignored fields.",
                "native_actions_replayed_once": 0})
        except BaseException:
            self.close()
            raise

    def _historical_guard(self):
        if self._closed:
            raise ValueError("FAST_RECOVERY_RELAY_CLOSED")
        # No original financial mutation occurs during reconstruction. Retain
        # both kernel owners, and freshly recheck full original source/account
        # at the eventual append boundary (normal live methods check every action).
        self._live._account._assert_owner()
        if self._pure is not None:
            self._pure.lease.assert_owner()

    def _prefix_record(self):
        tape = self._pure.export()
        record = copy.deepcopy(self._original)
        record["ledger"] = tape
        record["snapshot"] = self._historical_account.snapshot()
        reserved = {a["args"]["id"] for a in tape["actions"] if a["op"] == "reserve"}
        finished = {a["args"]["id"] for a in tape["actions"] if a["op"] == "finish"}
        record["action_proofs"] = {k: v for k, v in record["action_proofs"].items() if k in reserved}
        record["obligation_resolutions"] = {k: v for k, v in record.get("obligation_resolutions", {}).items() if k in finished}
        record["connected_journal"]["entries"] = copy.deepcopy(self._entries[:self._cursor])
        record["connected_journal_sha256"] = digest(record["connected_journal"])
        return record

    def _current(self):
        self._historical_guard()
        if not self._switched and self._cursor == len(self._entries):
            rebuilt = self._prefix_record()
            if rebuilt != self._original:
                raise ValueError("FAST_RECOVERY_EXACT_FULL_RECORD_PREFIX_REQUIRED")
            # This includes full current source identity and original owner.
            if self._live.export() != self._original:
                raise ValueError("FAST_RECOVERY_LIVE_ORIGINAL_CHANGED")
            self._receipt.update({"prefix_matched": True,
                "matched_native_actions_sha256": rebuilt["ledger"]["actions_sha256"],
                "matched_controller_snapshot_sha256": digest(rebuilt["snapshot"]),
                "matched_exact_record_sha256": digest(rebuilt),
                "native_actions_replayed_once": len(rebuilt["ledger"]["actions"])})
            self._pure.close()
            self._pure = None
            self._temporary.cleanup()
            self._temporary = None
            self._switched = True
        return self._live if self._switched else self

    def _assert_current(self):
        self._historical_guard()

    @property
    def _journal(self):
        return {"entries": self._entries[:self._cursor]}

    @property
    def _account(self):
        current = self._current()
        return current._account if current is not self else self._historical_account

    def _entry(self, key, request, *, plan=None, funding=None):
        for prior in self._entries[:self._cursor]:
            if prior["key"] == key:
                if prior["request"] != request:
                    raise ValueError("IDEMPOTENT_CONNECTED_ACTION_PAYLOAD_CHANGED")
                return prior
        if self._cursor >= len(self._entries):
            raise ValueError("FAST_REPLAY_CANNOT_APPEND_TO_HISTORICAL_PREFIX")
        expected = self._entries[self._cursor]
        if (expected["key"] != key or expected["request"] != request
                or expected["plan"] != plan or expected["funding"] != funding):
            raise ValueError("FAST_RECOVERY_EXACT_REQUEST_PLAN_FUNDING_PREFIX_REQUIRED:" + str(self._cursor))
        return expected

    def _perform(self, entry):
        if entry not in self._entries[:self._cursor]:
            raise ValueError("FAST_RECOVERY_PRIOR_ENTRY_REQUIRED")
        if entry["status"] == "REJECTED":
            raise ValueError(entry["receipt"]["error"])
        return copy.deepcopy(entry["receipt"])

    def _attempt(self, entry, *, new_entry):
        if not new_entry:
            return self._perform(entry)
        if entry != self._entries[self._cursor]:
            raise ValueError("FAST_RECOVERY_NEXT_AUTHENTICATED_ENTRY_REQUIRED")
        if entry["status"] == "REJECTED":
            # A real original predicate rejection remains a failure. It is never
            # converted to a successful continuation or retried on the live owner.
            raise ValueError(entry["receipt"]["error"])
        receipt = entry["receipt"]
        stop = receipt["sequence"] if entry["request"]["operation"] == "execute" else receipt["native_event_sequence"] + 1
        begin = len(self._pure._exchange.actions)
        if not begin < stop <= len(self._original["ledger"]["actions"]):
            raise ValueError("FAST_RECOVERY_EXACT_NATIVE_SLICE_REQUIRED")
        for action in self._original["ledger"]["actions"][begin:stop]:
            after = self._pure._exchange.execute(action["op"], action["args"], action["day"], _expected_before=action["before"])
            if after != action["after"] or self._pure._exchange.actions[-1] != action:
                raise ValueError("FAST_RECOVERY_NATIVE_ACTION_RESULT_MISMATCH")
        tape = self._pure.export()
        if tape["actions"] != self._original["ledger"]["actions"][:stop]:
            raise ValueError("FAST_RECOVERY_NATIVE_BYTES_PREFIX_REQUIRED")
        if entry["request"]["operation"] == "execute":
            actual = _native_snapshot(tape, tape["actions"][-1], self._historical_account.filesystem)
            if actual != receipt:
                raise ValueError("FAST_RECOVERY_EXACT_EXECUTE_RECEIPT_REQUIRED")
        else:
            if receipt["native_actions_sha256"] != tape["actions_sha256"]:
                raise ValueError("FAST_RECOVERY_EXACT_SPEND_RECEIPT_NATIVE_PREFIX_REQUIRED")
        self._cursor += 1
        return copy.deepcopy(receipt)

    def execute(self, op, args, day):
        with self._mutex:
            current = self._current()
            return JournalAccount.execute(self, op, args, day) if current is self else current.execute(op, args, day)

    def spend(self, ident, kind, amount, day, work, expected_net, allow_seed=False):
        with self._mutex:
            current = self._current()
            if current is not self:
                return current.spend(ident, kind, amount, day, work, expected_net, allow_seed=allow_seed)
            return JournalAccount.spend(self, ident, kind, amount, day, work, expected_net, allow_seed=allow_seed)

    def cost(self, ident, amount, day):
        return JournalAccount.cost(self, ident, amount, day)

    def advance_financial(self, day):
        return JournalAccount.advance_financial(self, day)

    def export(self):
        current = self._current()
        return self._prefix_record() if current is self else current.export()

    def snapshot(self):
        current = self._current()
        return self._historical_account.snapshot() if current is self else current.snapshot()

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            if self._pure is not None:
                self._pure.close()
        finally:
            try:
                if self._live is not None:
                    self._live.close()
            finally:
                if self._temporary is not None:
                    self._temporary.cleanup()


def recover_case(root, output, products, protocol, route, scenario, *, receipt_path=None):
    function = types.FunctionType(_RECOVERY_IO_FUNCTION.__code__,
        {**_RECOVERY_IO_FUNCTION.__globals__, "PrefixRelay": FastPrefixRelay, "__file__": __file__},
        _RECOVERY_IO_FUNCTION.__name__, _RECOVERY_IO_FUNCTION.__defaults__)
    function.__kwdefaults__ = _RECOVERY_IO_FUNCTION.__kwdefaults__
    return function(root, output, products, protocol, route, scenario, receipt_path=receipt_path)


def _source_hashes(root):
    names = [economics.PREFIX + name for name in ("recovery_fast.py", "recovery_run.py",
             "FAST_RECOVERY_AMENDMENT_R2_002.json", "verification/test_recovery_fast.py",
             "verification/test_recovery.py", "verification/verify_finance.py", "verification/verify_science.py",
             "verification/FAST_RECOVERY_QUALIFICATION_003.json", "verification/FAST_RECOVERY_REVIEW_002.json")]
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def register(root, output, publication_sha):
    root, output = Path(root).resolve(), Path(output).resolve()
    from experiments.public_portfolio_20261102.dispatch_case import _assert_publication_sha
    _assert_publication_sha(publication_sha)
    amendment = json.loads((root / AMENDMENT).read_text())
    qualification = json.loads((root / economics.PREFIX / "verification/FAST_RECOVERY_QUALIFICATION_003.json").read_text())
    review = json.loads((root / economics.PREFIX / "verification/FAST_RECOVERY_REVIEW_002.json").read_text())
    if qualification["status"] != "PASS" or review["status"] != "ACCEPTED_ENGINEERING_SCOPE":
        raise ValueError("FAST_RECOVERY_TEST_AND_INDEPENDENT_REVIEW_REQUIRED")
    hashes = _source_hashes(root)
    if hashes[economics.PREFIX + "recovery_run.py"] != amendment["unchanged_recovery_io_adapter_sha256"] or amendment["unchanged_native_source_sha256"] != recovery_run.EXPECTED_NATIVE_SOURCE:
        raise ValueError("FAST_RECOVERY_UNCHANGED_ORIGINAL_ADAPTER_AND_NATIVE_SOURCE_REQUIRED")
    for name, expected in qualification["source_hashes"].items():
        if hashes.get(name) != expected:
            raise ValueError("FAST_RECOVERY_TESTED_SOURCE_REQUIRED")
    if review.get("fast_recovery_source_sha256") != hashes[economics.PREFIX + "recovery_fast.py"] or review.get("qualification_receipt_sha256") != hashes[economics.PREFIX + "verification/FAST_RECOVERY_QUALIFICATION_003.json"]:
        raise ValueError("FAST_RECOVERY_INDEPENDENT_REVIEW_OF_EXACT_TESTED_CANDIDATE_REQUIRED")
    record = {"schema": "public-portfolio/fast-recovery-registration/v2", "publication_sha": publication_sha,
              "source_hashes": hashes, "native_source_sha256": recovery_run.EXPECTED_NATIVE_SOURCE,
              "scope": "Explicit same-account host-interruption continuation only, never actual-failure retry"}
    economics._save(output / "public" / STAGE, record)
    return record


def assert_registered(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    stage = json.loads((output / "public" / STAGE).read_text())
    if stage["source_hashes"] != _source_hashes(root):
        raise ValueError("EXACT_PROSPECTIVE_FAST_RECOVERY_SOURCE_REQUIRED")
    return stage


def closeout_completed_result(root, output, products, protocol, plan):
    """Validate an already-complete original result; never rerun its economics."""
    from connected_enterprise.scale import aggregate_native
    root, output = Path(root), Path(output)
    import sys
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(root / economics.PREFIX / "verification"))
        from experiments.public_portfolio_20261102.verification.verify_finance import check_case
    finally:
        sys.path[:] = previous_path
    folder = output / "public" / plan["case_id"]
    values, hashes = {}, {}
    for name in ("manifest.json", "account.public.json", "aggregation.json", "RESULT.json"):
        path = folder / name
        if path.is_symlink():
            raise ValueError("CLOSEOUT_REGULAR_PUBLIC_FILES_REQUIRED")
        data = path.read_bytes()
        value = json.loads(data)
        if data != canonical(value) + b"\n":
            raise ValueError("CLOSEOUT_EXACT_CANONICAL_PUBLIC_BYTES_REQUIRED")
        values[name], hashes[name] = value, hashlib.sha256(data).hexdigest()
    state, manifest, record = values["RESULT.json"], values["manifest.json"], values["account.public.json"]
    expected_manifest = economics.prepare_manifest(root, [p for p in products if p["route"] == plan["route"]], plan["case_id"])
    if manifest != expected_manifest or state["case_id"] != plan["case_id"] or state["route"] != plan["route"] or state["scenario"] != plan["scenario"]:
        raise ValueError("CLOSEOUT_EXACT_ORIGINAL_PLAN_MANIFEST_REQUIRED")
    if state["native_source_sha256"] != recovery_run.EXPECTED_NATIVE_SOURCE or record["connected_journal"]["source"]["sha256"] != recovery_run.EXPECTED_NATIVE_SOURCE:
        raise ValueError("CLOSEOUT_ORIGINAL_NATIVE_SOURCE_REQUIRED")
    profile = economics._profile(protocol, plan["route"], plan["scenario"])
    if state["cost_profile_microUSD"] != profile or state["opening_microUSD"] != economics._capital(protocol, profile, plan["scenario"]):
        raise ValueError("CLOSEOUT_ORIGINAL_COST_CAPITAL_REQUIRED")
    if values["aggregation.json"] != aggregate_native(record["ledger"]) or state["final_native_summary_microUSD"] != record["ledger"]["summary"]:
        raise ValueError("CLOSEOUT_EXACT_AGGREGATION_AND_NATIVE_SUMMARY_REQUIRED")
    arithmetic = check_case(folder, state, manifest, record, protocol["operating_end_hour_exclusive"])
    if not arithmetic["passed"]:
        raise ValueError("CLOSEOUT_FULL_COMPLETED_FINANCIAL_STATE_REQUIRED")
    private = output / "private" / plan["case_id"] / "account.sqlite"
    with JournalAccount(root, manifest, private, opening=state["opening_microUSD"], working=0,
                        contract="public-portfolio-" + plan["case_id"]) as original:
        if original.export() != record:
            raise ValueError("CLOSEOUT_AUTHENTICATED_ORIGINAL_EXPORT_MUST_MATCH_PUBLIC")
    for name, expected in hashes.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("CLOSEOUT_ORIGINAL_PUBLIC_BYTES_CHANGED")
    return state, {"schema": "public-portfolio/read-only-completed-result-closeout/v2",
        "status": "COMPLETE_READ_ONLY_CLOSEOUT", "case_id": plan["case_id"],
        "public_files_unchanged_sha256": hashes, "native_full_audit_on_original_reopen": True,
        "independent_arithmetic_checks_passed": arithmetic["passed"],
        "economic_function_rerun": False, "historical_actions_reexecuted_on_original": 0,
        "original_interrupted_resource_totals": None,
        "scope": "Original RESULT already complete; only authenticated read-only evidence reconciliation and reservation closeout"}


def recover_dispatch(root, output, products, protocol, plan, attempt):
    stage = assert_registered(root, output)
    reservation = output / "control/reservations" / (plan["case_id"] + ".json")
    original = json.loads(reservation.read_text())
    if original["status"] not in {"RUNNING", "RECOVERING_SAME_ACCOUNT"}:
        raise ValueError("EXACT_ORIGINAL_INTERRUPTED_RESERVATION_REQUIRED")
    qualification_run._replace(reservation, {**original, "status": "RECOVERING_SAME_ACCOUNT", "explicit_dispatch002_attempt": attempt})
    try:
        receipt_path = output / "public" / plan["case_id"] / ("FAST_RECOVERY_002_" + str(attempt).zfill(3) + ".json")
        if (output / "public" / plan["case_id"] / "RESULT.json").exists():
            state, receipt = closeout_completed_result(root, output, products, protocol, plan)
            economics._save(receipt_path, receipt)
        else:
            state, receipt = recover_case(root, output, products, protocol, plan["route"], plan["scenario"],
                                          receipt_path=receipt_path)
        assert_registered(root, output)
        qualification_run._replace(reservation, {**original, "status": "COMPLETE", "fast_recovery002": receipt,
                                                 "fast_recovery_publication_sha": stage["publication_sha"]})
        return {"ok": True, "case_id": plan["case_id"], "result": economics._compact(state), "recovery": receipt}
    except Exception as error:
        qualification_run._replace(reservation, {**original, "status": "RECOVERY_FAILED", "error_type": type(error).__name__, "error": str(error)[:2000]})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--publication-sha", required=True)
    parser.add_argument("--register", action="store_true", required=True)
    args = parser.parse_args()
    print(json.dumps(register(args.root, args.output, args.publication_sha)))
