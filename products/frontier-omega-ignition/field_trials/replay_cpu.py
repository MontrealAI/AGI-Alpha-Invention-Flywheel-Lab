"""Independently regenerate the displayed local Qwen observation from its two public SSE captures."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FIELD = HERE.parent / "field_lab"
RECORD = HERE / "recorded"


def read_observation():
    operation = json.loads((RECORD / "operation.json").read_bytes())
    if not operation["executed"] or operation["production_traffic"] or operation["billing"] is not None:
        raise ValueError("The recorded scope is a six-case public CPU pilot")
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for route in ("field", "conventional"):
            arm = operation["arms"][route]
            if any(arm[key] != 0 for key in ("client_exit", "independent_replay_exit", "live_tokenizer_exit")):
                raise ValueError("Incomplete original client or model-tokenizer comparison")
            with gzip.open(RECORD / (route + ".json.gz"), "rb") as stream:
                wire = stream.read(4_194_305)
            if len(wire) > 4_194_304 or hashlib.sha256(wire).hexdigest() != arm["receipt_sha256"]:
                raise ValueError("Changed public wire observation")
            trace = Path(tmp) / (route + ".json")
            trace.write_bytes(wire)
            received = json.loads(wire)
            if (received["route"] != route or received["target"]["model_sha256"] != operation["assets"]["weights_sha256"]
                    or received["target"]["runtime_sha256"] != operation["assets"]["server_sha256"]):
                raise ValueError("Provider or client identity differs")
            observation = subprocess.check_output([
                sys.executable, "-B", str(FIELD / "verify.py"), "--workload", str(FIELD / "workload.json"),
                "--receipt", str(trace)], text=True)
            for row in json.loads(observation):
                rows.append({"route": route, **row})
    acquisition = json.loads((HERE / "DEVELOPMENT.json").read_bytes())["acquisition"]
    return {"model": operation["model"], "scope": "recorded public synthetic CPU pilot", "hardware": operation["hardware"],
            "arms": rows, "acquisition_wall_seconds": acquisition["download_and_verify_wall_seconds"],
            "observed_wall_seconds": operation["wall_seconds"],
            "observed_cpu_seconds": operation["cpu_seconds_including_children"], "complete_cost": None,
            "field_traffic": None, "adoption": "defer"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New summary for inspection; default checks the shipped summary")
    args = parser.parse_args()
    result = read_observation()
    if args.output:
        with args.output.open("x", encoding="utf-8") as file:
            file.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif result != json.loads((RECORD / "summary.json").read_bytes()):
        raise SystemExit("Published pilot summary differs from the independent replay")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
