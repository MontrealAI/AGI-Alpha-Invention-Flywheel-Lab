# SPDX-License-Identifier: Apache-2.0
"""Exercise real native claim operations with openly authored commands and zero inference."""

from argparse import ArgumentParser
import json
from pathlib import Path
import sys
from time import perf_counter

from run_missions import canonical, digest, mission_spec, reusable, save, source_identity, verify_expected


def proposal(case, expected, control, spec):
    if expected["primary"].get("decision") == "ABSTAIN":
        missing = " et ".join(expected["primary"]["missing"])
        answer = f"Le journal autorisé ne contient pas {missing}. Il faut obtenir cette durée avant de calculer le débit agrégé."
        return {"summary": answer, "actions": [], "done": True}

    name = "audited_calculation.json"
    tool = control["tool"]
    actions = [{"tool": "construct_table", "name": name, "schema": tool["table_schema"], "sql": tool["sql"]}]
    for claim in spec["requirements"]["evidence"]["claims"]:
        ident = claim["id"]
        claim["reference"] = {"value": expected["primary"][ident], "source": "Independent exact Fraction control"}
        actions.append({"tool": "run_table", "name": name, "input": {"dataset": case["dataset"]},
                        "claim": {key: claim[key] for key in ("id", "unit", "dimension")}})
    return {"summary": "Effectuer le calcul exact autorisé." if case["lang"] == "fr" else "Run the authorized exact calculation.",
            "actions": actions, "done": True}


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("repo", "cases", "oracle", "sql-control", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_bytes())
    expected = json.loads(args.oracle.read_bytes())
    controls = json.loads(args.sql_control.read_bytes())["cases"]
    backend = source_identity(args.repo)
    sys.path.insert(0, str(args.repo.resolve() / "products/alpha-genesis-harness"))
    from bridge.universal_missions import UniversalMissionService
    from bridge.workflow_demo import FixtureRuntime

    args.output.mkdir(parents=True, exist_ok=False)
    results = {}
    for case in cases:
        if "data" not in case:
            continue
        ident = case["id"]
        truth = expected[ident]
        verify_expected(case, truth)
        spec = mission_spec(case, "fixture", "evaluator-authored-control", evidence=True)
        packet = proposal(case, truth, controls.get(ident), spec)
        start = perf_counter()
        runtime = FixtureRuntime([packet])
        service = UniversalMissionService(runtime, args.output / ident)
        try:
            mission = service.submit(spec)
            result = service.step(mission["id"])
            archive = service.export(mission["id"])
        finally:
            service.close()

        states = result["evidence"]["claims"]
        executed = [event for event in archive["state"]["events"] if event["kind"] == "tool_completed"
                    and event["detail"]["outcome"].get("operation_executed") is True]
        if truth["primary"].get("decision") == "ABSTAIN":
            assert not executed and {row["reason"] for row in states} == {"REQUIRED_FIELD_MISSING"}
            reuse = None
        else:
            assert {row["status"] for row in states} == {"VERIFIED"}
            assert {row["id"]: row["value"] for row in states} == truth["primary"]
            assert len(executed) == len(case["metrics"]) + 1
            artifact = archive["files"]["audited_calculation.json"].encode()
            reuse = reusable(artifact, case, truth["fresh_reuse"])
            assert reuse["matched"]
        save(args.output / (ident + "-archive.json"), archive)
        results[ident] = {"mode": "KNOWN_CASE_OPERATOR_ASSISTED", "actual_provider_requests": 0,
                          "runtime_seconds": perf_counter() - start, "executed_operations": len(executed),
                          "workflow_status": result["status"], "evidence": states, "fresh_reuse": reuse,
                          "archive_sha256": archive["sha256"], "operator_authorship_seconds": None}

    if source_identity(args.repo) != backend:
        raise ValueError("Native backend changed during assisted execution.")
    save(args.output / "RESULT.json", {"schema": "frontier/known-case-assisted-native-controls-v1", "cases": results,
         "case_sha256": digest(args.cases.read_bytes()), "oracle_sha256": digest(args.oracle.read_bytes()),
         "execution_backend_sha256": digest(canonical(backend)),
         "runner_sha256": digest(Path(__file__).read_bytes()),
         "scope": "Retrospective assisted controls after the case and runtime freezes. Ordinary authored commands, real native tool execution, no model execution. Outside the primary model comparison."})


if __name__ == "__main__":
    main()
