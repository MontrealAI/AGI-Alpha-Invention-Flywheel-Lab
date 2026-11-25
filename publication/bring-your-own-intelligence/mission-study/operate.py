# SPDX-License-Identifier: Apache-2.0
"""Run the assisted allocation artifact through HARNESS's read-only table tools."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA = {
    "groups": {"group_id": "TEXT", "min_slots": "INTEGER", "max_slots": "INTEGER"},
    "scenarios": {"scenario_id": "TEXT"},
    "forecasts": {"scenario_id": "TEXT", "group_id": "TEXT", "demand": "INTEGER"},
    "budget": {"total_slots": "INTEGER"},
}
ARTIFACT_NAME = "allocation.json"


class AllocationInstrument:
    """Use unchanged construction and execution entry points with authorized local data."""

    def __init__(self, harness):
        sys.path.insert(0, str(harness))
        from bridge.mission_tools import execute

        self.execute = execute
        self.artifacts = {}
        self.artifact_kinds = {}

    def write(self, name, content, kind):
        raw = content.encode("utf-8")
        self.artifacts[name] = raw
        self.artifact_kinds[name] = kind
        return {"name": name, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}

    def construct(self):
        return self.execute({
            "tool": "construct_table", "name": ARTIFACT_NAME, "schema": SCHEMA,
            "sql": (HERE / "allocation.sql").read_text(encoding="utf-8"),
        }, read=self.artifacts.__getitem__, write=self.write, kind=self.artifact_kinds.get, approved_tables={})

    def run(self, tables, *, authority="fixture"):
        # Supplied development records are not an owner data authorization.
        if authority == "fixture":
            option, approved = {"fixtures": tables}, {}
        elif authority == "operator-approved":
            option, approved = {"dataset": "hall"}, {"hall": tables}
        else:
            raise ValueError("Unknown data authority.")
        return self.execute({"tool": "run_table", "name": ARTIFACT_NAME, "input": option},
            read=self.artifacts.__getitem__, write=self.write, kind=self.artifact_kinds.get, approved_tables=approved)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harness", type=Path, default=REPO / "products" / "alpha-genesis-harness",
                        help="Source checkout or independently verified extracted executor.")
    parser.add_argument("--operator-approved", action="store_true",
                        help="Use only for data actually approved for this exact local objective.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    tables = json.loads(args.input.read_text(encoding="utf-8"))
    artifact = AllocationInstrument(args.harness)
    started = perf_counter()
    construction = artifact.construct()
    elapsed_construction = perf_counter() - started
    started = perf_counter()
    executed = artifact.run(tables, authority="operator-approved" if args.operator_approved else "fixture")
    result = {
        "schema": "frontier/assisted-allocation-operation-v1", "construction": construction, "operation": executed,
        "construct_wall_seconds": elapsed_construction, "execution_wall_seconds": perf_counter() - started,
        "scope": "Included-Codex assisted artifact, followed by actual HARNESS construction and execution. No unattended model dispatch.",
    }
    (args.output / ARTIFACT_NAME).write_bytes(artifact.artifacts[ARTIFACT_NAME])
    (args.output / "operation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
