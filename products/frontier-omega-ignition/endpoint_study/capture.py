"""Capture the complete displayed run table and scope of each official MLPerf report."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path

from lxml import html

REPORT_URL = "https://results.mlcommons.org/endpoints/report?source=phase2&submission="
IDS = {"d6b88dff-6bbb-4107-8d2e-1090decd4d53", "3fdca196-7298-4b65-832d-d455abd792eb",
       "053005da-b0ad-495d-9721-e39e9b144bd8"}


def content(element):
    return " ".join(element.text_content().split())


def extract(path, destination):
    raw = path.read_bytes()
    original = html.fromstring(raw)
    fields = {}
    for div in original.xpath('//div[span[contains(@class,"info-value-cell")]]'):
        label, value = div.xpath('./span[contains(@class,"info-label-cell")]')[0], div.xpath('./span[contains(@class,"info-value-cell")]')[0]
        key = " ".join(label.xpath('.//button//text()')).strip() or " ".join(label.xpath('./text()')).strip()
        if key in {"Submission ID", "Model Name", "Dataset Name", "Publication Date", "Version",
                   "Deployment", "Division", "System Availability", "Submission Status", "Submitter", "System Name"}:
            text = content(value)
            if fields.get(key, text) != text:
                raise ValueError(f"Conflicting metadata for {key}")
            fields[key] = text
    sid = fields["Submission ID"]
    if sid not in IDS:
        raise ValueError("Unexpected public submission")
    header = content(original.xpath('//h1')[0].getparent().getparent())
    verified = ("Verified by the MLCommons Association" in header and fields["Submission Status"] == "PUBLISHED")
    if not verified and "Pending MLCommons Association verification" not in header:
        raise ValueError("Unrecognized review state")
    table, = original.xpath('//table')
    rows = [[content(c) for c in tr.xpath('./th|./td')] for tr in table.xpath('.//tr')]
    filename = sid + ".csv"
    with (destination / filename).open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp, lineterminator="\n")
        writer.writerows(rows)
    return dict(id=sid, url=REPORT_URL+sid, report_sha256=sha256(raw).hexdigest(), table_file=filename,
                table_sha256=sha256((destination/filename).read_bytes()).hexdigest(), header=header,
                verified=verified, metadata=fields, n_run_columns=len(rows[0])-1)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("inputs", nargs=3, type=Path)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records = sorted((extract(f, args.output) for f in args.inputs), key=lambda v: v["id"])
    if {r["id"] for r in records} != IDS:
        raise ValueError("All three registered reports are required")
    (args.output/"manifest.json").write_text(json.dumps(records, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
