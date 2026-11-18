"""Recover the six published peaks in Ma et al., or replay the received table."""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML_SHA = "9ec39a73734769df4b7a5483ff8ba54bc3449f25ef59f9d76a379743416dd633"
PDF_SHA = "b5ea8e5f3a3a4e94482e33de0ec47045d5f53b27cceaf5d384b62b94456a04d0"
FIELDS = ("sn", "peak_r_absolute_mag", "galactic_r_extinction_mag", "host_E_BV_mag",
          "declination_dms", "redshift", "distance_Mpc")
COLUMNS = (0, 5, 6, 7, 9, 10, 11)
CONDITIONS = ("six_entries_only", "extinction_corrected_r_peak", "host_extinction_method")
NUMBER = r"-?\d+(?:\.\d+)?"
SHAPES = (r"SN \d{4}[a-z]+", NUMBER + "±" + NUMBER, NUMBER, r"(?:≲)?" + NUMBER,
          r"[+-]\d{2}:\d{2}:\d{2}(?:\.\d+)?", NUMBER, NUMBER + "±" + NUMBER)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source(path, expected):
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError(f"{path.name}: source differs from registered edition bytes")
    return data


def normalize(text):
    value = " ".join(text.split()).replace("−", "-")
    value = re.sub(r"\s*([±≲])\s*", r"\1", value)
    return value if value not in {"", "–", "—"} else None


def conditions(text):
    words = " ".join(text.lower().split())
    scope = bool(re.search(r"only the first (?:6|six) entries", words))
    peak = "r-band peak magnitude" in words and "after extinction correction" in words
    host = all(piece in words for piece in ("host galaxy extinction", "corresponding references",
                                             "na i d absorption", "resolution spectra"))
    return [key for key, found in zip(CONDITIONS, (scope, peak, host)) if found]


def check_headers(headers):
    # Bind the projection to the native publication headings on each route.
    required = (r"^SN$", r"^M\s*r", r"Galactic extinction\(r\)/mag", r"E\(B-V\)/mag",
                r"^dec$", r"^Redshift$", r"^Distance/Mpc$")
    if len(headers) != len(required) or any(not re.search(expr, value) for expr, value in zip(required, headers)):
        raise ValueError(f"Missing quantity or unit in the source headings: {headers!r}")


def semantic(path):
    from lxml import html

    figure = html.fromstring(source(path, HTML_SHA)).get_element_by_id("A1.T6")
    table, = figure.xpath(".//table")
    headers = [table.xpath("./thead/tr/*")[i].text_content().strip() for i in COLUMNS]
    check_headers(headers)

    def scientific_cell(node):
        # Select the presentation operator, excluding its alternative TeX annotation.
        pieces = node.xpath(".//text()[not(ancestor::annotation)]")
        return normalize("".join(pieces))

    rows = [[scientific_cell(row[i]) for i in COLUMNS] for row in table.xpath("./tbody/tr")]
    return rows, conditions(figure.text_content())


def historical(path):
    sys.path.insert(0, str(HERE.parents[1] / "table_desk"))
    from table_desk import reference

    matrix = reference(path, {"author_sha256": HTML_SHA, "table_ordinal": 6})
    check_headers([matrix[0][i] for i in COLUMNS])
    return ([[normalize(row[i]) for i in COLUMNS] for row in matrix[1:]],
            conditions(" ".join(matrix[0])))


def conventional(path):
    import fitz

    data = source(path, PDF_SHA)
    # The printed PDF calls this Table A.1. The HTML calls the same table 6.
    with fitz.open(stream=data, filetype="pdf") as document:
        page = document[15]
        full = page.get_text()
        if "Table A.1: The SNe Ia sample" not in full:
            raise ValueError("Physical page 16 no longer identifies the registered sample")
        words = []
        for word in page.get_text("words"):
            box = fitz.Rect(word[:4]) * page.rotation_matrix
            words.append(((box.x0 + box.x1) / 2, box.y1, word[4]))
    # Registered physical columns in landscape coordinates. The row anchor is
    # each left-hand SN label, allowing empty photometry columns to stay empty.
    bands = ((84, 128), (270, 312), (312, 392), (392, 438),
             (486, 533), (533, 568), (568, 618))

    def row_at(bottom, tolerance):
        return [" ".join(text for x, y, text in sorted(words)
                         if left <= x < right and abs(y - bottom) < tolerance)
                for left, right in bands]

    check_headers(row_at(98.5, 1))
    anchors = sorted(y for x, y, word in words if word == "SN" and 84 < x < 128 and 100 < y < 151)
    if len(anchors) != 6:
        raise ValueError("Could not identify all six SN row baselines")
    numerical = [[normalize(cell) for cell in row_at(y, 1)] for y in anchors]
    return numerical, conditions(full.split("Notes.", 1)[1].split("References.", 1)[0])


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(FIELDS)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def verify_reference(rows, notes):
    if len(rows) != 6 or len({row[0] for row in rows}) != 6 or tuple(notes) != CONDITIONS:
        raise ValueError("The semantic sample, row identifiers or eligibility notes are incomplete")
    for row in rows:
        if len(row) != len(SHAPES):
            raise ValueError("Unexpected physical projection")
        for i, (value, shape) in enumerate(zip(row, SHAPES)):
            if value is None and i in (1, 3):
                continue  # Only empty peak and host extinction cells occur on this bounded source.
            if value is None or not re.fullmatch(shape, value):
                raise ValueError(f"Unknown measurement encoding in {FIELDS[i]}: {value!r}")


def score(rows, notes, reference):
    if len(rows) != len(reference) or any(len(row) != len(FIELDS) for row in rows):
        raise ValueError("Lost a source row or field")
    differences = []
    matched_names = matched_cells = 0
    for row, truth in zip(rows, reference):
        for i, (value, expected) in enumerate(zip(row, truth)):
            if value != expected:
                differences.append({"sn": truth[0], "field": FIELDS[i], "observed": value})
            elif i == 0:
                matched_names += 1
            else:
                matched_cells += 1
    return {"accepted": not differences and tuple(notes) == CONDITIONS, "row_ids": matched_names,
            "quantities": matched_cells, "conditions": notes, "differences": differences,
            "csv_sha256": digest(csv_bytes(rows))}


def observe(pdf, author):
    import fitz
    from lxml import etree

    data = {}
    timings = {}
    for label, reader, path in (("table_desk", historical, author),
                                ("pdf_geometry", conventional, pdf), ("semantic_dom", semantic, author)):
        started = time.perf_counter()
        data[label] = reader(path)
        timings[label] = round(time.perf_counter() - started, 6)
    started = time.perf_counter()
    truth, truth_conditions = data["semantic_dom"]
    verify_reference(truth, truth_conditions)
    results = {key: score(rows, notes, truth) for key, (rows, notes) in data.items()}
    timings["compare_and_encode"] = round(time.perf_counter() - started, 6)
    return truth, {"schema": "ignition.peak-context/1", "source_baseline": "a16d3dd74cb231e04420fb320ed5386de6ef5c16",
                   "pdf_sha256": PDF_SHA, "html_sha256": HTML_SHA,
                   "pdf_bytes": pdf.stat().st_size, "html_bytes": author.stat().st_size,
                   "versions": {"python": sys.version.split()[0], "pymupdf": fitz.VersionBind,
                                "lxml": ".".join(str(part) for part in etree.LXML_VERSION)},
                   "scope": "six printed rows; numerical transcription and observation context",
                   "elapsed_seconds": timings, "results": results}


def rate_evidence(rows):
    # Even if every peak had a usable epoch, a rate needs two measurements
    # of the same object. The paper gives one row per SN in this projection.
    by_object = Counter(row[0] for row in rows if row[1] is not None)
    return {"reported_peaks": sum(by_object.values()),
            "possible_same_object_pairs_upper_bound": sum(n * (n - 1) // 2 for n in by_object.values())}


def read_record():
    record = json.loads((HERE / "observation.json").read_text(encoding="utf-8"))
    source_csv = (HERE / "peaks.csv").read_bytes()
    with io.StringIO(source_csv.decode(), newline="") as stream:
        reader = csv.reader(stream)
        if tuple(next(reader)) != FIELDS:
            raise ValueError("CSV header differs from the registered quantities")
        rows = [[value or None for value in row] for row in reader]
    if (record["html_sha256"], record["pdf_sha256"]) != (HTML_SHA, PDF_SHA):
        raise ValueError("Observation source identities changed")
    verify_reference(rows, record["results"]["semantic_dom"]["conditions"])
    if set(record["results"]) != {"semantic_dom", "pdf_geometry", "table_desk"}:
        raise ValueError("All three registered routes must remain inspectable")
    for label, outcome in record["results"].items():
        # The data-only record stores only deviations from the agreed CSV.
        # Reconstruct and score every original output with its independently
        # retained digest. Re-execution on both original inputs is a separate check.
        observed = [list(row) for row in rows]
        indexes = {row[0]: i for i, row in enumerate(rows)}
        for item in outcome["differences"]:
            observed[indexes[item["sn"]]][FIELDS.index(item["field"])] = item["observed"]
        if score(observed, outcome["conditions"], rows) != outcome:
            raise ValueError(f"Could not reproduce the {label} observation")
    return rows, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--html", type=Path)
    parser.add_argument("--output", type=Path, help="new directory for fresh results and CSV")
    args = parser.parse_args()
    if bool(args.pdf) != bool(args.html) or (args.output and not args.pdf):
        parser.error("For new extraction, supply both registered inputs")
    if args.pdf:
        rows, record = observe(args.pdf, args.html)
        if args.output:
            args.output.mkdir(parents=True, exist_ok=False)
            (args.output / "peaks.csv").write_bytes(csv_bytes(rows))
            (args.output / "observation.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            expected_rows, expected = read_record()
            if rows != expected_rows or record["results"] != expected["results"]:
                raise SystemExit("Fresh extraction differs from the registered observation")
    else:
        rows, record = read_record()
    outcomes = {name: {key: value for key, value in arm.items() if key != "differences"}
                for name, arm in record["results"].items()}
    print(json.dumps({"extraction": outcomes, "rate_evidence": rate_evidence(rows)},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
