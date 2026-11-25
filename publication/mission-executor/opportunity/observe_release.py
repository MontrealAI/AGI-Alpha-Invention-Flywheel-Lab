#!/usr/bin/env python3
"""Run a bounded, matched observation of actual release artifacts."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TAG = "weekly-2026.11.25"
RELEASE_ID = 457501084
API = "https://api.github.com/repos/FreeCAD/FreeCAD/releases"
URLS = {"tag": f"{API}/tags/{TAG}", "assets": f"{API}/{RELEASE_ID}/assets?per_page=100"}
TARGETS = tuple(f"FreeCAD_{TAG}-{platform}" for platform in (
    "macOS11-arm64.dmg", "Windows-x86_64.7z",
))


def utcnow():
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def attest(body, arm):
    parsed = json.loads(body)
    if arm == "tag":
        if parsed.get("tag_name") != TAG or parsed.get("id") != RELEASE_ID or parsed.get("draft") is not False:
            raise ValueError("unexpected release identity")
        parsed = parsed["assets"]
    if not isinstance(parsed, list) or len(parsed) >= 100:
        raise ValueError("partial or invalid asset list")
    accepted = {}
    for asset in parsed:
        name, digest = asset.get("name"), asset.get("digest")
        if name not in TARGETS:
            continue
        if name in accepted:
            raise ValueError("duplicate target name")
        if (
            asset.get("state") == "uploaded"
            and type(asset.get("size")) is int and asset["size"] > 0
            and isinstance(digest, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
            and asset.get("browser_download_url") == f"https://github.com/FreeCAD/FreeCAD/releases/download/{TAG}/{name}"
        ):
            accepted[name] = {key: asset[key] for key in ("id", "digest", "size", "created_at", "updated_at")}
    return accepted


def capture(arm, previous):
    headers = {"Accept": "application/vnd.github+json", "Cache-Control": "no-cache"}
    if previous and previous[0]:
        headers["If-None-Match"] = previous[0]
    started = time.monotonic()
    record = {"arm": arm, "url": URLS[arm], "started_at": utcnow(), "conditional": "If-None-Match" in headers}
    body = None
    try:
        with urlopen(Request(URLS[arm], headers=headers), timeout=30) as response:
            if response.geturl() != URLS[arm] or response.status != 200:
                raise ValueError("unexpected endpoint or status")
            body = response.read(512_001)
            if len(body) > 512_000:
                raise ValueError("response exceeds observation body limit")
            record.update({"status": response.status, "bytes": len(body), "etag": response.headers.get("ETag"),
                           "source_date": response.headers.get("Date"), "age": response.headers.get("Age"),
                           "remaining": response.headers.get("X-RateLimit-Remaining")})
    except HTTPError as error:
        record.update({"status": error.code, "source_date": error.headers.get("Date"),
                       "remaining": error.headers.get("X-RateLimit-Remaining")})
        if error.code == 304 and previous:
            body = previous[1]
            record.update({"bytes": 0, "etag": previous[0]})
    except (OSError, URLError, ValueError) as error:
        record["error"] = f"{type(error).__name__}: {error}"
        body = None
    record["completed_at"] = utcnow()
    record["elapsed_s"] = round(time.monotonic() - started, 6)
    if body is not None:
        try:
            record.update({"sha256": checksum(body), "accepted": attest(body, arm)})
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            record["error"] = f"{type(error).__name__}: {error}"
    return record, body


def run(directory, rounds, interval):
    directory.mkdir(parents=True, exist_ok=False)
    registration = {
        "registered_at_utc": utcnow(), "source_sha256": checksum(Path(__file__).read_bytes()),
        "release_id": RELEASE_ID, "tag": TAG, "targets": TARGETS, "arms": URLS,
        "interval_seconds": interval, "maximum_rounds": rounds,
        "acceptance": "Exact target name and published release identity with uploaded, nonempty asset and digest",
        "comparison": "Independent concurrent acquisition paths on one GitHub registry with equal poll cadence, body limits, and ETag policy",
        "stop": "Both arms see both exact targets, planned maximum, or STOP file",
    }
    (directory / "registration.json").write_text(json.dumps(registration, indent=2) + "\n")
    previous = {}
    first_observations = {}
    start = time.monotonic()
    with (directory / "observations.jsonl").open("w") as log, ThreadPoolExecutor(max_workers=len(URLS)) as pool:
        for number in range(rounds):
            while time.monotonic() < start + number * interval:
                if (directory / "STOP").exists():
                    return
                time.sleep(max(0, min(1, start + number * interval - time.monotonic())))
            if (directory / "STOP").exists():
                return
            futures = {arm: pool.submit(capture, arm, previous.get(arm)) for arm in URLS}
            for arm, request in futures.items():
                record, body = request.result()
                record["round"] = number + 1
                if "accepted" in record:
                    previous[arm] = record.get("etag"), body
                    (directory / (record["sha256"] + ".json")).write_bytes(body)
                    for name in record["accepted"]:
                        first_observations.setdefault((arm, name), record["completed_at"])
                line = json.dumps(record, separators=(",", ":")) + "\n"
                log.write(line)
                log.flush()
                print(line, end="", flush=True)
            if len(first_observations) == len(URLS) * len(TARGETS):
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--rounds", type=int, default=14)
    parser.add_argument("--interval", type=int, default=95)
    args = parser.parse_args()
    if args.rounds < 1 or args.interval < 30:
        parser.error("observations require at least one round and a 30 second interval")
    run(args.directory, args.rounds, args.interval)
