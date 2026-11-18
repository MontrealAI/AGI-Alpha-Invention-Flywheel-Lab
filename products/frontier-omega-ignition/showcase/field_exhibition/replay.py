"""Recheck the observing-night recipient and, optionally, a downloaded browser case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE if (HERE / "invention").is_dir() else HERE.parents[1]
sys.path.insert(0, str(PRODUCT / "invention"))
from qualify import qualification
from verify import verify


def read(path):
    return json.loads(path.read_bytes())


def replay(case_path=None):
    sky = qualification()
    if sky != read(PRODUCT / "invention/public.json"):
        raise ValueError("Frozen worklists or archive photometry differ from fresh qualification")
    repeat = PRODUCT / "invention/next_week"
    subprocess.run([sys.executable, "-B", str(repeat / "replay.py")], check=True, stdout=subprocess.DEVNULL)
    second = read(repeat / "RESULT.json")
    previous_missing = set(sky["photometry"]["missing_pair"])
    newly_measured = sorted(pair["target_id"] for pair in second["pairs_120"]
                            if pair["target_id"] in second["overlap_with_first"] and pair["target_id"] in previous_missing)
    if newly_measured != second["first_week_withheld_now_qualifies_120"]:
        raise ValueError("Cross-cohort change differs from the two checked target populations")
    field = PRODUCT / "field_lab"
    subprocess.run([sys.executable, "-B", str(field / "verify.py"), "--public", str(field / "PUBLIC.json")],
                   check=True, stdout=subprocess.DEVNULL)
    successor = PRODUCT / "successor_field"
    queue = successor / "archive-queue.csv"
    recorded = read(successor / "OBSERVATION.json")
    if hashlib.sha256(queue.read_bytes()).hexdigest() != recorded["queue_sha256"]:
        raise ValueError("Earth-orientation queue differs from its recorded delivery")
    subprocess.run([sys.executable, "-B", str(successor / "audit.py"), str(queue),
                    "--tolerance-ms", recorded["tolerance_ms"]], check=True, stdout=subprocess.DEVNULL)
    result = {"registered_worklists": len(sky["cases"]), "photometry": sky["photometry"]["direct_sql"],
              "second_week": {"targets": second["targets"], "pairs_120": len(second["pairs_120"]),
                              "pairs_10": len(second["pairs_10"]), "previously_withheld_now_measured": newly_measured},
              "fixture_captures": len(read(field / "PUBLIC.json")["receipts"]), "archive_dates": recorded["summary"]["dates"]}
    if case_path:
        request = read(case_path)
        mission = request["mission"]
        catalog = read(PRODUCT / "invention/catalog.json")
        verified = verify(mission, catalog, request["worklist"])
        candidates = [r for r in sky["cases"] if r["id"] == request["case_id"] and r["mission_sha256"] == request["worklist"]["mission_sha256"]]
        if (len(candidates) != 1 or candidates[0]["slots"] != request["worklist"]["slots"]
                or request["schema"] != "frontier.observing-case.v1" or request["acceptance"] != verified):
            raise ValueError("Selected case does not match its independently checked registration")
        result["selected_case"] = {"id": request["case_id"], "accepted": verified["accepted"],
                                   "covered_targets": verified["direct_objective"]}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", type=Path, help="JSON case downloaded in the public Forge")
    args = parser.parse_args()
    print(json.dumps(replay(args.case), ensure_ascii=False, indent=2))
