#!/usr/bin/env python3
"""Run all deterministic arms, the independent native-clock audit, and the offline recipient."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
sys.path.insert(0, str(PRODUCT))
from ignition import construction, delivery, development, evaluation
from ignition.controller import Controller
from ignition.store import Store, runtime_source
from conventional import convert
from git_witness import capture
from mission import clock_input, mission

SOURCE_REVISION = "777489f9e09c8d0dd6b12f9d90de6376330577a2"


def require(value, why):
    if not value:
        raise ValueError(why)


def read(name):
    return json.loads((HERE / name).read_bytes())


def native_audit(source, witness):
    require(witness["release_commit"] == source["commit"] == SOURCE_REVISION, "release ancestry mismatch")
    entries = witness["entries"]
    require(len(entries) == len(source["commits"]), "incomplete object population")
    db = sqlite3.connect(":memory:")
    with db:
        for (oid, authored, landed), record in zip(entries, source["commits"]):
            utc = db.execute("SELECT strftime('%Y-%m-%dT%H:%M:%SZ',?,'unixepoch'), "
                             "strftime('%Y-%m-%dT%H:%M:%SZ',?,'unixepoch')", (authored, landed)).fetchone()
            require((oid, *utc) == (record["oid"], record["author"], record["committer"]),
                    "source-clock disagreement on " + oid)
    db.close()
    return len(entries)


def assisted_proposal(definition):
    mapping = read("included_mapping.json")["mapping"]
    return {"kind": "record_migration",
            "program": {"extra_fields": definition["extra_fields"], "input_fields": definition["input_fields"],
                        "columns": [{"source": mapping[t["name"]], "type": t["type"], "target": t["name"]}
                                    for t in definition["targets"]]}}


def controller_run(work, name, base):
    start = time.perf_counter()
    m = copy.deepcopy(base)
    if name == "prior":
        m["resources"] = {}
    elif name == "included":
        m["resources"] = {"direct_method": "model", "execution_strategy": "direct", "max_repairs": 0}
        m["authority"] = {"assisted_model": True}
    ctrl = Controller(Store(work / name), assisted=("included session", "Codex, manually supplied") if name == "included" else None)
    rid, rev = ctrl.create({"request_id": "git-clock-study-" + name, "mission": m})
    state = ctrl.advance(rid, rev)
    if name == "included":
        require(state["status"] == "awaiting_model", "expected a reviewable manual exchange")
        require('"cases"' not in state["handoff"]["prompt"], "confirmation conditions disclosed to constructor")
        response = assisted_proposal(m["construction_spec"]["definition"])
        ctrl.intervene(rid, rev, "respond", {"sha256": state["handoff"]["sha256"], "response": response})
        state = ctrl.advance(rid, rev)
    tests = (state.get("evaluation") or {}).get("cases", ())
    record = {"status": state["status"], "method": state["routing"]["method"],
              "checks": len(tests), "passes": sum(t["candidate_pass"] for t in tests),
              "labels_examined": (state.get("mapping_resolution") or {}).get("labels_examined", []),
              "artifact_sha256": (state.get("artifact") or {}).get("sha256"),
              "obstruction": state.get("error") or state["routing"]["interpretation"]["obstruction"]}
    bundle = ctrl.deliver(rid, rev) if state["status"] == "verified" else None
    elapsed = round(time.perf_counter()-start, 6)
    return state, record, elapsed, bundle


def first_in_source_order(m):
    start = time.perf_counter()
    spec = m["construction_spec"]
    definition = copy.deepcopy(spec["definition"])
    seen = {construction.fingerprint(row) for _, _, row, _ in development.rows(definition)}
    program, reason = development.learn(definition)
    labels = []
    for item in m["resources"]["mapping_evidence"]["records"]:
        if program:
            break
        digest = construction.fingerprint(item["input"])
        if digest in seen:
            continue
        seen.add(digest)
        labels.append(item["id"])
        definition["demonstrations"].append({"input": {"rows": [item["input"]]},
                                            "expected": {"rows": [item["expected"]]}})
        program, reason = development.learn(definition)
    require(program is not None, "ordinary source-order construction deferred: " + str(reason))
    contract = construction.freeze_contract(spec)
    artifact = construction.build(contract, {"kind": spec["kind"], "program": program})
    result = evaluation.evaluate(contract, artifact)
    return {"status": result["status"], "labels_examined": labels,
            "checks": len(result["cases"]), "passes": sum(t["candidate_pass"] for t in result["cases"])}, round(time.perf_counter()-start, 6)


def sql_and_recipient(work, archive, source):
    start = time.perf_counter()
    from mission import ordinary
    sealed = [c for c in source["commits"] if c["oid"][-1] in "0123"]
    rows = [clock_input(r) for r in sealed]
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    expected = [ordinary(db, c) for c in sealed]
    projected = [convert(db, row) for row in rows]
    db.close()
    require(projected == expected, "SQL converted a source record incorrectly")
    body = "".join(json.dumps(row)+"\n" for row in rows)
    wd = work / "recipient"
    wd.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        z.extractall(wd)
    timing = {}
    for name, args in (("standalone_sql", [str(HERE / "conventional.py")]),
                       ("portable_converter", [str(wd / "run.py"), "migrate-jsonl"])):
        started = time.perf_counter()
        order = [sys.executable, "-I", *args]
        run = subprocess.run(order, input=body, text=True, capture_output=True)
        require(run.returncode == 0 and [json.loads(l) for l in run.stdout.splitlines()] == expected, name + " JSONL result")
        for fixture, error in (({k: v for k,v in rows[0].items() if k != "committer_date"}, "missing_field"),
                               ({**rows[0], "committer_hour": False}, "invalid_value"),
                               ({**rows[0], "unknown": 1}, "extra_field")):
            bad = subprocess.run(order, input=json.dumps(fixture)+"\n", text=True, capture_output=True)
            require(bad.returncode == 2 and error in bad.stderr and not bad.stdout, name + " failed to refuse " + error)
        timing[name + "_four_processes_seconds"] = round(time.perf_counter()-started, 6)
    checked = subprocess.run([sys.executable, "-I", str(wd / "run.py"), "verify"], capture_output=True)
    require(checked.returncode == 0, "portable verifier rejected its source or measurements")
    timing["two_routes_and_portable_verification_seconds"] = round(time.perf_counter()-start, 6)
    return {"sealed_records": len(rows), "matched": len(expected), "malformed_cases_refused_each": 3,
            "portable_verifier_exit": checked.returncode}, timing


def verify_recipient_versions(archived, fresh, registered_digest):
    # Authenticate the published executable as a whole before opening or running it.
    require(hashlib.sha256(archived).hexdigest() == registered_digest,
            "published recipient differs from its registered digest")
    with zipfile.ZipFile(io.BytesIO(archived)) as retained, zipfile.ZipFile(io.BytesIO(fresh)) as current:
        require(sorted(retained.namelist()) == sorted(current.namelist()), "published recipient member substitution")
        for member in current.namelist():
            if member == "ignition/construction.py":
                # Current deliveries embed the installed interpreter. The old one is
                # authenticated by the registered archive digest and exercised separately.
                require(current.read(member) == (PRODUCT / member).read_bytes(),
                        "fresh recipient constructor differs from the checkout")
            elif member not in ("receipt.json", "SHA256SUMS.json"):
                require(retained.read(member) == current.read(member), "published recipient mismatch in " + member)


def controls(m):
    definition = m["construction_spec"]["definition"]
    pool = copy.deepcopy(m["resources"]["mapping_evidence"])
    _, good = development.resolve_projections(definition, pool, development.projection_scope(m))
    item, = [r for r in pool["records"] if r["id"] == good["labels_examined"][0]]
    def adjudicate(records, budget, pin=True):
        evidence = {**pool, "records": records, "max_labels": budget}
        if pin:
            evidence["sha256"] = construction.fingerprint({k: evidence[k] for k in ("source","records","decision_sha256")})
        program, receipt = development.resolve_projections(definition, evidence, development.projection_scope(m))
        require(program is None and receipt["obstruction"], "unsupported projection escaped")
        return receipt["obstruction"]
    demo = definition["demonstrations"][0]
    same = {"id": "same-clock-control", "input": demo["input"]["rows"][0], "expected": demo["expected"]["rows"][0]}
    conflict = {**item, "id": "second independent label", "expected": {**item["expected"], "written_date": "contradiction"}}
    unrelated = {**m, "purpose": "Certify contributors' working hours from the two Git clocks."}
    program, refusal = development.resolve_projections(definition, pool, development.projection_scope(unrelated))
    require(program is None and not refusal["labels_examined"], "archive labels escaped their approved purpose")
    return {"unrelated_purpose": refusal["obstruction"], "unchanged_digest_substitution": adjudicate([item], 1, False),
            "uninformative": adjudicate([same], 1), "incompatible_observation": adjudicate([item, conflict], 2),
            "budget_exhausted": adjudicate([item], 0)}


def verify(output=None, receipt_path=None, git_path=None):
    started = time.perf_counter()
    m, sample = mission()
    source = read("source_clocks.json")
    witness = read("native_clocks.json")
    if git_path:
        require(capture(git_path, source)["entries"] == witness["entries"], "native object replay changed")
    native = native_audit(source, witness)
    metrics = {"common_setup_and_source_audit_seconds": round(time.perf_counter()-started, 6)}
    with tempfile.TemporaryDirectory() as tmp:
        wd = Path(tmp)
        prior, old, metrics["prior_controller_seconds"], _ = controller_run(wd, "prior", m)
        require(prior["status"] == "deferred" and "more than 16" in old["obstruction"], "prior route outcome changed")
        active, acquired, metrics["source_controller_and_delivery_seconds"], archive = controller_run(wd, "active", m)
        require(acquired["status"] == "verified" and acquired["passes"] == acquired["checks"], "acquired construction failed")
        _, included, metrics["included_handoff_replay_and_delivery_seconds"], _ = controller_run(wd, "included", m)
        require(included["status"] == "verified", "included mapping failed")
        ordinary, metrics["source_order_construction_and_checks_seconds"] = first_in_source_order(m)
        require(ordinary["status"] == "pass", "ordinary acquisition failed")
        cli, timing = sql_and_recipient(wd, archive, source)
        metrics.update(timing)
        def public_bundle():
            return delivery.export_bundle(active["contract"], active["artifact"], active["evaluation"],
                {"public_registration": "C1, Git release archive UTC cohorts",
                 "mission_source": "https://github.com/git/git", "release_commit": SOURCE_REVISION,
                 "source_projection": active["mapping_resolution"], "native_objects_corroborated": native,
                 "scope": "Public rehearsal with SQL and native Git cross-checks. Operator adoption and bill unknown."})
        fresh_public = public_bundle()
        archived = (HERE / "git-clock-converter.zip").read_bytes()
        verify_recipient_versions(archived, fresh_public, read("results.json")["recipient_sha256"])
        for label, bundle in (("current-public", fresh_public), ("archived", archived)):
            replay_work = wd / label
            replay_work.mkdir()
            sql_and_recipient(replay_work, bundle, source)
        if output:
            output.write_bytes(fresh_public)
    evidence_controls = controls(m)
    from cohort import cohort
    downstream = cohort(source, witness, SOURCE_REVISION, HERE / "git-clock-converter.zip")
    for key in ("recipient_process_unpack_and_projection_seconds", "direct_native_sql_seconds"):
        metrics[key] = downstream.pop(key)
    semantic = {"downstream_release_hour": downstream, "population": sample, "corroborated_native_objects": native, "legacy_bounded_route": old,
                "source_projection": acquired, "included_direct_replay": included,
                "ordinary_source_order": ordinary, "sql_and_recipient": cli, "adverse_acquisition": evidence_controls}
    model_path = HERE / "qwen_record.json"
    model_record = read(model_path.name) if model_path.exists() else None
    if model_record:
        contract = construction.freeze_contract(m["construction_spec"])
        require(model_record["contract_sha256"] == contract["sha256"], "different contract in Qwen trial")
        replay = []
        for step in model_record["proposed"]:
            try:
                proposal = construction.build(contract, step["response"])
                evaluated = evaluation.evaluate(contract, proposal)
                replay.append({"status": evaluated["status"], "checks": len(evaluated["cases"]),
                               "passes": sum(c["candidate_pass"] for c in evaluated["cases"])})
            except construction.ConstructionError as err:
                replay.append({"status": "compile_refusal", "code": err.code})
        if model_record["status"] == "verified":
            require(replay and replay[-1]["status"] == "pass", "live model acceptance cannot be reproduced")
        semantic["recorded_qwen"] = {"status": model_record["status"], "deterministic_proposal_replays": replay,
                                     "observed_total_calls_including_first_timeout": len(model_record["calls"])+len(read("qwen_timeout.json")["calls"])}
    metrics["all_routes_and_comparisons_seconds"] = round(time.perf_counter()-started, 6)
    measured = {"results": semantic, "wall_times": metrics,
                "qualification_runtime_sha256": runtime_source(),
                "recipient_sha256": hashlib.sha256(archived).hexdigest(),
                "fresh_recipient_sha256": hashlib.sha256(fresh_public).hexdigest(),
                "study_code_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob("*.py"))},
                "shared_acquisition": {"http_gets": len(source["exchanges"]),
                    "http_response_bytes": sum(x["response_bytes"] for x in source["exchanges"]),
                    "http_wall_seconds": source["elapsed_seconds"],
                    "original_git_bytes_with_batch_headers": witness["native_object_bytes_read_including_batch_headers"],
                    "native_validation_wall_seconds_excluding_checkout": witness["capture_seconds_excluding_checkout"]},
                "unmeasured_costs": ["archive checkout wall time and transfer",
                    "operator, independent reviewer and implementation labour",
                    "included Codex inference, editing, and interaction cost", "shared CPU allocation, power and supplier bill",
                    "historical construction, ongoing maintenance, delivery support and recipient adoption"],
                "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                "sources_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                   for name in ("REGISTRATION.md","COHORT_REGISTRATION.md","source_clocks.json","native_clocks.json","included_mapping.json")}}
    if receipt_path:
        receipt_path.write_text(json.dumps(measured, indent=2, ensure_ascii=False)+"\n")
    else:
        frozen = HERE / "results.json"
        if frozen.exists():
            recorded = read(frozen.name)
            require(recorded["results"] == semantic and recorded["sources_sha256"] == measured["sources_sha256"]
                    and recorded["recipient_sha256"] == measured["recipient_sha256"], "registered measurement changed")
    return measured


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--recipient", type=Path, help="write the deliverable ZIP")
    ap.add_argument("--receipt", type=Path, help="write a new timing and result observation")
    ap.add_argument("--native-git", type=Path, help="checkout containing the frozen public Git tag and its objects")
    opts = ap.parse_args()
    result = verify(opts.recipient, opts.receipt, opts.native_git)
    print(json.dumps({"source": result["results"]["source_projection"], "SQL": result["results"]["sql_and_recipient"],
                      "object_checks": result["results"]["corroborated_native_objects"]}, ensure_ascii=False))
