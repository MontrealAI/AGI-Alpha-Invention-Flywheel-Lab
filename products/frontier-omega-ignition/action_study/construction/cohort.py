"""Deliver the registered UTC release-hour review list and independently recompute membership."""
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mission import HERE, clock_input


def cohort(source, native, anchor, archive):
    ids = [r["oid"] for r in source["commits"]]
    if len(set(ids)) != len(ids) or anchor not in ids or ids != [row[0] for row in native["entries"]]:
        raise ValueError("release anchor or sample object identity mismatch")
    start = time.perf_counter()
    with tempfile.TemporaryDirectory() as work:
        # The caller selects the maintained public recipient, independently checked by verify.py.
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(work)
        rows = "".join(json.dumps(clock_input(r))+"\n" for r in source["commits"])
        run = subprocess.run([sys.executable, "-I", str(Path(work)/"run.py"), "migrate-jsonl"],
                             input=rows, text=True, stdout=subprocess.PIPE, check=True)
    values = [json.loads(line) for line in run.stdout.splitlines()]
    if len(values) != len(ids):
        raise ValueError("incomplete recipient output")
    anchor_row = values[ids.index(anchor)]
    target = (anchor_row["landed_date"], anchor_row["landed_hour"])
    selected = {role: [oid for oid, row in zip(ids, values) if (row[role+"_date"], row[role+"_hour"]) == target]
                for role in ("written", "landed")}
    recipient_seconds = round(time.perf_counter()-start, 6)

    start = time.perf_counter()
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE git (oid TEXT PRIMARY KEY, authored INTEGER NOT NULL, committed INTEGER NOT NULL)")
    db.executemany("INSERT INTO git VALUES (?,?,?)", native["entries"])
    sql = """SELECT oid FROM git WHERE strftime('%Y-%m-%dT%H', {clock}, 'unixepoch') =
        (SELECT strftime('%Y-%m-%dT%H', committed, 'unixepoch') FROM git WHERE oid = ?)"""
    for role, column in (("landed", "committed"), ("written", "authored")):
        direct = {row[0] for row in db.execute(sql.format(clock=column), (anchor,))}
        if direct != set(selected[role]):
            raise ValueError("direct native Git/SQLite comparison disagrees for " + role)
    db.close()
    return {"anchor": anchor, "utc_hour": f"{target[0]}T{target[1]:02}:00:00Z", "scope": len(ids),
            "landed_review_ids": selected["landed"], "authored_in_hour": len(selected["written"]),
            "false_inclusions_using_author_clock": sorted(set(selected["written"]) - set(selected["landed"])),
            "missed_inclusions_using_author_clock": sorted(set(selected["landed"]) - set(selected["written"])),
            "recipient_process_unpack_and_projection_seconds": recipient_seconds,
            "direct_native_sql_seconds": round(time.perf_counter()-start, 6)}


if __name__ == "__main__":
    source = json.loads((HERE/"source_clocks.json").read_bytes())
    native = json.loads((HERE/"native_clocks.json").read_bytes())
    archive = HERE / "git-clock-converter.zip"
    registered = json.loads((HERE / "results.json").read_bytes())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != registered["recipient_sha256"]:
        raise ValueError("recipient differs from the qualified archive")
    print(json.dumps(cohort(source, native, source["commit"], archive), indent=2))
