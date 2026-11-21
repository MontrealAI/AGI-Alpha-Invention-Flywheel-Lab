"""Download the three small, pinned public inputs and verify their bytes.

No credentials, model service, or paid API is used. Preserve authorship and the
source repositories' published licenses; see SOURCES.md. These are public
historical measurements, not newly generated measurements.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

COMMIT = "ae3e910dcea27cfd1631a28b793b6c63607baedd"
BASE = f"https://raw.githubusercontent.com/doyle-lab-ucla/bandit-optimization/{COMMIT}/"
FILES = {
    "amidation.csv": ("datasets/amidation.csv", "e77f6a498387888eec63423265d6feb9d8b1ff9299b8afbc3bcc1218a7e5857a"),
    "nib-etoh.csv": ("datasets/nib-etoh.csv", "d5216a673eefbaacc4ae961f4ff6acb73dbc1c83e37d0548fa7eaf84bbe5607c"),
    "nib-meoh.csv": ("datasets/nib-meoh.csv", "be9fccf4c4bee7fa2b868cbbf5e813d2a29765e4ffc1f92c84b450c8381d5f99"),
    "SOURCE-LICENSE.md": ("LICENSE.md", "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"),
    "SOURCE-DATASETS-README.md": ("datasets/README.md", "18db5845ff11b41df232a205534fd5b817f811588db6c09974020dd6b88f5a6b"),
}


def fetch(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for name, (source_path, expected) in FILES.items():
        destination = root / name
        reused = destination.exists()
        if reused:
            data = destination.read_bytes()
        else:
            with urllib.request.urlopen(BASE + source_path, timeout=30) as response:
                data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("source exceeds declared bounded-download size")
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise ValueError(f"source hash mismatch: {name}; existing files are never overwritten")
        if not reused:
            with destination.open("xb") as stream:
                stream.write(data)
        records.append({"file": name, "source_url": BASE + source_path, "sha256": actual,
                        "bytes": len(data), "reused_verified_bytes": reused})
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    args = parser.parse_args()
    print(json.dumps(fetch(args.data_dir), indent=2))

