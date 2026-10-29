"""Rerun preserved source-A false acceptance, then source-B refusal/integrity gates."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types

FREEZE_B = "6606628dcd020dc735219186ba678ec0f4bb3d906ff689f5b896966406af4b40"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def original(root, output):
    preserved = root / "evidence/cycle-005/verifier-review-P1"
    frozen = json.loads((preserved / "old-freeze.json").read_text())
    assert sha(preserved / "original-source.txt") == frozen["sources"]["mechanisms/pipeline.py"]
    assert sha(preserved / "original-memory-source.txt") == frozen["sources"]["mechanisms/memory.py"]
    # Imports are restricted to original identities; memory and pipeline execute captured bytes.
    for relative in ("mechanisms/construct.py", "mechanisms/criticism.py", "mechanisms/executor.py",
                     "mechanisms/mapping.py", "mechanisms/__init__.py", "flywheel/sandbox.py", "flywheel/retention.py"):
        assert sha(root / relative) == frozen["sources"][relative], relative
    import mechanisms
    memory = types.ModuleType("mechanisms.memory")
    memory.__package__ = "mechanisms"
    memory.__file__ = str(root / "mechanisms/memory.py")
    sys.modules["mechanisms.memory"] = memory
    mechanisms.memory = memory
    exec(compile((preserved / "original-memory-source.txt").read_bytes(), memory.__file__, "exec"), memory.__dict__)
    old = types.ModuleType("mechanisms.pipeline_original")
    old.__package__ = "mechanisms"
    old.__file__ = str(root / "mechanisms/pipeline.py")
    exec(compile((preserved / "original-source.txt").read_bytes(), old.__file__, "exec"), old.__dict__)
    from mechanisms import construct, criticism, executor
    task, _, _ = old.example("P1-rerun-original")
    program = construct.conventional(task)
    program["compensations"] = {}
    specification = {"invariants": [{"id": "release-custody", "kind": "release_after_failure"}],
                     "effect_scope": "exclusive_local_output"}
    result = old.verify(task, program, output / "actual-checks", specification)
    witness = copy.deepcopy(next(row["actual"] for row in result["checks"] if row["actual"].get("reserved")))
    witness["interrupt_stage"] = "during"
    objections = criticism.critique(task, program, witness, specification,
                                   {"pipeline": sha(preserved / "original-source.txt"), "executor": sha(root / "mechanisms/executor.py")})
    objection = next(row for row in objections if row.get("issue", {}).get("kind") == "release_after_failure")
    def reproduce(frozen_task, frozen_program, phase):
        actual = executor.execute(frozen_task, frozen_program, output / "separate-reproduction", phase)
        actual["interrupt_stage"] = "during"
        return actual
    adjudication = criticism.adjudicate(objection, reproduce)
    passed = result["passed"] is True and adjudication["status"] == "established"
    write(output / "REPORT.json", {"original_false_acceptance_reproduced": passed,
          "verification": result, "witness": witness, "objection": objection, "adjudication": adjudication,
          "original_pipeline_sha256": sha(preserved / "original-source.txt"),
          "original_memory_sha256": sha(preserved / "original-memory-source.txt")})
    return passed


def repaired(root, output):
    freeze = root / "campaign/cycle-005/FREEZE.json"
    assert sha(freeze) == FREEZE_B
    frozen = json.loads(freeze.read_text())
    for relative, expected in frozen["sources"].items():
        assert sha(root / relative) == expected, relative
    from mechanisms import pipeline, memory, construct
    task, donors, target = pipeline.example("P1-repaired-independent")
    program = construct.conventional(task)
    bad = []
    for kind in ("release_after_failure", "required_effect_available", "unknown-invariant"):
        bad.append((kind, {"invariants": [{"id": "unsupported", "kind": kind}]}))
    base = {"invariants": [{"id": "marker", "kind": "mark_after_reservation"}]}
    for label, value in (("empty", {"invariants": []}),
                         ("scope", dict(base, effect_scope="ambient-host")),
                         ("top-extra", dict(base, required_state="released")),
                         ("duplicate-id", {"invariants": [base["invariants"][0], base["invariants"][0]]})):
        bad.append((label, value))
    for label, fields in (("unknown-phase", {"phase_ids": ["absent"]}), ("empty-phase", {"phase_ids": []}),
                          ("duplicate-phase", {"phase_ids": [task["phases"][1]["id"]]*2}),
                          ("required-state", {"required_state": "RELEASED"}), ("artifact", {"artifact": "OTHER.json"})):
        inv = dict(base["invariants"][0], **fields)
        bad.append((label, {"invariants": [inv]}))
    refusals = {}
    for label, specification in bad:
        directory = output / label
        result = pipeline.verify(task, program, directory, specification)
        refusals[label] = {"result": result, "no_effects": sorted(p.name for p in directory.iterdir()) == ["VERIFICATION.json"]}
    developed = pipeline.develop(task, donors, target, output / "development", output / "memory")
    receipt = copy.deepcopy(developed["verification_receipt"])
    receipt["verifier_source"]["sha256"] = "0"*64
    acquisition_refused = False
    try:
        memory.acquire(task, developed["mapping"], developed["before"]["program"], developed["after"]["program"],
                       developed["obligations"], receipt, root)
    except ValueError:
        acquisition_refused = True
    record = developed["retained"]["record"]
    source_pinned = (record["provenance"]["dependency_sha256"].get("mechanisms/pipeline.py") == sha(root / "mechanisms/pipeline.py"))
    with tempfile.TemporaryDirectory(prefix="P1-verifier-binding-") as temporary:
        damaged = Path(temporary)
        for relative in {record["instrument"]["path"], *record["provenance"]["dependency_sha256"]}:
            target_path = damaged / relative
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / relative, target_path)
        verifier = damaged / "mechanisms/pipeline.py"
        verifier.write_bytes(verifier.read_bytes() + b"\n# simulated stale verifier\n")
        stale = memory.generate(output / "memory", task, donors, damaged, 64)
    gates = {"all_unsupported_specs_refuse_before_effects": all(row["result"].get("state") == "refused" and row["result"]["passed"] is False and row["no_effects"] for row in refusals.values()),
             "wrong_verifier_acquisition_refused": acquisition_refused,
             "actual_verifier_source_pinned": source_pinned,
             "changed_verifier_reuse_refused": stale.get("program") is None}
    write(output / "REPORT.json", {"source_freeze_sha256": FREEZE_B, "refusals": refusals,
          "gates": gates, "stale_reuse": stale, "passed": all(gates.values()),
          "scope": "Unsupported obligations are refused; resource release is not implemented by the fixed local broker.",
          "confirmation_alpha_spent": 0})
    return all(gates.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--original-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    sys.path.insert(0, str(root))
    output.mkdir(parents=True, exist_ok=False)
    if args.original_child:
        raise SystemExit(0 if original(root, output) else 1)
    command = [sys.executable, str(Path(__file__).resolve()), "--root", str(root), "--output", str(output / "original"), "--original-child"]
    child = subprocess.run(command, capture_output=True, text=True)
    write(output / "ORIGINAL_PROCESS.json", {"command": command, "returncode": child.returncode, "stdout": child.stdout, "stderr": child.stderr})
    passed = child.returncode == 0 and repaired(root, output)
    print(json.dumps({"passed": passed, "original_returncode": child.returncode}))
    raise SystemExit(0 if passed else 1)
