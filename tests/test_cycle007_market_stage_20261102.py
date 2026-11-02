import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import stage_cycle007_sources as staging

ROOT = Path(__file__).resolve().parents[1]
MARKET = "campaign/cycle-007/ECONOMICS_SOURCES.json"
PINNED = "9bb9410fa5b6fb0d5b185342796cb5f900ad8eb2709657315a249bc5f219050c"


class FrozenCycle007MarketStageTests(unittest.TestCase):
    def _fixture(self, directory):
        root = Path(directory) / "source"
        for name in ("run_cycle007_repaired.py", "experiments/commerce006.py", MARKET):
            source = ROOT / name
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        probe = root / "probe.txt"
        probe.write_text("historical fixture\n")
        freeze = {
            "files": {"probe.txt": hashlib.sha256(probe.read_bytes()).hexdigest()},
            "expected_absent_paths": ["experiments/__init__.py"],
        }
        frozen = root / staging.FREEZE
        frozen.parent.mkdir(parents=True, exist_ok=True)
        frozen.write_text(json.dumps(freeze))
        return root

    def test_market_matches_original_contract_and_stager_pin(self):
        contract = json.loads((ROOT / "campaign/cycle-007/ECONOMICS_CONTRACT.json").read_text())
        self.assertEqual(contract["market_source_manifest"], {"path": MARKET, "sha256": PINNED})
        self.assertEqual(staging.COMPATIBILITY_DEPENDENCIES[MARKET], PINNED)
        self.assertEqual(hashlib.sha256((ROOT / MARKET).read_bytes()).hexdigest(), PINNED)

    def test_stage_retains_market_and_verifies_bytes_without_new_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._fixture(directory)
            staged = Path(directory) / "staged"
            receipt = staging.stage(source, staged)
            self.assertEqual(receipt["additional_compatibility_dependencies"][MARKET], PINNED)
            self.assertEqual(hashlib.sha256((staged / MARKET).read_bytes()).hexdigest(), PINNED)
            self.assertTrue(staging.verify_stage(source, staged)["accepted"])
            self.assertFalse((staged / "experiments/__init__.py").exists())

    def test_missing_market_fails_before_stage_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._fixture(directory)
            (source / MARKET).unlink()
            staged = Path(directory) / "staged"
            with self.assertRaisesRegex(ValueError, "HISTORICAL_REGULAR_SOURCE_REQUIRED"):
                staging.stage(source, staged)
            self.assertFalse(staged.exists())

    def test_changed_market_fails_before_stage_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self._fixture(directory)
            (source / MARKET).write_bytes((source / MARKET).read_bytes() + b"\n")
            staged = Path(directory) / "staged"
            with self.assertRaisesRegex(ValueError, "PINNED_COMPATIBILITY_HELPER_CHANGED"):
                staging.stage(source, staged)
            self.assertFalse(staged.exists())


if __name__ == "__main__":
    unittest.main()
