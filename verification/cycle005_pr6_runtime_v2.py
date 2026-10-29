"""Read-only independent admission check of separately owned public PR6 runtime v2."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import numpy as np

HEAD = "2f8f7e7e318bb0306d390b271978423add35ab4c"
PINS = {"runtime.py": "740de7bb097f3ca3e23c6ee2142ae2559bd8622a0aa3e76c20e5fa28f7bc523e",
        "runtime_v2.py": "59ecf3024b4d7344d2297ed6b3fcdec3a8b04d7f883a9c9d50d5f14203538951",
        "verification/certify.py": "83391efeb99982c276e8662ead9d706be0c7ce02f8f0281c4e072d012ffe5b4d",
        "artifacts/controlled_s15.json": "df75e8119f67a54fa8cc6ffe0f2a51a7b80caf0ca71bb8480d875a1c69351556"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(root, output):
    started = time.monotonic()
    for relative, expected in PINS.items():
        if sha(root / relative) != expected:
            raise ValueError("PUBLIC_PR6_SOURCE_CHANGED " + relative)
    output.mkdir(parents=True, exist_ok=False)
    old, new = load("pr6_untouched_v1", root / "runtime.py"), load("pr6_separate_v2", root / "runtime_v2.py")
    candidate = root / "artifacts/controlled_s15.json"
    code = json.loads(candidate.read_text())
    alpha, expected = np.array([1, 1, 1, 1], complex)/2, np.array([1, 1, 1, 1j], complex)/2
    instrument = new.Instrument(candidate, PINS["artifacts/controlled_s15.json"])
    records = []
    for q in (0, instrument.n//2, instrument.n-1):
        for pauli in ("X", "Y", "Z"):
            for before in (False, True):
                state = instrument.encode(alpha)
                state = new.pauli(state, instrument.n, q, pauli) if before else state
                state = instrument.phase(state)
                state = state if before else new.pauli(state, instrument.n, q, pauli)
                result = instrument.recover([state])
                error = float(np.max(np.abs(result["logical_density"] - np.outer(expected, expected.conj()))))
                records.append({"q": q, "pauli": pauli, "before_gate": before, "density_error": error,
                                "input_mass": result["input_probability"], "recovered_trace": result["correctable_probability"], "passed": error < 2e-8})
    state = {word: amplitude*np.sqrt(.37) for word, amplitude in instrument.phase(instrument.encode(alpha)).items()}
    sub = instrument.recover([state])
    subnormalized = {"input_mass": sub["input_probability"], "recovered_trace": sub["correctable_probability"],
                     "passed": abs(sub["input_probability"]-.37) < 2e-8 and abs(sub["correctable_probability"]-.37) < 2e-8}
    witnesses = []
    for kind in ("fixed_zero_ancilla", "duplicate_first_coordinate"):
        changed = copy.deepcopy(code)
        changed["n"] += 1
        changed["physical_weights"] = [0] + changed["physical_weights"]
        for row in changed["codewords"]:
            row["probabilities"] = {(('0' if kind == 'fixed_zero_ancilla' else word[0])+word): probability for word, probability in row["probabilities"].items()}
        fixture = output / (kind + ".json")
        with fixture.open("x") as stream:
            json.dump(changed, stream, sort_keys=True)
        mathematical = {key: changed[key] for key in ('n', 'physical_weights', 'global_phase_exponent', 'logical_order', 'codewords')}
        broad = new._cert.certify(json.dumps(mathematical).encode())
        legacy = old.Instrument(fixture, sha(fixture))
        physical = legacy.phase(legacy.encode(alpha))
        if kind == "duplicate_first_coordinate":
            physical = old.pauli(physical, legacy.n, 0, "Z")
        original_result = legacy.recover([physical])
        refusal = None
        try:
            new.Instrument(fixture, sha(fixture))
        except ValueError as exc:
            refusal = str(exc)
        witnesses.append({"fixture": fixture.name, "fixture_sha256": sha(fixture), "broad_status": broad["status"],
                          "v1_input_mass": original_result["input_probability"], "v1_recovered_trace": original_result["correctable_probability"],
                          "v2_refusal": refusal,
                          "passed": broad["status"] == "CERTIFIED_EXACT_ALGEBRA_ONLY" and original_result["correctable_probability"] > 1.9
                                    and bool(refusal and refusal.startswith("UNSUPPORTED_RECOVERY_CLASS_NONZERO_MOMENTS"))})
    hash_refused = False
    try:
        new.Instrument(candidate, "0"*64)
    except ValueError as exc:
        hash_refused = str(exc) == "CANDIDATE_IDENTITY_MISMATCH"
    report = {"schema": "agi-alpha-cycle005-independent-pr6-runtime-admission/v1", "public_head": HEAD,
              "public_pr": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/6", "source_sha256": PINS,
              "original_pauli_checks": records, "subnormalized_mass": subnormalized, "historical_witnesses": witnesses,
              "hash_mismatch_refused": hash_refused,
              "passed": all(row["passed"] for row in records) and subnormalized["passed"] and all(w["passed"] for w in witnesses) and hash_refused,
              "verifier_sha256": sha(__file__), "wall_seconds": time.monotonic()-started,
              "limits": ["Read-only check of exact public PR6 source; no PR6 edits, approval or merge.",
                         "Original broad algebraic certificate remains valid for the two degenerate witnesses; v2 narrows supported recovery admission instead of renormalizing wrong output.",
                         "Same Python/numpy and upstream broad certifier; procedural checking, not external certification.",
                         "Selected post-exposure admission/Pauli regressions, not all physical errors, device fault tolerance, fresh statistical confirmation, resource advantage or commercial validation."],
              "confirmation_alpha_spent": 0}
    with (output / "REPORT.json").open("x") as stream:
        json.dump(report, stream, indent=2); stream.write("\n")
    print(json.dumps({"passed": report["passed"], "pauli_checks": len(records), "witnesses": len(witnesses)}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = check(args.source_root, args.output)
    raise SystemExit(0 if report["passed"] else 1)
