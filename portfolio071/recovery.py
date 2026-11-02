"""Prospectively registered, same-account recovery of the frozen controller.

Historical requests are replayed only in a disposable native audit database.
New requests use the original JournalAccount after exact prefix reconstruction.
No financial implementation or acceptance rule is replaced by this adapter.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time

from commercial.ledger import (
    _ADAPTIVE_ACCOUNT_CAPABILITY, amount as validate_amount,
    canonical, digest, strict_json,
)
from commercial.persistence import atomic_bytes
from commercial.single_writer import SingleWriterExchange
from connected_enterprise.finance import (
    JournalAccount, _identifier, _native_id, _seed_id, _validate_native_request,
    audit_journal,
)

REPO = Path(__file__).resolve().parents[1]
SOURCE_NAMES = ("portfolio071/recovery.py", "portfolio071/recovery_controller.py")
CHECKPOINT_SCHEMA = "portfolio071/controller-recovery-checkpoint/v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def same(left, right):
    return canonical(left) == canonical(right)


def read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64_000_000:
        raise ValueError("BOUNDED_REGULAR_RECOVERY_INPUT_REQUIRED")
    return strict_json(path.read_bytes())


def write_same(path, value):
    """Create a result, or require already-existing exact bytes; never replace."""
    path = Path(path)
    raw = canonical(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise ValueError("RECOVERY_OUTPUT_ALREADY_EXISTS_WITH_DIFFERENT_BYTES:" + path.name)
    else:
        with path.open("xb") as stream:
            stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def write_new(path, value):
    path = Path(path)
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")


def source_hashes():
    return {name: sha(REPO / name) for name in SOURCE_NAMES}


def public_before_open(account_path):
    """Read public native tape and journal body, never private DB/key bytes."""
    account_path = Path(account_path).absolute()
    tape_path = account_path.with_name(account_path.name + ".actions.jsonl")
    journal_path = account_path.with_name(account_path.name + ".connected-journal.json")
    marker_path = account_path.with_name(account_path.name + ".adaptive-account.json")
    signer_path = account_path.with_name(account_path.name + ".adaptive-simulation-key")
    # The frozen native persistence layer fsyncs every action to its tape and
    # creates the SQLite checkpoint only on clean close. An interrupted owner
    # can therefore have no SQLite file; that absence is not a fresh account.
    if account_path.is_symlink() or (account_path.exists() and not account_path.is_file()):
        raise ValueError("REGULAR_OR_ABSENT_NATIVE_CHECKPOINT_REQUIRED")
    # Inspect signer metadata only. Its existing bytes are authenticated solely
    # by the unchanged native owner; recovery never creates replacement authority.
    for path in (tape_path, journal_path, marker_path, signer_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError("EXISTING_ORIGINAL_ACCOUNT_AND_PUBLIC_HISTORY_REQUIRED")
    marker = read(marker_path)
    expected_marker = {"schema": "agi-alpha/adaptive012-account-namespace/v1",
                       "namespace": "adaptive012", "account_path": str(account_path.absolute())}
    if not same(marker, expected_marker):
        raise ValueError("ORIGINAL_NATIVE_ACCOUNT_NAMESPACE_CHANGED")
    if tape_path.stat().st_size > 64_000_000:
        raise ValueError("BOUNDED_ORIGINAL_NATIVE_TAPE_REQUIRED")
    raw = tape_path.read_bytes()
    lines = raw.splitlines()
    if not lines or any(not line for line in lines):
        raise ValueError("COMPLETE_ORIGINAL_PUBLIC_TAPE_REQUIRED")
    header = strict_json(lines[0])
    actions = [strict_json(line) for line in lines[1:]]
    if canonical(header) + b"\n" + b"".join(canonical(row) + b"\n" for row in actions) != raw:
        raise ValueError("CANONICAL_COMPLETE_PUBLIC_TAPE_REQUIRED")
    body = read(journal_path)["body"]
    return {"native_header": header, "native_actions": actions, "connected_journal": body,
            "native_account_marker": marker, "sqlite_checkpoint_present": account_path.exists(),
            "native_tape_sha256": hashlib.sha256(raw).hexdigest(),
            "native_tape_bytes": len(raw), "journal_body_sha256": digest(body),
            "native_actions_sha256": digest(actions),
            "native_action_count": len(actions), "journal_entry_count": len(body["entries"])}


def check_native_reopen(before, exported):
    """Only unchanged native recovery may resolve one existing final intent."""
    if before is None:
        if exported["ledger"]["actions"] or exported["connected_journal"]["entries"]:
            raise ValueError("FRESH_DEVELOPMENT_ACCOUNT_MUST_BE_EMPTY")
        return {"accepted": True, "scope": "FRESH_DEVELOPMENT_ACCOUNT", "resolved_pending": False}
    old_actions = before["native_actions"]
    ledger, journal = exported["ledger"], exported["connected_journal"]
    old_entries = before["connected_journal"]["entries"]
    entries = journal["entries"]
    if not same(old_actions, ledger["actions"][:len(old_actions)]):
        raise ValueError("ORIGINAL_NATIVE_PREFIX_CHANGED_DURING_REOPEN")
    if not same(before["native_header"]["config"], ledger["config"]):
        raise ValueError("ORIGINAL_NATIVE_CONFIGURATION_CHANGED")
    if not same({k: v for k, v in before["connected_journal"].items() if k != "entries"},
                {k: v for k, v in journal.items() if k != "entries"}) or len(entries) != len(old_entries):
        raise ValueError("ORIGINAL_JOURNAL_AUTHORITY_OR_DENOMINATOR_CHANGED")
    pending = [index for index, row in enumerate(old_entries) if row["status"] == "PENDING"]
    if pending and pending != [len(old_entries) - 1]:
        raise ValueError("ONLY_ONE_FINAL_NATIVE_PENDING_INTENT_ALLOWED")
    for index, old in enumerate(old_entries):
        new = entries[index]
        if old["status"] != "PENDING":
            if not same(old, new):
                raise ValueError("ORIGINAL_COMPLETE_JOURNAL_ENTRY_CHANGED")
        else:
            mutable = {"status", "receipt", "obligation_receipt"}
            if not same({k: v for k, v in old.items() if k not in mutable},
                        {k: v for k, v in new.items() if k not in mutable}):
                raise ValueError("ORIGINAL_PENDING_INTENT_CHANGED")
            if old.get("obligation_receipt") is not None and not same(old["obligation_receipt"], new["obligation_receipt"]):
                raise ValueError("EXISTING_PENDING_OBLIGATION_RECEIPT_CHANGED")
            if new["status"] not in {"COMPLETE", "REJECTED"}:
                raise ValueError("BUILT_IN_NATIVE_RECOVERY_DID_NOT_RESOLVE_INTENT")
    if not pending and (not same(old_actions, ledger["actions"]) or not same(before["connected_journal"], journal)):
        raise ValueError("UNEXPLAINED_NATIVE_REOPEN_MUTATION")
    if pending:
        old, resolved = old_entries[-1], entries[-1]
        start = old.get("attempt", {}).get("native_sequence")
        if type(start) is not int or not 0 <= start <= len(old_actions):
            raise ValueError("BOUND_PENDING_PREATTEMPT_SEQUENCE_REQUIRED")
        request = old["request"]
        expected = []
        if resolved["status"] == "REJECTED":
            if len(ledger["actions"]) != len(old_actions):
                raise ValueError("REJECTED_PENDING_INTENT_APPENDED_NATIVE_ACTION")
        elif request["operation"] == "execute":
            expected = [{"op": request["op"], "args": request["args"], "day": request["day"]}]
        elif request["operation"] == "spend" and resolved["funding"] == "SEED":
            expected = [{"op": "cost", "args": {"id": _seed_id(request, journal["source"]["sha256"]),
                         "amount": request["amount"]}, "day": request["day"]}]
        elif request["operation"] == "spend" and resolved["funding"] == "EARNED":
            plan = resolved["plan"]
            proof = exported["action_proofs"][plan["plan_id"]]["body"]
            obligation = resolved["obligation_receipt"]
            expected = [
                {"op": "reserve", "args": {"id": plan["plan_id"], "amount": request["amount"],
                    "expected_net_value": request["expected_net"], "intent_sha256": digest(proof)}, "day": request["day"]},
                {"op": "finish", "args": {"id": plan["plan_id"], "amount": request["amount"],
                    "artifact_sha256": digest({"work_artifact_sha256": digest(request["work"]),
                                                "obligation_receipt_sha256": digest(obligation)})}, "day": request["day"]},
            ]
        else:
            raise ValueError("UNSUPPORTED_PENDING_OPERATION_FOR_RECOVERY")
        if resolved["status"] == "COMPLETE":
            observed = [{key: row[key] for key in ("op", "args", "day")} for row in ledger["actions"][start:]]
            if not same(observed, expected):
                raise ValueError("NATIVE_REOPEN_APPENDED_BEYOND_EXACT_PENDING_INTENT")
    return {"accepted": True, "resolved_pending": bool(pending),
            "original_native_actions": len(old_actions), "reopened_native_actions": len(ledger["actions"]),
            "original_journal_entries": len(old_entries),
            "pending_resolution_status": entries[-1]["status"] if pending else None,
            "original_public_prefix_sha256": digest(before), "reopened_public_export_sha256": digest(exported)}


def _encode(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if is_dataclass(value):
        return {"__dataclass__": type(value).__name__, "value": _encode(asdict(value))}
    if isinstance(value, Path):
        return {"__path__": str(value)}
    if isinstance(value, Fraction):
        return {"__fraction__": [value.numerator, value.denominator]}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(item) for item in value]}
    if isinstance(value, set):
        items = [_encode(item) for item in value]
        return {"__set__": sorted(items, key=canonical)}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: _encode(item) for key, item in value.items()}
    raise ValueError("UNSUPPORTED_CONTROLLER_CHECKPOINT_VALUE:" + type(value).__name__)


def controller_state(local_values):
    from portfolio071.service import load_contracts
    if local_values.get("load_contracts") is not load_contracts:
        raise ValueError("ORIGINAL_SERVICE_LOADER_BINDING_REQUIRED")
    omitted = {"account", "session", "root", "output", "started_cpu", "started_wall", "load_contracts"}
    return {key: _encode(value) for key, value in local_values.items() if key not in omitted}


class RecoveryInterrupted(BaseException):
    """Controlled development interruption after durable operation/checkpoint."""


class RecoverySession:
    def __init__(self, original_account_path, output, recipe, *,
                 registration_commit=None, registration_sha256=None,
                 expected_source_hashes=None, development=False,
                 stop_after_new_operations=None):
        self.original_account_path = Path(original_account_path).absolute()
        self.output = Path(output).absolute()
        self.recipe = copy.deepcopy(recipe)
        self.development = development
        self.registration_commit = registration_commit
        self.registration_sha256 = registration_sha256
        self.expected_sources = expected_source_hashes or source_hashes()
        if not development and (not re.fullmatch(r"[0-9a-f]{40}", registration_commit or "")
                or not re.fullmatch(r"[0-9a-f]{64}", registration_sha256 or "")):
            raise ValueError("PROSPECTIVE_PUBLIC_RECOVERY_REGISTRATION_REQUIRED")
        if stop_after_new_operations is not None and (not development or type(stop_after_new_operations) is not int or stop_after_new_operations < 1):
            raise ValueError("CONTROLLED_INTERRUPTION_IS_DEVELOPMENT_ONLY")
        self.stop_after_new_operations = stop_after_new_operations
        self._adapter = None
        self.attempt = None
        self.before = None
        self.reopen = None
        self.cutover = None
        self.final_export = None
        self._started_cpu = time.process_time()
        self._started_wall = time.monotonic()
        self._check_sources()

    def _check_sources(self):
        if set(self.expected_sources) != set(SOURCE_NAMES) or self.expected_sources != source_hashes():
            raise ValueError("RECOVERY_SOURCE_CHANGED")

    def account(self, root, manifest, *, opening, working, contract):
        if self._adapter is not None:
            raise ValueError("ONE_ORIGINAL_ACCOUNT_OPEN_PER_RECOVERY_ATTEMPT")
        self._check_sources()
        root = Path(root).absolute()
        if any(path.is_symlink() for path in [self.output, *self.output.parents, self.original_account_path, *self.original_account_path.parents]):
            raise ValueError("REGULAR_ORIGINAL_ACCOUNT_AND_RECOVERY_OUTPUT_REQUIRED")
        if self.output == self.original_account_path.parent:
            raise ValueError("RECOVERY_OUTPUT_MUST_NOT_REPLACE_ORIGINAL_ACCOUNT_OUTPUT")
        original_manifest = self.original_account_path.parent / "manifest.json"
        if not self.development or original_manifest.exists() or original_manifest.is_symlink():
            if not same(read(original_manifest), manifest):
                raise ValueError("ORIGINAL_ACCOUNT_MANIFEST_CHANGED")
        if (self.output / "trajectory.json").exists() or (self.output / "RECOVERY_RESULT.json").exists():
            raise ValueError("COMPLETED_RECOVERY_OUTPUT_MUST_NOT_BE_REOPENED")
        self.output.mkdir(parents=True, exist_ok=True)
        prior = sorted(self.output.glob("recovery-attempt-*"))
        number = len(prior) + 1
        if [p.name for p in prior] != [f"recovery-attempt-{i:04d}" for i in range(1, number)]:
            raise ValueError("CONTIGUOUS_PRESERVED_RECOVERY_ATTEMPTS_REQUIRED")
        self.attempt = self.output / f"recovery-attempt-{number:04d}"
        self.attempt.mkdir(exist_ok=False)
        existing_paths = [self.original_account_path] + [
            self.original_account_path.with_name(self.original_account_path.name + suffix)
            for suffix in (".actions.jsonl", ".connected-journal.json", ".adaptive-account.json",
                           ".adaptive-simulation-key", ".adaptive-proofs.json", ".adaptive-resolutions.json")]
        exists = any(path.exists() or path.is_symlink() for path in existing_paths)
        if not exists and not self.development:
            raise ValueError("CANONICAL_RECOVERY_CANNOT_CREATE_AN_ACCOUNT")
        self.before = public_before_open(self.original_account_path) if exists else None
        if self.before is not None:
            write_new(self.attempt / "PREOPEN_PUBLIC.json", self.before)
        write_new(self.attempt / "ATTEMPT_START.json", {
            "schema": "portfolio071/recovery-attempt/v1", "attempt": number,
            "development": self.development, "registration_commit": self.registration_commit,
            "registration_sha256": self.registration_sha256, "sources": self.expected_sources,
            "recipe": self.recipe, "original_directory": self.original_account_path.parent.name,
            "original_account_existed": exists, "opening": opening, "working": working,
            "contract": contract, "manifest_sha256": digest(manifest),
            "preopen_public_sha256": digest(self.before) if self.before is not None else None,
            "started_utc": datetime.now(timezone.utc).isoformat(), "automatic_retries": 0})
        live = None
        try:
            live = JournalAccount(root, manifest, self.original_account_path,
                                  opening=opening, working=working, contract=contract)
            initial = live.export()
            self.reopen = check_native_reopen(self.before, initial)
            write_new(self.attempt / "NATIVE_REOPEN.json", self.reopen)
            self._adapter = ReplayThenAppend(self, live, root, manifest, initial)
            return self._adapter
        except BaseException as error:
            if live is not None:
                live.close()
            write_new(self.attempt / "ATTEMPT_RESULT.json", {
                "schema": "portfolio071/recovery-attempt-result/v1", "accepted": False,
                "status": "OWNER_REOPEN_OR_RECONSTRUCTION_SETUP_FAILED",
                "error_type": type(error).__name__, "error": str(error), "automatic_retries": 0})
            raise

    def annotate_resources(self, record):
        self._check_sources()
        if self.cutover is None or self.final_export is None:
            raise ValueError("EXACT_PREFIX_CUTOVER_AND_CLOSED_ACCOUNT_REQUIRED")
        record["resource_measurement"].update({
            "measurement_scope": "THIS_RECOVERY_INVOCATION_ONLY_INCLUDING_RECONSTRUCTION",
            "pre_interruption_process_cpu_seconds": None,
            "pre_interruption_wall_seconds": None,
            "complete_lineage_cpu_seconds": None,
            "unknown_scope": "Prior interrupted process telemetry was lost; no zero-cost or full-duration claim."})
        record["recovery_provenance"] = {
            "schema": "portfolio071/recovered-trajectory/v1", "sources": self.expected_sources,
            "registration_commit": self.registration_commit,
            "registration_sha256": self.registration_sha256,
            "original_directory": self.original_account_path.parent.name,
            "attempt_directory": self.attempt.name, "cutover": self.cutover,
            "native_reopen": self.reopen, "same_original_account": True,
            "new_equity_or_financing": 0, "automatic_retries": 0,
            "scope": "Same original account and unchanged economic policy after exact historical reconstruction; not an uninterrupted original process."}

    def finish(self, record):
        self._check_sources()
        if self.final_export is None or self.cutover is None:
            raise ValueError("COMPLETED_RECOVERED_CONTROLLER_REQUIRED")
        names = ("manifest.json", "trajectory.json", "native-at-horizon.json", "native-after-drain.json")
        files = {name: sha(self.output / name) for name in names}
        result = {"schema": "portfolio071/recovery-result/v1", "accepted": True,
            "id": record["id"], "recipe": self.recipe, "sources": self.expected_sources,
            "registration_commit": self.registration_commit,
            "registration_sha256": self.registration_sha256,
            "original_directory": self.original_account_path.parent.name,
            "recovery_directory": self.output.name, "attempt_directory": self.attempt.name,
            "native_reopen": self.reopen, "cutover": self.cutover,
            "public_output_sha256": files, "final_public_export_sha256": digest(self.final_export),
            "new_equity_or_financing": 0, "automatic_retries": 0,
            "process_cpu_seconds_observed_this_attempt": time.process_time() - self._started_cpu,
            "wall_seconds_observed_this_attempt": time.monotonic() - self._started_wall,
            "pre_interruption_resource_use": None,
            "scope": "Controller completion with retained original native history; independent full native/prefix/aggregate audits remain required."}
        write_new(self.output / "RECOVERY_RESULT.json", result)
        return result


class ReplayThenAppend:
    def __init__(self, session, live, root, manifest, initial):
        self.session, self.live, self.root = session, live, root
        self.manifest, self.initial = copy.deepcopy(manifest), copy.deepcopy(initial)
        self.entries = self.initial["connected_journal"]["entries"]
        self.actions = self.initial["ledger"]["actions"]
        self.journal_position = self.native_position = 0
        self.closed = self.append_mode = False
        self._mark = None
        self._nested = 0
        self.new_operations = 0
        self.checkpoint = None
        self.checkpoint_state_seen = self.checkpoint_result_seen = True
        self.checkpoint_path = session.output / "PRIVATE_CONTROLLER_CHECKPOINT.json"
        self._tmp = tempfile.TemporaryDirectory(prefix="portfolio071-history-replay-")
        config = self.initial["ledger"]["config"]
        self.replay = SingleWriterExchange(Path(self._tmp.name) / "replay.sqlite",
            root=root, manifest=manifest, opening=config["opening"], working=config["working"],
            contract=config["contract"], durable=False,
            _account_capability=_ADAPTIVE_ACCOUNT_CAPABILITY)
        try:
            if self.checkpoint_path.exists():
                envelope = read(self.checkpoint_path)
                state = live.verify_checkpoint(envelope)
                if (state.get("schema") != CHECKPOINT_SCHEMA
                        or state.get("stage") not in {"BEFORE_CALL", "AFTER_CALL"}
                        or not same(state.get("sources"), session.expected_sources)
                        or not same(state.get("recipe"), session.recipe)):
                    raise ValueError("CHECKPOINT_RECOVERY_SOURCE_OR_RECIPE_CHANGED")
                self.checkpoint = state
                self.checkpoint_state_seen = False
                self.checkpoint_result_seen = state["stage"] == "BEFORE_CALL"
                # This is private operating recovery authority, not a public artifact.
                write_new(session.attempt / "PRIVATE_PREVIOUS_CHECKPOINT.json", envelope)
            self._maybe_cutover()
        except BaseException:
            self.replay.close()
            self._tmp.cleanup()
            raise

    def _guard(self):
        if self.closed:
            raise ValueError("RECOVERY_ACCOUNT_CLOSED")
        self.session._check_sources()

    def _snapshot(self):
        tape = self.replay.export()
        return {"summary": copy.deepcopy(tape["summary"]),
            "state_digest": digest({"config": tape["config"], "actions_sha256": tape["actions_sha256"], "summary": tape["summary"]}),
            "actions_sha256": tape["actions_sha256"], "sequence": len(tape["actions"]),
            "scope": "SIMULATED", "ownership": "MANDATORY_SINGLE_LOCAL_POSIX_WRITER",
            "filesystem": copy.deepcopy(self.initial["snapshot"]["filesystem"])}

    def snapshot(self):
        self._guard()
        return self.live.snapshot() if self.append_mode else self._snapshot()

    def _historical_export(self):
        ledger = self.replay.export()
        reserved = {row["args"]["id"] for row in ledger["actions"] if row["op"] == "reserve"}
        finished = {row["args"]["id"] for row in ledger["actions"] if row["op"] == "finish"}
        result = {key: copy.deepcopy(value) for key, value in self.initial.items()
                  if key not in {"ledger", "snapshot", "action_proofs", "obligation_resolutions", "connected_journal", "connected_journal_sha256"}}
        journal = {**copy.deepcopy(self.initial["connected_journal"]),
                   "entries": copy.deepcopy(self.entries[:self.journal_position])}
        result.update(ledger=ledger, snapshot=self._snapshot(),
            action_proofs={key: copy.deepcopy(value) for key, value in self.initial["action_proofs"].items() if key in reserved},
            obligation_resolutions={key: copy.deepcopy(value) for key, value in self.initial["obligation_resolutions"].items() if key in finished},
            connected_journal=journal, connected_journal_sha256=digest(journal))
        return result

    def export(self):
        self._guard()
        return self.live.export() if self.append_mode else self._historical_export()

    def audit(self):
        self._guard()
        return self.live.audit() if self.append_mode else audit_journal(self._historical_export(), root=self.root, manifest=self.manifest)

    def mark(self, label, local_values):
        self._guard()
        if not isinstance(label, str) or not re.fullmatch(r"stable-original-line-[0-9]+", label):
            raise ValueError("STABLE_ORIGINAL_CONTROLLER_LOCATION_REQUIRED")
        state = controller_state(local_values)
        snapshot = self.snapshot()
        self._mark = {"marker": label, "controller_state": state,
                      "before_native_sequence": snapshot["sequence"],
                      "before_actions_sha256": snapshot["actions_sha256"]}
        if self.checkpoint is not None and all(same(self._mark[key], self.checkpoint.get(key)) for key in self._mark):
            self.checkpoint_state_seen = True
        self._maybe_cutover()
        if self.append_mode:
            self._checkpoint("BEFORE_CALL", None, None)

    def _checkpoint(self, stage, request, result):
        if self._mark is None:
            raise ValueError("CONTROLLER_STATE_MARK_REQUIRED_BEFORE_NEW_OPERATION")
        state = {"schema": CHECKPOINT_SCHEMA, "sources": self.session.expected_sources,
                 "recipe": self.session.recipe, **copy.deepcopy(self._mark),
                 "stage": stage, "request": copy.deepcopy(request), "result": copy.deepcopy(result)}
        envelope = self.live.seal_checkpoint(state)
        atomic_bytes(self.checkpoint_path, canonical(envelope) + b"\n")

    def _step_native(self, target):
        if type(target) is not int or not self.native_position <= target <= len(self.actions):
            raise ValueError("EXACT_MONOTONE_JOURNAL_NATIVE_BOUNDARY_REQUIRED")
        while self.native_position < target:
            event = self.actions[self.native_position]
            if type(event.get("seq")) is not int or event["seq"] != self.native_position:
                raise ValueError("ORIGINAL_NATIVE_SEQUENCE_CHANGED")
            after = self.replay._exchange.execute(event["op"], event["args"], event["day"],
                                                   _expected_before=event.get("before"))
            if not same(after, event["after"]):
                raise ValueError("RECONSTRUCTED_NATIVE_STATE_DIFFERS")
            self.native_position += 1

    def _maybe_cutover(self):
        if self.append_mode or self.journal_position != len(self.entries):
            return
        if self.native_position != len(self.actions):
            raise ValueError("UNEXPLAINED_NATIVE_ACTIONS_OUTSIDE_JOURNAL_PREFIX")
        if not (self.checkpoint_state_seen and self.checkpoint_result_seen):
            return
        rebuilt = self._historical_export()
        if not same(rebuilt, self.initial) or not same(self.live.export(), self.initial):
            raise ValueError("RECONSTRUCTED_NATIVE_EXPORT_NOT_EXACT_ORIGINAL_ACCOUNT")
        self.session.cutover = {"accepted": True, "matched_original_journal_entries": self.journal_position,
            "matched_original_native_actions": self.native_position,
            "reconstructed_public_export_sha256": digest(rebuilt),
            "authenticated_live_export_sha256": digest(self.initial),
            "checkpoint_present": self.checkpoint is not None,
            "checkpoint_state_and_result_reconstructed": self.checkpoint_state_seen and self.checkpoint_result_seen,
            "new_operation_count_at_cutover": self.new_operations}
        write_new(self.session.attempt / "EXACT_CUTOVER.json", self.session.cutover)
        self.replay.close()
        self._tmp.cleanup()
        self.append_mode = True

    def _historical(self, key, request):
        for row in self.entries[:self.journal_position]:
            if row["key"] == key:
                if not same(row["request"], request):
                    raise ValueError("HISTORICAL_IDEMPOTENT_PAYLOAD_CHANGED")
                if row["status"] == "REJECTED":
                    raise ValueError(row["receipt"]["error"])
                return copy.deepcopy(row["receipt"])
        if self.journal_position >= len(self.entries):
            self._maybe_cutover()
            if not self.append_mode:
                raise ValueError("SIGNED_CHECKPOINT_STATE_NOT_RECONSTRUCTED")
            raise AssertionError("CUTOVER_MUST_BE_HANDLED_BY_CALLER")
        row = self.entries[self.journal_position]
        if row["key"] != key or not same(row["request"], request):
            raise ValueError("HISTORICAL_CONTROLLER_REQUEST_MISMATCH")
        if row["status"] == "COMPLETE":
            receipt = row["receipt"]
            target = receipt["sequence"] if request["operation"] == "execute" else receipt["native_event_sequence"] + 1
            self._step_native(target)
        elif row["status"] == "REJECTED":
            receipt = row["receipt"]
            if receipt["native_sequence"] != self.native_position:
                raise ValueError("HISTORICAL_REJECTION_CHANGED_NATIVE_PREFIX")
        else:
            raise ValueError("UNRESOLVED_NATIVE_INTENT_AFTER_OWNER_REOPEN")
        self.journal_position += 1
        if row["status"] == "REJECTED":
            self._maybe_cutover()
            raise ValueError(receipt["error"])
        return copy.deepcopy(receipt)

    def _after(self, request, result, *, appended):
        if self._nested:
            self._maybe_cutover()
            return result
        if (self.checkpoint is not None and self.checkpoint_state_seen
                and self.checkpoint["stage"] == "AFTER_CALL"
                and same(request, self.checkpoint.get("request"))):
            if not same(result, self.checkpoint.get("result")):
                raise ValueError("SIGNED_CHECKPOINT_OPERATION_RESULT_CHANGED")
            self.checkpoint_result_seen = True
        self._maybe_cutover()
        if appended:
            self.new_operations += 1
            self._checkpoint("AFTER_CALL", request, result)
            if self.session.stop_after_new_operations == self.new_operations:
                raise RecoveryInterrupted("CONTROLLED_DEVELOPMENT_INTERRUPTION_AFTER_DURABLE_OPERATION")
        return result

    def execute(self, op, args, day):
        self._guard()
        _validate_native_request(op, args, day)
        request = {"operation": "execute", "op": op, "args": copy.deepcopy(args), "day": day}
        self._maybe_cutover()
        appended = self.append_mode
        if appended:
            result = self.live.execute(op, args, day)
        else:
            result = self._historical("native:" + _native_id(op, args), request)
        return self._after(request, result, appended=appended)

    def cost(self, ident, amount, day):
        validate_amount(amount)
        return self.execute("cost", {"id": _identifier(ident), "amount": amount}, day)

    def spend(self, ident, kind, amount, day, work, expected_net, allow_seed=False):
        self._guard()
        _identifier(ident); _identifier(kind); validate_amount(amount)
        if type(day) is not int or day < 0 or type(expected_net) is not int or type(allow_seed) is not bool:
            raise ValueError("DECLARED_CONNECTED_RESOURCE_CONTRACT_REQUIRED")
        if len(canonical(work)) > 1_000_000:
            raise ValueError("BOUNDED_CONNECTED_RESOURCE_WORK_REQUIRED")
        request = {"operation": "spend", "id": ident, "kind": kind, "amount": amount, "day": day,
                   "work": copy.deepcopy(work), "expected_net": expected_net, "allow_seed": allow_seed}
        self._maybe_cutover()
        appended = self.append_mode
        if appended:
            result = self.live.spend(ident, kind, amount, day, work, expected_net, allow_seed=allow_seed)
        else:
            prior = next((row for row in self.entries[:self.journal_position] if row["key"] == "spend:" + ident), None)
            summary = self.snapshot()["summary"]
            earned = expected_net > 0 and min(summary["available"], summary["unrestrictedEarned"]) >= amount
            refuses = (amount == 0 or summary["investmentStopped"]
                       or (not earned and (not allow_seed or summary["available"] < amount)))
            if prior is None and refuses:
                result = None
            else:
                result = self._historical("spend:" + ident, request)
        return self._after(request, result, appended=appended)

    def advance_financial(self, day):
        self._guard()
        if type(day) is not int or day < 0:
            raise ValueError("EXPLICIT_FINANCIAL_EVENT_DAY_REQUIRED")
        request = {"operation": "advance_financial", "day": day}
        self._maybe_cutover()
        appended = self.append_mode
        if appended:
            result = self.live.advance_financial(day)
        else:
            tape = self.replay.export()
            if tape["actions"] and day < tape["actions"][-1]["day"]:
                raise ValueError("EVENT_TIME_REGRESSION")
            terms = {row["id"]: strict_json(row["terms"]) for row in tape.get("prospective_terms", [])}
            states = {row["id"]: row["state"] for row in tape["orders"]}
            self._nested += 1
            try:
                for row in tape.get("prospective_orders", []):
                    if row["matured_at"] is None and states[row["order_id"]] in {"released", "breached"} and day > terms[row["terms_id"]]["maturity_day"]:
                        self.execute("mature", {"id": row["order_id"], "event_id": "maturity:" + row["order_id"] + ":" + row["terms_sha256"][:20]}, day)
            finally:
                self._nested -= 1
            result = self.snapshot()
            appended = self.append_mode and self.native_position < len(self.live.export()["ledger"]["actions"])
        return self._after(request, result, appended=appended)

    def close(self, exc_type=None, exc=None):
        if self.closed:
            return
        try:
            if exc_type is None:
                self._maybe_cutover()
                if not self.append_mode:
                    raise ValueError("CONTROLLER_ENDED_BEFORE_EXACT_PREFIX_CUTOVER")
                self.session.final_export = self.live.export()
            write_new(self.session.attempt / "ATTEMPT_RESULT.json", {
                "schema": "portfolio071/recovery-attempt-result/v1",
                "accepted": exc_type is None, "status": "CONTROLLER_CONTEXT_COMPLETE" if exc_type is None else "INTERRUPTED_OR_FAILED_NO_AUTOMATIC_RETRY",
                "error_type": exc_type.__name__ if exc_type else None, "error": str(exc) if exc else None,
                "matched_journal_entries": self.journal_position, "matched_native_actions": self.native_position,
                "new_operations": self.new_operations, "cutover": self.session.cutover,
                "private_checkpoint_preserved": self.checkpoint_path.exists(), "automatic_retries": 0})
        finally:
            self.closed = True
            self.replay.close()
            self._tmp.cleanup()
            self.live.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close(exc_type, exc)


def recover_trajectory(root, manifest, original_account_path, output, *, capital_usd,
                       world=None, policy="working_capital_aware", earned_only_k2=False,
                       horizon_days=1825, infer_idle_days=True, registration_commit=None,
                       registration_sha256=None, expected_source_hashes=None,
                       development=False, stop_after_new_operations=None):
    from portfolio071.economics import World
    from portfolio071.recovery_controller import execute_recovered, validate_controller
    validate_controller()
    world = World() if world is None else world
    recipe = {"world": asdict(world), "capital_usd": capital_usd, "policy": policy,
              "earned_only_k2": earned_only_k2, "horizon_days": horizon_days,
              "infer_idle_days": infer_idle_days}
    session = RecoverySession(original_account_path, output, recipe,
        registration_commit=registration_commit, registration_sha256=registration_sha256,
        expected_source_hashes=expected_source_hashes, development=development,
        stop_after_new_operations=stop_after_new_operations)
    record = execute_recovered(root, manifest, output, capital_usd=capital_usd, world=world,
        policy=policy, earned_only_k2=earned_only_k2, horizon_days=horizon_days,
        infer_idle_days=infer_idle_days, session=session)
    session.finish(record)
    return record
