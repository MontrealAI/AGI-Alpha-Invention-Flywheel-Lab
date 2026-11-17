#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Observe registered public publisher feeds through the production HARNESS transport."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ignition.research import FEEDS, discover_sources

PRODUCT = Path(__file__).resolve().parent
REPO = PRODUCT.parents[1]
FEED_KEYS = ["model-tooling", "distribution"]
OPERATOR_URL = "https://github.com/jqlang/jq"
OPERATOR_KEY = "github:jqlang/jq"
REGISTERED = {**{key: FEEDS[key][0] for key in FEED_KEYS}, OPERATOR_KEY: "jqlang/jq"}
MISSION = {"purpose": "Find publicly reported changes to local model tooling and package delivery.",
           "requirements": [], "authority": {"public_sources": True}, "resources": {"public_repositories": [OPERATOR_URL]}}
PATHS = [str(path.relative_to(REPO)) for path in (
    Path(__file__).resolve(), PRODUCT / "ignition/research.py", PRODUCT / "ignition/__init__.py",
    PRODUCT.parent / "alpha-genesis-harness/bridge")]
HEX = re.compile(r"[a-f0-9]{64}\Z")


def stamp():
    return datetime.now(timezone.utc)


def _git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def source_identity(expected):
    """Only assume committed source when the checkout and selected paths agree."""
    try:
        revision = _git("rev-parse", "--verify", "HEAD")
        changed = bool(_git("status", "--porcelain", "--untracked-files=all", "--", *PATHS))
    except (OSError, subprocess.CalledProcessError):
        return {"revision": None, "clean": None, "status": "BLOCKED", "reason": "No verifiable Git checkout"}
    if changed or (expected and expected != revision):
        return {"revision": revision, "clean": not changed, "status": "FAIL",
                "reason": "The revision or checked source files differ"}
    return {"revision": revision, "clean": True, "status": "PASS"}


def _parse_time(value):
    if not isinstance(value, str):
        raise ValueError("Missing publisher or retrieval time")
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("Missing time offset")
    return moment.astimezone(timezone.utc)


def qualify(data, began, ended, identity):
    cutoff = began.date() - timedelta(days=35)
    records, errors = [], []
    for item in data["sources"]:
        try:
            key = item["feed"]
            if key not in REGISTERED:
                raise ValueError("Unregistered source feed")
            repository = REGISTERED[key]
            if key == OPERATOR_KEY and (item.get("acquisition") != "operator-authorized public repository"
                                         or item.get("repository_url") != OPERATOR_URL):
                raise ValueError("The operator repository arm lost its authority provenance")
            release = item.get("role") == "Published release"
            origin = f"https://api.github.com/repos/{repository}/"
            query = ("releases?per_page=3" if release else
                     f"commits?per_page=1&until={cutoff.isoformat()}T23:59:59Z")
            if item["origin"] != origin + query:
                raise ValueError("Unexpected request identity")
            entry_prefix = f"https://github.com/{repository}/" + ("releases/" if release else "commit/")
            if not item["url"].startswith(entry_prefix):
                raise ValueError("Unexpected publisher record URL")
            if not HEX.fullmatch(item.get("source_response_sha256", "")):
                raise ValueError("Missing response content identity")
            observed = _parse_time(item["retrieved_at"])
            if not began <= observed <= ended:
                raise ValueError("Retrieval time is outside this live invocation")
            event = _parse_time(item["event_at"])
            if event > observed:
                raise ValueError("Publisher event lies after retrieval")
            if release:
                publication = _parse_time(item["published_at"])
                if publication != event:
                    raise ValueError("Release observation lacks its actual publisher timestamp")
            else:
                if item.get("published_at") is not None or event.date() > cutoff:
                    raise ValueError("Earlier commit must precede cutoff; its publication time is unknown")
                if not re.fullmatch(r"[a-f0-9]{40}", item["version"]):
                    raise ValueError("Earlier repository snapshot lacks a commit ID")
            if not isinstance(item["text"], str) or not item["text"].strip():
                raise ValueError("No publisher text observed")
            records.append({"feed": key, "acquisition": item.get("acquisition"), "publisher": item["publisher"], "version": item["version"],
                            "role": "release" if release else "earlier commit", "source": item["url"],
                            "request": item["origin"], "published_at": item.get("published_at"),
                            "event_at": item["event_at"], "retrieved_at": item["retrieved_at"],
                            "source_response_sha256": item["source_response_sha256"],
                            "source_excerpt_sha256": hashlib.sha256(item["text"].encode()).hexdigest(),
                            "source_excerpt_truncated": bool(item.get("excerpt_truncated")),
                            "reported_event_inside_window": cutoff < event.date() <= began.date()})
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(str(exc))
    missing = []
    for key in REGISTERED:
        for role in ("release", "earlier commit"):
            if not any(r["feed"] == key and r["role"] == role for r in records):
                missing.append({"feed": key, "role": role})
    if identity["status"] == "FAIL" or errors:
        status = "FAIL"
    elif identity["status"] != "PASS" or data["failures"] or missing:
        status = "BLOCKED"
    else:
        status = "PASS"
    return {"schema": "ignition-public-source-qualification/2", "status": status,
            "source_identity": identity, "started_at": began.isoformat(), "finished_at": ended.isoformat(),
            "window_start": cutoff.isoformat(), "registered_feeds": FEED_KEYS, "operator_repositories": [OPERATOR_URL],
            "observations": records, "failed_requests": data["failures"], "missing_roles": missing,
            "integrity_errors": errors, "capability_comparison": "unresolved",
            "scope": "Checks dated live publisher observations and an earlier repository pointer for two curated feeds and one operator-specified repository. "
                     "Committer time does not certify public availability. No capability, product, cost, demand "
                     "or historical-impossibility test ran."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", help="Exact source revision from the job event")
    parser.add_argument("--output", required=True, type=Path)
    opts = parser.parse_args()
    identity = source_identity(opts.expected_source)
    began = stamp()
    if identity["status"] == "FAIL":
        data = {"sources": [], "failures": []}
    else:
        data = discover_sources(MISSION, feeds=FEED_KEYS, as_of=began)
    report = qualify(data, began, stamp(), identity)
    opts.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {len(report['observations'])} validated observations, "
          f"{len(report['failed_requests'])} failed requests, {len(report['integrity_errors'])} integrity errors")
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
