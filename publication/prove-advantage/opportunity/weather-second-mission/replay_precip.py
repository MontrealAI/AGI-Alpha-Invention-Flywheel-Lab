#!/usr/bin/env python3
"""Replay the registered seven-day precipitation comparison from public sources."""

from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
import math
from pathlib import Path
import struct
import subprocess
from time import perf_counter
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
REGISTRATION_SHA256 = "6d32eb5d173c189571605c42658fc2b2d5cbed8829d712bcd347ed6f0b1c5f11"
MIB = 1 << 20
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
QUARTER = timedelta(minutes=15)
LST = timezone(timedelta(hours=-5))
FETCH = []


def fetch(url, limit):
    start = perf_counter()
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; public research verification)"})
    with urlopen(request, timeout=24) as response:
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError(f"Source exceeded the registered download limit: {url}")
        FETCH.append({"url": response.url, "status": response.status, "bytes": len(raw),
                      "sha256": sha256(raw).hexdigest(), "elapsed_seconds": round(perf_counter() - start, 4),
                      "last_modified_http": response.headers.get("Last-Modified")})
    return raw


def unpack_zstd(raw, expected_bytes):
    with subprocess.Popen(["zstd", "-dq", "--stdout"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as proc:
        # A temporary file for input would inflate retained bytes. Feed and drain
        # concurrently, while stopping a decompressed object at its expected size.
        from threading import Thread

        def feed():
            try:
                proc.stdin.write(raw)
            except BrokenPipeError:
                pass
            finally:
                proc.stdin.close()

        feeder = Thread(target=feed)
        feeder.start()
        data = proc.stdout.read(expected_bytes + 1)
        if len(data) != expected_bytes:
            proc.kill()
        status = proc.wait()
        feeder.join()
    if status or len(data) != expected_bytes:
        raise ValueError("Decoded Zarr chunk size or format differs from the source metadata")
    return data


def scalar_array(base, key, dtype, cells):
    decompressed_bytes = struct.calcsize(dtype) * cells
    return [item[0] for item in struct.iter_unpack(dtype, unpack_zstd(fetch(base + key, 1 * MIB), decompressed_bytes))]


def estimate_pardig(reg, days):
    source = reg["primary"]
    base = source["base"]
    raw_metadata = fetch(base + "zarr.json", 64 << 10)
    if sha256(raw_metadata).hexdigest() != source["metadata_sha256"]:
        raise ValueError("Archive metadata no longer matches the registered bytes")
    metadata = json.loads(raw_metadata)
    arrays = metadata["consolidated_metadata"]["metadata"]
    rates = arrays["precipitation"]
    if (metadata["zarr_format"], rates["data_type"], rates["dimension_names"], rates["attributes"]["units"],
        rates["attributes"]["step_type"]) != (3, "float32", ["time", "latitude", "longitude"], "m h**-1", "instant"):
        raise ValueError("Unexpected forecast metadata or unit; accumulation withheld")
    time_count, lat_count, lon_count = rates["shape"]
    if rates["chunk_grid"]["configuration"]["chunk_shape"] != [time_count, 5, 5]:
        raise ValueError("The registered tile layout is no longer available")
    latitude = scalar_array(base, "latitude/c/0", "<d", lat_count)
    longitude = scalar_array(base, "longitude/c/0", "<d", lon_count)
    station_lon, station_lat = reg["reference"]["coordinates_lon_lat"]
    i = min(range(lat_count), key=lambda j: abs(latitude[j] - station_lat))
    j = min(range(lon_count), key=lambda k: abs(longitude[k] - station_lon % 360))
    if max(abs(latitude[i] - station_lat), abs(longitude[j] - station_lon % 360)) > 0.05 + 1e-8:
        raise ValueError("No registered nearest cell covers the target")
    time_meta = arrays["time"]
    time_tile_len = time_meta["chunk_grid"]["configuration"]["chunk_shape"][0]
    if time_meta["attributes"]["units"] != "minutes since 2016-01-01 07:45:00":
        raise ValueError("Unexpected coordinate time origin")
    origin = datetime(2016, 1, 1, 7, 45, tzinfo=timezone.utc)
    start_index = (days[0] - origin) // QUARTER
    end_index = ((days[-1] + DAY) - origin) // QUARTER
    if not 0 <= start_index <= end_index < time_count or start_index // time_tile_len != end_index // time_tile_len:
        raise ValueError("Date range is outside the single registered time-coordinate tile")
    time_index = start_index // time_tile_len
    minutes = scalar_array(base, f"time/c/{time_index}", "<q", time_tile_len)
    tile_label = f"precipitation/c/0/{i // 5}/{j // 5}"
    tile = unpack_zstd(fetch(base + tile_label, 8 * MIB), time_count * 5 * 5 * 4)
    point_offset = (i % 5) * 5 + (j % 5)
    results = []
    for day in days:
        offset = (day - origin) // QUARTER
        xs = []
        for step in range(97):
            index = offset + step
            if origin + timedelta(minutes=minutes[index % time_tile_len]) != day + step * QUARTER:
                raise ValueError("Time coordinate does not match the registered sampling grid")
            xs.append(struct.unpack_from("<f", tile, 4 * (25 * index + point_offset))[0])
        if any(not math.isfinite(v) or v < 0 for v in xs):
            results.append({"state": "ABSTAIN", "reason": "missing, negative or nonfinite rate"})
            continue
        left = 250 * math.fsum(xs[:-1])
        right = 250 * math.fsum(xs[1:])
        results.append({"state": "complete", "n": len(xs), "estimate_mm": (left + right) / 2,
                        "left_mm": left, "right_mm": right})
    return results, {"latitude": latitude[i], "longitude_0_360": longitude[j], "tile": tile_label,
                     "decoded_bytes": len(tile)}


def observe(reg, station, days):
    raw = fetch(reg["gauge_data"].format(station_id=station["station_id"]), 256 << 10)
    rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    required = {"Date/Time (LST)", "Climate ID", "Station Name", "Precip. Amount (mm)", "Precip. Amount Flag"}
    if not required.issubset(rows.fieldnames or []):
        raise ValueError("Publisher did not provide the required hourly precipitation columns")
    values = {}
    duplicates = set()
    for row in rows:
        if row["Climate ID"] != station["climate_identifier"] or (row["Station Name"] or "").strip() != station["name"]:
            raise ValueError("CSV station identity differs from the registered station")
        stamp = row["Date/Time (LST)"]
        if not stamp:
            raise ValueError("CSV row has no identifiable time")
        instant = datetime.strptime(stamp, "%Y-%m-%d %H:%M").replace(tzinfo=LST).astimezone(timezone.utc)
        if instant in values:
            duplicates.add(instant)
        raw_flag = row["Precip. Amount Flag"]
        amount = row["Precip. Amount (mm)"]
        if raw_flag is None or amount is None:
            values[instant] = (None, "incomplete hourly CSV row")
            continue
        raw_flag = raw_flag.strip()
        amount = amount.strip()
        if raw_flag:
            values[instant] = (None, f"precipitation flag {raw_flag}")
        elif not amount:
            values[instant] = (None, "empty amount")
        else:
            value = float(amount)
            values[instant] = (value, "") if math.isfinite(value) and value >= 0 else (None, "invalid amount")
    results = []
    for day in days:
        slots = [day + n * HOUR for n in range(1, 25)]
        failures = Counter(reason for _, reason in (values.get(t, (None, "missing hour")) for t in slots) if reason)
        failures.update("duplicated timestamp" for instant in slots if instant in duplicates)
        if failures:
            results.append({"state": "ABSTAIN", "reasons": dict(failures)})
        else:
            results.append({"state": "complete", "n": 24, "total_mm": round(math.fsum(values[t][0] for t in slots), 8)})
    return results


def scoped_run(operation, days):
    try:
        return operation(), None
    except (OSError, ValueError, KeyError) as error:
        return [{"state": "ABSTAIN", "reason": str(error)} for _ in days], str(error)


def score(rows):
    common = [r for r in rows if all(r[key]["state"] == "complete" for key in ("reference", "ordinary", "pardig"))]
    if not common:
        return {"common_days": 0, "decision": "ABSTAIN", "reason": "No same-window common complete days"}
    ref = [r["reference"]["total_mm"] for r in common]
    ordinary = [r["ordinary"]["total_mm"] for r in common]
    candidate = [r["pardig"]["estimate_mm"] for r in common]
    left = [r["pardig"]["left_mm"] for r in common]
    right = [r["pardig"]["right_mm"] for r in common]

    def mae(xs):
        return math.fsum(abs(a-b) for a, b in zip(xs, ref)) / len(ref)

    def classified(xs):
        return sum((a >= 1) == (b >= 1) for a, b in zip(xs, ref))

    mae_ordinary = mae(ordinary)
    mae_pardig = mae(candidate)
    ordinary_class = classified(ordinary)
    pardig_class = classified(candidate)
    sufficient_days = len(common) >= 4 and any(t >= 1 for t in ref) and any(t < 1 for t in ref)
    passes = sufficient_days and mae_ordinary - mae_pardig >= 0.2 and pardig_class >= ordinary_class
    robust = max(mae(left), mae(right)) < mae_ordinary
    return {"common_days": len(common), "mae_mm": {"pardig": mae_pardig, "ordinary": mae_ordinary},
            "threshold_correct_days": {"pardig": pardig_class, "ordinary": ordinary_class},
            "held_reference_wet_days_at_1mm": sum(t >= 1 for t in ref),
            "pardig_sensitivity_mae_mm": {"left": mae(left), "right": mae(right)},
            "decision": "ADVANCE_TO_ANOTHER_RETROSPECTIVE_TRIAL" if passes and robust else "NO_GO_COMPARATIVE_ADVANCEMENT",
            "sufficient_nontrivial_coverage": sufficient_days}


def main():
    started = perf_counter()
    registered = (ROOT / "REGISTRATION.json").read_bytes()
    if sha256(registered).hexdigest() != REGISTRATION_SHA256:
        raise ValueError("Registration changed")
    reg = json.loads(registered)
    start = datetime.fromisoformat(reg["window"]["start_utc_inclusive"])
    end = datetime.fromisoformat(reg["window"]["end_utc_exclusive"])
    days = [start + n * DAY for n in range((end - start).days)]
    candidate, candidate_error = scoped_run(lambda: estimate_pardig(reg, days), days)
    if candidate_error is None:
        candidate, tile = candidate
    else:
        tile = None
    ordinary, ordinary_error = scoped_run(lambda: observe(reg, reg["ordinary_alternative"], days), days)
    reference, reference_error = scoped_run(lambda: observe(reg, reg["reference"], days), days)
    rows = [{"day_starts_utc": day.isoformat(), "pardig": p, "ordinary": o, "reference": r}
            for day, p, o, r in zip(days, candidate, ordinary, reference)]
    final = {"registration_sha256": REGISTRATION_SHA256,
             "replay_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
             "recorded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "candidate_tile": tile, "fetches": FETCH, "daily_outcomes": rows,
             "source_errors": {"pardig": candidate_error, "ordinary": ordinary_error, "reference": reference_error},
             "comparison": score(rows), "prospective_verdict": "ABSTAIN_NO_FIRST_SEEN_RECORDS",
             "elapsed_seconds": round(perf_counter() - started, 4)}
    output = ROOT / "RECEIPT.json"
    with output.open("x") as f:
        json.dump(final, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(json.dumps(final["comparison"]), flush=True)


if __name__ == "__main__":
    main()
