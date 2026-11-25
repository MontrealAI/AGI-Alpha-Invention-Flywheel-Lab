# SPDX-License-Identifier: Apache-2.0
"""Summarize observed arms without converting unfinished runs to completions."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest()


def canonical_digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return sha256(raw).hexdigest()


def transport_observation(directory, *, finished):
    records = []
    for request_path in sorted(directory.glob("dispatch-*-request.json")):
        request = read(request_path)
        base = request_path.name.removesuffix("-request.json")
        receipt_path = directory / f"{base}-receipt.json"
        response_path = directory / f"{base}-response.json"
        if request["canonical_body_sha256"] != canonical_digest(request["body"]):
            raise ValueError("An observed request body changed.")
        if "Independent exact study reference" in json.dumps(request["body"], ensure_ascii=False):
            raise ValueError("The evaluator-only reference entered a constructor request.")
        info = {"request_sha256": fingerprint(request_path), "status": "PENDING"}
        if receipt_path.exists():
            receipt = read(receipt_path)
            if receipt["request_sha256"] != request["transport_body_sha256"]:
                raise ValueError("A transport receipt no longer matches its request.")
            info.update(receipt_sha256=fingerprint(receipt_path), elapsed_seconds=receipt["transport_seconds"])
            if "error" in receipt:
                info.update(status="TRANSPORT_ERROR", error=receipt["error"])
            else:
                response = read(response_path)
                if canonical_digest(response) != receipt["payload_sha256"]:
                    raise ValueError("An observed model response changed.")
                info.update(status="REPLY", response_sha256=fingerprint(response_path),
                            finish_reason=receipt["finish_reason"], model_fingerprint=receipt["provider_fingerprint"],
                            reported_usage=receipt["provider_usage"])
        elif finished:
            raise ValueError("A completed experiment is missing a transport receipt.")
        records.append(info)
    return records


def summarize(study, study_digest, conventional, phases):
    registered = study["cohort"]["ordered_cases"]
    arms = {name: {} for name in study["arms"]}
    inputs = []
    current = read(conventional / "report.json")
    if set(current["cases"]) != set(registered) or current["independent_reference_sha256"] != study["independent_reference_source_sha256"]:
        raise ValueError("The ordinary exact control does not match the registration.")
    for c, values in current["cases"].items():
        arms["conventional"][c] = {"case":c,"arm":"conventional","observed_provider_dispatches":0,
            "precise_missing_cell":values["primary"].get("decision") == "ABSTAIN",
            "reusable_on_withheld":"fresh_reuse" in values, **values}
    recognized = set()
    for directory in phases:
        installation = read(directory / "installation.json")
        phase = installation["phase"]
        if (phase in recognized or installation["case_registration_sha256"] != study_digest
                or installation["order"] != study["execution_order"][phase]):
            raise ValueError("An observed arm does not match its registered phase.")
        recognized.add(phase)
        inputs.append({"phase":phase,"source_revision":installation["source_revision"],"source_sha256":installation["source_sha256"],
                       "runner_sha256":installation["runner_sha256"],"runtime_config_sha256":installation["config_sha256"],
                       "model":installation["model"],"installation_sha256":fingerprint(directory / "installation.json")})
        for ident, arm in installation["order"]:
            case_dir = directory / f"{ident}-{arm}"
            path = case_dir / "result.json"
            if not path.exists():
                if case_dir.is_dir():
                    dispatches = transport_observation(case_dir, finished=False)
                    arms[arm][ident] = {"case":ident,"arm":arm,"verdict":"INTERRUPTED",
                        "observed_provider_dispatches":len(dispatches),"transport_observations":dispatches,
                        "reason":"A declared case started but has no completed result receipt."}
                continue
            record = read(path)
            if record["case"] != ident or record["arm"] != arm:
                raise ValueError("A receipt migrated between experimental cells.")
            dispatches = transport_observation(case_dir, finished=True)
            observed = record["observed_provider_dispatches"]
            if observed != len(dispatches):
                raise ValueError("An observed provider-call denominator changed.")
            replay = {"case_result_sha256":fingerprint(path)}
            constructions = []
            for name in ("executed-archive.json","direct-tool-journal.json"):
                if (case_dir / name).is_file():
                    replay[name] = fingerprint(case_dir / name)
            if "executed-archive.json" in replay:
                archive = read(case_dir / "executed-archive.json")
                if record["archive_sha256"] != archive["sha256"]:
                    raise ValueError("A native observation changed archives.")
                for event in archive["state"]["events"]:
                    if event["kind"] == "tool_completed" and event["detail"]["tool"] == "construct_table":
                        outcome = event["detail"]["outcome"]
                        constructions.append(outcome)
            arms[arm][ident] = {**record,"observed_file_sha256":replay,"transport_observations":dispatches,
                              "completed_native_constructions":constructions}
    if len({x["runtime_config_sha256"] for x in inputs}) > 1 or len({x["model"] for x in inputs}) > 1:
        raise ValueError("Matched phases used different model or runtime parameters.")
    counts = {}
    for arm, cases in arms.items():
        values = list(cases.values())
        dispatch_statuses = [item["status"] for cell in values for item in cell.get("transport_observations",[])]
        counts[arm] = {"registered":len(registered),"observed":len(values),
            "without_observation":[c for c in registered if c not in cases],
            "strict_acceptances":sum(x["verdict"] == "ACCEPT" for x in values),
            "numerical_acceptances":sum(x["verdict"] == "ACCEPT" and x.get("reusable_on_withheld") is True
                                        for x in values),
            "interrupted":sum(x["verdict"] == "INTERRUPTED" for x in values),
            "false_user_facing_acceptances":sum(x.get("false_user_facing_acceptance") is True for x in values),
            "raw_work_contradictions":sum(x.get("raw_explicit_contradiction") is True for x in values),
            "false_verified_projection_acceptances":(
                sum(x.get("false_user_facing_acceptance") is True for x in values) if arm in {"assembly", "both"} else None),
            "actual_provider_dispatches":sum(x["observed_provider_dispatches"] for x in values),
            "returned_provider_replies":dispatch_statuses.count("REPLY"),
            "transport_errors":dispatch_statuses.count("TRANSPORT_ERROR"),
            "pending_provider_dispatches":dispatch_statuses.count("PENDING"),
            "observed_tool_actions":sum(x.get("action_attempts",0) for x in values),
            "successful_tool_events":sum(x.get("actual_tool_events",0) for x in values),
            "completed_native_constructions":sum(len(x.get("completed_native_constructions",[])) for x in values),
            "exact_primary_tool_runs":sum(run.get("primary_exact") is True for x in values for run in x.get("approved_runs",[])),
            "verified_native_claims":sum(claim["status"] == "VERIFIED" for x in values
                                         for claim in x.get("evidence",{}).get("claims",[])),
            "precise_missing_dispositions":sum(x.get("precise_missing_cell") is True and x["verdict"] == "ACCEPT"
                                               for x in values),
            "artifact_reuse_passes":sum(x.get("reusable_on_withheld") is True for x in values),
            "elapsed_completed_seconds":sum(x.get("task_elapsed_seconds",0) for x in values),
            "provider_elapsed_seconds":sum(x.get("provider_elapsed_seconds",0) for x in values),
            "observed_tokens_in":sum(x.get("observed_usage",{}).get("observed_tokens_in",0) for x in values),
            "observed_tokens_out":sum(x.get("observed_usage",{}).get("observed_tokens_out",0) for x in values),
            "no_reported_token_usage_dispatches":sum(x.get("observed_usage",{}).get("unknown_token_replies",0) for x in values),
            "operator_actions_during_execution":sum(x.get("operator_actions_after_case_start",0) for x in values),
            "paid_requests":sum(x.get("paid_requests",0) for x in values)}
    relevant = (counts["both"],counts["previous"])
    complete = all(count["observed"] == count["registered"] and count["interrupted"] == 0 for count in relevant)
    meets = complete and (counts["both"]["strict_acceptances"] > counts["previous"]["strict_acceptances"]
                         and counts["both"]["false_user_facing_acceptances"] == 0)
    return {"schema":"frontier/outcome-driven-observed-study/v1","registration_sha256":study_digest,
            "source_and_config":inputs,"counts":counts,"observed_cells":arms,
            "registered_materiality":"PASS_FINITE_PANEL" if meets else "FAIL_FINITE_PANEL" if complete else "UNSETTLED",
            "all_registered_trials_completed":all(count["observed"] == count["registered"] and count["interrupted"] == 0
                                                  for count in counts.values()),
            "scope":"One observation per registered case and arm. Deterministic reference authored separately under shared administration."
                    " Input work is synthetic, provider use is local, and complete economic costs are unknown.",
            "source_acquisition":"No external data source acquisition. Every task used the same pre-authorized case bytes.",
            "reporting_quality":"The original strict rubric can fail a case for a contradiction in proposed work. Only a false"
                                " verified projection is a machine admission error. Direct answer errors are separately labeled per arm."}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--registration", required=True, type=Path)
    parser.add_argument("--conventional", required=True, type=Path)
    parser.add_argument("--phases", nargs="+", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = summarize(read(args.registration), fingerprint(args.registration), args.conventional, args.phases)
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result["counts"],ensure_ascii=False,sort_keys=True))


if __name__ == "__main__":
    main()
