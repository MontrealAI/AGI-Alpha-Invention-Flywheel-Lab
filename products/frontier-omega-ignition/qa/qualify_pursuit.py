"""Qualify the regular CLI and then the transferred ZIPs on separate machines."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

PRODUCT = Path(__file__).resolve().parents[1]


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode()


def file_hash(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def output_json(args, cwd):
    run = subprocess.run(args, cwd=cwd, capture_output=True, check=False)
    if run.returncode:
        raise RuntimeError(f"{args[0]} exited {run.returncode}: {run.stderr.decode(errors='replace')[-1600:]}")
    return json.loads(run.stdout)


def produce(target, source):
    target.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as folder:
        private = Path(folder) / "state"
        cli = [sys.executable, "-B", "-m", "ignition", "--state", str(private)]
        cmd = [*cli, "pursue", "examples/public-research-ranked.shortlist", "--request-id", "qualify-public-research"]
        started = time.monotonic()
        first = output_json(cmd, PRODUCT)
        selection = first["selection"]
        screened = [item for item in selection["assessments"] if not item["eligible"]]
        if (selection["ranked"] != ["quantum", "scroll"] or [item["candidate"] for item in screened] != ["expensify"]
                or any(item["estimated_net_usd_cents"] is not None for item in selection["assessments"])):
            raise ValueError("The sourced portfolio must select affordable proof and preserve unknown economics")
        second = output_json(cmd, PRODUCT)
        if first != second:
            raise ValueError("A process restart changed the accepted package, outcome or mission identity")
        successor = output_json([*cli, "pursue", "examples/public-research-ranked.shortlist",
                                 "--request-id", "qualify-successor", "--reuse-from", "qualify-public-research"], PRODUCT)
        prior, fresh = successor["attempts"]
        if (prior.get("technical_status") != "reused_previous_negative" or prior.get("new_measurement") is not False
                or prior["reused_from"]["mission_id"] != first["attempts"][0]["mission_id"]
                or fresh["candidate"] != "scroll" or fresh["mission_id"] == first["attempts"][1]["mission_id"]):
            raise ValueError("The successor must reuse the exact negative and run its own scroll experiment")
        new_state = output_json([*cli, "show", fresh["mission_id"]], PRODUCT)
        if not new_state.get("scroll_field", {}).get("receipt"):
            raise ValueError("The successor did not collect its own public field evidence")
        attempts = first["attempts"]
        if [a["candidate"] for a in attempts] != ["quantum", "scroll"] or attempts[0]["commercial_state"] != "withheld":
            raise ValueError("The measured scored-resource tie must advance to the second experiment")
        receipt = {"source": source, "pursuit": first, "restart_identical": True, "successor": successor,
                   "elapsed_seconds_including_restart_and_successor": round(time.monotonic() - started, 3), "packages": {}}
        for a in attempts:
            name = a["candidate"]
            package = target / (name + ".zip")
            shutil.copyfile(private / "recipients" / a["recipient"]["file"], package)
            if file_hash(package) != a["recipient"]["sha256"]:
                raise ValueError("Transferred ZIP differs from the mission export")
            receipt["packages"][name] = file_hash(package)
            status = output_json([*cli, "commercial", a["mission_id"], "--version", "1"], PRODUCT)
            if status["collected_revenue"] is not None or status["commercial_state"] not in {"withheld", "identified"}:
                raise ValueError("A local test cannot establish a transaction")
        with ZipFile(target / "scroll.zip") as bundle:
            field = json.loads(bundle.read("mission-field.json"))
            if not field.get("receipt"):
                raise ValueError("Fresh public field measurement unavailable: " + str(field.get("error")))
            receipt["scroll_field"] = field["receipt"]["summary"]
    manifest = target / "qualification.json"
    manifest.write_bytes(encoded(receipt))
    print(file_hash(manifest))


def receive(target, expected):
    manifest = target / "qualification.json"
    if file_hash(manifest) != expected:
        raise ValueError("The delivered manifest differs from the source job's digest")
    summary = json.loads(manifest.read_bytes())
    results = {}
    for name, command in (("quantum", ["replay.py"]), ("scroll", ["scroll_tool.py", "self-check"])):
        path = target / (name + ".zip")
        if file_hash(path) != summary["packages"][name]:
            raise ValueError("Transferred package digest differs")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with ZipFile(path) as bundle:
                if any(n.endswith((".raw", ".u8", ".tif", ".so", ".sqlite3")) for n in bundle.namelist()):
                    raise ValueError("Unexpected data, binary or private state in the recipient")
                bundle.extractall(root)
            observed = output_json([sys.executable, "-IB", *command], root)
            if name == "quantum":
                if observed["decision"] != "withhold_contest_entry" or observed["toffolis"] != 42:
                    raise ValueError("Recipient disagrees with the scored result")
            elif observed["passed"] is not True or observed["cases"] != 32:
                raise ValueError("Recipient did not reproduce all numerical controls")
            results[name] = observed
    print(json.dumps({"source": summary["source"], "recipients": results}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("produce", "receive"))
    parser.add_argument("directory", type=Path)
    parser.add_argument("identity", help="checked Git source for produce; trusted manifest SHA-256 for receive")
    args = parser.parse_args()
    if args.action == "produce":
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=PRODUCT, text=True).strip() != args.identity:
            sys.exit("Requested source differs from checked-out HEAD")
        produce(args.directory, args.identity)
    else:
        receive(args.directory, args.identity)
