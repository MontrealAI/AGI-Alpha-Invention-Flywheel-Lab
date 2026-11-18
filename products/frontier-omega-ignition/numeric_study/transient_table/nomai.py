"""Audit which, if any, new planner targets belong to NOMAI's historical inspected cohort."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRODUCT = ROOT.parents[1]
RECORD = ROOT / "nomai-observation.json"
PDF = "19398ce08bb48996f502ddafda8de74f7609dd8f7b4bb615af7be852670b7f2a"
HTML = "60ecddc0b46c2d67fda8c7b8aa70d559feb27a0f65800190147383adf1d8d9ee"
GROUPS_SHA = "4c0df23c46813793d43181e289a3084feaba515012e0f704911667787e2213e6"
ID = re.compile(r"ZTF[0-9]{2}[a-z]{7}\b")


def digest(groups):
    return hashlib.sha256(json.dumps(groups, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate(groups):
    if len(groups) != 5 or any(not ids for ids in groups.values()):
        raise ValueError("Incomplete historical classification groups")
    ids = [value for group in groups.values() for value in group]
    if len(ids) != len(set(ids)) or not all(ID.fullmatch(x) for x in ids):
        raise ValueError("Repeated or malformed ZTF identifier")
    return set(ids)


def parse_rows(rows):
    if rows[0] != ["Class", "ZTF objectIds"] or len(rows) != 6:
        raise ValueError("Unexpected inspection table")
    groups = {}
    for label, values in rows[1:]:
        if label in groups:
            raise ValueError("Duplicate classification row")
        groups[label] = [s.strip() for s in values.split(",")]
    validate(groups)
    return groups


def semantic(path):
    from lxml import html
    doc = html.parse(str(path))
    table, = doc.xpath('//*[@id="Sx1.T3"]')
    rows = [[c.text_content().strip() for c in r] for r in table.xpath(".//table[1]//tr")]
    caption, = table.xpath("./figcaption")
    return parse_rows(rows), note(caption.text_content())


def primitive(path):
    sys.path.insert(0, str(PRODUCT / "table_desk"))
    from table_desk import reference
    rows = reference(path, {"author_sha256": HTML, "table_ordinal": 6})
    return parse_rows(rows)


def note(text):
    words = " ".join(text.replace("-\n", "").split())
    return all(term in words for term in ("photometric data", "confirmed or rejected"))


def page(path):
    result = subprocess.run(["pdftotext", "-f", "12", "-l", "12", "-layout", str(path), "-"],
                            check=True, capture_output=True)
    text = result.stdout.decode()
    body, caption = text.split("Table 3:", 1)
    start = body.index("ZTF objectIds")
    groups = {}
    current = ""
    for line in body[start:].splitlines()[1:]:
        found = list(ID.finditer(line))
        if not found:
            continue
        label = line[:found[0].start()].strip()
        if label:
            if label in groups:
                raise ValueError("Repeated group on the printed page")
            current = label
            groups[current] = []
        groups[current].extend(match.group() for match in found)
    validate(groups)
    return groups, note(caption)


def decision(groups):
    catalog = json.loads((PRODUCT / "invention/catalog.json").read_bytes())
    targets = [t["id"] for t in catalog["targets"]]
    history = validate(groups)
    return {"historical_ids": len(history), "counts": {label: len(group) for label, group in groups.items()},
            "planner_ids": len(targets), "overlap": sorted(history.intersection(targets))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    if bool(args.pdf) != bool(args.html) or args.record and not args.pdf:
        parser.error("Supply both pinned source files for fresh extraction")
    if args.pdf:
        for path, expected in ((args.pdf, PDF), (args.html, HTML)):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Source edition or bytes changed")
        times = {}
        begun = time.monotonic()
        groups, html_note = semantic(args.html)
        times["semantic"] = round(time.monotonic() - begun, 6)
        begun = time.monotonic()
        printed, pdf_note = page(args.pdf)
        times["pdf"] = round(time.monotonic() - begun, 6)
        begun = time.monotonic()
        installed = primitive(args.html)
        times["historical_reader"] = round(time.monotonic() - begun, 6)
        if groups != printed or groups != installed or not (html_note and pdf_note):
            raise ValueError("The IDs, categories or caption condition differ")
        record = {"pdf": PDF, "html": HTML, "groups": groups,
                  "route_sha256": {key: digest(value) for key, value in
                                   (("semantic", groups), ("pdf", printed), ("historical_reader", installed))},
                  "photometry_only_qualification": {"semantic": html_note, "pdf": pdf_note,
                                                    "historical_reader": None},
                  "result": decision(groups), "local_extraction_wall_s": times}
        if args.record:
            with RECORD.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2)
                stream.write("\n")
        else:
            frozen = json.loads(RECORD.read_bytes())
            if dict(record, local_extraction_wall_s=None) != dict(frozen, local_extraction_wall_s=None):
                raise ValueError("Fresh source does not reproduce stored observations")
    else:
        record = json.loads(RECORD.read_bytes())
    if (record["pdf"] != PDF or record["html"] != HTML
            or set(record["route_sha256"]) != {"semantic", "pdf", "historical_reader"}
            or digest(record["groups"]) != GROUPS_SHA or set(record["route_sha256"].values()) != {GROUPS_SHA}
            or record["photometry_only_qualification"] != {"semantic": True, "pdf": True, "historical_reader": None}
            or record["result"] != decision(record["groups"])):
        raise ValueError("Source or cohort observation differs")
    print(json.dumps(record["result"], sort_keys=True))


if __name__ == "__main__":
    main()
