"""Run one locked TOI-216 instrument at a time, without the other arm's data."""

import argparse
from csv import DictReader
from hashlib import sha256
import importlib.util
from io import StringIO
import json
from pathlib import Path
import sys


REGISTRATION = "3e6b94b7614c78c5ccf8c1325ea88e7f588f2dfec0eb0bab6d86cb4476803a39"
INPUTS = {
    "ground": "130fe4b4feb3d406b86725cf8dc778b8746eb8043e20fe168ec86822a9c916ef",
    "tess": "d052c68264ee2fa854f4fd8328c097c44ddca55f7db550c397c9c878ba89556f",
}
GROUND = "publication/factory/ground/fit_ground.py"
TESS = "products/frontier-member-tools/activation/"
SCRIPTS = {
    GROUND: "172e205dee6dc8affdcfb42db46db1e4fa790e92a64950af5ef988b21a4c5cd1",
    TESS + "joint_transit.py": "a41d3b239e1f7a29817bf9391193ebbce4cdc69f358b9b2961f6cc9d24a66f13",
    TESS + "transit_cascade.py": "f38c811e9df2443c8e8536c7342cbe607e0d864b7fb74bfbeb91dffb96f85f6e",
    TESS + "post_reveal_overlap.py": "368c4ed1a85fac4d43f321bb3170057784781e446b48d5d47c00aa11d2179efe",
}


def checked(path, digest):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"Locked digest mismatch for {path.name}")
    return raw


def load(path):
    module_spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[path.stem] = module
    sys.path.insert(0, str(path.parent))
    module_spec.loader.exec_module(module)
    return module


def ground_run(reducer, inputs, data):
    raw = checked(data / inputs["file_name"], inputs["sha256"])
    if len(raw) != inputs["bytes"]:
        raise ValueError("Ground photometry size diverged from the acquisition receipt")
    records = list(DictReader(StringIO(raw.decode("utf-8-sig")), delimiter="\t"))
    clock = [float(row["BJD_TDB"]) for row in records]
    utc = [float(row["JD_UTC"]) for row in records]
    try:
        fit = reducer.fit_file(inputs, data)
    except ValueError as error:
        if any(value > 2_400_000 for value in clock) or not all(value > 2_400_000 for value in utc):
            raise
        duration_hour = (max(utc) - min(utc)) * 24
        short_visit = duration_hour < 4.3
        return {
            "verdict": "ABSTAIN_INVALID_BJD_TDB_AND_SHORT_VISIT" if short_visit else "ABSTAIN_INVALID_BJD_TDB",
            "ground_reducer_error": str(error),
            "source": inputs,
            "samples": len(utc),
            "nonpositive_bjd_tdb_rows": sum(value <= 0 for value in clock),
            "plausible_bjd_tdb_rows": sum(value > 2_400_000 for value in clock),
            "positive_jd_utc_rows": sum(value > 2_400_000 for value in utc),
            "ground_visit_utc": [reducer.utc_date(min(utc)), reducer.utc_date(max(utc))],
            "ground_visit_elapsed_hour": duration_hour,
            "contact_coverage": "The JD_UTC visit is shorter than the candidate minimum transit duration of 4.3 h."
            if short_visit else "The BJD_TDB column cannot establish exposure timing at the transit contacts.",
        }
    return {"verdict": "MEASURE", **fit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=("ground", "tess"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    registration = json.loads(checked(base / "REGISTRATION.json", REGISTRATION))
    case = registration["held_case"]
    paths = (GROUND,) if args.arm == "ground" else tuple(k for k in SCRIPTS if k.startswith(TESS))
    for path in paths:
        checked(args.repo / path, SCRIPTS[path])
    reducer = load((args.repo / paths[0]).resolve())
    manifest = base / f"{args.arm.upper()}-INPUT.json"
    raw = checked(manifest, INPUTS[args.arm])
    inputs = json.loads(raw)
    if args.arm == "ground":
        if inputs["file_id"] != case["exofop_file_id"]:
            raise ValueError("Ground instrument diverged from registration")
        result = ground_run(reducer, inputs, args.data)
    else:
        product, = inputs["products"]
        if product["sector"] != case["tess_sector"] or product["tic_id"] != registration["target_tic"]:
            raise ValueError("TESS source diverged from registration")
        # The reducer consumes only a local, hashed manifest and its own FITS.
        work_manifest = args.data / "TESS-INPUT.json"
        work_manifest.write_bytes(raw)
        result = reducer.run(work_manifest)
    arm = {
        "arm": args.arm,
        "registration_sha256": REGISTRATION,
        "input_manifest_sha256": sha256(raw).hexdigest(),
        "scripts_sha256": {path: SCRIPTS[path] for path in paths},
        "result": result,
    }
    args.output.write_text(json.dumps(arm, indent=2, sort_keys=True, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
