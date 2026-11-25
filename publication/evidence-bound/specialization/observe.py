# SPDX-License-Identifier: Apache-2.0
"""Acquire bounded public USGS responses or replay the exact recorded bytes offline."""

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns, process_time_ns, sleep
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

import ordinary
import specialist


ROOT = Path(__file__).resolve().parent
ENDPOINT = "https://earthquake.usgs.gov/fdsnws/event/1/query"
LIMIT = 131072


def epoch_ms(stamp):
    return int(datetime.fromisoformat(stamp).timestamp() * 1000)


def fingerprint(content):
    return sha256(content).hexdigest()


def anchored_urls(window):
    west, east = window["west"], window["east"]
    common = {"format": "geojson", "eventtype": "earthquake", "starttime": window["start"], "endtime": window["end"],
              "minlatitude": window["south"], "maxlatitude": window["north"], "minmagnitude": 4, "orderby": "time-asc"}
    for name, low, high in (("east", west, 180), ("west", -180, east), ("wrapped", west, 360 + east)):
        yield name, ENDPOINT + "?" + urlencode({**common, "minlongitude": low, "maxlongitude": high})


def load(capture, name, url, fetch):
    path = capture / f"{name}.geojson"
    network = {}
    if fetch:
        request = Request(url, headers={"User-Agent": "FRONTIER research catalog comparison",
                                       "Accept": "application/geo+json, application/json"})
        start = perf_counter_ns()
        with urlopen(request, timeout=15) as response:
            if urlsplit(response.url).netloc != "earthquake.usgs.gov" or response.status != 200:
                raise ValueError("Unexpected public catalog response host or HTTP status")
            raw = response.read(LIMIT + 1)
            network = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                       "http_status": response.status, "wall_milliseconds": (perf_counter_ns() - start) / 1e6}
        if len(raw) > LIMIT:
            raise ValueError("Catalog response exceeded registered bytes")
        path.write_bytes(raw)
        sleep(0.35)
    else:
        with path.open("rb") as archived:
            raw = archived.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise ValueError("Archive exceeded registered bytes")

    document = json.loads(raw, parse_float=Decimal)
    features = document["features"]
    if document["type"] != "FeatureCollection" or document["metadata"]["count"] != len(features):
        raise ValueError("Incomplete or unrecognized catalog response")
    records = []
    for feature in features:
        properties = feature["properties"]
        longitude, latitude, _ = feature["geometry"]["coordinates"]
        records.append({"id": feature["id"], "lon": str(longitude), "lat": str(latitude),
                        "mag": None if properties["mag"] is None else str(properties["mag"]),
                        "time_ms": properties["time"], "updated_ms": properties["updated"]})
    return records, {"url": url, "bytes": len(raw), "sha256": fingerprint(raw),
                     "catalog_rows": len(records), "catalog_generation_ms": document["metadata"]["generated"], **network}


def measured(method, case):
    wall, cpu = [], []
    for _ in range(21):
        began, started_cpu = perf_counter_ns(), process_time_ns()
        result = method(case)
        wall.append(perf_counter_ns() - began)
        cpu.append(process_time_ns() - started_cpu)
    return result, {"trials": len(wall), "median_wall_microseconds": median(wall) / 1000,
                    "median_cpu_microseconds": median(cpu) / 1000}


def run(capture, fetch=False):
    registration_bytes = (ROOT / "REGISTRATION.json").read_bytes()
    registration = json.loads(registration_bytes)
    capture.mkdir(parents=True, exist_ok=True)
    panels = {}
    for section in ("development_window", "observed_reuse_window"):
        window = registration[section]
        collected = {}
        provenance = {}
        for region, url in anchored_urls(window):
            collected[region], provenance[region] = load(capture, f"{section}-{region}", url, fetch)
        bounds = {key: window[key] for key in ("west", "east", "south", "north")}
        bounds.update(min_magnitude=str(registration["audit_magnitude_floor"]), start_ms=epoch_ms(window["start"]),
                      end_ms=epoch_ms(window["end"]))
        case = {"bounds": bounds, "records": collected["west"] + collected["east"]}
        direct = {"bounds": bounds, "records": collected["wrapped"]}
        specialized, performance = measured(specialist.audit, case)
        baseline, baseline_performance = measured(ordinary.audit, case)
        wrapped = ordinary.audit(direct)
        panels[section] = {
            "spatial_and_time_bounds": bounds,
            "sources": provenance,
            "audited_selection": specialized,
            "independent_arithmetic_comparator": baseline,
            "wrapped_catalog_comparator": wrapped,
            "exact_id_agreement": specialized == baseline == wrapped,
            "geospatial_case_sha256": fingerprint(json.dumps(case, sort_keys=True, separators=(",", ":")).encode()),
            "specialist_performance": performance,
            "ordinary_sql_performance": baseline_performance,
        }
        (capture / f"{section}.case.json").write_text(json.dumps(case, sort_keys=True, indent=2) + "\n")
    return {"registration_sha256": fingerprint(registration_bytes),
            "algorithm_sha256": fingerprint((ROOT / "specialist.py").read_bytes()),
            "ordinary_sha256": fingerprint((ROOT / "ordinary.py").read_bytes()),
            "runner_sha256": fingerprint(Path(__file__).read_bytes()),
            "acquisition": "live historical data" if fetch else "offline exact archived bytes",
            "matched_windows": sum(panel["exact_id_agreement"] for panel in panels.values()),
            "panels": panels}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, default=ROOT / "samples")
    parser.add_argument("--fetch", action="store_true", help="Perform the registered six exact public requests")
    args = parser.parse_args()
    result = run(args.capture, args.fetch)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    sys_exit = 0 if result["matched_windows"] == 2 else 1
    raise SystemExit(sys_exit)
