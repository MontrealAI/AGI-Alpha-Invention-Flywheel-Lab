"""Build a deterministic portable ZIP of exactly the public recipient files."""
import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent
FILES = ("README.md", "REGISTRATION.md", "conventional.py", "package.py", "pairing_lab.py", "pilot.py",
         "project_data.py", "qualify.py", "receipt.json", "repair_experiment.py", "runs.csv",
         "test_pairing_lab.py", "test_pilot.py", "verify_decision.py")


def build(destination):
    with ZipFile(destination, "w") as archive:
        for name in FILES:
            entry = ZipInfo(name, date_time=(2026,11,17,0,0,0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry,(ROOT / name).read_bytes(), compresslevel=9)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("destination", type=Path)
    build(p.parse_args().destination)
