# SPDX-License-Identifier: Apache-2.0
"""Ordinary exact controls, separate from model-authored calculations."""

from fractions import Fraction
from hashlib import sha256
import re


def balance(data):
    volume_scale = {"mL": Fraction(1, 1000), "dL": Fraction(1, 10), "L": Fraction(1)}
    content_scale = {"mg/L": Fraction(1), "g/L": Fraction(1000), "ug/mL": Fraction(1)}
    volumes = [
        row["volume"] * volume_scale[row["volume_unit"]]
        for row in data["batches"]
    ]
    mass = sum(
        v * row["concentration"] * content_scale[row["concentration_unit"]]
        for v, row in zip(volumes, data["batches"], strict=True)
    )
    volume = sum(volumes)
    if volume <= 0:
        raise ValueError("The measured total volume must be positive.")
    return {
        "blend_concentration": str(mass / volume),
        "solute_mass": str(mass),
        "blend_volume": str(volume),
    }


def ledger_ratio(data):
    latest = {}
    for row in data["ledger"]:
        prior = latest.get(row["lane"])
        if prior is None or prior["revision"] < row["revision"]:
            latest[row["lane"]] = row
        elif prior["revision"] == row["revision"]:
            raise ValueError("Duplicate evidence revision for a lane.")
    live = [row for row in latest.values() if row["state"] == "active"]
    accepted = sum(row["accepted"] for row in live)
    attempts = sum(row["attempts"] for row in live)
    if attempts <= 0 or not 0 <= accepted <= attempts:
        raise ValueError("Incompatible ledger counts.")
    return {
        "acceptance_ratio": str(Fraction(accepted, attempts)),
        "accepted_total": str(accepted),
        "attempt_total": str(attempts),
    }


def observation_rate(data):
    rows = data["logs"]
    missing = sorted(
        f'{row["session"]}.{field}'
        for row in rows for field in ("litres", "minutes") if row[field] is None
    )
    if missing:
        return {"decision": "ABSTAIN", "missing": missing}
    litres = sum(row["litres"] for row in rows)
    minutes = sum(row["minutes"] for row in rows)
    if minutes <= 0:
        raise ValueError("The elapsed times must sum to a positive observation window.")
    return {"flow_rate": str(Fraction(litres, minutes))}


def header_revision(raw):
    text = raw.decode("utf-8")
    version = []
    for name in ("MAJOR", "MINOR", "MICRO"):
        field = re.search(rf"^#define +PY_{name}_VERSION\s+(\d+)\s*$", text, re.MULTILINE)
        if field is None:
            raise ValueError(f"Missing CPython header field {name}.")
        version.append(int(field[1]))
    return {"sha256": sha256(raw).hexdigest(), "version": version}


def select_header(case, fetched):
    revisions = {key:header_revision(fetched[key]) for key in case["sources"]}
    eligible = [
        (row["version"],key)
        for key, row in revisions.items()
        if row["version"][:2] == [3,12] and row["version"][2] >= 10
    ]
    if eligible:
        return {"decision": "USE", "revision": max(eligible)[1], "headers": revisions}
    return {"decision": "ABSTAIN", "headers": revisions}


ORACLES = {"balance": balance, "ledger_ratio": ledger_ratio, "observation_rate": observation_rate}
