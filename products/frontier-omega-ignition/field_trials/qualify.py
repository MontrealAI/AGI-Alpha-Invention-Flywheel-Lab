"""Rebuild the public continuation, its observations and a separate recipient."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from zipfile import ZipFile

PRODUCT = Path(__file__).resolve().parents[1]
ROOT = PRODUCT.parents[1]
DOCS = ROOT / "docs/frontier-omega-ignition/continuation"
SHOW = PRODUCT / "showcase/field_exhibition"


def run(args, *, cwd=PRODUCT, capture=None):
    print("+", " ".join(str(arg) for arg in args), flush=True)
    with (capture.open("wb") if capture else open(os.devnull, "wb")) as log:
        subprocess.run(list(map(str, args)), cwd=cwd, check=True, stdout=log if capture else None)


def python(*args, **kw):
    run([sys.executable, "-B", *args], **kw)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path, help="New public output directory")
    p.add_argument("--browser", action="store_true", help="Also exercise the bilingual exhibit and the private local workbench in Chromium")
    p.add_argument("--expected-head", help="Require a clean, exact Git source revision")
    options = p.parse_args()
    out = options.output.resolve()
    if options.expected_head:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        changes = subprocess.check_output(
            ["git", "status", "--porcelain", "--", str(PRODUCT), str(DOCS),
             "products/alpha-genesis-harness/bridge", "products/alpha-genesis-harness/scripts",
             ".github/workflows/frontier-ignition-field.yml"], cwd=ROOT)
        if head != options.expected_head or changes:
            raise SystemExit("The qualification requires the reviewed Git tree")
    out.mkdir(parents=True)
    start = time.monotonic()
    record = out / "receipts"
    record.mkdir()
    with tempfile.TemporaryDirectory(prefix="ignition-recipient-") as tmp:
        temp = Path(tmp)
        for folder in ("field_lab", "discovery_field", "invention", "successor_field", "field_trials"):
            python("-m", "unittest", "discover", "-s", folder, "-v")
        python("-m", "unittest", "discover", "-s", "tests", "-p", "test_followup_mission.py", "-v")
        python("invention/qualify.py", "--check")
        python("invention/plan.py", "--out", out / "worklist")
        python("invention/photometry.py", "--out", out / "photometry.csv")
        python("invention/next_week/replay.py", capture=record / "temporal-replication.json")
        shutil.copyfile(PRODUCT / "invention/next_week/photometry-120m.csv", out / "photometry-following-week.csv")
        python("field_lab/verify.py", "--public", "field_lab/PUBLIC.json", capture=record / "fixture-replay.json")
        python("field_trials/replay_cpu.py", capture=record / "recorded-cpu-pilot.json")
        python("field_lab/field.py", "fixture", "--output", temp / "http")
        shutil.copyfile(temp / "http/PUBLIC.json", record / "fresh-http.json")
        python("-m", "discovery_field.study", "replay", capture=record / "discovery.json")
        python("-m", "discovery_field.regrade", "--check", capture=record / "discovery-regrade.json")
        python("numeric_study/transient_table/study.py", capture=record / "transient-table.json")
        python("numeric_study/transient_table/nomai.py", capture=record / "historical-classifications.json")
        python("successor_field/observe.py", "--output", temp / "archive")
        shutil.copyfile(PRODUCT / "successor_field/archive-queue.csv", out / "archive-queue.csv")
        page, package = out / "FRONTIER_FIELD.html", out / "FRONTIER_INSTRUMENT.zip"
        python(SHOW / "build.py", "--output", page, "--recipient", package)
        if page.read_bytes() != (DOCS / "FRONTIER_FIELD.html").read_bytes():
            raise ValueError("Generated public exhibition differs from the checked-in one")
        with ZipFile(package) as archive:
            archive.extractall(temp / "recipient")
        python("-I", temp / "recipient/replay.py", cwd=temp / "recipient", capture=record / "recipient.json")
        shutil.copyfile(SHOW / "PRESENT.md", out / "PRESENTER.md")
        if options.browser:
            rebuilt = temp / "recipient-catalog.json"
            python("invention/reference.py", "--out", rebuilt, cwd=temp / "recipient")
            if rebuilt.read_bytes() != (temp / "recipient/invention/catalog.json").read_bytes():
                raise ValueError("The delivered source and ephemeris differ from the registered catalog")
            run(["node", SHOW / "browser.cjs", page, out / "views"], capture=record / "exhibition-browser.json")
            run(["node", PRODUCT / "qa/workbench_browser.cjs"])
    manifest = {p.relative_to(out).as_posix(): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}
    summary = {"schema": "ignition.field-qualification.v1", "verified_head": options.expected_head,
               "bilingual_browser_exercised": options.browser, "wall_seconds": round(time.monotonic()-start, 4),
               "sha256": manifest}
    (out / "qualification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: val for key, val in summary.items() if key != "sha256"}))


if __name__ == "__main__":
    main()
