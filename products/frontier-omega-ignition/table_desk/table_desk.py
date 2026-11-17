"""Turn an authorized printed table and a candidate transcription into a checked CSV."""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unicodedata
from html.parser import HTMLParser
from itertools import zip_longest
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clean(value):
    return " ".join(unicodedata.normalize("NFC", value).split())


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TableReader(HTMLParser):
    def __init__(self, ordinal):
        super().__init__()
        self.ordinal = ordinal
        self.count = self.depth = 0
        self.cell = self.row = None
        self.cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.depth and self.count == self.ordinal:
                raise ValueError("Nested author tables need an explicit semantic reference.")
            if not self.depth:
                self.count += 1
            self.depth += 1
        elif self.count == self.ordinal and self.depth == 1:
            if tag == "tr":
                if self.row is not None:
                    raise ValueError("Overlapping author rows.")
                self.row = []
            elif tag in {"td", "th"}:
                if self.row is None or self.cell is not None:
                    raise ValueError("Overlapping cells or missing author row.")
                attrs = dict(attrs)
                if any(attrs.get(k, "1") != "1" for k in ("rowspan", "colspan")):
                    raise ValueError("Spanning cells need an explicit rectangular reference.")
                self.cell = []
            elif self.cell is not None and tag in {"p", "br", "div"}:
                self.cell.append(" ")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "table":
            self.depth -= 1
        elif self.count == self.ordinal and self.depth == 1:
            if tag in {"td", "th"} and self.cell is not None:
                self.row.append(clean("".join(self.cell)))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.cells.append(self.row)
                self.row = None


def reference(author, spec):
    if author is None:
        raise ValueError("Independent author table unavailable.")
    if digest(author) != spec["author_sha256"]:
        raise ValueError("Author reference digest differs from registration.")
    parser = TableReader(spec["table_ordinal"])
    parser.feed(author.read_text(encoding="utf-8-sig"))
    parser.close()
    rows = parser.cells
    if (not rows or not rows[0] or parser.row is not None or
            any(len(row) != len(rows[0]) for row in rows)):
        raise ValueError("Author table is unavailable or nonrectangular.")
    return rows


def compare(proposal, expected):
    if not isinstance(proposal, list) or any(not isinstance(row, list) for row in proposal):
        return {"accepted": False, "reason": "Candidate must be a matrix of strings."}
    differences = []
    correct = 0
    absent = object()
    for r, (row, gold) in enumerate(zip_longest(proposal, expected, fillvalue=[]), 1):
        for c, (given, truth) in enumerate(zip_longest(row, gold, fillvalue=absent), 1):
            if isinstance(given, str) and truth is not absent and clean(given) == truth:
                correct += 1
                continue
            differences.append({"row": r, "column": c, "proposed": None if given is absent else given,
                                "reference": None if truth is absent else truth})
    shape_ok = len(proposal) == len(expected) and all(len(row) == len(expected[0]) for row in proposal)
    return {"accepted": shape_ok and not differences, "dimensions_match": shape_ok,
            "expected_dimensions": [len(expected), len(expected[0])],
            "proposed_row_lengths": [len(row) for row in proposal], "matching_cells": correct,
            "differences": differences}


def export(destination, rows):
    with (destination / "table.csv").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, lineterminator="\n").writerows(rows)


def registration(path):
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("schema") != "frontier-table-registration/1":
        raise ValueError("Unknown table registration format.")
    if type(spec["dpi"]) is not int or spec["dpi"] <= 0 or spec["dpi"] % 72:
        raise ValueError("Use a positive integer multiple of 72 DPI for integer pixel geometry.")
    if type(spec["table_ordinal"]) is not int or spec["table_ordinal"] < 1:
        raise ValueError("Author table ordinals begin at one.")
    edges = spec["column_edges_pt"]
    if len(edges) < 2 or any(type(v) is not int for v in edges) or edges != sorted(set(edges)):
        raise ValueError("Column boundaries must be increasing integer points.")
    pages = spec["pages"]
    if not pages or [p["page"] for p in pages] != sorted({p["page"] for p in pages}):
        raise ValueError("Register distinct physical pages in order.")
    for page in pages:
        x, y, right, bottom = page["box_pt"]
        if (type(page["page"]) is not int or page["page"] < 1 or
                any(type(v) is not int or v < 0 for v in page["box_pt"]) or
                not x <= edges[0] < edges[-1] <= right or y >= bottom):
            raise ValueError("Invalid PDF page or crop rectangle.")
        last = y
        for top, end in page["row_edges_pt"]:
            if type(top) is not int or type(end) is not int or not last <= top < end <= bottom:
                raise ValueError("Row rectangles must lie inside the crop and be ordered.")
            last = end
    return spec


def crops(pdf, spec, directory):
    from PIL import Image
    if digest(pdf) != spec["pdf_sha256"]:
        raise ValueError("PDF digest differs from registration.")
    scale = spec["dpi"] // 72
    version = subprocess.run(["pdftoppm", "-v"], capture_output=True, text=True, check=True)
    images = []
    for entry in spec["pages"]:
        page = str(entry["page"])
        x, y, right, bottom = [n * scale for n in entry["box_pt"]]
        stem = directory / f"page-{page}"
        subprocess.run(["pdftoppm", "-f", page, "-l", page, "-r", str(spec["dpi"]),
                        "-x", str(x), "-y", str(y), "-W", str(right - x), "-H", str(bottom - y),
                        "-singlefile", "-png", str(pdf.resolve()), str(stem)], check=True)
        file = stem.with_suffix(".png")
        with Image.open(file) as im:
            if im.size != (right - x, bottom - y):
                raise ValueError("Rendered dimensions differ from the registered crop.")
            pixels = hashlib.sha256(im.convert("RGB").tobytes()).hexdigest()
        images.append({"page": entry["page"], "name": file.name, "box_pt": entry["box_pt"],
                       "width_px": right - x, "height_px": bottom - y,
                       "png_sha256": digest(file), "rgb_sha256": pixels})
    return {"renderer": (version.stderr or version.stdout).splitlines()[0], "images": images}


def ocr(spec, directory, images):
    from PIL import Image
    scale = spec["dpi"] // 72
    version = subprocess.run(["tesseract", "--version"], capture_output=True, text=True, check=True)
    rows, attempts = [], []
    with tempfile.TemporaryDirectory() as tmp:
        cell = Path(tmp) / "cell.png"
        for entry, metadata in zip(spec["pages"], images):
            x, y, _, _ = entry["box_pt"]
            with Image.open(directory / metadata["name"]) as source:
                for top, bottom in entry["row_edges_pt"]:
                    row = []
                    for left, right in zip(spec["column_edges_pt"], spec["column_edges_pt"][1:]):
                        source.crop(((left-x)*scale, (top-y)*scale, (right-x)*scale, (bottom-y)*scale)).save(cell)
                        start = time.perf_counter()
                        run = subprocess.run(["tesseract", str(cell), "stdout", "-l", "eng", "--psm", "6"],
                                             capture_output=True, text=True)
                        attempts.append({"row": len(rows)+1, "column": len(row)+1, "returncode": run.returncode,
                                         "elapsed_seconds": round(time.perf_counter()-start, 6),
                                         "raw": run.stdout, "stderr": run.stderr})
                        row.append(clean(run.stdout) if run.returncode == 0 else None)
                    rows.append(row)
    return rows, {"reader": version.stdout.splitlines()[0], "attempts": attempts}


def execute(args, destination):
    spec = registration(args.registration)
    receipt = {"schema": "frontier-table-result/1", "route": args.action,
               "registration_sha256": digest(args.registration), "pdf_sha256": spec["pdf_sha256"],
               "author_sha256": spec["author_sha256"], "table_ordinal": spec["table_ordinal"],
               "instrument_sha256": digest(Path(__file__))}
    proposal = None
    if args.action in {"crop", "ocr", "check"}:
        receipt.update(crops(args.pdf, spec, destination))
    if args.action == "crop":
        receipt["verdict"] = "rendered"
    elif args.action == "ocr":
        proposal, details = ocr(spec, destination, receipt["images"])
        write_json(destination / "transcript.json", proposal)
        receipt.update(details)
        receipt["proposal_sha256"] = digest(destination / "transcript.json")
    elif args.action == "check":
        proposal = json.loads(args.candidate.read_text(encoding="utf-8"))
        receipt["proposal_sha256"] = digest(args.candidate)
        witness = json.loads(args.witness.read_text(encoding="utf-8"))
        receipt["witness_sha256"] = digest(args.witness)
        if (witness.get("registration_sha256") != receipt["registration_sha256"] or
                witness.get("proposal_sha256") != receipt["proposal_sha256"] or
                witness.get("crop_sha256") != [im["png_sha256"] for im in receipt["images"]]):
            receipt["verdict"] = "withheld"
            receipt["reason"] = "Transcript, registration or rendered images differ from the supplied witness."
    if args.action != "crop" and "verdict" not in receipt:
        try:
            authority = reference(args.author, spec)
        except (OSError, ValueError) as error:
            receipt.update(verdict="withheld", reason=str(error))
        else:
            if args.action == "direct":
                receipt["verdict"] = "direct_author_export"
                receipt["dimensions"] = [len(authority), len(authority[0])]
                export(destination, authority)
            else:
                receipt["comparison"] = compare(proposal, authority)
                receipt["verdict"] = "accepted" if receipt["comparison"]["accepted"] else "withheld"
                if receipt["verdict"] == "accepted":
                    export(destination, authority)
    if (destination / "table.csv").is_file():
        receipt["csv_sha256"] = digest(destination / "table.csv")
    write_json(destination / "receipt.json", receipt)
    return receipt["verdict"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    for command in ("crop", "ocr", "check", "direct"):
        sub = actions.add_parser(command)
        sub.add_argument("--registration", required=True, type=Path)
        sub.add_argument("--output", required=True, type=Path)
        if command != "direct":
            sub.add_argument("--pdf", required=True, type=Path)
        if command != "crop":
            sub.add_argument("--author", type=Path)
        if command == "check":
            sub.add_argument("--candidate", required=True, type=Path)
            sub.add_argument("--witness", required=True, type=Path)
    args = parser.parse_args()
    try:
        final = args.output
        if final.exists() or final.is_symlink():
            raise ValueError("Choose a fresh output directory.")
        final.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=final.parent) as tmp:
            stage = Path(tmp) / "result"
            stage.mkdir()
            result = execute(args, stage)
            os.rename(stage, final)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Table Desk: {error}\n")
    print(result)
    if result == "withheld":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
