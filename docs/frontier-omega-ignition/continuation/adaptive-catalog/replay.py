"""Replay public, already recorded responses and run a separate conventional comparator."""
import hashlib
import io
import json
import platform
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[3] / "products/frontier-omega-ignition"
sys.path.insert(0, str(PRODUCT))
from ignition import evaluation
from ignition.controller import Controller
from ignition.store import Store


def require(condition, message):
    if not condition:
        raise ValueError(message)


def replay(record, arm, directory):
    fixture = json.loads((PRODUCT / "examples/reading-catalog.json").read_bytes())
    mission = fixture["mission"]
    name = arm["arm"]
    if name != "adaptive":
        mission["resources"].update(execution_strategy="direct", direct_method="model" if name == "direct" else "specialist")
    ctrl = Controller(Store(directory / "state"), assisted=("recorded responses", "replay only"))
    rid, version = ctrl.create({"request_id": "catalog-replay-" + name, "mission": mission, "sources": []})
    run = ctrl.advance(rid, version)
    if "response" in arm:
        require(run["handoff"]["stage"] == arm["stage"], "Unexpected model stage")
        ctrl.intervene(rid, version, "respond", {"sha256": run["handoff"]["sha256"], "response": arm["response"]})
        run = ctrl.advance(rid, version)
    require((run["status"], run["contract_sha256"]) == (arm["status"], arm["contract_sha256"]), "Run verdict or contract changed")
    if run["status"] != "verified":
        return run["status"]
    require(run["artifact"]["sha256"] == arm["artifact_sha256"], "Different artifact")
    require(all(c["candidate_pass"] for c in run["evaluation"]["cases"]), "A frozen check failed")
    recipient = directory / name
    recipient.mkdir()
    with zipfile.ZipFile(io.BytesIO(ctrl.deliver(rid, version))) as z:
        z.extractall(recipient)
    subprocess.run([sys.executable, "-I", "run.py", "verify"], cwd=recipient, check=True, capture_output=True)
    result = subprocess.run([sys.executable, "-I", "run.py", "run"], cwd=recipient, check=True,
                            input=json.dumps(record["fresh_recipient_input"]), text=True, capture_output=True)
    require(json.loads(result.stdout) == record["fresh_expected"], "Recipient changed fresh row")
    return run["status"]


def compare_jq(record):
    fixture = json.loads((PRODUCT / "examples/reading-catalog.json").read_bytes())
    spec = fixture["mission"]["construction_spec"]
    checks = [(case["name"], case["input"], {"output": case["expected"]} if "expected" in case
               else {"error": case["error"]}) for case in spec["cases"]]
    controls = {"empty batch": {"output": {"rows": []}}, "missing columns": {"error": "missing_field"},
                "wrong envelope": {"error": "invalid_input"}, "extra column policy": {"error": "extra_field"}}
    checks.extend((name, data, controls[name]) for name, data in evaluation._probes(spec))
    checks.extend((f"development {i}", case["input"], {"output": case["expected"]}) for i, case
                  in enumerate(spec["definition"]["demonstrations"], 1))
    checks.append(("fresh recipient input", record["fresh_recipient_input"], {"output": record["fresh_expected"]}))
    results = []
    for name, data, expected in checks:
        begin = time.monotonic_ns()
        observed = subprocess.run(["jq", "-c", "-f", str(HERE / "catalog.jq")], input=json.dumps(data),
                                  capture_output=True, text=True, check=True)
        actual = json.loads(observed.stdout)
        results.append({"case": name, "matched": actual == expected, "elapsed_ns": time.monotonic_ns() - begin})
    return {"tool": subprocess.check_output(["jq", "--version"], text=True).strip(),
            "source_sha256": hashlib.sha256((HERE / "catalog.jq").read_bytes()).hexdigest(), "checks": results}


if __name__ == "__main__":
    record = json.loads((HERE / "OBSERVATIONS.json").read_bytes())
    with tempfile.TemporaryDirectory() as workspace:
        verdicts = {arm["arm"]: replay(record, arm, Path(workspace)) for arm in record["arms"]}
    jq_result = compare_jq(record)
    print(json.dumps({"python": platform.python_version(), "replayed": verdicts, "jq": jq_result}, indent=2))
    sys.exit(0 if all(c["matched"] for c in jq_result["checks"]) else 1)
