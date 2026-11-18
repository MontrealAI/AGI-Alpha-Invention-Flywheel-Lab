"""Check every recorded production-window output against a separate NumPy implementation.

Run `python3 -IB check_window_oracle.py run` after the acquisition and receiver test.
The result is written to stdout. No CT samples or normalized arrays are saved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalize(raw):
    voxels = np.frombuffer(raw, dtype=np.uint8).astype(np.float64)
    low, high = np.percentile(voxels, [1, 99], method="linear")
    clipped = np.clip(voxels, low, high)
    center = np.median(clipped)
    mad = np.median(np.abs(clipped - center))
    # The published CPU reference uses the unclipped population deviation as
    # its first fallback. The range is taken after percentile clipping.
    scales = (1.4826 * mad, np.std(voxels), (high - low) / 2)
    scale = next((x for x in scales if x >= 1e-6), 1.0)
    return np.asarray((clipped - center) / scale, dtype="<f4").tobytes()


def check(run, *, population_sample=False):
    start = time.monotonic()
    cpu_start = time.process_time()
    size = 24 if population_sample else 6
    result_file = "sample_receipt.json" if population_sample else "window_result.json"
    names = ["window_selection.json", "window_inputs.json", result_file]
    files = {name: (run / name).read_bytes() for name in names}
    selection, inputs, receipt = [json.loads(files[name]) for name in names]
    cases = selection["registered_windows"]
    results = receipt["tests"]
    if [len(cases), len(inputs["tiles"]), len(results)] != [size] * 3:
        raise ValueError("The registered window cohort is incomplete")
    rows = []
    for case, source, observed in zip(cases, inputs["tiles"], results, strict=True):
        if any(source[k] != case[k] or observed[k] != case[k] for k in ("ordinal", "x", "y")):
            raise ValueError("The scheduled windows and observed windows differ")
        raw = (run / "research_data" / f"{case['y']}_{case['x']}.raw").read_bytes()
        if sha(raw) != source["sha256"] or sha(raw) != observed["source_sha256"] or len(raw) != 17 * 384**2:
            raise ValueError("The independent oracle requires the recorded input bytes")
        normalized = normalize(raw)
        checksum = sha(normalized)
        if checksum != observed["recipient_output_sha256"]:
            raise ValueError(f"The receiver differs from the NumPy oracle at index {case['ordinal']}")
        rows.append({**case, "voxels": len(raw), "float32_output_bytes": len(normalized), "output_sha256": checksum})
    return {"inputs_sha256": {name: sha(data) for name, data in files.items()},
            "verified_outputs": rows, "normalized_bytes_checked": sum(row["float32_output_bytes"] for row in rows),
            "python": sys.version.split()[0], "numpy": np.__version__, "elapsed_seconds": time.monotonic() - start,
            "cpu_seconds": time.process_time() - cpu_start,
            "peak_rss_platform_units": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "receipt_scope": f"Mathematical output hashes for {size} recorded windows. Timings cover this check only."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directory with the selection, input, receiver manifests and research_data")
    parser.add_argument("--population-sample", action="store_true", help="check the registered 24-window sample")
    args = parser.parse_args()
    print(json.dumps(check(args.run, population_sample=args.population_sample), sort_keys=True, indent=2))
