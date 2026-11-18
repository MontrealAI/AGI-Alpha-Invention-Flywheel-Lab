"""Reproduce the unseen Terwel et al. Table 4 acquisition or audit its frozen observations."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECORD = ROOT / "observation.json"
VISUAL = ROOT / "visual.json"
PDF_SHA = "26342e1a642cd3fe7e0e3ab5c6ae725bc8b9801e1f95484ae00a9b00d30c5d39"
HTML_SHA = "193f9bfeece2c2c5c6a4bb610aecab80b36b6351681496c10531e699d1763850"
VISUAL_SHA = "9979d36fa68d08bc0834161b2d595a23f136bb5cf545cf53e6b65a0b162fe35b"
IMAGE_SHA = "91d9616d78be5471f36003dbaa1fe7b63f54d7d79d6fd498a88a8fd8c10f0898"
SEMANTIC_SHA = "707975ce95d1a73b9564765b8b8decf6e850139edd80f056f453351e2e899ea6"
FIELDS = ("name", "redshift", "host_separation_arcsec", "start_rest_days", "duration_rest_days", "g_abs_mag", "r_abs_mag", "i_abs_mag")
CONDITIONS = ["rounded_10_rest_frame_days", "absolute_magnitude_range_when_detected"]


def bound(path, expected):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"{path.name}: input differs from registered bytes")
    return data


def note_codes(text):
    text = " ".join(text.lower().split())
    codes = []
    if "rest frame days" in text and "rounded to 10 days" in text:
        codes.append(CONDITIONS[0])
    if "range of detections" in text and "absolute magnitude if detected" in text:
        codes.append(CONDITIONS[1])
    return codes


def semantic(path):
    from lxml import html
    publication = html.fromstring(bound(path, HTML_SHA))
    figure, = publication.xpath('//*[@id="S4.T4"]')
    rows = figure.xpath(".//table[1]//tr")
    if [len(row) for row in rows[:3]] != [4, 12, 13] or len(rows) != 12:
        raise ValueError("Three-level header or data row population changed")

    def content(cell):
        value = cell.text or ""
        for child in cell:
            if child.tag == "math":
                value += child.attrib["alttext"]
            elif child.tag == "sup":
                value += "^" + child.text_content().strip()
            else:
                raise ValueError("Unregistered cell structure")
            value += child.tail or ""
        return value.strip().replace(" ^", "^")

    matrix = []
    for row in rows[3:]:
        cells = [content(row[i]) for i in (0, 3, 4, 5, 6, 7, 8, 9)]
        for i in range(5, 8):
            cells[i] = None if cells[i] == "–" else cells[i].replace(" – ", "..")
        matrix.append(cells)
    caption, = figure.xpath("./figcaption")
    return {"rows": matrix, "table_conditions": note_codes(caption.text_content())}


def conventional(path):
    bound(path, PDF_SHA)
    page = ["pdftotext", "-f", "10", "-l", "10"]
    tags = ET.fromstring(subprocess.run(page + ["-bbox-layout", str(path), "-"],
                                        check=True, capture_output=True).stdout)
    words = [(float(w.attrib["xMin"]), float(w.attrib["yMin"]), float(w.attrib["yMax"]), w.text or "")
             for w in tags.iter() if w.tag.rsplit("}", 1)[-1] == "word"]
    # Column bounds in PDF points. Redshift words locate the rows vertically;
    # note glyphs occupy a smaller font above the associated value's baseline.
    ys = sorted(y for x, y, _, value in words if 151 < x < 187 and 101 < y < 176 and re.fullmatch(r"0[.]\d+", value))
    if len(ys) != 9:
        raise ValueError("Missing or ambiguous PDF row anchors")
    bounds = [(36, 84), (151, 187), (187, 216), (216, 243), (243, 278), (278, 328), (328, 378), (378, 425)]
    matrix = []
    for anchor in ys:
        cells = []
        for column, (left, right) in enumerate(bounds):
            parts = sorted((x, top, bottom, value) for x, top, bottom, value in words
                           if left <= x < right and abs(top - anchor) < 2)
            tokens = [("^" if bottom-top < 5 else "") + v.replace("−", "-") for _, top, bottom, v in parts]
            if not tokens:
                raise ValueError("No PDF glyphs found in registered field")
            if column >= 5:
                if tokens == ["–"]:
                    value = None
                elif len(tokens) == 3 and tokens[1] == "–":
                    value = "..".join([tokens[0], tokens[2]])
                else:
                    raise ValueError("Ambiguous magnitude interval in the PDF text layer")
            else:
                value = " ".join(tokens).replace(" ^", "^")
            cells.append(value)
        matrix.append(cells)
    text = subprocess.run(page + ["-layout", str(path), "-"], check=True, capture_output=True).stdout.decode()
    notes = text.split("Notes.", 1)[1].split("(1)", 1)[0]
    return {"rows": matrix, "table_conditions": note_codes(notes)}


def historical(path):
    sys.path.insert(0, str(ROOT.parents[1] / "table_desk"))
    from table_desk import reference
    try:
        reference(path, {"author_sha256": HTML_SHA, "table_ordinal": 4})
    except ValueError as exc:
        return {"status": "withheld", "reason": str(exc)}
    return {"status": "constructed"}


def compare(candidate, reference):
    rows = candidate["rows"]
    if len(rows) != 9 or any(len(row) != 8 for row in rows):
        raise ValueError("A registered row or field is missing")
    mismatches = []
    for i, (row, other) in enumerate(zip(rows, reference["rows"]), 1):
        for name, observed, expected in zip(FIELDS, row, other):
            if observed != expected:
                mismatches.append({"row": i, "field": name, "observed": observed, "semantic": expected})
    failed_identifiers = sum(m["field"] == "name" for m in mismatches)
    matched_notes = sum(code in candidate["table_conditions"] for code in CONDITIONS)
    return {"scientific_fields": 63-len(mismatches)+failed_identifiers, "row_ids": 9-failed_identifiers,
            "table_conditions": matched_notes, "differences": mismatches,
            "accepted": not mismatches and candidate["table_conditions"] == reference["table_conditions"] == CONDITIONS}


def outcomes(record):
    visual = json.loads(bound(VISUAL, VISUAL_SHA))
    semantic_rows = record["semantic"]
    observed = json.dumps(semantic_rows, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    if hashlib.sha256(observed).hexdigest() != SEMANTIC_SHA:
        raise ValueError("The independently acquired semantic observation changed")
    return {arm: compare(candidate, semantic_rows) for arm, candidate in
            [("included_visual", visual), ("direct_pdf", record["direct_pdf"]), ("semantic_export", semantic_rows)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--record", action="store_true", help="write a new first observation, refusing overwrite")
    args = parser.parse_args()
    if bool(args.pdf) != bool(args.html) or args.record and not args.pdf:
        parser.error("Provide both source files for fresh acquisition.")
    record = {}
    if args.pdf:
        wall = {}
        for key, fn, path in (("semantic", semantic, args.html), ("direct_pdf", conventional, args.pdf),
                              ("historical_reader", historical, args.html)):
            started = time.perf_counter()
            record[key] = fn(path)
            wall[key] = round(time.perf_counter() - started, 6)
        record.update(pdf_sha256=PDF_SHA, html_sha256=HTML_SHA, visual_sha256=VISUAL_SHA,
                      visual_page_png_sha256=IMAGE_SHA, acquisition_wall_s=wall)
        record["results"] = outcomes(record)
        if args.record:
            with RECORD.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        else:
            frozen = json.loads(RECORD.read_bytes())
            if {k: v for k, v in record.items() if k != "acquisition_wall_s"} != {k: v for k, v in frozen.items() if k != "acquisition_wall_s"}:
                raise ValueError("Actual source does not reproduce the frozen observations")
    else:
        record = json.loads(RECORD.read_bytes())
    if (record["pdf_sha256"], record["html_sha256"], record["visual_sha256"], record["visual_page_png_sha256"]) != (PDF_SHA, HTML_SHA, VISUAL_SHA, IMAGE_SHA):
        raise ValueError("Recorded input identity differs")
    if record["results"] != outcomes(record):
        raise ValueError("Recorded acceptance differs from the source-bound observations")
    print(json.dumps({"results": record["results"], "historical_reader": record["historical_reader"]},
                     sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
