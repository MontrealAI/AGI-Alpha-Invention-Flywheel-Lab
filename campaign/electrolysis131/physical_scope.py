"""Source-pinned, non-safety physical-domain audit for Electrolysis131.

No model fitting, procurement bidding, financial account or device actuation.
Original physical observations are downloaded transiently from one frozen public
commit, pinned by Git blob IDs. Only compact non-personal statistics are emitted.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.request import Request, urlopen

UPSTREAM = "HydrogenDude/ERCOT_Electrolyzer_Sim_Engine"
COMMIT = "a534d8a89cf5e662f183d91a9b40b7936387c4a2"
PINS = {
    "data/experiment/timestamp.txt": "7aed2b14ad8e0b6c73051290b51654e13b0306c3",
    "data/experiment/power_command.txt": "124bbe0a34ba11e87493c2da252490905e7897c5",
    "data/experiment/stack_power.txt": "8e95d6f8c21c3672b301f6156372722e8a7c982a",
    "data/experiment/smps_power.txt": "9a4b59d3288398a6982ffa12c7a0265bee52bc99",
    "data/experiment/chiller_power.txt": "5ace0651239536a785a391ded179d59f71c999e8",
    "data/experiment/subsystem_power.txt": "efac091237fc7320ba9ba7034ec739a9e6a114af",
    "data/experiment/hydrogen_flow.txt": "4b8b9e4c0852faf2b7a313144d89e00ec9bf6c23",
    "data/experiment/hydrogen_flow_cs.txt": "8883060f0c48fea734367f7deed9f36d2d832f36",
    "src/matlab/models/define_electrolyzer_system.m": "9bb57547794f04fbf5de5175109782814a946e5b",
}
MAX_BYTES = 2_000_000
TIMESTAMP_FORMAT = "%d-%b-%Y %H:%M:%S"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\\0" + data).hexdigest()


def verify_source(path: str, data: bytes) -> dict:
    if path not in PINS or len(data) > MAX_BYTES:
        raise ValueError("UNREGISTERED_OR_OVERSIZE_UPSTREAM")
    if git_blob_sha(data) != PINS[path]:
        raise ValueError("PINNED_UPSTREAM_BLOB_CHANGED")
    return {"git_blob_sha1": PINS[path], "raw_sha256": hashlib.sha256(data).hexdigest(),
            "byte_count": len(data)}


def download_one(path: str) -> bytes:
    if path not in PINS:
        raise ValueError("UNREGISTERED_UPSTREAM")
    url = f"https://raw.githubusercontent.com/{UPSTREAM}/{COMMIT}/{path}"
    request = Request(url, headers={"User-Agent": "agi-alpha-electrolysis131-source-pin/1"})
    with urlopen(request, timeout=40) as response:  # no retries, bounded bytes
        data = response.read(MAX_BYTES + 1)
    verify_source(path, data)
    return data


def parse_float_lines(raw: bytes) -> list[float]:
    try:
        lines = raw.decode("utf-8").splitlines()
        if not lines or any(not line.strip() for line in lines):
            raise ValueError("MISSING_NUMERIC_ROW")
        result = [float(x.strip()) for x in lines]
        if not all(math.isfinite(x) for x in result):
            raise ValueError("NONFINITE_MEASUREMENT")
        return result
    except UnicodeError as exc:
        raise ValueError("INVALID_UTF8_MEASUREMENT") from exc


def read_times(raw: bytes) -> list[datetime]:
    try:
        times = [datetime.strptime(x.strip(), TIMESTAMP_FORMAT)
                 for x in raw.decode("utf-8").splitlines()]
    except (UnicodeError, ValueError) as exc:
        raise ValueError("INVALID_TIMESTAMP") from exc
    if len(times) < 30 or any(b-a != timedelta(seconds=1) for a,b in zip(times,times[1:])):
        raise ValueError("MISSING_OR_DUPLICATED_SECOND")
    return times


def parse_model_bound(source: bytes) -> dict:
    try:
        s = source.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("INVALID_MODEL") from exc
    # Contractually inspect exact source statements, never infer a value from title.
    pattern = lambda field: rf"stack\\.{field}\\s*=\\s*([0-9]+(?:\\.[0-9]+)?)\\s*;"
    matches = [re.search(pattern(name), s) for name in
               ("P_rated_kW", "P_max_kW", "turndown_ratio")]
    if any(m is None for m in matches) or not all(token in s for token in
              ("P = max(P, 0);", "P = min(P, stack.P_max_kW);",
               "stack.P_min_kW       = stack.P_max_kW * stack.turndown_ratio;")):
        raise ValueError("UNSUPPORTED_MODEL_OR_BOUND")
    rated, maximum, ratio = (float(m.group(1)) for m in matches)
    if not (rated > 0 and 0 < maximum <= rated and 0 < ratio < 1):
        raise ValueError("INVALID_PHYSICAL_BOUNDS")
    return {"rated_kW": rated, "declared_model_max_kW": maximum,
            "declared_model_min_turndown_kW": maximum * ratio,
            "source_model_is_clipped_at_max": True}


def summarize(inputs: dict[str, bytes]) -> dict:
    if set(inputs) != set(PINS):
        raise ValueError("COMPLETE_REGISTERED_SOURCE_REQUIRED")
    identity = {name: verify_source(name, raw) for name, raw in sorted(inputs.items())}
    model = parse_model_bound(inputs["src/matlab/models/define_electrolyzer_system.m"])
    times = read_times(inputs["data/experiment/timestamp.txt"])
    columns = {}
    for path, raw in inputs.items():
        if path.endswith(".txt") and "timestamp" not in path:
            values = parse_float_lines(raw)
            if len(values) != len(times):
                raise ValueError("UNALIGNED_MEASUREMENTS")
            columns[Path(path).stem] = values
    p = columns["stack_power"]
    flow = columns["hydrogen_flow"]
    cap = model["declared_model_max_kW"]
    lower = model["declared_model_min_turndown_kW"]
    n = len(p)
    count = lambda predicate: sum(bool(predicate(power, flow[i])) for i, power in enumerate(p))
    counts = {
        "above_declared_model_Pmax": count(lambda x,y: x > cap),
        "positive_below_declared_turndown": count(lambda x,y: 0 < x < lower),
        "in_declared_positive_model_range": count(lambda x,y: lower <= x <= cap),
        "recorded_flow_positive_when_stack_power_zero": count(lambda x,y: x == 0 and y > 0),
        "recorded_flow_zero_when_stack_power_positive": count(lambda x,y: x > 0 and y == 0),
        "recorded_positive_flow_above_model_Pmax": count(lambda x,y: x > cap and y > 0),
    }
    return {
        "schema": "agi-alpha/electrolysis131-physical-scope/v1",
        "source_commit": COMMIT, "source": f"https://github.com/{UPSTREAM}",
        "doi": "10.5061/dryad.8931zcs64",
        "input_identities": identity, "model": model,
        "measured_seconds": n, "first_local_recorded_timestamp": times[0].isoformat(),
        "last_local_recorded_timestamp": times[-1].isoformat(),
        "measurement_ranges": {
            "stack_power_kW": {"min": min(p), "max": max(p)},
            "recorded_hydrogen_flow": {"min": min(flow), "max": max(flow),
                                      "original_units_require_source_contract": True},
        },
        "counts": counts,
        "shares_of_all_rows": {k: v/n for k,v in counts.items()},
        "decision": "NO_MODEL_FITTING_OR_SAFETY_CLAIM",
        "new_independent_observation_constructed": False,
        "offline_test_inference": None, "buyer_evidence": None,
        "native_t365_profit": None, "actual_host_cost_usd": None,
        "scope": ("One published physical PEM run; declared source-simulation cap is not a "
                  "certified hardware cap, and instantaneous power/flow mismatch is not "
                  "diagnosed as a fault. No cross-plant/AEM validation or device action."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    data = {path: download_one(path) for path in PINS}  # exactly once per file
    result = summarize(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("CREATE_ONLY_OUTPUT")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\\n")
    print(json.dumps({"status": "PHYSICAL_SCOPE_ONLY", "rows": result["measured_seconds"],
                      "counts": result["counts"], "source_commit": COMMIT}, sort_keys=True))


if __name__ == "__main__":
    main()
