"""Registered epochs and byte identities for the two public IERS bulletins."""
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EPOCH = date(1858, 11, 17)
DATES = tuple(date(2026, 8, 1) + timedelta(days=n) for n in range(34)) + (date(2026, 10, 2),)
ISSUES = {"forecast": "bulletina-xxxix-031", "reference": "bulletinb-464"}
SELECTION = frozenset(DATES)
FIELDS = ("utc_date", "mjd", "forecast_s", "final_ms", "sigma_ms", "final_minus_forecast_ms", "action", "reason",
          "forecast_issue", "reference_issue", "tolerance_ms")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked_facts(name, kind):
    path = HERE / "facts" / f"{name}.{kind}"
    data = path.read_bytes()
    manifest = json.loads((HERE / "SOURCES.json").read_text())
    if sha(data) != manifest["projections"][path.name]["sha256"]:
        raise ValueError(f"Factual projection changed: {path.name}")
    return data.decode("utf-8")
