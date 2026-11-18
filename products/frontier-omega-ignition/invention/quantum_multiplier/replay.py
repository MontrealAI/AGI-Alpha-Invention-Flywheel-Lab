"""Reconstruct and verify the decoder multiplier study in a fresh directory."""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from contextlib import nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT_SHA256 = "19ee4259f4d20a779d2484b3dea635d2e0efd23fce39c859e70228f668e53093"


def run_json(name, *args):
    completed = subprocess.run(
        [sys.executable, "-IB", str(ROOT / name), *map(str, args)],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return json.loads(completed.stdout)


def replay(output, check_sdk=False):
    source = ROOT / "scheme42.txt"
    if hashlib.sha256(source.read_bytes()).hexdigest() != INPUT_SHA256:
        raise ValueError(
            "Published multiplication tensor does not match the registered source"
        )
    if output.exists():
        raise FileExistsError("Circuit output must be a fresh directory")
    output.mkdir(parents=True)
    run_json("compile_multiplier.py", source, output)
    sensitivity = run_json("check_rotations.py", source, output)
    candidates = sorted(output.glob("*.kmx"))
    verified = run_json("verify_multiplier.py", *candidates)
    delivered = output / "flexible_on_stronger_order.kmx"
    if (ROOT / "multiplier.kmx").read_bytes() != delivered.read_bytes():
        raise ValueError(
            "Distributed recipient circuit differs from the reconstruction"
        )
    measured = verified[delivered.name]
    strongest = verified["stronger_fixed_rotations.kmx"]["cnot"]
    follows = measured["cnot"]
    if len(verified) != 5 or any(
        (r["toffolis"], r["qubits"]) != (42, 36) for r in verified.values()
    ):
        raise ValueError(
            "An arm violates the registered 42-Toffoli, 36-wire acceptance"
        )
    if (
        strongest != sensitivity["conventional_best_cx"]
        or follows != sensitivity["flexible_on_stronger_order_cx"]
    ):
        raise ValueError("Independently measured counts disagree with the search")
    result = {
        "decision": "withhold_contest_entry",
        "basis": "Width and Toffolis tie all controls. No official full-decoder score.",
        "material_cnot_advantage_over_strongest_control": follows * 100
        <= 95 * strongest,
        "qubits": measured["qubits"],
        "toffolis": measured["toffolis"],
        "ranked_submission": False,
        "official_full_decoder_scored": False,
        "authoritative_payment_observed": False,
        "primary_cnot": {
            name: verified[name + ".kmx"]["cnot"]
            for name in ("conventional", "conventional_2opt", "flexible_pivots")
        },
        "strongest_conventional_cnot": strongest,
        "followup_cnot": follows,
        "tensor_sha256": INPUT_SHA256,
        "circuits": verified,
        "cyclic_rotation_pairs": sensitivity["rotation_pairs"],
    }
    request_path = ROOT / "REQUEST.json"
    threshold = 500
    if request_path.exists():
        request = json.loads(request_path.read_text())
        if not isinstance(request, dict) or set(request) != {
            "minimum_cnot_improvement_bps"
        }:
            raise ValueError("Invalid recipient request")
        threshold = request["minimum_cnot_improvement_bps"]
        if type(threshold) is not int or not 1 <= threshold <= 10000:
            raise ValueError("Invalid CNOT threshold")
    result["minimum_cnot_improvement_bps"] = threshold
    result["requested_cnot_threshold_met"] = (
        strongest - follows
    ) * 10000 >= threshold * strongest
    if check_sdk:
        result["published_sdk"] = run_json("test_kickmix.py", delivered)
    return result


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument(
        "--output", type=Path, help="fresh directory to retain all five circuits"
    )
    cli.add_argument(
        "--kickmix",
        action="store_true",
        help="also run 256 checks through kickmix==1.0.0",
    )
    args = cli.parse_args()
    temporary = (
        tempfile.TemporaryDirectory() if args.output is None else nullcontext(None)
    )
    with temporary as root:
        folder = Path(root) / "circuits" if root else args.output
        result = replay(folder, args.kickmix)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
