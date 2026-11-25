#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify what the bounded Sky Patrol acquisition can support."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
import math
from pathlib import Path

import pyarrow
from pyarrow import parquet


TARGET = 652835415411
CHECK_TARGET = 8590141875
CURVES = ("asassn-v2-photometry", "asassn-v2-master-photometry", "asassn-v2-alternate-photometry")


def admissible_input(directory, stem):
    raw = (directory / f"{stem}.raw").read_bytes()
    receipt = json.loads((directory / f"{stem}-receipt.json").read_bytes())
    if receipt["status"] != 200 or not 0 < len(raw) == receipt["bytes"] <= 4_000_000 or sha256(raw).hexdigest() != receipt["sha256"]:
        raise ValueError(f"Unbound response bytes for {stem}")
    return parquet.ParquetFile(BytesIO(raw))


def parse(directory):
    receipts = {path.name.removesuffix("-receipt.json"): json.loads(path.read_bytes())
                for path in sorted(directory.glob("asassn-*-receipt.json"))}
    basic = admissible_input(directory, "asassn-v2-target").read().to_pylist()
    master = admissible_input(directory, "asassn-v2-master").read().to_pylist()
    if len(basic) != 1 or len(master) != 1 or basic[0]["tic_id"] != 55652896:
        raise ValueError("TOI-216 target identity failed")
    if basic[0]["asas_sn_id"] != TARGET or master[0]["asas_sn_id"] != TARGET:
        raise ValueError("Sources disagree on TOI-216 Sky Patrol identity")
    delta_dec = basic[0]["dec_deg"] + 63.260063
    delta_ra = (basic[0]["ra_deg"] - 73.980231) * math.cos(math.radians(-63.260063))
    target_separation_arcsec = 3600 * math.hypot(delta_ra, delta_dec)
    if target_separation_arcsec > 2.0:
        raise ValueError("Catalog counterpart does not match registered coordinates")
    blocks = {label: admissible_input(directory, label).metadata.num_rows for label in CURVES}
    positive = admissible_input(directory, "asassn-v2-control-photometry").read(columns=["asas_sn_id", "jd"]).to_pylist()
    all_valid = all(row["asas_sn_id"] == CHECK_TARGET and math.isfinite(row["jd"]) for row in positive)
    if not positive or not all_valid:
        raise ValueError("Upstream documented example did not produce dated control rows")
    empty = not any(blocks.values())
    return {
        "schema": "frontier/toi216-asassn-physical-admission-v1", "pyarrow": pyarrow.__version__,
        "target_id": {"TIC": 55652896, "asas_sn_id": TARGET, "separation_arcsec": target_separation_arcsec},
        "target_rows_by_block": blocks,
        "positive_transport_control": {"asas_sn_id": CHECK_TARGET, "finite_dated_rows": len(positive), "same_telescope_api": True,
                                       "does_not_establish_coverage_for_toi216": True},
        "same_target_and_month_positive_control": False,
        "april_attribution": "ABSTAIN", "physical_confirmation": False,
        "observation_admission": "EMPTY_TARGET_PRODUCTS" if empty else "AWAIT_REGISTERED_COVERAGE_CHECK",
        "scope": "Bounded public data acquisition. Archive absence of returned photometry does not establish absence of exposures.",
        "transport_control_registration": json.loads((directory / "ASASSN-TRANSPORT-CONTROL.json").read_bytes()),
        "request_receipts": receipts,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(parse(args.directory), indent=2,sort_keys=True))
