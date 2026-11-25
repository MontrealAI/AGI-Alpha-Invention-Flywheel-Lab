# SPDX-License-Identifier: Apache-2.0
"""Reevaluate fixed previous receipts with the new outcome projection, without inference."""

from argparse import ArgumentParser
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys


def read_archive(path, portable_digest):
    raw = path.read_bytes()
    archive = json.loads(raw)
    if archive["sha256"] != portable_digest({key:value for key,value in archive.items() if key != "sha256"}):
        raise ValueError("The old public archive digest did not match.")
    return archive, sha256(raw).hexdigest()


def run(history, candidate):
    root = candidate.resolve() / "products/alpha-genesis-harness"
    sys.path.insert(0, str(root))
    from bridge.mission_evidence import assess_claims
    from bridge.mission_outcomes import assemble_outcome
    from bridge.mission_schema_context import constructor_context
    from bridge.workflows import portable_digest

    def recheck(state, files):
        return assemble_outcome(state, assess_claims(state, lambda name: files[name].encode()))

    earlier_runs = {}
    for case in ("eb-f01", "eb-f02", "eb-f03", "eb-f04"):
        path = history / "observed" / case / "evidence" / "executed-archive.json"
        archive, commitment = read_archive(path, portable_digest)
        state, files = archive["state"], archive["files"]
        outcome = recheck(state, files)
        if outcome["conclusions"] or outcome["quantitative_report_ready"]:
            raise ValueError(f"An earlier failed run gained an unsupported conclusion: {case}.")
        earlier_runs[case] = {"recorded_workflow_disposition":state["status"], "archive_sha256":archive["sha256"],
            "public_archive_bytes_sha256":commitment, "outcome_status":outcome["status"],
            "verified_conclusions":outcome["conclusions"], "unresolved":outcome["unresolved"],
            "approved_schema":constructor_context(state["spec"]["mission"]["requirements"]),
            "previous_refusals":[e["detail"].get("reason",e["detail"].get("code")) for e in state["events"]
                                 if e["kind"] == "tool_refused"],
            "archived_drafts":[x for name,x in files.items() if name.endswith((".md",".txt"))]}
    missing = earlier_runs["eb-f03"]
    labels = [x["label"] for item in missing["unresolved"] for x in item.get("missing", [])]
    if missing["outcome_status"] != "ABSTAIN" or "logs[1].minutes" not in labels or not missing["archived_drafts"]:
        raise ValueError("The known contradictory French draft did not resolve to the precise missing observation.")

    corrected, corrected_bytes = read_archive(history / "assisted" / "eb-f01-archive.json", portable_digest)
    original, files = corrected["state"], corrected["files"]
    positive = recheck(original, files)
    if positive["status"] != "VERIFIED" or len(positive["conclusions"]) != 3:
        raise ValueError("The historical exact assisted result no longer rechecks.")
    altered = {}
    changed = deepcopy(original)
    requirements = changed["spec"]["mission"]["requirements"]
    first_dataset = next(iter(requirements["approved_tables"].values()))
    first_table = next(iter(first_dataset.values()))
    first_table.pop()
    altered["changed_input_bytes"] = recheck(changed, files)
    stale = deepcopy(original)
    stale["spec_hash"] = "0" * 64
    altered["different_mission_revision"] = recheck(stale, files)
    invalid = deepcopy(original)
    for control in invalid["spec"]["mission"]["requirements"]["evidence"]["inputs"].values():
        control["origin"] = "DEVELOPMENT_FIXTURE"
    altered["synthetic_fixture_substitution"] = recheck(invalid, files)
    if any(value["conclusions"] or value["quantitative_report_ready"] for value in altered.values()):
        raise ValueError("A historical negative-control continuation accepted an unsupported claim.")
    return {"classification":"Recorded-artifact replay, zero model requests, no mission rerun or promotion.",
            "source_bytes_sha256":{name:sha256((root/"bridge"/name).read_bytes()).hexdigest() for name in
                                    ("mission_evidence.py","mission_outcomes.py","mission_schema_context.py")},
            "previous_failed_runs":earlier_runs,"assisted_control":{"historical_bytes_sha256":corrected_bytes,
                "archived_input_sha256":corrected["sha256"],"verified_now":positive["conclusions"]},
            "negative_controls":{key:{"status":value["status"],"unresolved":value["unresolved"]}
                                 for key,value in altered.items()},"unsupported_admitted":0}


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("history", "candidate", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    result = run(args.history, args.candidate)
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write("\n")
    print(json.dumps({"statuses":{c:x["outcome_status"] for c,x in result["previous_failed_runs"].items()},
                      "unsupported_admitted":result["unsupported_admitted"],"verified_assisted":len(result["assisted_control"]["verified_now"])},
                     sort_keys=True))


if __name__ == "__main__":
    main()
