"""Registered UTC-clock task. SQL expectations are authored independently of the constructor."""
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from ignition.construction import fingerprint
from ignition.development import projection_scope

HERE = Path(__file__).resolve().parent
PURPOSE = "Convert Git archive clock records to written and landed UTC date, hour and minute for release cohort analysis."
PARTS = ("date", "hour", "minute")
TARGETS = [{"name": role + "_" + part, "type": "text" if part == "date" else "integer"}
           for role in ("written", "landed") for part in PARTS]
SQL = """select date(:author) written_date, cast(strftime('%H', :author) as integer) written_hour,
cast(strftime('%M', :author) as integer) written_minute, date(:committer) landed_date,
cast(strftime('%H', :committer) as integer) landed_hour, cast(strftime('%M', :committer) as integer) landed_minute"""


def clock_input(record):
    fields = {}
    for role in ("author", "committer"):
        instant = datetime.fromisoformat(record[role].replace("Z", "+00:00"))
        if instant.utcoffset() is None:
            raise ValueError("Git clock requires an explicit time zone")
        instant = instant.astimezone(timezone.utc)
        fields.update({role + "_date": instant.date().isoformat(), role + "_hour": instant.hour,
                       role + "_minute": instant.minute})
    return fields


def ordinary(db, record):
    return dict(db.execute(SQL, {role: record[role] for role in ("author", "committer")}).fetchone())


def mission():
    source = json.loads((HERE / "source_clocks.json").read_bytes())
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    observations = [{"id": c["oid"], "input": clock_input(c), "expected": ordinary(db, c)}
                    for c in source["commits"]]
    db.close()
    sealed = [r for r in observations if r["id"][-1] in "0123"]
    training = [r for r in observations if r["id"][-1] not in "0123"]
    demos = [r for r in training if all(r["input"]["author_" + p] == r["input"]["committer_" + p]
                                       for p in PARTS)][:2]
    if len(demos) != 2 or len({fingerprint(r["input"]) for r in demos}) != 2:
        raise ValueError("Registered development did not furnish two distinct equal-clock inputs.")
    sealed_inputs = {fingerprint(r["input"]) for r in sealed}
    if any(fingerprint(r["input"]) in sealed_inputs for r in demos):
        raise ValueError("Registered development contaminates confirmation.")
    # Different Git objects can have identical clocks to minute precision. Never expose
    # any of these confirmation vectors through an acquisition input, even with a different ID.
    pool = [r for r in training if r not in demos and fingerprint(r["input"]) not in sealed_inputs]
    source_ref = {"publisher": source["publisher"], "locator": "https://github.com/git/git",
                  "version": source["commit"], "retrieved_at": source["exchanges"][-1]["retrieved_utc"]}
    binding = {"source": source_ref, "records": pool}
    groups = defaultdict(list)
    for item in sealed:
        groups[fingerprint(item["input"])].append(item)
    cases = [{"name": "commit clocks " + items[0]["id"][:12],
              "input": {"rows": [r["input"] for r in items]}, "expected": {"rows": [r["expected"] for r in items]}}
             for items in groups.values()]
    seed = sealed[0]["input"]
    cases.extend([{"name": "missing commit minute", "input": {"rows": [
                      {k: v for k, v in seed.items() if k != "committer_minute"}]}, "error": "missing_field"},
                  {"name": "invalid UTC hour", "input": {"rows": [{**seed, "author_hour": False}]},
                   "error": "invalid_value"}])
    cross = {"oid": "authored-cross-midnight", "author": "2003-12-31T22:57:00Z",
             "committer": "2004-01-01T00:06:00Z"}
    genuine = next(c for c in source["commits"] if c["oid"][-1] in "0123" and c["author"][:16] != c["committer"][:16])
    swapped = {"oid": "swapped roles control", "author": genuine["committer"], "committer": genuine["author"]}
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    for control in (cross, swapped):
        cases.append({"name": control["oid"], "input": {"rows": [clock_input(control)]},
                      "expected": {"rows": [ordinary(db, control)]}})
    db.close()
    fields = ["author_" + p for p in PARTS] + ["committer_" + p for p in PARTS]
    definition = {"input_fields": fields, "targets": TARGETS, "extra_fields": "reject",
                  "demonstrations": [{"input": {"rows": [r["input"] for r in demos]},
                                      "expected": {"rows": [r["expected"] for r in demos]}}]}
    spec = {"purpose": PURPOSE, "kind": "record_migration", "definition": definition, "cases": cases}
    m = {"purpose": PURPOSE, "beneficiary": "MONTREAL.AI release archive engineering (public rehearsal)",
         "requirements": ["Written is the author timestamp. Landed is the committer timestamp.",
                          "Copy each UTC date, hour and minute to the corresponding output without rounding.",
                          "Refuse missing or extra fields and unsupported values under the typed migration contract."],
         "authority": {}, "resources": {}, "time": {}, "construction_spec": spec}
    binding["decision_sha256"] = projection_scope(m)
    m["resources"]["mapping_evidence"] = {**binding, "sha256": fingerprint(binding), "max_labels": 4}
    return m, {"commits": len(observations), "development_ids": [r["id"] for r in demos],
               "sealed_records": len(sealed), "distinct_sealed_vectors": len(groups),
               "pool_records": len(pool), "pool_records_excluded_to_protect_sealed_inputs": len(training)-len(demos)-len(pool)}
