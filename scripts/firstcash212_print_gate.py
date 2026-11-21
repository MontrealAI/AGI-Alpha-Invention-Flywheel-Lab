#!/usr/bin/env python3
"""FIRSTCASH212 independent PDF delivery-completeness gate.

Operates the unmodified FIRSTCASH209 source and public fixture. No live buyer
or data, network reads, payment calls, model APIs, or account operations.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from pypdf import PdfReader

SOURCE = Path("tools/firstcash209_decision_kit.py")
FIXTURE = Path("campaign/unseen-first-cash-209/PUBLIC_SELF_CASE.json")
EXPECTED_SOURCE_BLOB = "cf9ca511395523415ac3aea66a7c7080a6dafb0d"
EXPECTED_FIXTURE_BLOB = "f8cfbefcaf5327110c7395d77d7e977ab9d6108b"
OWNER_HEAD = "03ab77bf51c6fef2308556bfc0541a965d880030"
SOURCE_MARKERS = [f"FC212SOURCE{i:02d}MARKER" for i in range(15)]
DECISION_MARKERS = [
    f"FC212ALT{i}MARKER" for i in range(3)
] + [
    f"FC212FALSIFY{i}MARKER" for i in range(3)
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, stdout=None):
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False, timeout=120)
    if stdout is not None:
        Path(stdout).write_bytes(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"COMMAND_FAILED:{command[0]}:{proc.returncode}:"
                           + proc.stderr.decode("utf-8", "replace")[-2000:])
    return proc


def source_boundary():
    if run(["git", "rev-parse", f"HEAD:{SOURCE}"]).stdout.decode().strip() != EXPECTED_SOURCE_BLOB:
        raise RuntimeError("ORIGINAL_SOURCE_BLOB_CHANGED")
    if run(["git", "rev-parse", f"HEAD:{FIXTURE}"]).stdout.decode().strip() != EXPECTED_FIXTURE_BLOB:
        raise RuntimeError("ORIGINAL_CASE_BLOB_CHANGED")
    run(["git", "merge-base", "--is-ancestor", OWNER_HEAD, "HEAD"])


def stress_case(original):
    case = copy.deepcopy(original)
    case["kind"] = "synthetic_fixture"
    case["case_id"] = "firstcash212-synthetic-layout-stress"
    for i, opt in enumerate(case["options"]):
        opt["sources"] = [
            {"url": f"https://example.org/not-a-real-source/{SOURCE_MARKERS[i*5+j]}",
             "sha256": None, "scope": "synthetic_control"}
            for j in range(5)
        ]
        opt["strongest_alternative"]["en"] = (
            "Independent qualified human and conventional software alternative. "
            + "ordinary control " * 8 + f" {DECISION_MARKERS[i]}"
        )
        opt["falsification"]["fr"] = (
            "Procédure indépendante pour réfuter le bénéfice supposé. "
            + "vérifier les résultats " * 6 + f" {DECISION_MARKERS[3+i]}"
        )
        for field in ("strongest_alternative", "falsification", "productive_mean",
                      "accepted_outcome", "title"):
            for language in ("en", "fr"):
                if len(opt[field][language]) > 240:
                    raise RuntimeError("SYNTHETIC_TEXT_OUTSIDE_SOURCE_CONTRACT")
    return case


def make_pdf(case_path, root, name):
    outdir = root / name
    bundle = outdir / "bundle"
    outdir.mkdir()
    run([sys.executable, "-B", str(SOURCE), "build", "--case", str(case_path),
         "--output", str(bundle)], outdir / "build.log")
    run([sys.executable, "-B", str(SOURCE), "verify", "--output", str(bundle)],
        outdir / "verify.log")
    pdf = outdir / "document.pdf"
    run(["google-chrome", "--headless", "--no-sandbox", "--disable-gpu",
         "--disable-dev-shm-usage", "--disable-background-networking",
         "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
         (bundle / "DECISION.html").resolve().as_uri()], outdir / "chrome.log")
    reader = PdfReader(str(pdf))
    page_count = len(reader.pages)
    a4 = []
    text_pages = []
    for page in reader.pages:
        w, h = map(float, (page.mediabox.width, page.mediabox.height))
        a4.append(590 <= w <= 600 and 836 <= h <= 845)
        text_pages.append(page.extract_text() or "")
    text = re.sub(r"\s+", "", "\n".join(text_pages)).upper()
    expected = SOURCE_MARKERS + DECISION_MARKERS if name == "synthetic_stress" else ["FRONTIER"]
    missing = [marker for marker in expected if marker not in text]
    result = {
        "case_role": name,
        "source_kind": "synthetic_fixture" if name == "synthetic_stress" else "public_self_case",
        "pdf_sha256": digest(pdf), "pdf_bytes": pdf.stat().st_size,
        "pages": page_count, "a4_per_page": a4,
        "source_markers_required": len(SOURCE_MARKERS) if name == "synthetic_stress" else 0,
        "decision_markers_required": len(DECISION_MARKERS) if name == "synthetic_stress" else 0,
        "missing_markers": missing,
        "rendering_acceptance": page_count == 10 and all(a4) and not missing,
        "payment_or_buyer_claim": False,
    }
    (outdir / "audit.json").write_text(json.dumps(result, sort_keys=True, indent=2)+"\n")
    return result


def main():
    root = Path(sys.argv[1]).resolve()
    if root.exists():
        raise RuntimeError("FRESH_OUTPUT_REQUIRED")
    root.mkdir(parents=True)
    report = {
        "schema": "firstcash212/independent-print-acceptance/v1",
        "frozen_protocol": "f7594699e5fe57a29321ffd4275979fb5139a88a",
        "source_owner_commit": OWNER_HEAD,
        "original_source_blob": EXPECTED_SOURCE_BLOB,
        "original_case_blob": EXPECTED_FIXTURE_BLOB,
        "complete_cost_profit": None, "collected_revenue": None,
        "paid_customer": False, "release_approved": False,
        "cases": [], "overall_delivery_acceptance": False
    }
    try:
        source_boundary()
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        stress = stress_case(fixture)
        stress_file = root / "SYNTHETIC_INPUT.json"
        stress_file.write_text(json.dumps(stress, ensure_ascii=False, indent=2)+"\n")
        report["cases"].append(make_pdf(FIXTURE, root, "original_self_case"))
        report["cases"].append(make_pdf(stress_file, root, "synthetic_stress"))
        report["overall_delivery_acceptance"] = all(x["rendering_acceptance"] for x in report["cases"])
        report["disposition"] = "BOUNDED_TWO_CASE_PASS" if report["overall_delivery_acceptance"] else "PDF_CONTENT_LOSS_OR_LAYOUT_FAILURE_NO_DEPLOY"
    except Exception as exc:
        report["disposition"] = "EXECUTION_FAILURE_NO_DEPLOY"
        report["error"] = str(exc)[:2200]
    (root / "RESULT.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["overall_delivery_acceptance"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
