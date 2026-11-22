"""Inspect one frozen development cell; do not fit models or read held-out cells."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import platform
import time
import urllib.request

SOURCE_COMMIT = "754304f6191b06a78a762636f211e98fcf3dc305"
SOURCE_PATH = "Microsoft/manufacturer1-endt44198-2024/timeseries/processed/Microsoft__manufacturer1-endt44198-2024-A0067__202603_1000x1C-35degC.bdf.csv"
URL = f"https://media.githubusercontent.com/media/battery-data-alliance/bdf-datastore/{SOURCE_COMMIT}/{SOURCE_PATH}"
EXPECTED_BYTES = 8346123
EXPECTED_SHA256 = "2f9b6c457da76b95b4780c703f90280210f57b818ac677ff0c9ff4968bba49c3"


def inspect_csv(data: bytes) -> dict:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    fields = reader.fieldnames
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("Missing or duplicate CSV fields")
    stats = {name: {"numeric": 0, "missing": 0, "nonnumeric": 0,
                    "minimum": None, "maximum": None} for name in fields}
    samples = []
    rows = 0
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Ragged CSV")
        rows += 1
        if len(samples) < 2:
            samples.append(row)
        for name, value in row.items():
            stat = stats[name]
            if value.strip() == "":
                stat["missing"] += 1
                continue
            try:
                number = float(value)
            except ValueError:
                stat["nonnumeric"] += 1
                continue
            if not math.isfinite(number):
                raise ValueError(f"Nonfinite numeric value in {name}")
            stat["numeric"] += 1
            stat["minimum"] = number if stat["minimum"] is None else min(number, stat["minimum"])
            stat["maximum"] = number if stat["maximum"] is None else max(number, stat["maximum"])
    if not rows:
        raise ValueError("Empty CSV")
    return {"rows": rows, "fields": fields, "column_stats": stats,
            "first_two_development_rows": samples}


def main() -> None:
    started = time.perf_counter()
    with urllib.request.urlopen(URL, timeout=120) as response:
        data = response.read(EXPECTED_BYTES + 1)
    actual_sha256 = hashlib.sha256(data).hexdigest()
    if len(data) != EXPECTED_BYTES or actual_sha256 != EXPECTED_SHA256:
        raise ValueError(f"Source mismatch: bytes={len(data)}, sha256={actual_sha256}")
    report = {"kind": "actual_physical_lab_development_data_inspection",
              "source_url": URL, "source_commit": SOURCE_COMMIT,
              "source_bytes": len(data), "source_sha256": actual_sha256,
              "license": "CDLA-Permissive-2.0", "development_cell": "A0067",
              "held_out_cells_read": 0, "models_fitted": 0,
              "python": platform.python_version(), **inspect_csv(data)}
    report["wall_seconds"] = time.perf_counter() - started
    print("BATTERY_PHYSICAL100_PROBE=" + json.dumps(report, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
