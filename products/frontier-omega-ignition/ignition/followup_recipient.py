"""Replay a local follow-up delivery. No network access or telescope interface."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from plan import build
from reference import targets_from_alerts
from verify import verify


def read(name):
    def unique(items):
        record = dict(items)
        if len(record) != len(items):
            raise ValueError("Duplicate key in received document")
        return record
    return json.loads((ROOT / name).read_bytes(), object_pairs_hook=unique)


def same_document(left, right):
    # JSON booleans and numbers have distinct types even when Python equality agrees.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def main():
    mission = read("mission.json")
    catalog = read("catalog.json")
    alerts = (ROOT / "sources/fink-alerts.json").read_bytes()
    if (hashlib.sha256(alerts).hexdigest() != catalog.get("alerts_sha256")
            or targets_from_alerts(json.loads(alerts)) != catalog.get("targets")):
        raise ValueError("Catalog does not reproduce the public source alerts")
    plan = build(mission, catalog)
    construct = sys.argv[1:] == ["--construct"]
    if sys.argv[1:] and not construct:
        raise ValueError("Use review_followup.py to verify the delivered worklist")
    if not construct and not same_document(read("plan.json"), plan):
        raise ValueError("Delivered worklist differs from the current mission and catalog")
    receipt = verify(mission, catalog, plan)
    if receipt.get("accepted") is not True or plan.get("dispatch_authorized") is not False:
        raise ValueError("The local worklist failed independent planning acceptance")
    if not construct and not same_document(read("verification.json"), receipt):
        raise ValueError("Independent verification differs from the delivered receipt")
    print(json.dumps({"plan": plan, "verification": receipt}, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
