"""Meaningful scheduling controls; no confirmatory account is opened here."""
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import json
import multiprocessing
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import strict_json
from connected_enterprise.finance import SOURCE_PATHS
from portfolio071.economics import World, execute_trajectory
from portfolio071.service import SOURCES, prepare_manifest
from portfolio071.thermal import construct, development_request
from scripts.replay_portfolio071_parallel import (
    ECONOMIC_FREEZE, ORCHESTRATION_SOURCES, WORKFLOW, _execute_job, _preflight,
    _schedule, registered_jobs, select_workers, validate_completed, validate_freezes,
)


ROOT = Path(__file__).resolve().parents[1]


class ParallelOrchestrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="portfolio071-spawn-development-")
        cls.root = Path(cls.temp.name) / "source"
        for name in sorted(set(SOURCE_PATHS) | set(SOURCES)):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        pairs = []
        for task in ("heat_delivery", "thermal_continuity"):
            request = development_request(task)
            request["id"] = "spawn-development-" + task
            pairs.append((request, construct(request)))
        cls.manifest = prepare_manifest(cls.root, pairs)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_exact_registered_denominator_has_no_duplicate_account_identity(self):
        jobs = registered_jobs()
        self.assertEqual(len(jobs), 24)
        self.assertEqual([j["capital_usd"] for j in jobs[:5]], [25000, 100000, 1000000, 10000000, 1000000000])
        self.assertEqual([j["directory"] for j in jobs], [f"arm-{i:02d}" for i in range(24)])
        self.assertTrue(all(j["horizon_days"] == 1825 for j in jobs))
        self.assertTrue(jobs[-2]["earned_only_k2"])
        self.assertEqual(jobs[-1]["policy"], "stylized_prepaid_reach_capacity")

    def test_explicit_worker_request_cannot_exceed_observed_resource_bound(self):
        with patch("scripts.replay_portfolio071_parallel.resource_limits",
                   return_value={"conservative_worker_maximum": 2}):
            self.assertEqual(select_workers()[0], 2)
            with self.assertRaisesRegex(ValueError, "RESOURCE_BOUND_2"):
                select_workers(3)
        with patch("scripts.replay_portfolio071_parallel.resource_limits",
                   return_value={"conservative_worker_maximum": 0}):
            with self.assertRaisesRegex(ValueError, "INSUFFICIENT_MEMORY"):
                select_workers()

    def test_frozen_executing_and_staged_source_mismatches_are_refused(self):
        original = strict_json(ECONOMIC_FREEZE.read_bytes())
        replica = Path(self.temp.name) / "executing-source-copy"
        paths = set(original["source_hashes"]) | ORCHESTRATION_SOURCES
        for name in paths:
            destination = replica / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        hashes = {name: hashlib.sha256((replica / name).read_bytes()).hexdigest() for name in ORCHESTRATION_SOURCES}
        amendment = {"source_hashes": hashes, "source_overrides": {WORKFLOW: {
            "previous_sha256": original["source_hashes"][WORKFLOW], "amended_sha256": hashes[WORKFLOW]}}}
        receipt = Path(self.temp.name) / "development-orchestration-freeze.json"
        receipt.write_text(json.dumps(amendment))
        checked = validate_freezes(self.root, self.manifest, repo=replica, orchestration_freeze=receipt)
        self.assertEqual(checked["original_source_count"], 72)
        for base, expected in ((replica, "FROZEN_EXECUTING_SOURCE_CHANGED"),
                               (self.root, "ORIGINAL_STAGED_RUNTIME_SOURCE_CHANGED")):
            target = base / "portfolio071/economics.py"
            before = target.read_bytes()
            try:
                target.write_bytes(before + b"\n# development tampering probe\n")
                with self.assertRaisesRegex(ValueError, expected):
                    validate_freezes(self.root, self.manifest, repo=replica, orchestration_freeze=receipt)
            finally:
                target.write_bytes(before)

    def test_pool_creation_failure_accounts_for_all_unstarted_indices(self):
        jobs = registered_jobs()[:2]
        output = Path(self.temp.name) / "pool-never-opened"
        with patch("scripts.replay_portfolio071_parallel.ProcessPoolExecutor",
                   side_effect=RuntimeError("development injected pool creation failure")) as constructor:
            records, statuses, failures = _schedule(self.root, self.manifest, output, jobs, 2)
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(records, {})
        self.assertEqual([row["index"] for row in statuses], [0, 1])
        self.assertTrue(all(row["status"] == "NOT_STARTED_INFRASTRUCTURE_FAILURE" for row in statuses))
        self.assertTrue(any(row["status"] == "POOL_INFRASTRUCTURE_FAILURE" for row in failures))
        self.assertFalse(output.exists())

    def test_spawn_matches_actual_serial_native_tapes_and_account_results(self):
        serial = Path(self.temp.name) / "serial"
        spawned = Path(self.temp.name) / "spawned"
        serial.mkdir()
        spawned.mkdir()
        jobs = []
        for index, (capital, world) in enumerate(((95000, World()),
                (1000000, World(name="development-cancellation", default_every=1)))):
            job = {"index": index, "directory": f"arm-{index:02d}", "world": asdict(world),
                   "capital_usd": capital, "policy": "working_capital_aware",
                   "earned_only_k2": False, "horizon_days": 65}
            jobs.append(job)
            _execute_job(str(self.root), self.manifest, str(serial), job)
        with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as pool:
            futures = [pool.submit(_execute_job, str(self.root), self.manifest, str(spawned), job) for job in jobs]
            summaries = [future.result() for future in futures]
        self.assertEqual(len(summaries), 2)
        for job in jobs:
            for name in ("native-at-horizon.json", "native-after-drain.json"):
                left = strict_json((serial / job["directory"] / name).read_bytes())
                right = strict_json((spawned / job["directory"] / name).read_bytes())
                self.assertEqual(left["ledger"], right["ledger"])
            left = strict_json((serial / job["directory"] / "trajectory.json").read_bytes())
            right = strict_json((spawned / job["directory"] / "trajectory.json").read_bytes())
            for field in ("operating_endpoint", "post_horizon_drain_endpoint", "rolling_profit", "daily", "tax_settlements", "decisions"):
                self.assertEqual(left[field], right[field])
            self.assertTrue(right["native_account_audit"]["accepted"])
            self.assertTrue(right["post_horizon_native_audit"]["accepted"])

    def test_retention_is_read_only_and_rejects_wrong_recipe_or_incomplete_gate(self):
        output = Path(self.temp.name) / "retention"
        output.mkdir()
        job = registered_jobs()[0]
        directory = output / job["directory"]
        execute_trajectory(self.root, self.manifest, directory, capital_usd=25000)
        database_stat = (directory / "account.sqlite").stat()
        retained, receipt = validate_completed(self.root, self.manifest, directory, job)
        after = (directory / "account.sqlite").stat()
        self.assertEqual((database_stat.st_size, database_stat.st_mtime_ns), (after.st_size, after.st_mtime_ns))
        self.assertEqual(retained["capital_usd"], 25000)
        self.assertTrue(receipt["independent_audit"]["accepted"])
        with self.assertRaisesRegex(ValueError, "RECIPE_MISMATCH"):
            validate_completed(self.root, self.manifest, directory, {**job, "capital_usd": 100000})
        tape_path = directory / "native-at-horizon.json"
        raw = tape_path.read_bytes()
        altered = strict_json(raw)
        altered["ledger"]["config"]["contract"] = "wrong-native-contract"
        try:
            tape_path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError, "NATIVE_CONTRACT_OR_OPENING_MISMATCH"):
                validate_completed(self.root, self.manifest, directory, job)
        finally:
            tape_path.write_bytes(raw)
        (output / "arm-01").mkdir()
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_EXISTING_ACCOUNT_REFUSED"):
            _preflight(self.root, self.manifest, output, registered_jobs(), True)


if __name__ == "__main__":
    unittest.main()
