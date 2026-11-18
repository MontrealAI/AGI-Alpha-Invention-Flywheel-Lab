#!/usr/bin/env python3
"""Prepare, adjudicate or reproduce the observing-team shadow trial entirely offline."""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
if __name__ == "__main__":
    sys.path.insert(0, str(PRODUCT))
from action_study.shadow import fieldkit as kit


def clock(call, *args):
    start, cpu = time.perf_counter_ns(), time.process_time_ns()
    result = call(*args)
    return result, {"elapsed_ns": time.perf_counter_ns() - start, "process_cpu_ns": time.process_time_ns() - cpu}


def files_identity():
    paths = ["action_study/shadow/" + n for n in ("REGISTRATION.md", "archive.py", "direct_inputs.py", "fieldkit.py", "shadow.py")]
    paths += ["action_study/desk.py", "action_study/ztf.py", "action_study/pack.py",
              "invention/early_survey/exposures/verify.py", "invention/early_survey/exposures/avro_packet.py",
              "evolution_trials/broker_control.py"]
    return {p: hashlib.sha256((PRODUCT / p).read_bytes()).hexdigest() for p in paths}


def execute_arm(assignments, by_id, function):
    replies = []
    for task in assignments["tasks"]:
        c = by_id[task["case_id"]]
        answer = function(c["band"], c["cutoff_utc"])
        replies.append({"ticket": task["ticket"], "source_set_sha256": task["source_set_sha256"], "answer": answer})
    return {"protocol_sha256": assignments["protocol_sha256"], "responses": replies}


def direct_submission(directory, cases):
    original = kit.load(HERE / "direct" / "answers.json")
    assignment = kit.load(directory / "tasks/D.json")
    kit.check(original["protocol_sha256"] == assignment["protocol_sha256"], "Direct worker used a different protocol")
    idmap = {t["case_id"]: t for t in assignment["tasks"]}
    answers = {}
    out = []
    for r in original["responses"]:
        cid = r["case_id"]
        kit.check(cid in cases and cid not in answers and r["source_set_sha256"] == idmap[cid]["source_set_sha256"],
                  "Direct worker returned a duplicate, foreign or stale case")
        answers[cid] = r["answer"]
        out.append({"ticket": idmap[cid]["ticket"], "source_set_sha256": r["source_set_sha256"], "answer": r["answer"]})
    return {"protocol_sha256": original["protocol_sha256"], "responses": out}, answers


def run_study(directory):
    started = datetime.now(timezone.utc).isoformat()
    from action_study.shadow import archive
    plan, cases = archive.plan_and_cases()
    by_id = {c["case_id"]: c for c in cases}
    directory = Path(directory)
    _, preparation = clock(kit.initialize, directory, plan, cases)
    kit.write(directory / "plan.json", plan)
    kit.write(directory / "cases.json", cases)
    expected, grading = clock(archive.sql_reference, cases)
    decisions = {c["case_id"]: {} for c in cases}
    observed_times = {}
    dbpath = directory / "private.sqlite"
    functions = {"B": archive.conventional, "C": archive.engine, "E": lambda band, cutoff: {"action": "keep_open"}}
    passes = []
    with closing(kit.connect(directory)) as db:
        commitment, key_seal = clock(kit.save_key, db, expected)
        kit.write(directory / "independent-key.json", expected)
        for i, order in enumerate(("BCE", "ECB")):
            run = {}
            for arm in order:
                taskfile = directory / "tasks" / (arm + ".json")
                # Include assignment and result JSON I/O and database delivery in each measured route.
                def take_run():
                    assignments = kit.load(taskfile)
                    batch = execute_arm(assignments, by_id, functions[arm])
                    recipient = directory / (arm + "-responses-" + str(i) + ".json")
                    kit.write(recipient, batch)
                    delivered = kit.load(recipient)
                    kit.submit(db, delivered)
                    for t, a in zip(assignments["tasks"], delivered["responses"]):
                        old = decisions[t["case_id"]].setdefault(arm, a["answer"])
                        kit.check(old == a["answer"], "Route changed its answer on a repeated prefix")
                _, run[arm] = clock(take_run)
            passes.append({"order": list(order), "routes": run})
        if (HERE / "direct" / "answers.json").is_file():
            direct_replies, returned = direct_submission(directory, by_id)
            _, intake = clock(kit.submit, db, direct_replies)
            observed_times["retained_direct_answer_intake_only"] = intake
            for cid, answer in returned.items():
                decisions[cid]["D"] = answer
        batch, close_time = clock(kit.blind, db)
        kit.write(directory / "blind-review.json", batch)
    # Reopen the delivered store so scoring cannot depend on in-memory receipts.
    with closing(kit.connect(directory)) as db:
        results, adjudication = clock(kit.summarize, db)
    kit.write(directory / "scores.json", results)
    observed_times.update(protocol_preparation=preparation, independent_packet_sql=grading, key_seal=key_seal,
                          route_passes=passes, blind_close=close_time, reopened_scoring=adjudication)
    quantity = ("slots", "clusters", "submitted", "missing_submissions", "accepted", "scientifically_correct", "late_submissions", "invalid_decisions", "correct_deliveries",
                "false_priorities", "missed_priorities", "missing_actions_on_deliverable", "unsettled_reference",
                "accepted_with_observed_beneficiary_use", "accepted_cases_unresolved_by_actual_incumbent",
                "availability_to_accepted_decision_seconds")
    arms = {a: {k: results["arms"][a][k] for k in quantity} for a in kit.ARMS}
    compact_cases = []
    for c in cases:
        ref = expected[c["case_id"]]
        compact_cases.append({"case": c["case_id"], "source_set_sha256": c["source_set_sha256"],
                              "expected": ref["action"], "measurement": ref.get("measurement"),
                              "submitted_actions": {arm: ans["action"] for arm, ans in decisions[c["case_id"]].items()}})
    historical = kit.load(archive.BROKER / "BROKER_CONTROL.json")["costs"]["repeatable_live_control"]
    public = {
        "schema": "frontier.shadow-review/1", "mode": "historical_rehearsal",
        "science": {"target": archive.TARGET, "cases": compact_cases, "arms": arms,
                    "protocol_sha256": results["protocol_sha256"], "independent_key_sha256": commitment,
                    "unique_positive_witnesses": len({r["measurement"]["witness"] for r in expected.values() if r.get("measurement")}),
                    "participants": 0, "real_beneficiary_queue_decisions": 0},
        "scope": "Six correlated cutoffs from two known notices on one already known object. Times refer to exposure, not contemporaneous broker delivery.",
        "methods": {"A": "No willing human incumbent or independently observed existing beneficiary workflow enrolled.",
                    "B": "Conventional bounded TAP plus an independent original-packet decoder, eligibility and photometry.",
                    "C": "Integrated Fink and ALeRCE question, scoped receiver and recommendation.",
                    "D": "No independent direct frontier worker assigned to this retrospective queue.",
                    "E": "Recorded inaction: keep the unresolved notice open at every cutoff."},
        "direct_worker": None,
        "independence": "SQL selects and computes from the original packets, using a second Avro decoder. The TAP parser is shared with B and the full Avro decoder with C. All approaches share the same survey observations.",
        "execution": {"started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
                      "python": platform.python_implementation() + " " + platform.python_version(),
                      "network_requests": 0, "original_source_digests": archive.pins(), "source_files": files_identity(),
                      "recorded_clock": observed_times, "database_bytes": dbpath.stat().st_size},
        "cost": {"historical_conventional_acquisition": {k: historical[k] for k in ("requests_count", "response_bytes", "wall_s", "process_cpu_s")},
                 "current_rehearsal": "Two offline passes per executed route on one host. Acquisition was historical. First pass includes route initialization; OS cache may already be warm. Repeated submissions are idempotent and do not increase the case count. Stage timings omit interpreter startup, prior development, cached source acquisition and off-host costs.",
                 "complete_cost_by_arm": {a: results["arms"][a]["costs"]["complete_cost"] for a in kit.ARMS},
                 "per_accepted_useful_decision_by_arm": {a: results["arms"][a]["costs"]["cost_per_accepted_useful_decision"] for a in kit.ARMS},
                 "unknown_terms": list(kit.CATEGORIES) + list(kit.MEASURES),
                 "historical_broker_or_operator_availability": None, "actual_downstream_scientific_value": None},
    }
    if (HERE / "direct" / "receipt.json").is_file():
        receipt = kit.load(HERE / "direct" / "receipt.json")
        for name, expected_hash in receipt["worker_files_sha256"].items():
            kit.check(kit.safe_member(name) and hashlib.sha256((HERE / "direct" / name).read_bytes()).hexdigest() == expected_hash,
                      "Retained direct worker artifact changed")
        public["methods"]["D"] = "Fresh-context included AI with permitted public archive routines; scored from its retained original submission."
        public["direct_worker"] = receipt
    kit.write(directory / "public-result.json", public)
    return public


def public_paths():
    """Fixed public paths. Prospective assignments and receipts have no path into this archive."""
    from action_study import pack
    from action_study.shadow import archive
    paths = set(pack.BASE + pack.ZTF_CODE + pack.ZTF_DATA + pack.AVRO_CODE + pack.AVRO_DATA)
    paths.update("action_study/shadow/" + n for n in (
        "REGISTRATION.md", "README.md", "PUBLIC_RESULT.json", "archive.py", "direct_inputs.py", "fieldkit.py", "shadow.py", "test_shadow.py"))
    paths.update(("invention/early_survey/RESULT.json", "invention/early_survey/exposures/RESULT.json",
                  "invention/early_survey/exposures/test_exposures.py", "invention/early_survey/exposures/ARCHIVE_ACCESS.json",
                  "invention/early_survey/exposures/STREAM_FIRST_REVIEW.md",
                  "evolution_trials/BROKER_CONTROL.json",
                  "evolution_trials/broker_control.py", "evolution_trials/broker_sources/alerce-window.vot"))
    paths.update("evolution_trials/broker_sources/" + cid + ".avro.gz" for pair in archive.ANCHORS.values() for cid in pair)
    paths.update("action_study/shadow/direct/" + n for n in ("answers.json", "worker.json", "review.py", "receipt.json"))
    return tuple(sorted(paths))


def portable(out):
    files = [(p, (PRODUCT / p).read_bytes()) for p in public_paths()]
    with Path(out).open("xb") as dest, zipfile.ZipFile(dest, "w") as z:
        for name, raw in files:
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return {"members": len(files), "bytes": Path(out).stat().st_size,
            "sha256": hashlib.sha256(Path(out).read_bytes()).hexdigest()}


def check_direct(root):
    from action_study.shadow.direct_inputs import build
    packet = Path(root) / "direct-inputs"
    recorded = kit.load(HERE / "direct/receipt.json")
    kit.check(build(packet) == recorded["task_sha256"], "Direct work packet changed")
    worker = packet / "review.py"
    shutil.copyfile(HERE / "direct/review.py", worker)
    replay = subprocess.run([sys.executable, "-B", str(worker)], cwd=packet, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, check=True, timeout=60)
    kit.check(replay.stdout == (HERE / "direct/answers.json").read_bytes(),
              "The independent direct construction did not reproduce its original answers")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("rehearse", help="Run the six archived slots, both computational routes, inaction and independent SQL.")
    p.add_argument("--out", type=Path, required=True, help="New private rehearsal directory")
    p = sub.add_parser("direct-inputs", help="Recreate the original public direct-worker packet without any response or answer key.")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("portable", help="Create a deterministic recipient using only named public source files.")
    p.add_argument("--out", type=Path, required=True)
    sub.add_parser("check", help="Re-run and check the registered scientific endpoint against the recorded result.")
    p = sub.add_parser("prepare", help="Freeze a roster, private assignments and independently randomized review codes.")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--cases", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("bind-sources", help="Hash explicitly selected local files for the authorized cutoff.")
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--file", action="append", required=True)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("verify-sources", help="Check the local files assigned to a prospective case.")
    p.add_argument("--dir", type=Path, required=True)
    p.add_argument("--packet", type=Path, required=True)
    p.add_argument("--case-id", required=True)
    p = sub.add_parser("close-reviews", help="Lock independent reviews and preserve a reason for any missing assessments.")
    p.add_argument("--study", required=True, type=Path)
    p.add_argument("--reason", required=True)
    for command, flag in (("lock-key", "key"), ("submit", "responses"), ("review", "ratings")):
        p = sub.add_parser(command)
        p.add_argument("--study", required=True, type=Path)
        p.add_argument("--" + flag, type=Path, required=True)
    for command in ("blind", "score"):
        p = sub.add_parser(command)
        p.add_argument("--study", required=True, type=Path)
        p.add_argument("--out", type=Path, required=True)
        if command == "score":
            p.add_argument("--costs", type=Path)
    args = parser.parse_args()
    if args.command == "direct-inputs":
        from action_study.shadow.direct_inputs import build
        print(build(args.out))
    elif args.command == "portable":
        print(json.dumps(portable(args.out), sort_keys=True))
    elif args.command == "bind-sources":
        manifest = kit.bind_sources(args.dir, args.file)
        kit.write(args.out, {"source_set_sha256": kit.digest(manifest), "source_manifest": manifest})
    elif args.command == "verify-sources":
        task = next((t for t in kit.load(args.packet)["tasks"] if t["case_id"] == args.case_id), None)
        kit.check(task is not None and task.get("source_manifest"), "Unknown case or missing field source manifest")
        actual = kit.bind_sources(args.dir, task["source_manifest"])
        kit.check(actual == task["source_manifest"] and kit.digest(actual) == task["source_set_sha256"],
                  "The source changed. Obtain a new qualified assignment.")
        print(task["source_set_sha256"])
    elif args.command == "prepare":
        print(kit.initialize(args.out, kit.load(args.plan), kit.load(args.cases)))
    elif args.command == "rehearse":
        print(json.dumps(run_study(args.out)["science"]["arms"], indent=2))
    elif args.command == "check":
        original = kit.load(HERE / "PUBLIC_RESULT.json")
        with tempfile.TemporaryDirectory() as temp:
            observed = run_study(Path(temp) / "study")
            check_direct(temp)
        kit.check(original["science"] == observed["science"], "Frozen scientific or arm result differs")
        kit.check(original["direct_worker"] == observed["direct_worker"], "Recorded direct route differs")
        kit.check(original["execution"]["original_source_digests"] == observed["execution"]["original_source_digests"],
                  "Original packet or TAP identity changed")
        kit.check(original["execution"]["source_files"] == observed["execution"]["source_files"],
                  "Qualification was made with different software. Run qualification again on current source.")
        print("Six frozen cutoffs, five arm denominators and the direct worker's original answers reproduced.")
    else:
        with closing(kit.connect(args.study)) as db:
            if args.command == "lock-key":
                print(kit.save_key(db, kit.load(args.key)))
            elif args.command == "submit":
                kit.submit(db, kit.load(args.responses))
            elif args.command == "close-reviews":
                kit.close_reviews(db, args.reason)
            elif args.command == "review":
                kit.review(db, kit.load(args.ratings))
            elif args.command == "blind":
                kit.write(args.out, kit.blind(db))
            elif args.command == "score":
                kit.write(args.out, kit.summarize(db, kit.load(args.costs) if args.costs else None))


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, ValueError, TypeError) as exc:
        raise SystemExit(f"Shadow study rejected input: {exc}") from exc
