"""Recheck a supplied publisher response; no network access or publisher page retained."""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from . import protocol


def check(key, path):
    record = protocol.sources()[key]
    if path.stat().st_size > 4_000_000:
        raise ValueError("This registered acquisition used at most four million bytes")
    raw = path.read_bytes()
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8"))).split())
    exact = protocol.digest(raw) == record["source_response_sha256"]
    fragments = all(f in text for f in record["fragments"])
    return {"source": key, "observed_response_sha256": protocol.digest(raw), "exact_observed_response": exact,
            "all_observed_fragments_present": fragments, "registered_response_accepted": exact and fragments}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=tuple(protocol.sources()))
    parser.add_argument("response", type=Path)
    args = parser.parse_args()
    result = check(args.source, args.response)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["registered_response_accepted"] else 1)
