"""Entrypoint copied to a delivered package as run.py. Python 3.10+."""
import hashlib
import json
import sys
from pathlib import Path


MEMBERS = (
    "README.txt", "artifact.json", "context.json", "contract.json", "example-input.json",
    "ignition/__init__.py", "ignition/construction.py", "ignition/evaluation.py", "receipt.json", "run.py",
)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _strict(raw):
    def refuse_constant(_):
        raise ValueError("nonfinite numeric literal")
    return json.loads(raw, object_pairs_hook=_unique, parse_constant=refuse_constant)


def semantic_receipt(receipt):
    # Wall-clock timing is an observation of one run, not a reproducible identity.
    return {k: v for k, v in receipt.items() if k != "telemetry_ns"}


def main():
    if sys.argv[1:] not in (["verify"], ["run"]):
        raise ValueError("Usage: python3 -I run.py verify | run < input.json")
    base = Path(__file__).resolve().parent
    hashes = _strict((base / "SHA256SUMS.json").read_bytes())
    if set(hashes) != set(MEMBERS):
        raise ValueError("unexpected bundle member list")
    for name in MEMBERS:
        path = base / name
        if path.is_symlink() or path.parent.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes[name]:
            raise ValueError(f"bundle content differs: {name}")
    sys.path.insert(0, str(base))
    from ignition.construction import ConstructionError, MAX_BYTES, canonical, execute
    from ignition.evaluation import evaluate
    artifact = _strict((base / "artifact.json").read_bytes())
    if sys.argv[1] == "verify":
        contract = _strict((base / "contract.json").read_bytes())
        archived = _strict((base / "receipt.json").read_bytes())
        new = evaluate(contract, artifact)
        if new["status"] != "pass" or canonical(semantic_receipt(archived)) != canonical(semantic_receipt(new)):
            raise ValueError("reproduction failed or accepted scope changed")
        print(json.dumps({"status": "pass", "contract_sha256": contract["sha256"], "artifact_sha256": artifact["sha256"],
                          "cases": len(new["cases"]), "comparison": new["comparison"]["outcome"]}))
    else:
        data = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("input exceeds 2 MiB")
        try:
            result = execute(artifact, _strict(data))
        except ConstructionError as error:
            print(json.dumps({"error": error.code, "message": str(error)}), file=sys.stderr)
            return 2
        print(canonical(result).decode())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RecursionError) as failure:
        print(str(failure), file=sys.stderr)
        raise SystemExit(2)
