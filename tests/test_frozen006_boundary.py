import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from flywheel.reproduction006 import materialize, FREEZE, FREEZE_SHA256

ROOT = Path(__file__).resolve().parents[1]


class Frozen006BoundaryTests(unittest.TestCase):
    def test_materialized_closure_matches_unchanged_freeze_without_git(self):
        before = (ROOT/FREEZE).read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), FREEZE_SHA256)
        with tempfile.TemporaryDirectory(prefix='alpha-frozen006-', dir='/tmp') as folder:
            destination=Path(folder)/'source'
            result=materialize(ROOT,destination)
            self.assertEqual(result['sources_checked'],6363)
            self.assertTrue(result['destination_git_ancestry_absent'])
            frozen=json.loads(before)
            for name, expected in frozen['sources'].items():
                self.assertEqual(hashlib.sha256((destination/name).read_bytes()).hexdigest(),expected,name)
            self.assertEqual((destination/FREEZE).read_bytes(),before)
            self.assertEqual((ROOT/FREEZE).read_bytes(),before)
            self.assertNotEqual((ROOT/'flywheel/legacy.py').read_bytes(),(destination/'flywheel/legacy.py').read_bytes())
            self.assertEqual(result['substituted_original_inputs']['flywheel/legacy.py']['origin'],
                             'historical/cycle-006/legacy.py.txt')
            with self.assertRaises(FileExistsError): materialize(ROOT,destination)

    def test_changed_freeze_or_historical_workflow_refused_before_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'source'
            (root/Path(FREEZE).parent).mkdir(parents=True)
            shutil.copy2(ROOT/FREEZE,root/FREEZE)
            (root/'.github/workflows').mkdir(parents=True)
            (root/'.github/workflows/campaign.yml').write_text('new operating workflow')
            historical=root/'historical/cycle-006/campaign-workflow.yml.txt'
            historical.parent.mkdir(parents=True)
            historical.write_text('corrupted frozen workflow')
            destination=Path(folder)/'out'
            with self.assertRaisesRegex(ValueError,'FROZEN006_SOURCE_IDENTITY_MISMATCH'):
                materialize(root,destination)
            self.assertFalse(destination.exists())
            historical.unlink()
            historical.symlink_to(ROOT/'historical/cycle-006/campaign-workflow.yml.txt')
            with self.assertRaisesRegex(ValueError,'FROZEN006_SYMLINK_REFUSED'):
                materialize(root,destination)
            self.assertFalse(destination.exists())
            (root/FREEZE).write_text('{}')
            with self.assertRaisesRegex(ValueError,'FROZEN006_FREEZE_IDENTITY_MISMATCH'):
                materialize(root,destination)
            self.assertFalse(destination.exists())

    def test_hosted_replay_uses_materialized_original_runtime(self):
        # Frozen source stays unchanged. A prospective supervisor may launch its
        # authenticated --worker, but must not substitute the current worker.
        workflow=(ROOT/'.github/workflows/campaign.yml').read_text()
        self.assertIn('python -m flywheel.reproduction006 --root . --output "$RUNNER_TEMP/frozen-cycle-006"',workflow)
        self.assertNotIn('python run_cycle006.py --output',workflow)
        self.assertNotIn('python "$RUNNER_TEMP/frozen-cycle-006/run_cycle006.py" --output',workflow)
        self.assertIn('from flywheel.reproduction006 import FREEZE, FREEZE_SHA256',workflow)
        self.assertIn('hashlib.sha256(freeze_raw).hexdigest() != FREEZE_SHA256',workflow)
        self.assertIn('hashlib.sha256(runner_path.read_bytes()).hexdigest() != pins["run_cycle006.py"]',workflow)
        self.assertIn('module.source_identity(root, freeze_path, FREEZE_SHA256)',workflow)
        self.assertIn('len(frozen["sources"]) != 6363',workflow)
        self.assertIn('from experiments import resource006_v4',workflow)
        self.assertIn('resource006_v4.run(',workflow)
        self.assertIn('"--worker",',workflow)
        self.assertIn('str(runner_path), "--worker"',workflow)

    def test_prospective_supervision_retains_bounds_receipts_and_failed_history(self):
        workflow=(ROOT/'.github/workflows/campaign.yml').read_text()
        for condition in (
            '"wall_seconds": 360, "cpu_seconds": 240',
            '"memory_bytes": 4 * 1024 ** 3',
            '"output_bytes": 64 * 1024 ** 2',
            '"storage_bytes": 512 * 1024 ** 2',
            'result["receipt"]["state"] != "complete"',
            'completed.get("state") != "COMPLETE"',
            'completed.get("report_sha256") != hashlib.sha256(report).hexdigest()',
            'atomic_json(output / "INTERRUPTED.json", {',
            '"historical_v3_failure_repaired_retroactively": False',
            '"prior_v3_run": "42083204982"',
        ):
            with self.subTest(condition=condition):
                self.assertIn(condition,workflow)
