"""Run frozen candidate on all held cases and capture independent controls."""

from argparse import ArgumentParser
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from fractions import Fraction
from time import perf_counter

from strategic_reference import normal_form, independent_certificate


HERE = Path(__file__).resolve().parent
REGISTRATION_TEXT = "4417b33af28d8d0acfdd814714f8dd837d94fe6d2414c885c3ba2fbcd061d274"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def run(cmd):
    clock = perf_counter()
    completed = subprocess.run([str(p) for p in cmd], capture_output=True, text=True,
                               env={**os.environ, "OPENBLAS_NUM_THREADS":"1", "OMP_NUM_THREADS":"1",
                                    "MKL_NUM_THREADS":"1", "PYTHONHASHSEED":"0"}, check=False)
    return completed, perf_counter()-clock


def equivalence(value: Fraction, candidate):
    return value == Fraction(candidate)


def main():
    p = ArgumentParser()
    p.add_argument("output", type=Path)
    p.add_argument("--candidate", type=Path)
    p.add_argument("--freeze", type=Path, help="JSON mapping relative candidate file names to exact SHA-256")
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    registration = HERE / "REGISTRATION.json"
    assert sha(registration) == REGISTRATION_TEXT
    frozen = json.loads(registration.read_bytes())
    path = HERE / "held_games.json"
    assert sha(path) == frozen["files"][path.name]
    cases = json.loads(path.read_bytes())
    if args.candidate is not None:
        if args.freeze is None:
            raise SystemExit("Require an exact candidate freeze before execution")
        candidate_dir = args.candidate.resolve()
        candidate_hashes = json.loads(args.freeze.read_bytes())
        assert {"solve_observation.py", "observation.py"} <= set(candidate_hashes)
        for name, digest in candidate_hashes.items():
            assert sha(candidate_dir / name) == digest
    else:
        candidate_dir = None
        candidate_hashes = {}
    results = []
    complete_started_at = datetime.now(timezone.utc).isoformat()
    for task in cases:
        game = task["game"]
        control = normal_form(game)
        result = {"id":task["id"], "time_started":datetime.now(timezone.utc).isoformat(),
                  "independent_control":control}
        path = args.output / task["id"]
        path.mkdir()
        source = path / "setting.json"
        write_json(source, game)
        if candidate_dir is not None:
            cert = path / "certificate.json"
            receipt = path / "candidate.json"
            cli, duration = run([sys.executable, candidate_dir / "solve_observation.py", source,
                                 "--certificate", cert, "--receipt", receipt])
            result["candidate_seconds"] = duration
            result["returncode"] = cli.returncode
            if not cert.is_file() or not receipt.is_file():
                result.update(status="missing_candidate_artifact", stderr=cli.stderr[-1200:])
            else:
                try:
                    candidate_certificate = json.loads(cert.read_bytes())
                    independent = independent_certificate(game, candidate_certificate)
                    verified_path = path / "candidate-verifier.json"
                    verified, verifier_seconds = run([sys.executable, candidate_dir / "observation.py",
                                                       source, cert, "--output", verified_path])
                    result["verifier_seconds"] = verifier_seconds
                    result["verifier_returncode"] = verified.returncode
                    if not verified_path.is_file():
                        raise ValueError("Candidate verifier output missing. " + verified.stderr[-450:])
                    reported = json.loads(verified_path.read_bytes())
                    numeric_agreement = all(equivalence(Fraction(independent[key]), reported[key])
                                            for key in ("lower", "upper", "width"))
                    numerics = control["private_mix"] if control["status"] == "computed" else None
                    scale = control["weight_scale"]
                    references_enclosed = (
                        numerics is None or
                        all(float(Fraction(independent["lower"])) - scale*1e-7 <= v <=
                            float(Fraction(independent["upper"])) + scale*1e-7
                            for v in (numerics["maximin"], numerics["minimax"],
                                      numerics["achieved_by_row_policy"], numerics["achieved_by_column_policy"]))
                    )
                    narrow = Fraction(independent["width"]) <= Fraction(scale, 2_000_000)
                    approved = numeric_agreement and references_enclosed and narrow and reported["verdict"] == "QUALIFIED"
                    result.update(status="accepted" if approved else "failed_acceptance",
                                  independent_certificate=independent,
                                  candidate_claim=reported, comparisons={
                                      "exact_claims_equal_independent_arithmetic":numeric_agreement,
                                      "encloses_conventional_primal_and_dual":references_enclosed,
                                      "narrow":narrow,
                                  }, certificate_sha256=sha(cert), setting_sha256=sha(source))
                    if task["id"] == "g01":
                        altered = deepcopy(candidate_certificate)
                        altered["row"][0]["mass"] += 1
                        tampered_path = path / "invalid-mass.json"
                        write_json(tampered_path, altered)
                        try:
                            independent_certificate(game, altered)
                            independent_rejected = False
                        except ValueError:
                            independent_rejected = True
                        bad, _ = run([sys.executable, candidate_dir / "observation.py", source, tampered_path,
                                      "--output", path / "invalid-mass-attempt.json"])
                        changed = deepcopy(game)
                        changed["scenarios"][0]["weights"][0] += 1
                        changed_path = path / "changed-setting.json"
                        write_json(changed_path, changed)
                        wrong, _ = run([sys.executable, candidate_dir / "observation.py", changed_path, cert,
                                        "--output", path / "wrong-model-attempt.json"])
                        result["negative_controls"] = {
                            "independent_invalid_mass_rejected":independent_rejected,
                            "candidate_invalid_mass_rejected":bad.returncode != 0,
                            "candidate_changed_game_rejected":wrong.returncode != 0,
                        }
                except (ValueError, KeyError, TypeError) as err:
                    result.update(status="failed_certificate", error=str(err))
        else:
            result["status"] = "baseline_only"
        write_json(path / "report.json", result)
        results.append(result)
        conventional = control.get("private_mix", {}).get("maximin")
        gain = control.get("private_mixture_gain")
        print(f"{task['id']} {result['status']} | value {conventional} | private mix increment {gain}", flush=True)

    final = {
        "schema":"frontier/observation-game-independent-holdout-v1",
        "registration_sha256":sha(registration),
        "held_game_sha256":frozen["files"]["held_games.json"],
        "candidate_source_sha256":candidate_hashes,
        "independent_method_sha256":sha(HERE / "strategic_reference.py"),
        "started_at":complete_started_at,
        "completed_at":datetime.now(timezone.utc).isoformat(),
        "candidate_accepted":sum(r["status"] == "accepted" for r in results),
        "explicit_normal_form_count":sum(r["independent_control"]["status"] == "computed" for r in results),
        "count":len(results),
        "results":results,
    }
    write_json(args.output / "INDEPENDENT-STRATEGIC-REPORT.json", final)


if __name__ == "__main__":
    main()
