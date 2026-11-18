"""Reconstruct the dated public queue exported by the bilingual exhibition."""
from datetime import datetime, timedelta
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PRODUCT = HERE if (HERE / "invention").is_dir() else HERE.parents[1]
sys.path.insert(0, str(PRODUCT))
from invention.evolution.alert import calculate as archive_changes
from invention.early_survey.survey import calculate as early_changes
from invention.early_survey.exposures.verify import calculate as recover_exposures


def project(cohort, as_of):
    return {
        "schema": "frontier.change-desk-case.v1", "cohort": cohort["id"],
        "as_of_utc": as_of, "coverage": cohort["coverage"], "alerts": cohort["alerts"],
    }


def second_archive(snapshot):
    """Preserve the first broker and independently reopen the second at the same instant."""
    if snapshot["cohort"] != "early_warm":
        raise ValueError("Only the matched October notices have a qualified second source")
    cases = recover_exposures(as_of=snapshot["as_of_utc"])["witnesses"]
    alerts = {(a["target_id"], a["band"]): a for a in snapshot["alerts"]}
    visible = []
    for band, extra in sorted(cases.items()):
        alert = alerts[(extra["target_id"], band)]
        if (alert["issued_utc"] != extra["issued_utc"] or alert["deadline_utc"] != extra["deadline_utc"]
                or alert["status"] != extra["fink_status"]
                or any(extra[part]["candid"] != alert[part]["candid"] for part in ("baseline", "trigger"))):
            raise ValueError("Additional witness belongs to a different registered decision")
        if extra["witness"]:
            visible.append({k: extra[k] for k in ("target_id", "band", "source", "status", "witness",
                                                "delta_from_baseline_mag", "formal_error_mag", "aperture", "forced_photometry")})
    acquisition = json.loads((PRODUCT / "invention/early_survey/exposures/sources/index.json").read_bytes())
    return {"broker": "ALeRCE", "survey": "ZTF", "source_url": acquisition["alerce-api"]["url"], "witnesses": visible}


def archive_series():
    series = []
    for calculate in (archive_changes, early_changes):
        for complete in calculate()["cohorts"]:
            days = []
            current = datetime.fromisoformat(complete["start_utc"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(complete["end_utc"].replace("Z", "+00:00"))
            while current <= end:
                as_of = current.isoformat().replace("+00:00", "Z")
                cohort = next(c for c in calculate(as_of=as_of)["cohorts"] if c["id"] == complete["id"])
                days.append(project(cohort, as_of))
                current += timedelta(days=1)
            if days[-1]["alerts"] != complete["alerts"] or days[-1]["coverage"] != complete["coverage"]:
                raise ValueError("The final public checkpoint differs from the source-bound result")
            window = {"id": complete["id"], "start": complete["start_utc"], "end": complete["end_utc"], "days": days}
            if complete["id"] == "early_warm":
                window["second_archive"] = {snap["as_of_utc"]: second_archive(snap) for snap in days}
            series.append(window)
    return series


def check_snapshot(path):
    supplied = json.loads(path.read_bytes())
    name = supplied["cohort"]
    calculate = early_changes if name in {"early_cold", "early_warm"} else archive_changes
    at = supplied["as_of_utc"]
    result = calculate(as_of=at)
    matches = [c for c in result["cohorts"] if c["id"] == name]
    if len(matches) != 1:
        raise ValueError("The downloaded observing cohort is unavailable at that time")
    expected = project(matches[0], at)
    if "second_archive" in supplied:
        if name != "early_warm":
            raise ValueError("The additional source was qualified for the October notices")
        subprocess.run([sys.executable, "-B", str(PRODUCT / "invention/early_survey/exposures/verify.py"), "--check"],
                       check=True, stdout=subprocess.DEVNULL)
        expected["second_archive"] = second_archive(expected)
    # The browser may serialize 32.0 as 32. Treat both as a number while
    # retaining JSON booleans, strings, nulls and complete 19-digit identifiers.
    def structural(value):
        def numeric(raw):
            return ("number", Decimal(raw))
        return json.loads(json.dumps(value, allow_nan=False), parse_float=numeric, parse_int=numeric)
    if structural(supplied) != structural(expected):
        raise ValueError("The downloaded decision differs from the historical prefix")
    verifier = "early.py" if calculate is early_changes else "verify.py"
    with tempfile.TemporaryDirectory() as directory:
        full = Path(directory) / "snapshot.json"
        full.write_text(json.dumps(result, allow_nan=False), encoding="utf-8")
        subprocess.run([sys.executable, "-B", str(PRODUCT / "evolution_trials" / verifier),
                        "--as-of", at, "--check", str(full)], check=True, stdout=subprocess.DEVNULL)
    return {"cohort":name, "as_of_utc":at, "target_bands":len(supplied["coverage"]),
            "issued_alerts":len(supplied["alerts"]), "additional_witnesses":len(supplied.get("second_archive", {}).get("witnesses", []))}
