"""Replay frozen strong alternatives and bound the information-structure difference."""

from argparse import ArgumentParser
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys

from grade_strategic_games import run, sha, write_json
from strategic_reference import independent_certificate


HERE = Path(__file__).resolve().parent
PLAN_SHA = "968b2dd99ae65f95431ae58fcdc5e276b82862c3773b05c66313694e0f32bd1d"
REPORT_SHA = "6b02ecb5bdd2658ff88541e7d59d72d78278dae2896d3bddeaf39e7ddb9be64b"


def exact_match(expected, claimed):
    return all(Fraction(expected[k]) == Fraction(claimed[k]) for k in ("lower","upper","width"))


def main():
    options = ArgumentParser()
    options.add_argument("output", type=Path)
    options.add_argument("--candidate", type=Path, required=True)
    args = options.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    candidate = args.candidate.resolve()
    freeze = candidate / "QUALIFICATION-PLAN.json"
    assert sha(freeze) == PLAN_SHA
    for name, digest in json.loads(freeze.read_bytes())["candidate_sha256"].items():
        assert sha(candidate / name) == digest
    prior = HERE / "strategic-final-v1" / "INDEPENDENT-STRATEGIC-REPORT.json"
    assert sha(prior) == REPORT_SHA
    rows = json.loads(prior.read_bytes())["results"]
    observations = []
    for row in rows:
        task = row["id"]
        source = prior.parent / task / "setting.json"
        game = json.loads(source.read_bytes())
        directory = args.output / task
        directory.mkdir()
        cert, native = directory / "oracle-certificate.json", directory / "oracle-receipt.json"
        completed, seconds = run([sys.executable, candidate / "compare_observation.py", "double-oracle",
                                  source, "--certificate", cert, "--receipt", native])
        original = row["independent_certificate"]
        result = {"id":task,"startup_inclusive_seconds":seconds,"returncode":completed.returncode}
        if cert.is_file() and native.is_file():
            receipt = json.loads(native.read_bytes())
            exact = independent_certificate(game,json.loads(cert.read_bytes()))
            matches = exact_match(exact,receipt["verification"])
            result.update(status=receipt["status"], iterations=receipt["iterations"],
                          exact_bounds=exact, independent_exact_agreement=matches,
                          intervals_overlap=not (
                            Fraction(exact["lower"]) > Fraction(original["upper"]) or
                            Fraction(original["lower"]) > Fraction(exact["upper"])
                          ), certificate_sha256=sha(cert), reported_seconds=receipt["whole_seconds"])
        else:
            result.update(status="failure",error=completed.stderr[-1000:])
        if row["independent_control"]["private_mixture_gain"] > 1e-7:
            public = directory / "public-menu-receipt.json"
            command, public_seconds = run([sys.executable,candidate/"compare_observation.py","public-menu",source,
                                           "--receipt",public])
            if command.returncode != 0:
                result["public_menu"]={"status":"failure","error":command.stderr[-1000:]}
            else:
                full = json.loads(public.read_bytes())
                independently_checked = {}
                for key,value in full["instruments"].items():
                    restricted = deepcopy(game)
                    restricted["instruments"] = [v for v in game["instruments"] if v["id"]==key]
                    control = independent_certificate(restricted,value["certificate"])
                    assert exact_match(control,value["verification"])
                    independently_checked[key]={"lower":control["lower"],"upper":control["upper"]}
                public_lower = max(Fraction(v["lower"]) for v in independently_checked.values())
                public_upper = max(Fraction(v["upper"]) for v in independently_checked.values())
                assert public_lower == Fraction(full["lower"]) and public_upper == Fraction(full["upper"])
                exact_gain=[Fraction(original["lower"])-public_upper,Fraction(original["upper"])-public_lower]
                result["public_menu"]={"status":"exactly_checked",
                    "instrument_bounds":independently_checked,"seconds":public_seconds,
                    "exact_private_gain_interval":[str(v) for v in exact_gain],
                    "decimal_private_gain_interval":[float(v) for v in exact_gain],
                    "gain_verified_strictly_positive":exact_gain[0]>0}
        write_json(directory / "independent-comparators.json",result)
        observations.append(result)
        print(task,result["status"],result.get("iterations"),flush=True)
    write_json(args.output/"INDEPENDENT-COMPETITORS.json",{"schema":"frontier/held-observation-comparators-v1",
      "candidate_plan":PLAN_SHA,"held_report":REPORT_SHA,"rows":observations})


if __name__ == "__main__":
    main()
