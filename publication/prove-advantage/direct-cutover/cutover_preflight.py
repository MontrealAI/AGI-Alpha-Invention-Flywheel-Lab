"""Determine whether a specific public MODIS/VIIRS overlap experiment can run."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
from time import perf_counter, process_time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


ORNL = "https://modis.ornl.gov/rst/api/v1/"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
SITES = {
    "morgan-arboretum": ("45.432139", "-73.950000"),
    "mont-saint-bruno": ("45.550000", "-73.316667"),
}
PRODUCTS = ("MOD09A1", "VNP09H1", "VJ209H1")
YEARS = (2024, 2025)
REFLECTANCE_BANDS = {
    "MOD09A1": ("sur_refl_b01", "sur_refl_b02", "sur_refl_state_500m", "sur_refl_qc_500m"),
    "VNP09H1": ("SurfReflect_I1", "SurfReflect_I2", "SurfReflect_State_500m", "SurfReflect_QC_500m"),
}
MAX_RESPONSE = 256 * 1024


class StopRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, method="GET", byte_range=None):
    opener = build_opener(StopRedirect())
    summary = {"url": url, "method": method}
    started = perf_counter()
    try:
        headers = {"Accept": "application/json"}
        if byte_range:
            headers["Range"] = byte_range
        with opener.open(Request(url, method=method, headers=headers), timeout=35) as response:
            body = response.read(MAX_RESPONSE + 1)
            if len(body) > MAX_RESPONSE:
                raise ValueError("response exceeds the scoped acquisition")
            summary.update(status=response.status, bytes=len(body), sha256=sha256(body).hexdigest())
    except HTTPError as error:
        with error:
            body = error.read(min(MAX_RESPONSE, 1024))
        location = error.headers.get("Location")
        summary.update(status=error.code, bytes=len(body), sha256=sha256(body).hexdigest())
        if location:
            target = urlsplit(location)
            summary["redirect_origin"] = f"{target.scheme}://{target.netloc}" if target.netloc else None
            summary["redirect_path"] = target.path
        if error.code == 400:
            summary["detail"] = body.decode(errors="replace").strip()[:500]
    except (URLError, TimeoutError, ValueError) as error:
        body = b""
        summary.update(status=None, bytes=0, error=type(error).__name__)
    summary["elapsed_s"] = round(perf_counter() - started, 4)
    return summary, body


def json_or_none(summary, body):
    if summary["status"] != 200:
        return None
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def acquisition(point, product):
    coords = {"latitude": point[0], "longitude": point[1]}
    summary, body = request(ORNL + product + "/dates?" + urlencode(coords))
    response = json_or_none(summary, body)
    days = {}
    if isinstance(response, dict):
        days = {item["modis_date"]: item["calendar_date"] for item in response["dates"]}
    return summary, days


def specified_starts(year):
    return [f"A{year}{day:03d}" for day in range(145, 274, 8)]


def pixel_sample(point, product, day, calendar):
    query = urlencode({
        "latitude": point[0], "longitude": point[1], "startDate": day, "endDate": day,
        "kmAboveBelow": 0, "kmLeftRight": 0,
    })
    summary, body = request(ORNL + product + "/subset?" + query)
    response = json_or_none(summary, body)
    if not isinstance(response, dict):
        return summary, None
    if (response.get("nrows"), response.get("ncols")) != (1, 1):
        raise ValueError("unexpected pixel footprint")
    if (float(response["latitude"]), float(response["longitude"])) != tuple(map(float, point)):
        raise ValueError("unexpected requested site")
    bands = {}
    for row in response["subset"]:
        if row["band"] not in REFLECTANCE_BANDS[product]:
            continue
        if row["modis_date"] != day or row["calendar_date"] != calendar or len(row["data"]) != 1:
            raise ValueError("unexpected pixel time or shape")
        detail = (row["data"][0], row["tile"], row["proc_date"])
        if row["band"] in bands and bands[row["band"]] != detail:
            raise ValueError("conflicting pixel")
        bands[row["band"]] = detail
    if bands.keys() != set(REFLECTANCE_BANDS[product]):
        raise ValueError("missing required bands")
    red, nir, state, quality = (bands[key][0] for key in REFLECTANCE_BANDS[product])
    valid = all(isinstance(x, int) for x in (red, nir, state, quality))
    valid = valid and 0 < red <= 16000 and 0 < nir <= 16000 and 0 <= state < 65535 and quality >= 0
    valid = valid and (state & 3) == 0 and ((state >> 3) & 7) == 1 and (state & 0xB704) == 0
    if product == "MOD09A1":
        valid = valid and (quality & 0x3FF) == 0 and bool(quality & (1 << 30))
    else:
        valid = valid and (quality & 0xFFF) == 0 and bool(quality & (1 << 12))
    return summary, {"day": day, "calendar": calendar, "bands": bands,
                     "grid": [response[key] for key in ("xllcorner", "yllcorner", "cellsize")],
                     "strict_qa_eligible": valid, "ndvi_if_eligible": (nir - red) / (nir + red) if valid else None}


def successor_access(point):
    query = urlencode({
        "short_name": "VJ209H1", "page_size": 1, "point": f"{point[1]},{point[0]}",
        "temporal": "2026-09-01T00:00:00Z,2026-09-10T00:00:00Z",
    })
    source, body = request(CMR + "?" + query)
    response = json_or_none(source, body)
    entries = response["feed"]["entry"] if isinstance(response, dict) else []
    if len(entries) != 1:
        return {"catalog": source, "granule": None, "delivery": None}
    item = entries[0]
    name = item["title"]
    archive = next(
        link["href"] for link in item["links"]
        if link["href"].startswith(
            "https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/VJ209H1.002/")
        and link["href"].endswith(".h5")
    )
    delivery, _ = request(archive, "HEAD")
    pixel_data, _ = request(archive, byte_range="bytes=0-63")
    return {"catalog": source, "granule": name, "concept": item.get("collection_concept_id"),
            "delivery": delivery, "ranged_get": pixel_data,
            "method_scope": "anonymous archive HEAD and bounded GET; no login or credential use"}


def audit():
    since = datetime.now(timezone.utc).isoformat()
    wall, cpu = perf_counter(), process_time()
    with ThreadPoolExecutor(max_workers=3) as workers:
        futures = {(site, product): workers.submit(acquisition, point, product)
                   for site, point in SITES.items() for product in PRODUCTS}
        successors = {site: workers.submit(successor_access, point) for site, point in SITES.items()}
        sites = {}
        for site, point in SITES.items():
            source = {product: futures[(site, product)].result() for product in PRODUCTS}
            matches = {}
            samples = {}
            for year in YEARS:
                candidates = specified_starts(year)
                terra_days = source["MOD09A1"][1]
                suomi_days = source["VNP09H1"][1]
                common = [item for item in candidates if item in terra_days and terra_days[item] == suomi_days.get(item)]
                matches[str(year)] = {"requested": len(candidates),
                                      "terra_available": sum(item in terra_days for item in candidates),
                                      "suomi_available": sum(item in suomi_days for item in candidates),
                                      "common_windows": common}
                if common and not samples:
                    for product in REFLECTANCE_BANDS:
                        samples[product] = pixel_sample(point, product, common[0], terra_days[common[0]])
            held = matches["2025"]
            sites[site] = {
                "point": point, "dates": matches, "sample": samples,
                "date_endpoints": {product: {"receipt": r, "records": len(days),
                                                "last": max(days.values(), default=None)}
                                   for product, (r, days) in source.items()},
                "noaa21": successors[site].result(),
                "suomi_decision": "ABSTAIN_INSUFFICIENT_OVERLAP" if len(held["common_windows"]) < 12
                                  else "PROCEED_TO_FULL_QA_AND_CALIBRATION",
                "noaa21_decision": "ABSTAIN_UNOBSERVED_PIXEL_DATA",
            }
    return {"ambition": "CAPTURE THE EXPONENTIAL", "started_utc": since, "elapsed_s": round(perf_counter() - wall, 4),
            "process_cpu_s": round(process_time() - cpu, 4), "python": platform.python_version(),
            "pilot_replacement": False, "observed_new_paid_inference_calls": 0,
            "scope": "eligibility preflight; no completed calibration, post-cutover deployment, or economic result",
            "sites": sites}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(), indent=2, sort_keys=True) + "\n")
