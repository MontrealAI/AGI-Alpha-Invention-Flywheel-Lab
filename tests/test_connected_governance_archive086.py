"""Governance086 prospective C12-C13 extracted-source qualification.

Registered AFTER frozen C0-C11 and BEFORE prospective source-closure repair.
These are offline engineering regressions, not commercial or policy evidence.
C12 requires complete fail-closed canonical inventory, never a checker-only ZIP.
C13 executes the unmodified C0-C11 cases from a fresh extracted, inventory-
selected source subset; full canonical released archive qualification remains
a distinct mandatory hosted acceptance gate.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from connected_enterprise.runner import source_paths


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "campaign/governance_change086.py",
    "campaign/governance_change086/REVIEW_INTEGRITY_ADDENDUM.md",
    "tests/test_connected_governance_change086.py",
    "tests/test_connected_governance_review_integrity086.py",
    "tests/test_connected_governance_archive086.py",
    ".github/workflows/governance-change086.yml",
}


class Governance086ReleaseClosureTests(unittest.TestCase):
    def test_C12_canonical_release_inventory_includes_complete_research(self):
        inventory = set(source_paths(ROOT))
        self.assertTrue(REQUIRED <= inventory, "GOVERNANCE086_INCOMPLETE_RELEASE_SOURCE:" + repr(sorted(REQUIRED - inventory)))
        for name in REQUIRED:
            file = ROOT / name
            self.assertTrue(file.is_file() and not file.is_symlink(), name)

    def test_C13_extracted_inventory_subset_executes_frozen_C0_to_C11(self):
        inventory = set(source_paths(ROOT))
        self.assertTrue(REQUIRED <= inventory, "GOVERNANCE086_INCOMPLETE_RELEASE_SOURCE")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            archive = path / "research-source-subset.zip"
            extracted = path / "extracted"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for name in sorted(REQUIRED):
                    z.write(ROOT / name, name)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(set(z.namelist()), REQUIRED)
                z.extractall(extracted)
            env = dict(os.environ, PYTHONPATH=str(extracted), PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1")
            for pattern in ("test_connected_governance_change086.py",
                            "test_connected_governance_review_integrity086.py"):
                proc = subprocess.run(
                    [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v"],
                    cwd=extracted, env=env, capture_output=True, text=True, timeout=120, check=False)
                self.assertEqual(proc.returncode, 0, f"{pattern}: {proc.stdout[-3000:]} {proc.stderr[-3000:]}")


if __name__ == "__main__":
    unittest.main()
