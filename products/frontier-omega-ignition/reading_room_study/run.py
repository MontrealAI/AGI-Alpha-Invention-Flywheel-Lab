"""Reproduce RR-01. Each invocation creates one new, immutable-in-use run directory."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
from xml.etree import ElementTree

from lxml import html
import pymupdf

from control import BLOCKS as ADVERSE_BLOCKS, EXPECTED, write_inputs


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_PRODUCER = HERE.parent / "reading_room" / "edition.py"
PDF_SHA = "4c303bc5a9c4cafbbb11b4d84a0fb4ceb8f7b95822fbdf935c6560f658807c01"
HTML_SHA = "237e73a6dfb99ddfaf4d2d184e8783c87ba0332e77e1fb655dce1a3557facd71"
REGISTRATION = "c326679543960c3d364f1582d91e9cb0e61d406f"
# Recorded visually before scoring; the split passage at index 19 cannot be linked.
KEY = [1] * 9 + [2] * 9 + [None] + [3] * 8 + [4] * 10
HEADINGS = {f"h{i}" for i in range(1, 7)}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flat(value):
    return " ".join(value.split())


def source_material(path):
    tree = ElementTree.parse(path)
    body = tree.find("{*}body")
    blocks = []
    for element in body.iter():
        tag = element.tag.split("}")[-1]
        if tag in HEADINGS or tag == "p":
            blocks.append(("heading" if tag in HEADINGS else "paragraph",
                           flat("".join(element.itertext()))))
    stats = {"blocks": len(blocks), "tables": len(body.findall(".//{*}table")),
             "math": len(body.findall(".//{*}math")), "lists": len(body.findall(".//{*}ol")),
             "existing_pdf_page_links": sum("#page=" in a.get("href", "").lower()
                                            for a in body.findall(".//{*}a"))}
    return blocks, stats


def run_arm(command, cwd):
    start_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    elapsed = time.perf_counter() - start
    end_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {"exit_code": result.returncode, "wall_seconds": round(elapsed, 6),
            "child_cpu_seconds": round(end_cpu.ru_utime + end_cpu.ru_stime
                                       - start_cpu.ru_utime - start_cpu.ru_stime, 6),
            "stderr": result.stderr.strip()[:800]}


def adjudicate(edition, source_rows, gold):
    receipt = json.loads((edition / "receipt.json").read_text(encoding="utf-8"))
    web = html.parse(str(edition / "index.html"))
    blocks = receipt["blocks"]
    nodes = web.xpath('//*[starts-with(@id, "passage-") and @data-index]')
    rows = []
    # Align each published block by its content identity, so a single dropped
    # equation cannot shift later scientific reference pages or inflate errors.
    if len(set(source_rows)) != len(source_rows):
        raise ValueError("RR-01 requires an occurrence key for identical authored blocks.")
    for idx, ((kind, original), expected) in enumerate(zip(source_rows, gold), 1):
        matching = [(position, b) for position, b in enumerate(blocks, 1)
                    if b.get("kind") == kind and isinstance(b.get("text"), str)
                    and flat(b["text"]) == original]
        position, block = matching[0] if len(matching) == 1 else (None, {})
        found = web.xpath(f'//*[@id="passage-{position}"]')
        node = found[0] if len(found) == 1 else None
        heading_or_paragraph = node.xpath('.//*[self::p or self::h1 or self::h2 or self::h3 or self::h4 or self::h5 or self::h6]') if node is not None else []
        # Labels may themselves be paragraphs. Identify the actual supplied passage.
        text_present = any(flat("".join(n.itertext())) == original for n in heading_or_paragraph)
        links = node.xpath('.//a[starts-with(@href,"source.pdf#page=")]/@href') if node is not None else []
        page = block.get("page")
        linked = block.get("status") == "matched"
        sources = block.get("candidate_pages")
        expected_anchors = [f"source.pdf#page={page}"] if linked else []
        safe = isinstance(page, int) and page == expected if linked else page is None
        displayed = flat(node.text_content()).lower() if node is not None else ""
        unresolved_labeled = linked or (bool(original) and flat(original).lower() != displayed
                                         and block.get("status") in {"missing", "ambiguous"})
        consistent = (links == expected_anchors and
                      (sources == [page] if linked else isinstance(sources, list))
                      and node is not None and node.get("data-status") == block.get("status")
                      and node.get("data-index") == str(position) and unresolved_labeled)
        faithful = (block.get("index") == position and block.get("kind") == kind
                    and isinstance(block.get("text"), str) and flat(block["text"]) == original and text_present)
        rows.append({"index": idx, "status": block.get("status", "omitted"), "page": page,
                     "matches_reference": safe, "source_content_preserved": faithful, "html_agrees": consistent,
                     "candidate_pages": sources})
    order = ([n.get("data-index") for n in nodes] == [str(i) for i in range(1, len(gold)+1)]
             and [(r.get("kind"), flat(r["text"])) for r in blocks] == source_rows)
    return rows, (len(blocks) == len(source_rows) and order)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path, help="new directory, must not exist")
    ap.add_argument("--producer", type=Path, default=DEFAULT_PRODUCER)
    args = ap.parse_args()
    out, producer = args.output.resolve(), args.producer.resolve()
    pdf, source = (ROOT / "docs/research" / f"cycle-001.{ext}" for ext in ("pdf", "html"))
    if digest(pdf) != PDF_SHA or digest(source) != HTML_SHA:
        raise SystemExit("The public paper has changed. RR-01 requires the registered exact bytes.")
    out.mkdir()
    material, original_stats = source_material(source)
    if len(material) != len(KEY):
        raise SystemExit("Author manuscript denominator differs from registration.")
    write_inputs(out)
    stats = {}
    for label, src, document in [("candidate", source, pdf), ("adverse", out/"control.json", out/"control.pdf")]:
        stats[label] = run_arm([sys.executable, str(producer), "--pdf", str(document),
                                "--source", str(src), "--output", str(out/label)], out)
    stats["conventional"] = run_arm([sys.executable, str(HERE/"compare.py"), str(source), str(pdf),
                                    str(out/"conventional")], out)
    stats["poppler_text"] = run_arm(["pdftotext", str(pdf), str(out/"native.txt")], out)
    controls = []
    scored = []
    row_count = False
    adverse_count = False
    evaluation_errors = {}
    for label, source_rows, gold in [("candidate", material, KEY),
                                     ("adverse", [("paragraph", t) for t in ADVERSE_BLOCKS],
                                      [2, None, None, None, 1])]:
        try:
            result, exact_count = adjudicate(out/label, source_rows, gold)
            if label == "candidate":
                scored, row_count = result, exact_count
            else:
                adverse_count = exact_count
                for obs, (status, pages) in zip(result, EXPECTED):
                    passed = (obs["status"] == status and obs["candidate_pages"] == pages and
                              obs["source_content_preserved"] and obs["html_agrees"] and obs["matches_reference"])
                    controls.append({"index": obs["index"], "observed": obs["status"],
                                     "page": obs["page"], "passed": passed})
        except (OSError, ValueError, KeyError, TypeError) as error:
            evaluation_errors[label] = str(error).replace(str(out), "RUN")

    linked = [r for r in scored if r["status"] == "matched"]
    correct = [r for r in linked if r["matches_reference"]]
    bad = [r["index"] for r in scored if not all(r[k] for k in
           ("source_content_preserved", "html_agrees", "matches_reference"))]
    supported_pages = sorted({r["page"] for r in correct})
    receiver = out/"candidate"
    pdf_identity = (receiver/"source.pdf").is_file() and digest(receiver/"source.pdf") == PDF_SHA
    portable = stats["candidate"]["exit_code"] == 0 and pdf_identity and all(
        (receiver/name).is_file() for name in ("index.html", "receipt.json"))
    passed = (portable and row_count and not bad and supported_pages == [1, 2, 3, 4]
              and scored[18]["status"] != "matched")
    conventional_links = []
    conv = out/"conventional"
    if stats["conventional"]["exit_code"] == 0:
        alternative = html.parse(str(conv/"index.html"))
        conventional_links = json.loads((conv/"links.json").read_text())
        conventional_anchors = alternative.xpath('//a[starts-with(@href,"source.pdf#page=")]/@href')
        if (len(conventional_links) != len(KEY) or digest(conv/"source.pdf") != PDF_SHA
            or conventional_anchors != [f"source.pdf#page={r['page']}" for r in conventional_links
                                        if r["page"] is not None]):
            raise ValueError("Conventional output differs from its page-link records.")
    comparisons = [(r["page"], KEY[r["index"]-1]) for r in conventional_links if r["page"]]
    raw_text = out/"native.txt"
    native_counts = [len(page.strip()) for page in raw_text.read_text().split("\f") if page.strip()] if raw_text.exists() else []
    for label in ("candidate", "adverse", "conventional"):
        folder = out/label
        stats[label]["output_bytes"] = sum(f.stat().st_size for f in folder.glob("*") if f.is_file())
    report = {
        "study": "RR-01", "registration_commit": REGISTRATION,
        "input_sha256": {"html": HTML_SHA, "pdf": PDF_SHA, "adverse_pdf": digest(out/"control.pdf"),
                         "adverse_json": digest(out/"control.json")},
        "code_sha256": {f.name: digest(f) for f in [producer, HERE/"run.py", HERE/"compare.py", HERE/"control.py"]},
        "tool_versions": {"python": platform.python_version(), "mupdf_binding": pymupdf.VersionBind,
                          "lxml": ".".join(str(i) for i in html.etree.LXML_VERSION[:3]),
                          "pdftotext": subprocess.run(["pdftotext", "-v"], text=True,
                          capture_output=True, check=True).stderr.splitlines()[0]},
        "verdicts": {"portable_delivery": portable, "passage_acceptance": passed,
                     "adverse_controls": adverse_count and len(controls) == 5 and all(r["passed"] for r in controls),
                     "whole_document_accessibility": "unqualified", "economic_value": "unmeasured",
                     "institutional_or_frontier_advantage": "unestablished"},
        "paper": {"source_html": original_stats,
                  "candidate": {"total": len(KEY), "counts": dict(Counter(r["status"] for r in scored)),
                                "correct_links": len(correct), "wrong_links": len(linked)-len(correct),
                                "reference_pages_linked": supported_pages, "failed_rows": bad,
                                "all_blocks_present_in_receipt_and_html_order": row_count,
                                "unchanged_pdf": pdf_identity,
                                "correctly_linked_indices": [r["index"] for r in correct],
                                "unresolved_indices": [r["index"] for r in scored if r["status"] != "matched"]},
                  "conventional": {"total": len(KEY), "correct_links": sum(a == b for a,b in comparisons),
                                   "wrong_links": sum(a != b for a,b in comparisons),
                                   "linked_indices": [r["index"] for r in conventional_links if r["page"]],
                                   "preserves_author_markup": bool(conventional_links)},
                  "poppler_text": {"pages_with_text": len(native_counts), "characters_each_page": native_counts}},
        "adverse": {"total": len(EXPECTED), "passed": sum(1 for r in controls if r["passed"]), "rows": controls},
        "process_costs": stats, "evaluation_errors": evaluation_errors,
        "unmeasured_costs": ["included Codex engineering time and inference bill", "human comparator",
                             "assistive technology study", "acquisition, maintenance and support"],
    }
    (out/"RESULTS.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report["verdicts"], sort_keys=True))
    return 0 if all(s["exit_code"] == 0 for s in stats.values()) and not evaluation_errors else 1


if __name__ == "__main__":
    sys.exit(main())
