"""Run a real checker against a planted metering defect and a repaired program."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXED = "charged = sum(result[1] for result in results)"
DEFECT = "charged = sum(result[1] for result in results if result[0])"
CASE = "test_pairing_lab.PairingChecks.test_all_attempts_count_and_double_success_is_one"


def run():
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for name in ("pairing_lab.py", "test_pairing_lab.py", "conventional.py", "runs.csv"):
            shutil.copy(ROOT / name, work / name)
        program = work / "pairing_lab.py"
        original = program.read_text()
        if original.count(FIXED) != 1:
            raise ValueError("registered fault injection site changed")
        check = [sys.executable, "-B", "-m", "unittest", CASE]
        program.write_text(original.replace(FIXED, DEFECT))
        rejected = subprocess.run(check,cwd=work,capture_output=True,text=True)
        if rejected.returncode != 1 or "AssertionError" not in rejected.stderr:
            raise ValueError("unchanged independent witness check failed to confirm the defect")
        program.write_text(program.read_text().replace(DEFECT,FIXED))
        repaired = subprocess.run(check,cwd=work,capture_output=True,text=True)
        if repaired.returncode or program.read_text() != original:
            raise ValueError("repair failed the same independent test")
        return {"mode": "deliberately injected source defect", "verified_problem": "failed attempts undercharged",
                "frozen_check": CASE, "rejected_exit": rejected.returncode,
                "repaired_exit": repaired.returncode, "repair_author": "explicit deterministic source correction",
                "autonomous_diagnosis_demonstrated": False}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
