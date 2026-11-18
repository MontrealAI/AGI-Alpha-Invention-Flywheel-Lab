"""Exercise the operator CLI on disposable snapshots containing a real exported mission."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter


PRODUCT = Path(__file__).resolve().parents[1]
ENV = {k: v for k, v in os.environ.items() if not k.startswith("IGNITION_")}
ENV["PYTHONDONTWRITEBYTECODE"] = "1"


def execute(module, *args, expected=0):
    proc = subprocess.run([sys.executable, "-B", "-m", module, *map(str, args)],
                          cwd=PRODUCT, env=ENV, capture_output=True, timeout=30)
    if (proc.returncode == 0) != (expected == 0):
        raise RuntimeError(f"Unexpected exit from {module}: {proc.returncode}")
    return proc.stdout


def hosted(state, *args, environment="staging", expected=0):
    return execute("ignition.hosted", "--state", state, "--environment", environment,
                   *args, expected=expected)


def mission(state, *args):
    return execute("ignition", "--state", state / "workspaces" / "test-lab", *args)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify(root):
    live, restored = root / "live", root / "restored"
    backup = root / "backup"
    # CLI emits an invitation: discard it in memory, never print or retain it.
    hosted(live, "invite", "test-lab")
    purpose = "Transfer a synthetic review queue in an offline staging restoration drill."
    brief = root / "brief.json"
    brief.write_text(json.dumps({"mission": {
        "purpose": purpose, "beneficiary": "Staging operator",
        "requirements": ["Preserve the stage label on each row"],
        "authority": {}, "resources": {"max_model_calls": 0},
        "construction_spec": {"kind": "record_migration", "purpose": purpose,
                              "definition": {"columns": [{"source": "stage", "target": "review",
                                                           "type": "text"}], "extra_fields": "drop"},
                              "cases": [{"name": "Synthetic handoff", "input": {"rows": [{"stage": "ready"}]},
                                         "expected": {"rows": [{"review": "ready"}]}}]}}}))
    run = json.loads(mission(live, "start", brief, "--request-id", "restore-export-drill"))
    require(run["status"] == "verified", "The staging compiler did not deliver an artifact")
    run_id, version = run["id"], run["version"]
    first = root / "before.zip"
    mission(live, "export", run_id, first, "--version", version)
    hosted(live, "backup", backup)
    started = perf_counter()
    hosted(restored, "restore", backup)
    elapsed = round((perf_counter() - started) * 1000, 2)
    second = root / "after.zip"
    mission(restored, "export", run_id, second, "--version", version)
    require(first.read_bytes() == second.read_bytes(), "The re-exported bundle changed")
    replayed = json.loads(mission(restored, "start", brief, "--request-id", "restore-export-drill"))
    require(replayed["id"] == run_id and replayed["version"] == version, "Restored request was duplicated")
    hosted(restored, "restore", backup, expected=1)
    damaged = root / "incomplete"
    shutil.copytree(backup, damaged)
    (damaged / "workspaces" / "test-lab" / "missions.sqlite3").unlink()
    bad = root / "refused"
    hosted(bad, "restore", damaged, expected=1)
    require(not bad.exists(), "Incomplete backup produced an available state directory")
    hosted(bad, "restore", backup, environment="production", expected=1)
    require(not bad.exists(), "Staging state was restored into the production environment")
    return {"scope": "disposable local staging; storage restore through operator CLI",
            "bundle_sha256": hashlib.sha256(second.read_bytes()).hexdigest(),
            "same_request_after_restore": True, "restore_process_ms": elapsed,
            "partial_restore_published": False, "model_calls": 0}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="ignition-ops-recovery-") as tmp:
        print(json.dumps(verify(Path(tmp)), indent=2))
