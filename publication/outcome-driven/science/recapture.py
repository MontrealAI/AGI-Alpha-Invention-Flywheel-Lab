#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reissue the exact public queries used by the two April timing checks."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
HOSTS = {"ssd.jpl.nasa.gov", "asassn-lb01.ifa.hawaii.edu", "asassn-data01.ifa.hawaii.edu", "asassn-data02.ifa.hawaii.edu"}
ASASSN_SEQUENCE = (
    "asassn-v2-target", "asassn-v2-photometry", "asassn-v2-master", "asassn-v2-master-photometry",
    "asassn-v2-alternate-photometry", "asassn-v2-control-target", "asassn-v2-control-photometry",
)


def acquire(directory, name, source):
    url, payload = source["url"], source.get("payload")
    if urlsplit(url).hostname not in HOSTS:
        raise ValueError("Unregistered public source host")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    request = Request(url, data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    with urlopen(request, timeout=25) as response:
        if response.status != 200 or urlsplit(response.url).hostname not in HOSTS:
            raise ValueError("Unadmitted archive response")
        data = response.read(4_000_001)
        if not 0 < len(data) <= 4_000_000:
            raise ValueError("Unadmitted archive body length")
        receipt = {"url": url, "payload": payload, "utc": datetime.now(timezone.utc).isoformat(), "status": response.status,
                   "bytes": len(data), "sha256": sha256(data).hexdigest(), "original_sha256": source["sha256"]}
    (directory / f"{name}.raw").write_bytes(data)
    (directory / f"{name}-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="New output directory")
    parser.add_argument("--include-skypatrol", action="store_true", help="Also request the public photometry transport controls")
    args = parser.parse_args()
    args.directory.mkdir()
    clock = json.loads((HERE / "APRIL-CLOCK-RESULT.json").read_bytes())
    for name, source in clock["jpl_receipts"].items():
        acquire(args.directory, name, source)
    if args.include_skypatrol:
        photometry = json.loads((HERE / "ASASSN-RESULT.json").read_bytes())
        for name in ASASSN_SEQUENCE:
            acquire(args.directory, name, photometry["request_receipts"][name])
        control = photometry["transport_control_registration"]
        (args.directory / "ASASSN-TRANSPORT-CONTROL.json").write_text(json.dumps(control, indent=2) + "\n")
