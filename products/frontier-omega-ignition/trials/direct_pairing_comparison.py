"""Compare the frozen direct-Codex entry point with an independently extracted receiver."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
FLAGSHIP = HERE.parent / "flagship"
DIRECT = HERE / "direct_pairing.py"
DIRECT_COMMIT = "a2c20c40856c7493c5c675c0674b0fab42bac5e9"
DIRECT_HASH = "cc8737702bcc9c02b4bac100131ea0b9566c61cf62de5e32ebe94de2e0e167d0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cwd, *args):
    return subprocess.run([sys.executable, "-E", "-s", "-B", *map(str,args)], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout


def normalize(source, phase, budget, floor):
    item = source[phase]
    if item is None:
        return None
    obj = {key: item[key] for key in ("tasks", "solved", "tokens")}
    obj["qualifies"] = obj["tokens"] <= budget * obj["tasks"] and obj["solved"]*100 >= floor*obj["tasks"]
    return obj


def compare():
    if sha(DIRECT) != DIRECT_HASH:
        raise ValueError("direct baseline differs from pre-outcome source")
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        received = temp / "receiver"
        received.mkdir()
        archive = temp / "Pairing_Lab.zip"
        run(temp,FLAGSHIP / "package.py",archive)
        with ZipFile(archive) as bundle:
            bundle.extractall(received)
            file_count = len(bundle.namelist())
        run(received,"-m","unittest","discover","-v")
        run(received,"qualify.py","--check","receipt.json")
        correction = json.loads(run(received,"repair_experiment.py"))
        rebuilt = temp / "rebuilt.zip"
        run(received,"package.py",rebuilt)
        if sha(rebuilt) != sha(archive):
            raise ValueError("recipient bundle changed on re-export")
        receipt = json.loads((received / "receipt.json").read_bytes())
        summaries = {}
        for label, frozen in receipt["arms"].items():
            p = frozen["parameters"]
            args = ["--budget",p["budget"],"--width",p["width"]]
            if p["model"]:
                args.extend(["--model",p["model"]])
            if p["repository"]:
                args.extend(["--repository",p["repository"]])
            direct = json.loads(run(temp,DIRECT,received / "runs.csv",*args,"--floor-percent",p["min_percent"]))
            actual = json.loads(run(received,"pairing_lab.py",*args,"--min-percent",p["min_percent"],"--summary"))
            projected = {"selected": actual["selected"],
                         **{phase: normalize(actual,phase,p["budget"],p["min_percent"])
                            for phase in ("calibration","audit")}}
            if direct != projected or actual["qualifies"] != frozen["qualifies"] or not frozen["conventional_sql"]["agreement"]:
                raise AssertionError(f"{label}: independent artifacts disagree")
            summaries[label] = {"selected": direct["selected"], "calibration": direct["calibration"],
                                "audit": direct["audit"], "direct_receiver_sql_agree": True}
        return {"schema": "pairing-lab-direct-comparison/1", "direct_source_commit": DIRECT_COMMIT,
                "direct_source_sha256": sha(DIRECT), "comparison_source_sha256": sha(Path(__file__)),
                "receiver_qualification_receipt_sha256": sha(received / "receipt.json"),
                "receiver_archive_sha256": sha(archive), "receiver_file_count": file_count,
                "portable_checks": {"unittest_discovery": "passed", "registered_sql_cohort": "passed",
                                    "frozen_repair_check": correction, "byte_identical_reexport": True},
                "evidence": "Direct included-Codex Python from the pre-outcome decision rule, "
                            "independent executable SQL, and the portable selector agreed on the registered inputs.",
                "cost_scope": "No new model inference or paid service during replay. Public grading is historical. "
                              "Development labor, underlying meter omissions, hosting, grader operation and "
                              "complete economic cost were not measured. No causal advantage follows from matching outputs.",
                "arms": summaries}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check",type=Path)
    args = parser.parse_args()
    result = compare()
    if args.check:
        if json.loads(args.check.read_bytes()) != result:
            raise SystemExit("comparison differs from the recorded evidence")
        print("Matched direct, recipient and SQL across all seven arms and reproduced the portable artifact.")
    else:
        print(json.dumps(result,indent=2))
