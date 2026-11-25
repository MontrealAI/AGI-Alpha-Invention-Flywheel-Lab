# SPDX-License-Identifier: Apache-2.0
"""Diagnose immutable native SQL constructions separately from observed mission grades."""

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import json
import sys

from run import exact_row, retained_reuse, save, verified_json


def inspect(trial, case, expected, reuse, replay):
    archive_path = trial / "executed-archive.json"
    recorded_path = trial / "result.json"
    if not archive_path.is_file() or not recorded_path.is_file():
        return None
    archive = json.loads(archive_path.read_bytes())
    record = json.loads(recorded_path.read_bytes())
    if archive["sha256"] != record["archive_sha256"] or record["case"] != case["id"]:
        raise ValueError("A recorded archive differs from its observation.")
    inspected = []
    for name, metadata in archive["state"]["artifacts"].items():
        if metadata["kind"] != "table_instrument":
            continue
        raw = archive["files"][name].encode()
        if sha256(raw).hexdigest() != metadata["sha256"]:
            raise ValueError("A retained artifact no longer matches the recorded bytes.")
        result = {"artifact": name, "sha256": metadata["sha256"],
                  "bound_run_observed": any(x["artifact"] == name and x["bound"] for x in record.get("approved_runs",[]))}
        if expected["primary"].get("decision") == "ABSTAIN":
            result["diagnosis"] = "Missing required data. No numerical audit run."
        else:
            try:
                observed = replay(raw, case["data"])
            except ValueError as error:
                result.update(diagnosis="Query could not run on approved data.", error=str(error))
            else:
                exact = exact_row(observed["rows"], case["metrics"], expected["primary"])
                result.update(primary_exact=exact, rows=observed["rows"], output_sha256=observed["output_sha256"])
                if exact:
                    result["held_reuse"] = retained_reuse(raw, case, expected, reuse)
        inspected.append(result)
    return {"case": case["id"], "arm": record["arm"], "observed_verdict": record["verdict"],
            "observed_archive_sha256": archive["sha256"], "construction_diagnostics": inspected}


def main():
    parser = ArgumentParser(description=__doc__)
    for key in ("repo", "registration", "cases", "reuse", "oracle", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--phases", nargs="+", type=Path, required=True)
    args = parser.parse_args()
    registered = verified_json(args.registration, args.registration_sha256)
    cases = {case["id"]: case for case in verified_json(args.cases, registered["authorized_cases_sha256"])}
    reuse = verified_json(args.reuse, registered["withheld_reuse_sha256"])
    oracle = verified_json(args.oracle, registered["independent_oracle_sha256"])
    sys.path.insert(0, str(args.repo.resolve() / "products/alpha-genesis-harness"))
    from bridge.mission_tools import _replay

    records = []
    for phase in args.phases:
        installation = json.loads((phase / "installation.json").read_bytes())
        if installation["order"] != registered["execution_order"][installation["phase"]]:
            raise ValueError("Unexpected observations in the registered phase.")
        for ident, arm in installation["order"]:
            checked = inspect(phase / f"{ident}-{arm}", cases[ident], oracle[ident], reuse, _replay)
            if checked is not None:
                records.append(checked)
    save(args.output, {"schema": "frontier/outcome-driven-construction-diagnostics-v1",
                       "scope": "Independent retrospective SQL replay on sealed synthetic inputs. No inference calls or mission reruns. Recorded mission verdicts remain fixed.",
                       "executions": records})


if __name__ == "__main__":
    main()
