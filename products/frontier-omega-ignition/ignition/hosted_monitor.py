"""Read-only operator probe with actionable output and nonzero exit on alarms."""
import argparse
import contextlib
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import shutil
import sqlite3
import sys
from urllib.parse import urlsplit


def metrics(state):
    latest_query = """SELECT r.data FROM revisions r JOIN
        (SELECT id, MAX(version) AS version FROM revisions GROUP BY id) h
        ON r.id=h.id AND r.version=h.version"""
    totals = {"workspaces": 0, "queued": 0, "running": 0, "blocked": 0, "oldest_queued_seconds": 0}
    now = datetime.now(timezone.utc)
    with contextlib.closing(sqlite3.connect((state / "access.sqlite3").as_uri()+"?mode=ro", uri=True)) as db:
        tenants = [r[0] for r in db.execute("SELECT alias FROM workspace")]
    totals["workspaces"] = len(tenants)
    for tenant in tenants:
        path = state / "workspaces" / tenant / "missions.sqlite3"
        if not path.is_file():
            continue
        with contextlib.closing(sqlite3.connect(path.as_uri()+"?mode=ro", uri=True, timeout=2)) as db:
            for row, in db.execute(latest_query):
                data = json.loads(row)
                if data.get("operation", {}).get("state","active") != "active":
                    continue
                status = data["status"]
                if status in ("blocked", "running", "queued"):
                    totals[status] += 1
                if status == "queued":
                    age = (now - datetime.fromisoformat(data["events"][-1]["at"])).total_seconds()
                    totals["oldest_queued_seconds"] = max(totals["oldest_queued_seconds"], int(age))
    totals["free_bytes"] = shutil.disk_usage(state).free
    return totals


def check(state, origin, port, *, client=http.client.HTTPConnection):
    result, alarms = {}, []
    try:
        with contextlib.closing(client("127.0.0.1", port, timeout=5)) as conn:
            conn.request("GET", "/readyz", headers={"Host": urlsplit(origin).netloc})
            res = conn.getresponse()
            reply = json.loads(res.read(4096))
            result["ready"] = res.status == 200 and reply.get("status") == "ok"
            if not result["ready"]:
                alarms.append("Local model or service unavailable: check the pinned model, storage and service journal.")
    except (ValueError, OSError, http.client.HTTPException):
        alarms.append("Service probe unavailable: check the service, proxy hostname and model.")
    try:
        result.update(metrics(state))
        if result["free_bytes"] < 1024**3:
            alarms.append("Less than 1 GiB free: pause new missions and check storage/backups.")
        if result["oldest_queued_seconds"] > 300:
            alarms.append("Active mission queued over five minutes: inspect workers and pause further admissions.")
    except (ValueError, OSError, sqlite3.Error, KeyError):
        alarms.append("Private storage unreadable: stop admission; inspect ownership, disk and the last verified backup.")
    return {"measurements":result,"alarms":alarms}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--port", type=int, default=8784)
    args = parser.parse_args()
    result = check(args.state.resolve(), args.origin, args.port)
    print(json.dumps(result))
    return int(bool(result["alarms"]))


if __name__ == "__main__":
    sys.exit(main())
