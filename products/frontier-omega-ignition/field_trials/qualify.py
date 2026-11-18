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
        for folder in ("field_lab", "discovery_field", "invention", "invention/evolution", "invention/early_survey",
                       "invention/early_survey/exposures", "evolution_trials", "numeric_study/peak_context", "successor_field", "field_trials"):
            python("-m", "unittest", "discover", "-s", folder, "-v")
        for folder in ("action_study", "action_study/observing", "action_study/opportunities", "action_study/shadow"):
            python("-m", "unittest", "discover", "-s", folder, "-v")
        for pattern in ("test_evidence_projection.py", "test_evidence_action_mission.py"):
            python("-m", "unittest", "discover", "-s", "tests", "-p", pattern, "-v")
        python("action_study/construction/verify.py", capture=record / "fresh-clock-construction.json")
        python("action_study/construction/cohort.py", capture=record / "release-cohort.json")
        python("action_study/opportunities/verify.py", capture=record / "opportunity-records.json")
        python("action_study/shadow/shadow.py", "check", capture=record / "shadow-rehearsal.json")
        python("-m", "unittest", "discover", "-s", "tests", "-p", "test_followup_mission.py", "-v")
        python("-m", "unittest", "discover", "-s", "tests", "-p", "test_change_mission.py", "-v")
        python("-m", "unittest", "discover", "-s", "endpoint_lab", "-p", "test_rounding_audit.py", "-v")
        python("invention/evolution/alert.py", "--check", capture=record / "november-change-decisions.json")
        python("evolution_trials/verify.py", "--check", "invention/evolution/RESULT.json",
               capture=record / "direct-november-change-decisions.json")
        python("invention/early_survey/survey.py", "--check", capture=record / "october-change-decisions.json")
        python("evolution_trials/early.py", "--check", "invention/early_survey/RESULT.json",
               capture=record / "direct-october-change-decisions.json")
        python("invention/early_survey/exposures/verify.py", "--check", capture=record / "cross-broker-check.json")
        python("evolution_trials/broker_control.py", "--check", capture=record / "conventional-packet-replay.txt")
        recovered = out / "recovered-observations.json"
        python("invention/early_survey/exposures/verify.py", "--out", recovered)
        sys.path.insert(0, str(PRODUCT))
        from ignition.change_recipient import archive_csv
        (out / "recovered-observations.csv").write_bytes(archive_csv(json.loads(recovered.read_bytes())["witnesses"]))
        shutil.copyfile(PRODUCT / "invention/early_survey/worklist.csv", out / "early-candidate-queue.csv")
        python("field_lab/intake_qualification.py", "--check", capture=record / "intake-decisions.json")
        python("numeric_study/peak_context/study.py", capture=record / "peak-table.json")
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
        python("-m", "discovery_field.decision_study.open_decisions", capture=record / "open-opportunity-review.json")
        python("-m", "discovery_field.decision_study.report", capture=record / "source-withdrawal-review.json")
        python("discovery_field/decision_study/calibration_bounds.py", "--check", capture=record / "equal-site-bounds.json")
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
        recipient = temp / "recipient"
        python("-I", recipient / "action_study/observing/desk.py", "--check", cwd=recipient, capture=record / "public-alerts.json")
        python("-I", recipient / "action_study/qualification_choice/verify.py", cwd=recipient, capture=record / "public-engineering.json")
        for profile in ("ztf-persistence", "gw-status", "engineering-qualification"):
            mission = temp / (profile + "-mission.json")
            receipt = out / (profile + ".json")
            tool = recipient / "action_study/desk.py"
            python("-I", tool, "example", profile, cwd=recipient, capture=mission)
            python("-I", tool, "decide", mission, cwd=recipient, capture=receipt)
            python("-I", tool, "verify", receipt, "--mission", mission, cwd=recipient)
        for src, dst in (("qualification_choice/qualification_input.json", "next-engineering-trial.json"),
                         ("construction/git-clock-converter.zip", "git-clock-converter.zip"),
                         ("shadow/PUBLIC_RESULT.json", "shadow-review.json"),
                         ("qualification_choice/economics.json", "engineering-economics.json")):
            shutil.copyfile(PRODUCT / "action_study" / src, out / dst)
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
