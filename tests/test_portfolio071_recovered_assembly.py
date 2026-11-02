"""Independent assembly refuses stale, remapped or nonpublic recovery evidence."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import canonical, digest
from scripts import assemble_portfolio071_recovered as check


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")


class RecoveredAssemblyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.commit, self.freeze = "a" * 40, "b" * 64
        self.sources = {name: str(i) * 64 for i, name in enumerate(check.SOURCES, 1)}

    def tearDown(self):
        self.temp.cleanup()

    def public_files(self, folder):
        for name in check.PUBLIC_FILES:
            put(folder / name, {"file": name})
        return check.public_input_hashes(folder)

    def producer(self, attempts=1):
        job = check.recipes()[8]
        folder = self.root / "recovery" / job["directory"]
        header = {"config": {"contract": "fixture", "opening": 1}}
        actions = [{"seq": 0, "op": "cost", "args": {"id": "init", "amount": 1}, "day": 0}]
        journal = {"entries": [{"key": "init", "status": "COMPLETE"}]}
        raw = canonical(header) + b"\n" + b"".join(canonical(row) + b"\n" for row in actions)
        before = {"native_header": header, "native_actions": actions, "connected_journal": journal,
                  "native_tape_sha256": hashlib.sha256(raw).hexdigest(), "native_tape_bytes": len(raw),
                  "journal_body_sha256": digest(journal), "native_actions_sha256": digest(actions),
                  "native_action_count": len(actions), "journal_entry_count": len(journal["entries"])}
        manifest = {"jobs": []}
        identity = {"durable_actions_file_sha256": before["native_tape_sha256"],
                    "durable_actions_file_bytes": before["native_tape_bytes"],
                    "journal_body_sha256": before["journal_body_sha256"],
                    "native_actions": 1, "journal_entries": 1, "manifest_canonical_sha256": digest(manifest)}
        cutover = {"accepted": True, "matched_original_native_actions": 1,
                   "matched_original_journal_entries": 1, "reconstructed_public_export_sha256": "d" * 64,
                   "authenticated_live_export_sha256": "d" * 64,
                   "checkpoint_state_and_result_reconstructed": True, "new_operation_count_at_cutover": 0}
        reopened = {"accepted": True, "original_public_prefix_sha256": digest(before),
                    "reopened_native_actions": 1, "original_journal_entries": 1,
                    "reopened_public_export_sha256": "d" * 64}
        provenance = {"same_original_account": True, "cutover": cutover, "native_reopen": reopened,
                      "registration_commit": self.commit, "registration_sha256": self.freeze, "sources": self.sources}
        trajectory = {"recovery_provenance": provenance}
        final = {"ledger": {"actions": actions}, "connected_journal": journal}
        for name, value in zip(check.PUBLIC_FILES, (manifest, trajectory, final, final)):
            put(folder / name, value)
        hashes = check.public_input_hashes(folder)
        recipe = check.recipe_for_recovery(job)
        for number in range(1, attempts + 1):
            attempt = folder / f"recovery-attempt-{number:04d}"
            start = {"schema": "portfolio071/recovery-attempt/v1", "development": False,
                     "original_account_existed": True, "attempt": number, "recipe": recipe,
                     "sources": self.sources, "registration_commit": self.commit,
                     "registration_sha256": self.freeze, "original_directory": job["directory"],
                     "opening": job["capital_usd"] * 1_000_000, "working": 0,
                     "contract": "portfolio071-" + digest(check.expected_id(job))[:24],
                     "manifest_sha256": digest(manifest), "preopen_public_sha256": digest(before)}
            put(attempt / "ATTEMPT_START.json", start)
            put(attempt / "PREOPEN_PUBLIC.json", before)
            if number == attempts:
                put(attempt / "NATIVE_REOPEN.json", reopened)
                put(attempt / "EXACT_CUTOVER.json", cutover)
                put(attempt / "ATTEMPT_RESULT.json", {"accepted": True,
                    "status": "CONTROLLER_CONTEXT_COMPLETE", "cutover": cutover})
        result = {"schema": "portfolio071/recovery-result/v1", "accepted": True,
                  "id": check.expected_id(job), "recipe": recipe, "sources": self.sources,
                  "registration_commit": self.commit, "registration_sha256": self.freeze,
                  "original_directory": job["directory"], "recovery_directory": job["directory"],
                  "new_equity_or_financing": 0, "automatic_retries": 0,
                  "public_output_sha256": hashes, "attempt_directory": f"recovery-attempt-{attempts:04d}",
                  "cutover": cutover, "native_reopen": reopened, "final_public_export_sha256": digest(final)}
        put(folder / "RECOVERY_RESULT.json", result)
        return folder, job, identity, hashes

    def call_producer(self, fixture):
        folder, job, identity, hashes = fixture
        return check.check_producer(folder, job, identity, self.sources, self.commit, self.freeze, hashes)

    def schedule(self):
        targets = check.RECOVERED_INDICES + check.FRESH
        value = {"schema": "portfolio071/recovery-scheduling/v1", "accepted": True, "failures": [],
                 "full24_independent_acceptance": False, "registration_commit": self.commit,
                 "registration_sha256": self.freeze, "runner_sha256": "c" * 64, "sources": self.sources,
                 "financial_and_orchestration_binding": {"economic_freeze_sha256": check.FINANCIAL_FREEZE_SHA256,
                    "orchestration_freeze_sha256": check.ORCHESTRATION_FREEZE_SHA256,
                    "original_source_count": 72, "runtime_source_hashes": {str(i): "d" * 64 for i in range(56)}},
                 "worker_count": 2, "resource_limits": {"conservative_worker_maximum": 4},
                 "recovered_indices": check.RECOVERED_INDICES, "unopened_indices": check.FRESH,
                 "preserved_complete_indices": check.CLOSED, "completed_indices": targets,
                 "closed_public_identities": {}, "automatic_retries": 0, "scheduled_indices": list(targets),
                 "retained_indices": [], "execution_statuses": [{"index": i, "status":
                    "COMPLETED_FIRST_ORIGINAL_EXECUTION" if i == 23 else "COMPLETED_SAME_ACCOUNT_RECOVERY"} for i in targets]}
        self.put_schedule(value)
        return value

    def put_schedule(self, value):
        folder = self.root / "recovery"
        put(folder / "RECOVERY_SCHEDULING_RESULT.json", value)
        put(folder / "stage-attempt-0001/START.json", value)
        put(folder / "stage-attempt-0001/RESULT.json", value)

    def call_schedule(self):
        return check.check_schedule(self.root, self.commit, self.freeze, self.sources, {check.RUNNER: "c" * 64}, {})

    def test_exact24_map_has16_original7_recovered1_first(self):
        rows = check.path_map()
        self.assertEqual([row["index"] for row in rows], list(range(24)))
        self.assertEqual([row["index"] for row in rows if row["disposition"] == "RECOVERED_SAME_ORIGINAL_ACCOUNT"], check.RECOVERED_INDICES)
        self.assertEqual([row["index"] for row in rows if row["disposition"] == "FIRST_ORIGINAL_EXECUTION"], [23])
        self.assertEqual(len({row["original_account_directory"] for row in rows}), 24)
        self.assertTrue(all(row["public_source"].startswith("recovery/") for row in rows if row["index"] in check.RECOVERED_INDICES))

    def test_recipe_identity_preserves_original_menu_order(self):
        from scripts.replay_portfolio071_parallel import registered_jobs
        jobs = check.recipes()
        self.assertEqual([{k: v for k, v in job.items() if k != "infer_idle_days"} for job in jobs], registered_jobs())
        self.assertEqual(len({check.expected_id(job) for job in jobs}), 24)

    def test_prospective_source_guard_checks_actual_frozen_repository(self):
        repo = Path(__file__).resolve().parents[1]
        names = {*check.SOURCES, check.RUNNER, check.THIS_SOURCE, check.PREFIX_PATH,
                 check.SECOND_PREFIX_PATH, check.ORCHESTRATION_V1_PATH, check.WORKFLOW_V1_PATH,
                 "scripts/verify_portfolio071_recovery_prefix.py"}
        registration = {"recovered_indices": check.RECOVERED_INDICES, "unopened_indices": check.FRESH,
                        "preserved_complete_indices": check.CLOSED, "registered_total_accounts": 24,
                        "financial_freeze_sha256": check.FINANCIAL_FREEZE_SHA256,
                        "orchestration_freeze_sha256": check.ORCHESTRATION_FREEZE_SHA256,
                        "source_hashes": {name: check.sha(repo / name) for name in names}}
        path = self.root / "development-only-registration-fixture.json"
        put(path, registration)
        financial, actual, sources = check.check_sources(repo, path, self.commit)
        self.assertEqual(len(financial["source_hashes"]), 72)
        self.assertEqual(actual, registration)
        self.assertEqual(sources, {name: registration["source_hashes"][name] for name in check.SOURCES})
        registration["source_hashes"][check.SOURCES[0]] = "0" * 64
        put(path, registration)
        with self.assertRaisesRegex(ValueError, "REGISTERED_SOURCE_CHANGED"):
            check.check_sources(repo, path, self.commit)

    def test_scheduler_preserves_original_interrupted_receipts(self):
        value = self.schedule()
        observed, evidence = self.call_schedule()
        self.assertEqual(observed, value)
        self.assertEqual(len(evidence["attempts"]), 1)
        put(self.root / "ORCHESTRATION.json", {"accepted": True})
        with self.assertRaisesRegex(ValueError, "ORIGINAL_INTERRUPTED_ORCHESTRATION"):
            self.call_schedule()

    def test_scheduler_cannot_remap_fresh23_to_recovered(self):
        value = self.schedule()
        value["execution_statuses"][-1]["status"] = "COMPLETED_SAME_ACCOUNT_RECOVERY"
        self.put_schedule(value)
        with self.assertRaisesRegex(ValueError, "EXACT_COMPLETION_DISPOSITION"):
            self.call_schedule()

    def test_scheduler_cannot_hide_missing_or_duplicate_index(self):
        value = self.schedule()
        value["scheduled_indices"][-1] = 22
        self.put_schedule(value)
        with self.assertRaisesRegex(ValueError, "EXACT_SCHEDULED_RETAINED_PARTITION"):
            self.call_schedule()

    def test_scheduler_cannot_claim_full_independent_acceptance(self):
        value = self.schedule()
        value["full24_independent_acceptance"] = True
        self.put_schedule(value)
        with self.assertRaisesRegex(ValueError, "WITHOUT_INDEPENDENT_PROMOTION"):
            self.call_schedule()

    def test_current_inputs_are_bound_around_fresh_audit(self):
        folder = self.root / "arm-08"
        expected = self.public_files(folder)
        with patch.object(check, "audit_arm", return_value={"accepted": True, "arm": "arm-08"}) as auditor:
            result, actual, elapsed = check.audit_current(self.root, folder)
        auditor.assert_called_once_with(self.root, folder)
        self.assertEqual(expected, actual)
        self.assertTrue(result["accepted"])
        self.assertGreaterEqual(elapsed, 0)

    def test_mutation_during_fresh_audit_is_refused(self):
        folder = self.root / "arm-08"
        self.public_files(folder)
        def mutate(*_):
            put(folder / "native-after-drain.json", {"changed": True})
            return {"accepted": True}
        with patch.object(check, "audit_arm", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "INPUT_CHANGED_DURING_FRESH"):
                check.audit_current(self.root, folder)

    def test_actual_original_public_tail_required_without_reading_database(self):
        folder = self.root / "original"
        folder.mkdir()
        config = {"contract": "original"}
        actions = [{"seq": 0, "after": {"cash": 1}}]
        journal = {"entries": [{"request": "original"}]}
        (folder / "account.sqlite.actions.jsonl").write_bytes(canonical({"config": config}) + b"\n" + canonical(actions[0]) + b"\n")
        put(folder / "account.sqlite.connected-journal.json", {"body": journal, "signature": "not-exported"})
        # An absent SQLite checkpoint is normal after process loss. This reader
        # must validate only the retained public durable history.
        exported = {"ledger": {"config": config, "actions": actions}, "connected_journal": journal}
        result = check.verify_actual_public_tail(folder, exported)
        self.assertEqual(result["native_action_count"], 1)
        self.assertNotIn("signature", str(result))
        changed = copy.deepcopy(exported)
        changed["ledger"]["actions"][0]["after"]["cash"] = 2
        with self.assertRaisesRegex(ValueError, "ACTUAL_ORIGINAL_PUBLIC_TAPE"):
            check.verify_actual_public_tail(folder, changed)

    def test_valid_producer_binds_exact_first_preopen_and_last_cutover(self):
        result = self.call_producer(self.producer())
        self.assertEqual(len(result["attempts"]), 1)
        self.assertTrue(result["cutover"]["accepted"])

    def test_prior_interrupted_attempt_must_remain_in_denominator(self):
        result = self.call_producer(self.producer(attempts=2))
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["attempts"][0]["disposition"], "INTERRUPTED_WITHOUT_TERMINAL_RECEIPT_RETAINED")

    def test_missing_attempt_refused(self):
        fixture = self.producer(attempts=2)
        (fixture[0] / "recovery-attempt-0001").rename(fixture[0] / "removed-attempt-0001")
        with self.assertRaisesRegex(ValueError, "CONTIGUOUS_PRESERVED_ATTEMPTS"):
            self.call_producer(fixture)

    def test_stale_producer_public_output_hashes_refused(self):
        fixture = self.producer()
        hashes = dict(fixture[3]); hashes["trajectory.json"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "STALE_PUBLIC_INPUTS"):
            self.call_producer((*fixture[:3], hashes))

    def test_first_preopen_cannot_be_replaced_with_later_prefix(self):
        fixture = self.producer()
        fixture[2]["native_actions"] = 2
        with self.assertRaisesRegex(ValueError, "FIRST_PREOPEN_DIFFERS"):
            self.call_producer(fixture)

    def test_preopen_claimed_hash_cannot_hide_changed_embedded_actions(self):
        fixture = self.producer()
        before = check.read(fixture[0] / "recovery-attempt-0001/PREOPEN_PUBLIC.json")
        before["native_actions"][0]["args"]["amount"] = 2
        with self.assertRaisesRegex(ValueError, "PREOPEN_PUBLIC_CONTENT_AND_IDENTITIES"):
            check.check_preopen_public(before)

    def test_cutover_before_exact_reconstruction_refused(self):
        fixture = self.producer()
        folder = fixture[0]
        for path in (folder / "RECOVERY_RESULT.json", folder / "recovery-attempt-0001/ATTEMPT_RESULT.json",
                     folder / "recovery-attempt-0001/EXACT_CUTOVER.json"):
            value = check.read(path)
            target = value["cutover"] if "cutover" in value else value
            target["new_operation_count_at_cutover"] = 1
            put(path, value)
        with self.assertRaisesRegex(ValueError, "EXACT_COMPLETE_HISTORICAL_RECONSTRUCTION"):
            self.call_producer(fixture)

    def test_recipe_changed_from_frozen_arm_is_refused(self):
        fixture = self.producer()
        fixture[1]["capital_usd"] *= 2
        with self.assertRaisesRegex(ValueError, "RECIPE_OR_SOURCE_IDENTITY"):
            self.call_producer(fixture)

    def test_public_view_copies_only_exact_four_public_files(self):
        folder = self.root / "recovery/arm-08"
        hashes = self.public_files(folder)
        put(folder / "PRIVATE_CONTROLLER_CHECKPOINT.json", {"private": "never-read"})
        output = self.root / "assembled"; output.mkdir()
        rows = [{"public_source": "recovery/arm-08", "directory": "arm-08", "input_sha256": hashes}]
        view = check.copy_public_view(output, self.root, rows, {"registered_arms": 24})
        self.assertEqual(sorted(p.name for p in (view / "arm-08").iterdir()), sorted(check.PUBLIC_FILES))
        self.assertEqual(check.public_input_hashes(view / "arm-08"), hashes)

    def test_public_view_refuses_attempt_to_include_private_file(self):
        folder = self.root / "recovery/arm-08"
        hashes = self.public_files(folder)
        hashes["PRIVATE_CONTROLLER_CHECKPOINT.json"] = "0" * 64
        output = self.root / "assembled"; output.mkdir()
        rows = [{"public_source": "recovery/arm-08", "directory": "arm-08", "input_sha256": hashes}]
        with self.assertRaisesRegex(ValueError, "ONLY_FOUR_PUBLIC_FILES"):
            check.copy_public_view(output, self.root, rows, {})

    def test_public_view_refuses_stale_source_identity(self):
        folder = self.root / "recovery/arm-08"
        hashes = self.public_files(folder)
        put(folder / "trajectory.json", {"changed": True})
        output = self.root / "assembled"; output.mkdir()
        rows = [{"public_source": "recovery/arm-08", "directory": "arm-08", "input_sha256": hashes}]
        with self.assertRaisesRegex(ValueError, "PUBLIC_VIEW_SOURCE_CHANGED"):
            check.copy_public_view(output, self.root, rows, {})


if __name__ == "__main__":
    unittest.main()
