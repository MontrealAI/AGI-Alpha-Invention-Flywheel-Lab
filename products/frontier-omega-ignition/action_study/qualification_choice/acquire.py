"""Fetch only public SWE-bench status metadata, into a fresh review directory."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

A = "20260217_mini-v2.0.0_gpt-5-2-high"
B = "20260219_mini-v2.0.0_gpt-5-2-codex"
LEADERBOARD = "https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/193160a463a435d05cf44a1fa9dc5eac832113c3/data/leaderboards.json"
EXPERIMENTS = "https://raw.githubusercontent.com/SWE-bench/experiments/40f164d5b8f1d249bf95a6df8b74b577fd8e519d/evaluation/verified/"
BUCKET = "https://swe-bench-submissions.s3.amazonaws.com"
LOGS = f"bash-only/{B}/logs/"
STATUS = re.compile(rb'^\{\s*"patch_is_None"\s*:\s*(true|false),\s*"patch_exists"\s*:\s*(true|false),\s*"patch_successfully_applied"\s*:\s*(true|false),\s*"resolved"\s*:\s*(true|false)\s*[,}]')
ID = re.compile(r"^[a-zA-Z0-9_.-]+__[a-zA-Z0-9_.-]+-\d+$")


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def digest(data):
    return sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")


def acquire(url, byte_range=None):
    headers = {"User-Agent": "FRONTIER-OMEGA-public-status-review/1"}
    if byte_range is not None:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        if byte_range is not None:
            content_range = response.headers.get("Content-Range", "")
            start = byte_range[0]
            if response.status != 206 or not content_range.startswith(f"bytes {start}-"):
                raise ValueError("Origin did not honor the registered bounded byte range")
        limit = 6_000_000 if byte_range is None else byte_range[1] - byte_range[0] + 1
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("Source exceeds its declared byte limit")
        return data, {"url": url, "sha256": digest(data), "bytes": len(data),
                      "retrieved_utc": utc(), "http": response.status,
                      "content_range": response.headers.get("Content-Range"),
                      "last_modified": response.headers.get("Last-Modified"), "etag": response.headers.get("ETag")}


def collect(destination, until_decision=None):
    destination.mkdir(parents=True, exist_ok=False)
    start, cpu = time.perf_counter(), time.process_time()
    catalogue = []
    for folder in (A, B):
        data, record = acquire(EXPERIMENTS + folder + "/metadata.yaml")
        (destination / (folder + ".yaml")).write_bytes(data)
        catalogue.append(record)
    board, record = acquire(LEADERBOARD)
    catalogue.append(record)
    results = next(group["results"] for group in json.loads(board)["leaderboards"] if group["name"] == "Verified")
    left, right = [next(result for result in results if result["folder"] == name) for name in (A, B)]
    if right.get("logs") != "s3://swe-bench-submissions/" + LOGS.rstrip("/") or right.get("per_instance_details"):
        raise ValueError("Publisher's B acquisition route changed")
    if any(row["agent"] != "mini-SWE-agent" or row["mini-swe-agent_version"] != "2.0.0" for row in (left, right)):
        raise ValueError("Harness identity differs")
    for row in (left, right):
        count = Fraction(str(row["resolved"])) * 500 / 100
        if count.denominator != 1 or not 0 <= count <= 500:
            raise ValueError("Published percentage does not identify an integer pooled count")
    ids = left["per_instance_details"]
    if len(ids) != 500 or any(not ID.fullmatch(key) or type(value["resolved"]) is not bool for key, value in ids.items()):
        raise ValueError("A status roster is incomplete or ambiguous")
    index, record = acquire(BUCKET + "/?" + urlencode({"list-type": "2", "delimiter": "/", "prefix": LOGS, "max-keys": "1000"}))
    catalogue.append(record)
    root = ElementTree.fromstring(index)
    if root.findtext("{*}IsTruncated") != "false":
        raise ValueError("Truncated B submission index")
    observed = [section.findtext("{*}Prefix").removeprefix(LOGS).removesuffix("/") for section in root.findall("{*}CommonPrefixes")]
    if len(observed) != 500 or set(observed) != set(ids):
        raise ValueError("B index differs from A roster")
    groups = defaultdict(list)
    for key in ids:
        groups[key.rsplit("-", 1)[0].replace("__", "/")].append(key)
    schedule = sorted(groups, key=lambda repo: (len(groups[repo]), repo))
    pool = {name: {key: row[key] for key in ("folder", "name", "date", "resolved", "cost", "instance_calls", "reasoning_effort")} for name, row in zip(("A", "B"), (left, right))}
    save(destination / "sources.json", {"catalogue": catalogue, "pool": pool, "schedule": schedule})
    def fetch_status(key):
        history = []
        for attempt in range(3):
            try:
                data, receipt = acquire(BUCKET + "/" + LOGS + key + "/report.json", (0, 114))
                match = STATUS.match(data)
                if not match:
                    raise ValueError("Unrecognized evaluator status prefix")
                return {"id": key, "a": ids[key]["resolved"], "b_prefix": data.decode("ascii"),
                        "etag": receipt["etag"], "last_modified": receipt["last_modified"],
                        "content_range": receipt["content_range"], "retrieved_utc": receipt["retrieved_utc"],
                        "failed_attempts": history}
            except (OSError, ValueError) as error:
                history.append({"type": type(error).__name__, "message": str(error), "utc": utc()})
                if attempt < 2:
                    time.sleep(1 + attempt)
        return {"id": key, "a": ids[key]["resolved"], "failed_attempts": history}
    timings = []
    if until_decision is not None:
        # Imported only on this acquisition mode to keep full lookup independent.
        if __package__:
            from .adapter import interval, sign
            from .roster import decode_prefix
        else:
            from adapter import interval, sign
            from roster import decode_prefix
        source_roster = decode_prefix((until_decision / "roster.parquet-prefix").read_bytes())
        if set(source_roster) != set(ids) or any(source_roster[key] != repo for repo, keys in groups.items() for key in keys):
            raise ValueError("The independent Princeton denominator disagrees with submission IDs")
        margins = {key: int(Fraction(str(record["resolved"])) * 5) for key, record in pool.items()}
        sizes = {repo: len(keys) for repo, keys in groups.items()}
        known = {}
        decision = None
    with ThreadPoolExecutor(max_workers=12) as workers:
        for repo in schedule:
            begin = time.perf_counter()
            rows = list(workers.map(fetch_status, sorted(groups[repo])))
            save(destination / (repo.replace("/", "__") + ".json"), rows)
            timings.append({"repo": repo, "seconds": round(time.perf_counter() - begin, 5),
                            "attempts": sum(len(row["failed_attempts"]) + int("b_prefix" in row) for row in rows),
                            "successes": sum("b_prefix" in row for row in rows)})
            print(repo, timings[-1], flush=True)
            if until_decision is not None:
                if any("b_prefix" not in row for row in rows):
                    raise ValueError("A required original evaluator status is unavailable")
                known[repo] = {"A": sum(r["a"] for r in rows), "B": sum(
                    STATUS.match(r["b_prefix"].encode("ascii")).group(4) == b"true" for r in rows)}
                low, high = interval(sizes, margins, known)
                decision = sign(low, high, len(known) == len(sizes))
                if decision:
                    save(destination / "decision.json", {"finding": decision, "bounds": [str(low), str(high)],
                         "disclosed_repositories": list(known), "source_reports": sum(sizes[r] for r in known)})
                    break
    save(destination / "timings.json", {"wall_seconds": time.perf_counter() - start,
                                          "cpu_seconds": time.process_time() - cpu, "groups": timings})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="A new capture directory")
    parser.add_argument("--until-decision", type=Path, metavar="ROSTER_DIRECTORY",
                        help="Stop live requests at the first strict ordering on a separately captured Princeton roster")
    args = parser.parse_args()
    collect(args.directory, args.until_decision)
