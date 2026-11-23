"""Cross-check source dimensions against the rendered MLCommons report tables."""

from argparse import ArgumentParser
from decimal import Decimal
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path

from .__main__ import load_observations
from .mlcommons import MATCH

FIELDS = ("Concurrency", "System Tokens/Second", "TTFT P90 (ms)")


class ReportRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.table = {}
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if self.row is not None and tag in ("td", "th"):
            self.cell = []

    def handle_data(self, value):
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if self.cell is not None and tag in ("td", "th"):
            self.row.append("".join(self.cell).strip())
            self.cell = None
        if tag == "tr" and self.row is not None:
            if self.row and self.row[0] in FIELDS:
                field, *values = self.row
                if field in self.table:
                    raise ValueError(f"Duplicate report row {field}")
                self.table[field] = [Decimal(value.replace(",", "")) for value in values]
            self.row = None


def audit(directory):
    cohort = {}
    for row in load_observations()["rows"]:
        if row["facts"] == MATCH:
            cohort.setdefault(row["submission_id"], []).append(row)
    reports = []
    for key, rows in sorted(cohort.items()):
        with (directory / (key + ".html")).open("rb") as file:
            raw = file.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Oversized report")
        parser = ReportRows()
        parser.feed(raw.decode("utf-8"))
        seen = set()
        indexed = {row["load"]: row for row in rows}
        if len(indexed) != len(rows):
            raise ValueError("The rendered-table check needs unique concurrency within each report")
        for load, throughput, first_token in zip(*(parser.table[field] for field in FIELDS), strict=True):
            expected = indexed[load]
            if load in seen or (
                abs(throughput - Decimal(expected["objective"])) > Decimal("0.05")
                or abs(first_token - Decimal(expected["upper_metric"])) > Decimal("0.05")
            ):
                raise ValueError(f"Report differs for {key} at concurrency {load}")
            seen.add(load)
        if seen != indexed.keys():
            raise ValueError(f"Report coverage differs for {key}")
        reports.append({
            "report": "https://results.mlcommons.org/endpoints/report?source=phase2&submission=" + key,
            "html_sha256": sha256(raw).hexdigest(),
            "matched_points": len(seen),
        })
    return {"reports": reports, "matched_points": sum(row["matched_points"] for row in reports),
            "scope": "Same publisher's rendered concurrency, system TPS and first-token P90. "
                     "End-to-end interactivity comes from the result feed. No independent workload execution."}


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(audit(parser.parse_args().directory), indent=2))
