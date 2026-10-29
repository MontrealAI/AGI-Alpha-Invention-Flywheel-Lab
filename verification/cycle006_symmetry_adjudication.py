"""Read-only development adjudication of unordered-intervention exchange symmetry."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write("\n")


def evaluate(root, artifact_path, source_sha256, output, repaired=False):
    root, output = root.resolve(), output.resolve()
    source = root / "experiments/norman006/model.py"
    if sha(source) != source_sha256:
        raise ValueError("CANDIDATE_SOURCE_IDENTITY_MISMATCH")
    split = json.loads((root / "experiments/interaction006_data/SPLIT.json").read_text())
    data_path = root / "experiments/interaction006_data/development.npz"
    if sha(data_path) != split["public_files"]["development.npz"]:
        raise ValueError("DEVELOPMENT_DATA_IDENTITY_MISMATCH")
    output.mkdir(parents=True, exist_ok=False)
    started, cpu = time.monotonic(), time.process_time()
    prior = resource.getrusage(resource.RUSAGE_CHILDREN)
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("verifier_readonly_norman_candidate", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with np.load(data_path, allow_pickle=False) as loaded:
        development = {key: loaded[key].copy() for key in loaded.files}
    artifact = json.loads(artifact_path.read_text())
    if artifact["interpreter_source_sha256"] != source_sha256:
        raise ValueError("ARTIFACT_INTERPRETER_IDENTITY_MISMATCH")
    if repaired:
        original_receipts = root / "evidence/cycle-006/verifier-symmetry-original"
        constraint = json.loads((original_receipts / "CONSTRAINT.json").read_text())
        if sha(original_receipts / "ADJUDICATION.json") != constraint["evidence_sha256"] or artifact["configuration"]["constraints"] != [constraint] or artifact["configuration"]["symmetric"] is not True:
            raise ValueError("REPAIR_NOT_BOUND_TO_ESTABLISHED_ORIGINAL_CONSTRAINT")
    original = {key: development[key] for key in ("A", "B", "ctrl", "pairs", "genes")}
    cases = {"all80_development_pairs": original}
    if repaired:
        first = np.arange(16)
        second = (np.arange(16) * 7 + 13) % len(development["pairs"])
        cases["additional16_real_input_compositions_no_AB_claim"] = {
            "A": development["A"][first], "B": development["B"][second], "ctrl": development["ctrl"][first],
            "pairs": np.asarray(["metamorphic-%02d" % i for i in range(16)]), "genes": development["genes"]}
    checks = {}
    for name, inputs in cases.items():
        swapped = dict(inputs, A=inputs["B"], B=inputs["A"])
        first = module.predict(artifact, inputs)
        second = module.predict(artifact, swapped)
        difference = np.abs(first["prediction"] - second["prediction"])
        maximum = float(difference.max())
        location = np.unravel_index(np.argmax(difference), difference.shape)
        checks[name] = {"pairs": len(inputs["pairs"]), "max_absolute_swap_difference": maximum,
            "largest_witness": {"pair": str(inputs["pairs"][location[0]]), "gene": str(inputs["genes"][location[1]]),
                "original_prediction": float(first["prediction"][location]), "swapped_prediction": float(second["prediction"][location])},
            "first_basis_receipt": first["basis_receipt"], "swapped_basis_receipt": second["basis_receipt"],
            "passed": maximum <= 1e-10}
    status = "repair_verified_in_functional_scope" if repaired and all(value["passed"] for value in checks.values()) else "established" if not repaired and any(not value["passed"] for value in checks.values()) else "refuted" if not repaired else "repair_failed"
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {"schema": "agi-alpha-cycle006-exchange-symmetry-adjudication/v1", "status": status,
        "claim_challenged": "Prediction for the same unordered simultaneous pair must be invariant to exchanging A/B input role labels.",
        "candidate_source_sha256": source_sha256, "artifact_file_sha256": sha(artifact_path), "candidate_artifact_sha256": artifact["artifact_sha256"],
        "data_sha256": sha(data_path), "source_split_sha256": sha(root / "experiments/interaction006_data/SPLIT.json"),
        "verifier_sha256": sha(Path(__file__)), "tolerance": 1e-10, "checks": checks,
        "constructor_claim_origin": "Actual development search winner; no seeded defect. Independent verifier recomputes predictions from checked artifact and exact development inputs.",
        "evidence_effect": "Exchanging only role labels leaves the requested unordered intervention unchanged; materially different outputs violate this functional contract. This does not establish a biological finding or improved prediction accuracy.",
        "resources": {"wall_seconds": time.monotonic() - started, "verifier_cpu_seconds": time.process_time() - cpu,
            "child_cpu_seconds": usage.ru_utime + usage.ru_stime - prior.ru_utime - prior.ru_stime},
        "limits": ["Development-only functional adjudication; no protected AB outcomes read", "Additional composition cases use real single-effect inputs but have no asserted observed double outcomes", "Shared host/model/library procedural separation, not independent external certification"]}
    write(output / "ADJUDICATION.json", report)
    if status == "established":
        write(output / "CONSTRAINT.json", {"kind": "exchange_symmetry", "status": "established", "evidence_sha256": sha(output / "ADJUDICATION.json")})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repaired", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.artifact, args.source_sha256, args.output, args.repaired)
    print(json.dumps({"status": report["status"], "max_swap_difference": max(value["max_absolute_swap_difference"] for value in report["checks"].values())}))
    raise SystemExit(0 if report["status"] in ("established", "repair_verified_in_functional_scope") else 1)
