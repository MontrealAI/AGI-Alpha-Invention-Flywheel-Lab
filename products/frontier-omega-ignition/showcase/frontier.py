"""Build the offline bilingual exhibition from the public edition and registered study."""
import argparse
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
REPO = PRODUCT.parents[1]
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))
from showcase.build import csp_hash, sha

PAPER = REPO / "docs/research/cycle-001.pdf"
MANUSCRIPT = PAPER.with_suffix(".html")
BUILDER = PRODUCT / "reading_room/edition.py"
STUDY = PRODUCT / "reading_room_study"


def plate(pdf):
    """Project the physical text-line boxes of each real page onto its own sheet."""
    result = subprocess.run(["pdftotext", "-bbox-layout", str(pdf), "-"], capture_output=True, check=True)
    pages = ET.fromstring(result.stdout).findall(".//{*}page")
    parts = ['<svg viewBox="0 0 560 350" aria-hidden="true" focusable="false">',
             '<defs><linearGradient id="sheet" x1="0" x2="1" y1="0" y2="1">'
             '<stop stop-color="#302538"/><stop offset=".64" stop-color="#4c394c"/>'
             '<stop offset="1" stop-color="#221a29"/></linearGradient></defs>']
    for i, page in enumerate(reversed(pages)):
        width = float(page.attrib["width"])
        height = float(page.attrib["height"])
        # Preserve actual line positions apart from the uniform per-page projection.
        x, y = 20 + i * 49, 126 + i * 2.8
        parts.append(f'<g class="folio-page" transform="matrix({158/width:.6f} {-81/width:.6f} '
                     f'{153/height:.6f} {184/height:.6f} {x} {y:.2f})">'
                     f'<rect width="{width}" height="{height}" fill="url(#sheet)" stroke="#dec399" stroke-width="3"/>')
        for line in page.findall(".//{*}line"):
            a = line.attrib
            left, top, right, bottom = (float(a[k]) for k in ("xMin", "yMin", "xMax", "yMax"))
            parts.append(f'<rect x="{left:.1f}" y="{top:.1f}" width="{right-left:.1f}" '
                         f'height="{max(1.3, (bottom-top)*.29):.1f}" fill="#e7c598"/>')
        parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


def table_record(files):
    evidence = PRODUCT / "table_desk/evidence"
    paths = ["cycle-001.csv", "page-1.png", "page-2.png", "included-vision-receipt.json",
             "direct-author-receipt.json", "tesseract-receipt.json", "nemotron/observation.json",
             "nemotron/receipt.json", "nemotron/page-1.txt", "nemotron/page-2.txt"]
    for name in paths:
        files["table/" + name] = (evidence / name).read_bytes()
    read = lambda name: json.loads(files["table/" + name])
    inference, model = read("nemotron/observation.json"), read("nemotron/receipt.json")
    if (sha(files["table/nemotron/observation.json"]) != model["observation_sha256"]
            or not model["accepted"]):
        raise ValueError("Published model run no longer matches adjudication.")
    for page, attempt in enumerate(inference["crops"], 1):
        if (sha(files[f"table/page-{page}.png"]) != attempt["image_sha256"]
                or sha(files[f"table/nemotron/page-{page}.txt"]) != attempt["raw_sha256"]):
            raise ValueError("Registered table image or model response differs.")
    results = [read(n + "-receipt.json") for n in ("included-vision", "direct-author", "tesseract")]
    if any(r["csv_sha256"] != sha(files["table/cycle-001.csv"]) for r in [*results, model]):
        raise ValueError("The four Table Desk routes do not agree on the downloaded CSV.")
    return {"cells": model["matching_cells"], "seconds": inference["wall_seconds"],
            "threads": inference["threads"], "page_seconds": [r["wall_seconds"] for r in inference["crops"]]}


def make_kit(output, study, qualification):
    files = {name: (output / name).read_bytes() for name in
             ("source.pdf", "index.html", "manuscript.original.txt", "receipt.json")}
    files.update({"edition.py": BUILDER.read_bytes(), "PROTOCOL.md": (STUDY / "PROTOCOL.md").read_bytes(),
                  "RESULTS.json": (STUDY / "RESULTS.json").read_bytes()})
    receipt = json.loads(files["receipt.json"])
    candidate = study["paper"]["candidate"]
    if (receipt["summary"]["matched"] != candidate["correct_links"] + candidate["wrong_links"]
            or receipt["summary"]["total"] != candidate["total"] - candidate["counts"].get("omitted", 0)):
        raise ValueError("Reader counts and independent study no longer correspond.")
    if (receipt["pdf_sha256"] != sha(files["source.pdf"])
            or receipt["source_sha256"] != sha(files["manuscript.original.txt"])
            or receipt["instrument_sha256"] != sha(files["edition.py"])):
        raise ValueError("Recipient input or instrument has drifted.")
    if (study["input_sha256"]["html"] != receipt["source_sha256"]
            or study["input_sha256"]["pdf"] != receipt["pdf_sha256"]
            or study["code_sha256"]["edition.py"] != receipt["instrument_sha256"]
            or study["tool_versions"]["pdftotext"] != receipt["extractor"]):
        raise ValueError("Study inputs, instrument or Poppler version differ from this build.")
    for name in ("index.html", "receipt.json", "source.pdf", "manuscript.original.txt"):
        if sha(files[name]) != study["publication_receipt"]["recipient_sha256"][name]:
            raise ValueError(f"Registered recipient differs from new build: {name}")
    files["annotated-author.html"] = (output / "annotated-author.html").read_bytes()
    rich = qualification["results"]["cycle-001"]
    if not rich["accepted"] or sha(files["annotated-author.html"]) != rich["html_sha256"]:
        raise ValueError("Augmented author edition has changed since RR-02.")
    files["RECIPIENT_QUALIFICATION.json"] = (STUDY / "RECIPIENT_QUALIFICATION.json").read_bytes()
    files["SUCCESSOR_RESULTS.json"] = (STUDY / "SUCCESSOR_RESULTS.json").read_bytes()
    files["SUCCESSOR_PROTOCOL.md"] = (STUDY / "SUCCESSOR_PROTOCOL.md").read_bytes()
    table = table_record(files)
    source = ("https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/"
              "971abc64c3545d5e476c9cb36e71ed8bf41eb925/products/frontier-omega-ignition/reading_room_study")
    files["README.txt"] = (
        "FRONTIER OMEGA READING ROOM / SALLE DE LECTURE\n\n"
        "Open index.html for the offline reader. Ouvrez index.html pour lire hors ligne.\n"
        "Open annotated-author.html for the full author edition with PDF citations. "
        "Ouvrez annotated-author.html pour l’édition originale enrichie de liens vers le PDF.\n"
        "Open table/cycle-001.csv for the verified table. Le tableau vérifié se trouve dans table/cycle-001.csv.\n"
        "With Python 3 and Poppler / Avec Python 3 et Poppler :\n"
        "python3 edition.py --pdf source.pdf --source manuscript.original.txt "
        "--source-format html --output replay\n\n"
        "Registration and independent evaluation / Protocole et évaluation :\n" + source +
        "\nCompare PDF page numbers manually if your viewer ignores #page. "
        "Saisissez le numéro de page si votre lecteur PDF ignore #page.\n"
    ).encode()
    buffer = io.BytesIO()
    offsets = {}
    resources = {"source.pdf", "table/page-1.png", "table/page-2.png", "table/cycle-001.csv",
                 "table/nemotron/receipt.json"}
    with ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_STORED if name in resources else ZIP_DEFLATED
            archive.writestr(info, data)
            if name in resources:
                offsets[name] = [buffer.tell() - len(data), len(data)]
    raw = buffer.getvalue()
    for name, (start, size) in offsets.items():
        if raw[start:start + size] != files[name]:
            raise ValueError(f"Embedded recipient offset is invalid: {name}")
    return {"bytes": base64.b64encode(raw).decode(), "sha256": sha(raw),
            "offsets": offsets}, receipt, table


def render():
    study = json.loads((STUDY / "RESULTS.json").read_bytes())
    qualification = json.loads((STUDY / "RECIPIENT_QUALIFICATION.json").read_bytes())
    successor = json.loads((STUDY / "SUCCESSOR_RESULTS.json").read_bytes())
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reader"
        subprocess.run([sys.executable, "-B", str(BUILDER), "--source", str(MANUSCRIPT),
                        "--pdf", str(PAPER), "--output", str(out)], check=True, capture_output=True)
        subprocess.run([sys.executable, "-B", str(STUDY / "annotate.py"), "--edition", str(out)],
                       check=True, capture_output=True)
        archive, receipt, table = make_kit(out, study, qualification)
    payload = {"archive": archive, "receipt": receipt, "study": study, "successor": successor, "qualified_recipient": qualification, "table": table}
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026")
    sheet = (HERE / "frontier.css").read_text()
    script = (HERE / "opportunities.js").read_text() + "\n" + (HERE / "frontier.js").read_text()
    policy = ("default-src 'none'; object-src 'none'; img-src blob:; connect-src 'none'; base-uri 'none'; form-action 'none'; "
              f"style-src {csp_hash(sheet)}; script-src {csp_hash(script)}")
    document = (HERE / "frontier.html").read_text()
    for token, replacement in (("<!--POLICY-->", policy), ("/*STYLE*/", sheet), ("<!--FOLIO-->", plate(PAPER)),
                               ("<!--PAYLOAD-->", encoded), ("/*APP*/", script)):
        if document.count(token) != 1:
            raise ValueError(f"Missing or duplicated template marker: {token}")
        document = document.replace(token, replacement)
    return document


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.write_text(render(), encoding="utf-8")
    print(f"{args.output}: {sha(args.output.read_bytes())}")
