"""Project compact numerical facts from saved official MLPerf Endpoints HTML reports.

The lxml dependency applies to source acquisition only. No embedded report script
is evaluated. Supply all three reports via explicit local files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from lxml import html

IDS = {"d6b88dff-6bbb-4107-8d2e-1090decd4d53", "3fdca196-7298-4b65-832d-d455abd792eb",
       "053005da-b0ad-495d-9721-e39e9b144bd8"}
URL = "https://results.mlcommons.org/endpoints/report?source=phase2&submission="
META = {"Submission ID": "id", "Submission Status": "status", "Submitter": "submitter",
        "Model Name": "model", "Dataset Name": "dataset", "System Name": "system",
        "Publication Date": "published", "Division": "division", "Version": "version",
        "Deployment": "deployment", "System Availability": "availability"}
FIELDS = {"Concurrency": ("concurrency", int), "System Tokens/Second": ("system_tps", str),
          "Tokens/Second per User": ("tps_per_user", str), "TTFT P90 (ms)": ("ttft_p90_ms", str),
          "Time Per Output Token (TPOT) (ms)/P90": ("tpot_p90_ms", str),
          "Config Type": ("config_type", str), "Config Region": ("config_region", str),
          "Result State": ("state", str), "Measured Accuracy Score": ("point_accuracy", str),
          "Total Queries Failed": ("failed", int), "Total Queries Issued": ("issued", int),
          "Run Duration (s)": ("duration_s", str), "Configuration Summary": ("configuration", str)}


def extract(path):
    markup = path.read_bytes()
    root = html.fromstring(markup)
    record = {}
    for label in root.xpath('//span[contains(concat(" ",normalize-space(@class)," ")," info-label-cell ")]'):
        words = label.xpath(".//button//text()") or label.xpath("./text()")
        key = META.get(" ".join(" ".join(words).split()))
        if key is None:
            continue
        cell, = label.getparent().xpath('./*[contains(concat(" ",normalize-space(@class)," ")," info-value-cell ")]')
        value = " ".join(cell.text_content().split())
        if key in record and record[key] != value:
            raise ValueError(f"Conflicting metadata: {key}")
        record[key] = value
    if set(record) != set(META.values()) or record["id"] not in IDS:
        raise ValueError("Unexpected report identity or missing report metadata.")
    record["url"] = URL + record["id"]
    table, = root.xpath("//table")
    rows = {}
    section = ""
    for tr in table.xpath(".//tr"):
        cells = [" ".join(el.text_content().split()) for el in tr.xpath("./th|./td")]
        if not cells:
            continue
        name, values = cells[0], cells[1:]
        if name == "Field Name":
            if values != [f"Run {n}" for n in range(1, len(values)+1)]:
                raise ValueError("Missing or reordered run identities.")
            rows["run"] = list(range(1, len(values)+1))
        elif name in {"Time to First Token (TTFT) (ms)", "Time Per Output Token (TPOT) (ms)", "Query Latency (ms)"}:
            section = name
        else:
            key = f"{section}/{name}" if section else name
            if key in FIELDS:
                dest, cast = FIELDS[key]
                if dest in rows:
                    raise ValueError(f"Ambiguous column: {name}")
                rows[dest] = [None if cell == "—" else cast(cell.replace(",", "")) for cell in values]
    if set(rows) != {"run", *(f[0] for f in FIELDS.values())}:
        raise ValueError("Missing required numerical fields.")
    if len({len(series) for series in rows.values()}) != 1:
        raise ValueError("Incomplete run table.")
    record["points"] = [dict(zip(rows, run)) for run in zip(*rows.values())]
    return record, hashlib.sha256(markup).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path, help="fresh directory")
    p.add_argument("files", type=Path, nargs=3)
    args = p.parse_args()
    results = sorted((extract(f) for f in args.files), key=lambda pair: pair[0]["id"])
    if {r["id"] for r, _ in results} != IDS:
        p.error("Supply exactly one report from each registered source.")
    args.output.mkdir(exist_ok=False, parents=True)
    reports = {"schema": "frontier-endpoints/reports/v1", "sources": [r for r, _ in results]}
    (args.output/"reports.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    (args.output/"retrieval.json").write_text(json.dumps(
        [{"id": r["id"],"url": r["url"],"raw_html_sha256": digest} for r, digest in results],
        indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()
