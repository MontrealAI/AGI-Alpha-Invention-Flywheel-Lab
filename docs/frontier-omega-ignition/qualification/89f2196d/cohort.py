#!/usr/bin/env python3
"""Two remaining original missions, each attempted once on frozen IGNITION 89f2196d.

The original three-mission denominator includes migration (FAIL/deferred in
44155490455), release integrity (must actually construct and verify), and
physical qualification (must explicitly stop/defer without constructing).
A later success cannot replace the failed migration or establish a crossing.
Use separate clean checkouts of the evidence revision and frozen product.
No prompt, mission fixture, evaluation or product code is changed by this study.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unicodedata


FROZEN = "89f2196d552810bc56696a7f380ae66c55f8763a"
ARMS = ("integrity", "unsupported")
REVIEW = Path(__file__).resolve().parents[4]
PRODUCT_ROOT = Path(os.environ.get("IGNITION_PRODUCT_ROOT", REVIEW)).resolve()
PRODUCT = PRODUCT_ROOT / "products/frontier-omega-ignition"
sys.path.insert(0, str(PRODUCT))
import qualify_live as hosted
from ignition import construction, delivery
from ignition.controller import Controller
from ignition.provider import LocalProvider
from ignition.store import Store, digest, runtime_source


def git(directory, *args):
    result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)
    if result.returncode:
        raise hosted.Blocked("Cannot resolve the required Git identity.")
    return result.stdout.strip()


def bind_sources():
    if hosted.checked_source() != FROZEN or git(PRODUCT_ROOT, "rev-parse", "--show-toplevel") != str(PRODUCT_ROOT):
        raise hosted.Blocked("Check out the exact frozen product source.")
    observed = git(REVIEW, "rev-parse", "HEAD")
    expected = os.environ.get("IGNITION_EVIDENCE_SOURCE", observed)
    rel = str(Path(__file__).resolve().relative_to(REVIEW))
    if (expected != observed or git(REVIEW, "rev-parse", "--show-toplevel") != str(REVIEW)
            or git(REVIEW, "status", "--porcelain", "--untracked-files=all", "--", rel)):
        raise hosted.Blocked("Evidence driver differs from its declared checkout.")
    blob = git(REVIEW, "rev-parse", f"HEAD:{rel}")
    if git(REVIEW, "hash-object", str(Path(__file__).resolve())) != blob:
        raise hosted.Blocked("Evidence driver bytes differ from the declared Git blob.")
    return {"product_revision": FROZEN, "evidence_revision":observed, "driver_git_blob":blob,
            "runtime_sha256":runtime_source(), "python":sys.version.split()[0]}


def completed_stages(calls, expected):
    return (len(calls) == len(expected) and {row.get("stage") for row in calls} == set(expected)
            and all(row.get("mode") == "local" and row.get("status") == "completed"
                    and row.get("reported_model") == hosted.MODEL_ALIAS
                    and row.get("application_model_calls") == 1 and row.get("response_sha256")
                    and row.get("response_schema_sha256") for row in calls))


def physical_result(state, calls):
    research = state.get("research") or {}
    passed = (state["status"] == "deferred" and research.get("decision") in {"defer","stop"}
              and all(state.get(key) is None for key in ("contract","artifact","evaluation"))
              and not state.get("unsuccessful_calls") and completed_stages(calls, ("discover","challenge")))
    return "PASS" if passed else "FAIL"


def observed_directory_checks(work, spec):
    """Reproduce exact frozen positive byte observations through the actual folder interface."""
    outputs = []
    for case in spec["cases"]:
        expected = case.get("expected")
        if expected is None:
            continue
        with tempfile.TemporaryDirectory(dir=work) as tmp:
            root = Path(tmp)
            for name, encoded in case["input"]["files"].items():
                construction._logical_path(name)
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(encoded,validate=True))
            process = subprocess.run([sys.executable,"-IB",str(work/"delivery"/"run.py"),
                                      "audit-directory",str(root)], cwd=work, capture_output=True,
                                     stdin=subprocess.DEVNULL,env={"LANG":"C.UTF-8","PATH":os.defpath})
            try:
                result = json.loads(process.stdout)
            except (ValueError, UnicodeError):
                result = None
            accepted = result == expected and process.returncode == (0 if expected["ok"] else 1)
            outputs.append({"fixture_case":case["name"], "exit":process.returncode, "passed":accepted,
                            "expected_sha256":digest(expected), "observed_sha256":digest(result)})
    return outputs


def public_rationale(value, known_urls, known_literals=()):
    """Preregistered public fixtures only. Never echo unfiltered text to logs."""
    row = {"source":"challenge.response.reason","type":"untrusted model explanation",
           "status":"unavailable","full_utf8_sha256":None}
    if not isinstance(value,str) or not value.strip():
        return row
    raw = value.encode("utf-8",errors="surrogatepass")
    row["full_utf8_sha256"] = hashlib.sha256(raw).hexdigest()
    row["status"] = "omitted by public text filter"
    if any(unicodedata.category(c).startswith("C") for c in value):
        return row
    # Replace exact registered public URLs in the screening copy. Any remaining
    # link, email, markup, secret label or token-shaped identifier suppresses the whole field.
    check = value
    for token in re.findall(r"https?://[^\s<>()\[\]]+",value,flags=re.I):
        url = token.rstrip(".,;!?:")
        if url not in known_urls:
            return row
        check = check.replace(token," ")
    for literal in known_literals:
        if re.fullmatch(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+",literal):
            # A public publisher name or registered filename appearing as ordinary prose.
            check = re.sub(r"(?<![\w./@-])"+re.escape(literal)+r"(?![\w/@-]|\.[A-Za-z0-9])",
                           " ",check,flags=re.I)
    forbidden = (r"(?i)(?:[a-z][a-z0-9+.-]{1,15}://|www\.|mailto:|file:|data:|//|@|[<>]|"
                 r"\b(?:api[ _-]?key|password|passphrase|private[ _-]?key|access[ _-]?token|"
                 r"refresh[ _-]?token|secret|bearer|authorization|credentials?|recovery phrase)\b|"
                 r"\b(?:[a-z0-9-]+\.)+[a-z]{2,63}\b|\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b|"
                 r"(?<![a-z0-9])(?:sk[-_]|gh[pousr]_|github_pat_|xox[baprs]-|AKIA|ASIA)|"
                 r"[0-9a-f]{24,}|[A-Za-z0-9_+/=-]{32,})")
    if re.search(forbidden,check):
        return row
    clean = " ".join(value.split())
    row.update(status="included",text=clean[:400],truncated=len(clean)>400)
    return row


def observe(arm, fixture, model, work, public, record):
    # No source retrieval or new permission is granted. Use the original fixture verbatim.
    store = Store(work/"missions")
    controller = Controller(store, provider_factory=lambda: model)
    mission = fixture["mission"]
    run_id, revision = controller.create({"mission":mission,"sources":fixture["sources"],
                                        "request_id":"cohort-"+arm})
    controller.advance(run_id, revision)
    state = store.get(run_id)
    calls = hosted.compact_calls(state)
    research = state.get("research") or {}
    record.update(mission_status=state["status"], stage=state["stage"], calls=calls,
                  mission_input_sha256=state["input_sha256"], diagnostic=hosted.diagnostic(state,calls),
                  reason_sha256=digest(research["decision_reason"]) if research.get("decision_reason") else None,
                  physically_measured=False, artifact_constructed=bool(state.get("artifact")))
    challenge = next((c["response"] for c in state["calls"].values() if c["stage"] == "challenge"),{})
    allowed_urls = {s["url"] for s in fixture["sources"] if isinstance(s.get("url"),str)}
    known_literals = {s["publisher"] for s in fixture["sources"] if isinstance(s.get("publisher"),str)}
    known_literals.update((mission.get("construction_spec") or {}).get("definition",{}).get("manifest",{}))
    record["decision_reason"] = public_rationale(challenge.get("reason"),allowed_urls,known_literals)
    suggested = challenge.get("decision")
    record["challenger_recommendation"] = suggested if suggested in {"build","incumbent","defer","stop"} else None
    record["controller_decision"] = research.get("decision") if research.get("decision") in {"build","incumbent","defer","stop"} else None
    record["tokens"] = {key:sum(r["usage"][key] for r in calls) if calls and
                        all(isinstance(r.get("usage"),dict) and type(r["usage"].get(key)) is int for r in calls)
                        else None for key in ("input_tokens","output_tokens")}
    if arm == "unsupported":
        record["status"] = physical_result(state,calls)
        return
    record["status"] = "FAIL"
    if (state["status"] != "verified" or not completed_stages(calls,("discover","challenge","construct"))
            or state.get("unsuccessful_calls")):
        return
    artifact, contract, assessment = state["artifact"],state["contract"],state["evaluation"]
    original = construction.freeze_contract(mission["construction_spec"])
    if (contract != original or assessment["status"] != "pass" or artifact.get("kind") != "manifest_audit"
            or artifact["program"] != mission["construction_spec"]["definition"]):
        return
    # The public export includes only the original public fixture, the accepted manifest,
    # checked product code, digest-scoped provider metadata and the verification receipt.
    # Private worker state and unconstrained generated prose are excluded.
    safe_context = {"fixture":arm, "fixture_sha256":record["fixture_sha256"],"source":record["sources"],
                    "purpose":mission["purpose"],"execution":"schema-enabled loopback CPU model",
                    "model":hosted.MODEL_ALIAS,"calls":calls,"commercial_validation":"unmeasured"}
    archive = delivery.export_bundle(contract,artifact,assessment,safe_context)
    record["portable"] = hosted.check_portable(archive,work)
    record["folder_checks"] = observed_directory_checks(work,mission["construction_spec"])
    record.update(contract_sha256=contract["sha256"], artifact_sha256=artifact["sha256"],
                  assessment_sha256=digest(assessment), case_count=len(assessment["cases"]),
                  conventional_comparison=assessment["comparison"]["outcome"])
    if (record["portable"]["verified_exit"] == record["portable"]["example_exit"] == 0
            and record["folder_checks"] and all(x["passed"] for x in record["folder_checks"])):
        # Publish the exact archive that just passed both recipient entry points.
        (public/"artifact.zip").write_bytes(archive)
        record.update(status="PASS",published_zip_sha256=hashlib.sha256(archive).hexdigest())


def execute(arm, work, public, record):
    record["sources"] = bind_sources()
    data = (PRODUCT/"examples"/(arm+".json")).read_bytes()
    fixture = json.loads(data)
    record.update(fixture_sha256=hashlib.sha256(data).hexdigest(), started_at=hosted.stamp())
    if fixture["id"] != arm or fixture["mission"]["authority"].get("local_model") is not True:
        raise ValueError("Unregistered or unauthorized fixture.")
    binary, weights = hosted.setup_model(work,record)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port = sock.getsockname()[1]
    threads = hosted.available_threads()
    record.update(threads=threads,model=hosted.MODEL_ALIAS,model_revision=hosted.pinned.MODEL_REVISION)
    command = [str(binary),"-m",str(weights),"--alias",hosted.MODEL_ALIAS,"--host","127.0.0.1",
               "--port",str(port),"--ctx-size","32768","--threads",str(threads),"--threads-batch",str(threads),
               "--parallel","1","--n-gpu-layers","0","--seed","6144","--temp","0"]
    env = {"PATH":os.defpath,"LD_LIBRARY_PATH":str(binary.parent),"HOME":str(work),"LANG":"C.UTF-8",
           "NO_PROXY":"127.0.0.1"}
    with (work/"private-server.log").open("wb") as log:
        process = subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.DEVNULL,
                                   stdout=log,stderr=log)
        try:
            hosted.wait_ready(process,port)
            model = LocalProvider("llama-cpp",hosted.MODEL_ALIAS,port,hosted.pinned.MODEL_SHA,
                                  output_tokens=8192,timeout=600,schema_output=True)
            run_start = time.monotonic()
            observe(arm,fixture,model,work,public,record)
            record["mission_wall_seconds"] = round(time.monotonic()-run_start,6)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    if bind_sources() != record["sources"]:
        raise ValueError("Study source changed during execution.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm",choices=ARMS,required=True)
    parser.add_argument("--work",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    work,public = args.work.resolve(),args.output.resolve()
    if (any(p.exists() or p.is_relative_to(REVIEW) or p.is_relative_to(PRODUCT_ROOT) for p in (work,public))
            or work.is_relative_to(public) or public.is_relative_to(work)):
        parser.error("Choose fresh separate private and public directories outside both checkouts.")
    work.mkdir(mode=0o700,parents=True)
    public.mkdir(mode=0o700,parents=True)
    record = {"protocol":"ignition/original-cohort/1","arm":args.arm,"status":"BLOCKED",
              "original_cohort":["migration","integrity","unsupported"],"earlier_migration_status":"FAIL",
              "earlier_migration_workflow_run":44155490455,"earlier_migration_receipt_artifact":14362922436,
              "commercial_validation":"unmeasured","frontier_crossing":"unproven","usage_cost_complete":False,
              "hosted_run":os.environ.get("GITHUB_RUN_ID"),"hosted_attempt":os.environ.get("GITHUB_RUN_ATTEMPT")}
    start = time.monotonic()
    try:
        execute(args.arm,work,public,record)
    except hosted.Blocked as error:
        record.update(status="BLOCKED",obstruction=str(error))
    except Exception as error:
        record.update(status="FAIL",error_class=type(error).__name__)
    if record["status"] != "PASS" and (public/"artifact.zip").exists():
        # This temporary output was created by this isolated process; failed verification never exports it.
        (public/"artifact.zip").unlink()
        record.pop("published_zip_sha256", None)
    record.update(finished_at=hosted.stamp(), study_wall_seconds=round(time.monotonic()-start,6))
    (public/"receipt.json").write_text(json.dumps(record,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({k:record[k] for k in ("arm","status","mission_status","diagnostic","case_count",
                                           "published_zip_sha256","error_class","obstruction","study_wall_seconds")
                      if k in record}))
    return {"PASS":0,"FAIL":1,"BLOCKED":2}[record["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
