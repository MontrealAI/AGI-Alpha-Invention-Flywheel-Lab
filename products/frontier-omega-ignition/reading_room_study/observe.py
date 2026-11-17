"""Run the registered scorer and attest the complete recipient bytes externally."""
import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("Choose a new observation directory.")
    scorer = Path(__file__).resolve().with_name("run.py")
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, str(scorer), "--output", str(output)], check=False)
    elapsed = time.perf_counter() - start
    r = resource.getrusage(resource.RUSAGE_CHILDREN)
    if proc.returncode or not (output/"RESULTS.json").is_file():
        return proc.returncode or 1
    record = json.loads((output/"RESULTS.json").read_text(encoding="utf-8"))
    record["publication_receipt"] = {
        "recipient_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                             for f in sorted((output/"candidate").glob("*")) if f.is_file()},
        "scoring_wall_seconds": round(elapsed, 6),
        "scoring_cpu_seconds_including_children": round(r.ru_utime + r.ru_stime, 6),
    }
    with (output/"observed.json").open("x", encoding="utf-8") as fh:
        fh.write(json.dumps(record, indent=2, ensure_ascii=False)+"\n")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
