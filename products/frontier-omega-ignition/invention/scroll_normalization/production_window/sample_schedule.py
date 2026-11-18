"""Run the frozen out-of-sample study of the same PHerc0139 reader schedule."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import monotonic, process_time

import acquire_windows
import bench_recipient

SEED = "AGI-Alpha:bd0ddc3dddb643856edcb8aa81cfb978713cc73a:PHerc0139:population:v1"
RECIPIENT = "03f8dbea716abd7108a03b2c947b21a13eb36617750c601733b85ae3b04de7e3"


def select(layout, previous):
    if len(layout) != 2122 or len(set(previous)) != 6:
        raise ValueError("The population differs from the registered schedule")
    unseen = set(range(len(layout))) - set(previous)
    def rank(i):
        return sha256(f"{SEED}:{i}".encode("ascii")).digest(), i
    return sorted(sorted(unseen, key=rank)[:24])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path)
    p.add_argument("directory", type=Path, help="new research directory for local scan bytes and receipts")
    args = p.parse_args()
    archive, output = args.archive.resolve(), args.directory.resolve()
    if sha256(archive.read_bytes()).hexdigest() != RECIPIENT:
        raise ValueError("The supplied recipient differs from the frozen comparator package")
    if output.exists():
        raise ValueError("Use a new directory to preserve earlier attempts")
    start, cpu = monotonic(), process_time()
    acquire_windows.run(output, select=select, byte_budget=175_000_000)
    trial = bench_recipient.trial(archive, output)
    trial["scope"] = "Twenty-four distinct uniformly hash-ranked windows from the 2,116 previously unsampled positions on one published schedule. CPU component times only."
    acquire_windows.write(output / "sample_receipt.json", trial)
    rows = trial["tests"]
    conventional = sum(r["median_cpu_ms"]["incumbent"] for r in rows)
    candidate = sum(r["median_cpu_ms"]["candidate"] for r in rows)
    result = {"registered_sample": 24, "tested": len(rows), "zero_mad_windows": sum(r["mad"] == 0 for r in rows),
              "nonconstant_zero_mad_windows": sum(r["mad"] == 0 and r["nonzero_voxels"] > 0 for r in rows),
              "incumbent_sum_window_medians_ms": conventional, "candidate_sum_window_medians_ms": candidate,
              "ratio_of_sums": conventional / candidate, "median_window_ratio": median(r["incumbent_over_candidate"] for r in rows),
              "bytes": json.loads((output / "window_inputs.json").read_text())["bytes_received"],
              "elapsed_seconds": monotonic()-start, "parent_process_cpu_seconds": process_time()-cpu,
              "recipient_sha256": RECIPIENT, "source": acquire_windows.SPONSOR + acquire_windows.STORE}
    acquire_windows.write(output / "sample_summary.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
