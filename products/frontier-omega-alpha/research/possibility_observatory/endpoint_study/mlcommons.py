"""Adapt the public MLCommons Results Explorer data without evaluating page scripts."""

from collections import Counter
from decimal import Decimal
from functools import cache
from hashlib import sha256
import json
from pathlib import Path
import re

SOURCE = "https://results.mlcommons.org/endpoints/__data.json"
SOURCE_SHA256 = "ce3226048090ba13e5d2369b582126f8440ba3485926f91ed81396fe15acada0"
MAX_SNAPSHOT = 2_000_000
MATCH = {
    "version": "1.0",
    "division": "Standardized",
    "model": "deepseek-v4_1-flash",
    "dataset": "mlperf_agentic_inference_dataset",
    "availability": "Available",
    "submission": "official",
    "run": "valid-online",
}


def public_feed(raw):
    nodes = json.loads(raw, parse_float=Decimal)["nodes"]
    pool = nodes[0]["data"]
    if not isinstance(pool, list) or len(pool) > 30_000:
        raise ValueError("Unexpected Results Explorer value table")

    @cache
    def read(index, depth):
        if type(index) is not int or not -1 <= index < len(pool) or depth > 24:
            raise ValueError("Unexpected Results Explorer value reference")
        if index == -1:
            return None
        value = pool[index]
        if isinstance(value, dict):
            return {key: read(ref, depth + 1) for key, ref in value.items()}
        if isinstance(value, list):
            return [read(ref, depth + 1) for ref in value]
        return value

    # This only interprets the selected JSON data nodes. It executes no source text.
    phase = pool[pool[0]["phase2"]]
    if read(phase["mode"], 0) != "public" or read(phase["source"], 0) != "api":
        raise ValueError("Expected the public API-backed feed")
    data = pool[phase["data"]]
    return {name: read(data[name], 0) for name in ("meta", "submissions", "systems", "runs")}


def unique(items, key):
    indexed = {item[key]: item for item in items}
    if len(indexed) != len(items):
        raise ValueError("Duplicate in the source identity table")
    return indexed


def normalize(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Expected a pinned public data file")
    with path.open("rb") as file:
        raw = file.read(MAX_SNAPSHOT + 1)
    if len(raw) > MAX_SNAPSHOT or sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Size or source digest differs from the preregistered capture")
    data = public_feed(raw)
    counts = Counter(run["submission_id"] for run in data["runs"])
    systems = unique(data["systems"], "id")
    submissions = unique(data["submissions"], "submission_id")
    runs = unique(data["runs"], "run_id")
    if counts != {key: entry["run_count"] for key, entry in submissions.items()}:
        raise ValueError("Measurement counts differ from the submission manifest")
    rows = [measurement(run, submissions[run["submission_id"]], systems[run["system_id"]])
            for _, run in sorted(runs.items())]
    return {"schema": "frontier-omega-alpha/endpoint-observations-v1",
            "source": SOURCE, "source_sha256": SOURCE_SHA256,
            "generated_at": data["meta"]["generated_at"], "rows": rows}


def decimal_text(value):
    if value is None:
        return None
    if type(value) not in (int, Decimal):
        raise ValueError("Unexpected published measurement type")
    return format(value, "f")


def measurement(run, submission, system):
    if run["system_id"] != submission["system_id"] or run["model_id"] != submission["model_id"]:
        raise ValueError("Mismatched submission, model or system identity")
    result_ids = submission["result_ids"]
    versions = {m.group(1) for ident in result_ids
                if (m := re.match(r"^(\d+\.\d+)\.\d+\.", ident))}
    if len(versions) > 1:
        raise ValueError("Mixed result versions in a submission")
    official = (submission["publication_status"] == "Official"
                and submission["submission_status"] == "PUBLISHED"
                and submission["is_provisional"] is False and submission["is_test"] is False)
    online = (run["scenario"] == "Online" and run["offline"] in ("none", "")
              and run["result_state"] == "complete" and run["is_valid"] is True
              and run["is_test"] is False)
    return {
        "id": run["run_id"],
        "published": submission["publish_date"] or None,
        "facts": {
            "version": next(iter(versions), ""),
            "division": submission["division"],
            "model": submission["model_name"],
            "dataset": submission["dataset_name"],
            "availability": system["system_availability_status"],
            "submission": "official" if official else "unqualified",
            "run": "valid-online" if online else "unqualified",
        },
        "metric": decimal_text(run["e2e_avg_interactivity"]),
        "objective": decimal_text(run["system_tps"]),
        "upper_metric": decimal_text(run["ttft_ms"]),
        "load": run["concurrency"],
        "submission_id": submission["submission_id"],
        "result_ids": result_ids,
        "system": system["system_name"],
    }
