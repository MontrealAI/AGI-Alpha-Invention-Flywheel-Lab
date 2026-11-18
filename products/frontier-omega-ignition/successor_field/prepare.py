"""Regenerate the six small factual projections from the hash-pinned publisher originals."""
import argparse
import csv
from datetime import date
from html import escape
from html.parser import HTMLParser
import io
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path
from cohort import HERE, ISSUES, SELECTION, sha


class PublishedTable(HTMLParser):
    """Retain cell values, actual header spans, and the release's flag legend."""
    def __init__(self):
        super().__init__()
        self.rows = []
        self.cell = None
        self.row = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        if tag in {"th", "td"}:
            self.cell = [tag, dict(attrs).get("colspan", "1"), []]
        if tag == "br" and self.cell is not None:
            self.cell[2].append(" ")

    def handle_data(self, value):
        if self.cell is not None:
            self.cell[2].append(value)

    def handle_endtag(self, tag):
        if self.cell is not None and tag == self.cell[0]:
            name, span, pieces = self.cell
            self.row.append((name, span, " ".join("".join(pieces).split())))
            self.cell = None
        if tag == "tr":
            self.rows.append(self.row)
            self.row = None


def in_scope(ymd):
    return date(*map(int, ymd)) in SELECTION


def html_extract(raw):
    table = PublishedTable()
    table.feed(raw)
    table.close()
    lines = ["<table>", "<thead>"]
    for n, row in enumerate(table.rows):
        if n == 4:
            lines.extend(["</thead>", "<tbody>"])
        if n >= 4 and not in_scope([cell[2] for cell in row[1:4]]):
            continue
        cells = []
        for tag, span, value in row:
            attr = f' colspan="{int(span)}"' if int(span) > 1 else ""
            cells.append(f"<{tag}{attr}>{escape(value)}</{tag}>")
        lines.append("<tr>" + "".join(cells) + "</tr>")
    return "\n".join(lines + ["</tbody>", "</table>", ""])


def csv_extract(raw):
    lines = raw.splitlines()
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\n")
    records = csv.reader(lines, delimiter=";")
    writer.writerow(next(records))
    writer.writerows(row for row in records if in_scope(row[1:4]))
    return out.getvalue()


def text_extract(raw, name):
    if name == "forecast":
        begin, end = "PREDICTIONS:", "CELESTIAL POLE OFFSET SERIES:"
        markers = ("UT1-UTC(sec)",)
    else:
        begin, end = "1 - DAILY FINAL VALUES", "2 - DAILY FINAL VALUES"
        markers = ("Angular unit is", "(0 h UTC)", "Final values", "Preliminary extension",
                   "DATE     MJD")
    section = raw.split(begin, 1)[1].split(end, 1)[0]
    keep = [begin]
    for line in section.splitlines():
        words = line.split()
        if any(key in line for key in markers):
            keep.append(line.strip())
        elif re.match(r"^\s*20\d{2}\s+\d+\s+\d+\s+\d{5}\s", line) and in_scope(words[:3]):
            keep.append(line.rstrip())
    return "\n".join(keep) + "\n"


def prepare(source, destination, manifest):
    destination.mkdir(parents=True, exist_ok=False)
    result = {}
    for name, issue in ISSUES.items():
        for kind in ("txt", "csv", "html"):
            filename = f"{issue}.{kind}"
            expected = manifest["sources"][filename]
            raw = (source / filename).read_bytes()
            if (len(raw), sha(raw)) != (expected["bytes"], expected["sha256"]):
                raise ValueError(f"Publisher bytes differ: {filename}")
            raw = raw.decode("ascii")
            if kind == "txt":
                value = text_extract(raw, name)
            elif kind == "csv":
                value = csv_extract(raw)
            else:
                value = html_extract(raw)
            target = destination / f"{name}.{kind}"
            data = value.encode("utf-8")
            target.write_bytes(data)
            result[target.name] = {"bytes": len(data), "sha256": sha(data)}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-dir", type=Path, help="Use previously downloaded original files")
    ap.add_argument("--output", required=True, type=Path, help="A new directory")
    args = ap.parse_args()
    manifest = json.loads((HERE / "SOURCES.json").read_text())
    if args.output.exists() or args.output.is_symlink():
        ap.error("Use a new output directory")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        source = args.source_dir if args.source_dir else Path(tmp)
        if args.source_dir is None:
            for name, item in manifest["sources"].items():
                with urllib.request.urlopen(item["url"], timeout=40) as resp:
                    data = resp.read(item["bytes"] + 1)
                if sha(data) != item["sha256"]:
                    raise ValueError(f"Downloaded edition differs: {name}")
                (source / name).write_bytes(data)
        stage = Path(tmp) / "projections"
        result = prepare(source, stage, manifest)
        if result != manifest["projections"]:
            sys.exit("Factual projection differs from the registered bytes")
        stage.rename(args.output)
    print("Six publisher source identities and six factual projections reproduced.")


if __name__ == "__main__":
    main()
