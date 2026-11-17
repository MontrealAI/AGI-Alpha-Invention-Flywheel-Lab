"""Reproduce the published, licensed measurement projection; no network access."""
import argparse
import csv
import hashlib
import io
from pathlib import Path

SOURCE = "a3fafa234f5498b235de1a7d0c3fbdc6e10c2496465b078f359f1bd1dba595d1"


def project(raw):
    if hashlib.sha256(raw).hexdigest() != SOURCE:
        raise ValueError("source bytes differ from the registered upstream snapshot")
    result = io.StringIO(newline="")
    writer = csv.writer(result, lineterminator="\n")
    writer.writerow(("task", "model", "harness", "solved", "tokens"))
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
        if row["in_grid"] != "1":
            raise ValueError("unexpected out-of-grid measurement")
        writer.writerow([row[key] for key in ("instance", "model", "agent", "solved", "total_tok")])
    return result.getvalue().encode("utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("destination", type=Path)
    opt = parser.parse_args()
    opt.destination.write_bytes(project(opt.upstream.read_bytes()))
