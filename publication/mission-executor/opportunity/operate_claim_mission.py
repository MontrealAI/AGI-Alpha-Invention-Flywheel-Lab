#!/usr/bin/env python3
"""Apply the real controller to frozen live claim receipts using an authored transport."""

import argparse
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from time import monotonic

from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime


DATABASE = "publication-evidence"
RESULT_NAME = "publication-checks.json"
SCHEMA = {"checks": {"edition": "TEXT", "language": "TEXT", "claim_id": "TEXT", "accepted": "INTEGER"}}


def project_receipts(records, arm):
    rows = []
    for use in ("first", "repeat"):
        trial = records[use]
        title = trial["capture"]["job"]
        for claim in trial["outputs"][arm]["claims"]:
            rows.append({"edition": title, "language": claim["language"], "claim_id": claim["id"],
                         "accepted": int(claim["decision"] == "PASS")})
    return rows


def conventional_counts(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["edition"], row["language"]].append(row["accepted"])
    return [[*group, len(counts), sum(counts)] for group, counts in sorted(groups.items())]


def table_proposal(summary, sql):
    return {"summary": summary, "done": False, "actions": [
        {"tool": "construct_table", "name": RESULT_NAME, "schema": SCHEMA, "sql": sql},
        {"tool": "run_table", "name": RESULT_NAME, "input": {"dataset": DATABASE}},
    ]}


class AuthoredReceiptTransport(FixtureRuntime):
    """Advance the local developer work in response to exact runtime output."""

    def __init__(self, expected):
        super().__init__([])
        self.expected = expected

    def generate(self, data):
        payload = json.loads(data["prompt"].split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
        events = payload["latest_tool_results"]
        computed = [row["outcome"]["rows"] for row in events
                    if row.get("kind") == "tool_completed" and "rows" in row.get("outcome", {})]
        if not computed:
            action = table_proposal(
                "Compute a preliminary count by language from the actual checked publication claims.",
                "SELECT language, COUNT(*), SUM(accepted) FROM checks GROUP BY language ORDER BY language",
            )
        elif computed[-1] == self.expected:
            rendered = "\n".join(f"| {edition} | {language} | {checked} | {correct} |"
                                 for edition, language, checked, correct in computed[-1])
            text = (
                "# Qualified-scope publication check\n\n"
                "These are the recorded live quantitative witnesses, grouped by publication and language.\n\n"
                "| Publication | Language | Checks | Accepted |\n| --- | --- | ---: | ---: |\n"
                + rendered + "\n\nThe complete comparative trial measures matching accuracy within this scope. "
                "No commercial benefit is established.\n"
            )
            action = {"summary": "Record accepted counts after agreement with the ordinary comparator.",
                      "done": True, "actions": [{"tool": "write_document", "name": "verified-claims.md", "content": text}]}
        elif all(len(row) == 3 for row in computed[-1]):
            action = table_proposal(
                "The actual result collapsed distinct publication jobs. Extend the instrument to retain both keys.",
                "SELECT edition, language, COUNT(*), SUM(accepted) FROM checks "
                "GROUP BY edition, language ORDER BY edition, language",
            )
        else:
            action = {"summary": "Stop for review because the returned result disagrees with the comparator.",
                      "done": True, "actions": []}
        self.responses = iter([action])
        return super().generate(data)


def run(public_evidence, journal):
    begin = monotonic()
    record = json.loads(public_evidence)
    rows = project_receipts(record, "retained")
    expected = conventional_counts(project_receipts(record, "ordinary"))
    spec = {
        "ambition": "Produce an evidence-bound bilingual release decision from the checked Game Theory and "
                    "Opportunity Capture claims by retaining separate totals by publication and language.",
        "language": "en", "provider": "fixture", "model": "authored-codex-operator",
        "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        "max_turns": 4, "max_actions": 8, "max_output_tokens": 512,
        "tools": ["construct_table", "run_table", "write_document"],
        "requirements": {"approved_tables": {DATABASE: {"checks": rows}}},
    }
    runtime = AuthoredReceiptTransport(expected)
    service = UniversalMissionService(runtime, journal)
    try:
        opened = service.submit(spec)
        results = []
        for _ in range(4):
            view = service.step(opened["id"])
            settled = [event["detail"]["outcome"] for event in view["events"]
                       if event["kind"] == "tool_completed" and "rows" in event["detail"]["outcome"]]
            results.append({"status": view["status"], "results": [event["rows"] for event in settled]})
            if view["status"] != "ready":
                break
        if view["status"] != "needs_review" or not settled or settled[-1]["rows"] != expected:
            raise RuntimeError("no settled runtime result matches the accepted conventional counts")
        return {
            "schema": "frontier/authorized-publication-mission-v1",
            "mode": "INCLUDED_CODEX_AUTHORED_TRANSPORT_DEVELOPMENT_ONLY",
            "input_sha256": sha256(public_evidence).hexdigest(), "counts_from_separate_conventional_code": expected,
            "runtime_turns": len(runtime.calls), "actual_actions": view["actions"], "statuses": results,
            "final": view, "export": service.export(opened["id"]),
            "complete_local_wall_seconds": round(monotonic() - begin, 6),
            "limitations": "Actual bounded local execution with authored proposals. Separate comparison shares the administrator. "
                           "This is development use of the candidate runtime, with no live provider or economic advantage claim.",
        }
    finally:
        service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_evidence", type=Path)
    parser.add_argument("journal", type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.claim_evidence.read_bytes(), args.journal), ensure_ascii=False, indent=2))
