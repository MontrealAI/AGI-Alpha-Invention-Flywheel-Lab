"""Repeat the recorded anonymous read-only queries into a new directory."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from time import monotonic
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent


def fetch(item, folder):
    name, record = item
    start = monotonic()
    try:
        request = Request(record["url"], headers={"User-Agent": "MONTREAL.AI-IGNITION-archive-study/1.0"})
        with urlopen(request, timeout=90) as response:
            data = response.read()
            status = response.status
        with (folder/(name + ".gz")).open("xb") as dest:
            dest.write(gzip.compress(data, mtime=0))
        result = {"http_status": status, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        result["same_as_frozen"] = result["sha256"] == record["sha256"]
    except (OSError, HTTPError) as exc:
        result = {"error": str(exc), "http_status": getattr(exc, "code", None)}
    return {"query": name, "observed_utc": datetime.now(timezone.utc).isoformat(), "url": record["url"],
            "wall_seconds": round(monotonic()-start, 4), **result}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("output", type=Path, help="new directory for new source bytes; keep private until rights are checked")
    args = ap.parse_args()
    raw = (HERE/"sources/index.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != "797dc2172e9b4b67732d57c0f0db27434f3f41cbe1af84dfc94f97fb3f64c1a2":
        ap.error("query manifest differs from registered public sources")
    args.output.mkdir()
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda item: fetch(item, args.output), json.loads(raw).items()))
    (args.output/"receipt.json").write_text(json.dumps(records, indent=2) + "\n")
    print(json.dumps({"queries": len(records), "failed": sum("error" in item for item in records),
                      "matching_frozen": sum(item.get("same_as_frozen", False) for item in records)}))
