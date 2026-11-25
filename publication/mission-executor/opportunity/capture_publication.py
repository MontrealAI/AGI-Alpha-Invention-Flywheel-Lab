#!/usr/bin/env python3
"""Capture approved live Pages and same-revision original evidence."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from time import monotonic
from urllib.request import Request, urlopen


REPO = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
PAGES = f"https://montrealai.github.io/{REPO.split('/')[1]}/frontier-omega-alpha"
RECEIPT = f"{PAGES}/atlas-release.json"
EVIDENCE = {
    "game": {
        "game-receipt.json": "publication/universal/game-theory/MISSION-RECEIPT.json",
        "example-verification.json": "publication/universal/game-theory/EXAMPLE-VERIFICATION.json",
    },
    "opportunity": {
        "radar-control.json": "publication/opportunity/discovery/RADAR-CONTROL.json",
        "hy-mt3.json": "publication/opportunity/discovery/pilot-receipts/hy-mt3.json",
        "hy-mt2.json": "publication/opportunity/discovery/pilot-receipts/hy-mt2.json",
    },
}


def get(url):
    start = monotonic()
    with urlopen(Request(url, headers={"Cache-Control": "no-cache"}), timeout=40) as response:
        if response.geturl() != url or response.status != 200:
            raise ValueError("unexpected publication endpoint")
        body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError("publication body exceeds configured limit")
        header_date = response.headers.get("Date")
    return body, {
        "url": url, "sha256": sha256(body).hexdigest(), "bytes": len(body),
        "date": header_date, "acquired_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(monotonic() - start, 6),
    }


def capture(job, target):
    start = monotonic()
    target.mkdir(parents=True, exist_ok=False)
    manifest, first = get(RECEIPT)
    (target / "release-initial.json").write_bytes(manifest)
    info = json.loads(manifest)
    revision = info["source_commit"]
    if re.fullmatch("[0-9a-f]{40}", revision) is None:
        raise ValueError("release has invalid source identity")
    addresses = {"index.html": PAGES + "/", "fr.html": PAGES + "/fr.html"}
    addresses.update({
        name: f"https://raw.githubusercontent.com/{REPO}/{revision}/{path}"
        for name, path in EVIDENCE[job].items()
    })
    requests = {"release-initial.json": first}
    with ThreadPoolExecutor(max_workers=len(addresses)) as pool:
        queued = {name: pool.submit(get, url) for name, url in addresses.items()}
        for name, future in queued.items():
            raw, requests[name] = future.result()
            if name.endswith(".html"):
                binding = f'data-atlas-digest="{info["ledger_sha256"]}"'.encode()
                if raw.count(binding) != 1:
                    raise ValueError(f"{name} failed to bind the live ledger")
            (target / name).write_bytes(raw)
    last, requests["release-final.json"] = get(RECEIPT)
    (target / "release-final.json").write_bytes(last)
    if manifest != last:
        raise ValueError("publication changed during capture")
    return {
        "schema": "frontier/production-claim-capture-v1", "job": job, "source_commit": revision,
        "workflow_run": info["workflow_run"], "ledger_sha256": info["ledger_sha256"],
        "elapsed_seconds": round(monotonic() - start, 6), "requests": requests,
        "response_bytes": sum(record["bytes"] for record in requests.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", choices=EVIDENCE)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    capture_receipt = capture(args.job, args.directory)
    rendered = json.dumps(capture_receipt, ensure_ascii=False, indent=2) + "\n"
    (args.directory / "capture.json").write_text(rendered, encoding="utf-8")
    print(rendered, end="")
