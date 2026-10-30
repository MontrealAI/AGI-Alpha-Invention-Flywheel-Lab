"""Check paper provenance, rendered outputs and a completed separate PDF QA.

This performs mechanical identity/coverage checks. It neither performs visual
inspection nor treats rendering, pending QA, or an authored receipt as external
scientific/commercial certification.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DOC = "docs/next009"
OUTPUTS = {"paper.md", "paper.tex", "paper.pdf", "paper.html", "reading.css",
           "latex-header.tex", "figures/successor.png", "figures/successor.pdf"}
REQUIRED_INPUTS = {
    "evidence/next009/verification/primary-confirmation/artifacts/ACCEPTANCE.json",
    "evidence/next009/numeric-edition/verification-v1/artifacts/NET3_NUMERIC_FEASIBILITY.json",
    "evidence/next009/verification/successor-primary-final-v2/artifacts/ACCEPTANCE.json",
    "evidence/next009/commerce/net1-primary-final-v1/artifacts/COMMERCIAL.json",
    "evidence/next009/verification/commercial-audit/artifacts/AUDIT.json",
    "verification/next009/CONFIRMATION_FREEZE.json",
    "verification/next009/SUCCESSOR_FREEZE.json",
    "research/next009/REPLAY_INPUTS.json",
    "research/next009/build_paper.py",
}
RESTORE_SHA = "80a83387114ba12b0ef48299e07bb9f522fe51bd5f60adb66265a1da558ea0ef"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def regular(root, name):
    if type(name) is not str:
        raise ValueError("PAPER_PATH_STRING_REQUIRED")
    relative = PurePosixPath(name)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("UNSAFE_PAPER_PATH:" + name)
    path = root.joinpath(*relative.parts)
    if any(p.is_symlink() for p in [path, *path.parents]) or not path.is_file():
        raise ValueError("REGULAR_UNSYMLINKED_PAPER_FILE_REQUIRED:" + name)
    return path


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("DUPLICATE_PAPER_RECEIPT_KEY:" + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_PAPER_RECEIPT")))


def hash_string(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None


class ReadingEdition(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.hidden = 0
        self.headings = self.paragraphs = self.visible_characters = 0
        self.external_resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "body":
            self.in_body = True
        if tag in {"script", "style", "pre"}:
            self.hidden += 1
        if self.in_body and not self.hidden:
            if tag in {"h1", "h2", "h3"}:
                self.headings += 1
            if tag == "p":
                self.paragraphs += 1
        if tag in {"img", "script", "iframe", "source", "video", "audio"}:
            source = attrs.get("src", "")
            if source and not source.startswith("data:"):
                self.external_resources.append(source)
        if tag == "link" and attrs.get("rel") == "stylesheet":
            href = attrs.get("href", "")
            if href and not href.startswith("data:"):
                self.external_resources.append(href)

    def handle_endtag(self, tag):
        if tag in {"script", "style", "pre"}:
            self.hidden = max(0, self.hidden - 1)
        if tag == "body":
            self.in_body = False

    def handle_data(self, data):
        if self.in_body and not self.hidden:
            self.visible_characters += len(data.strip())


def check(root=ROOT, restore_archives=False):
    root = Path(root).resolve()
    restored = []
    if restore_archives:
        source = regular(root, "research/next009/restore_evidence.py")
        if sha(source) != RESTORE_SHA:
            raise ValueError("FROZEN_RESTORE_HELPER_CHANGED")
        spec = importlib.util.spec_from_file_location("paper009_archive_restore", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for manifest in sorted((root / "evidence/next009/archives").glob("*.manifest.json")):
            restored.append(module.restore(manifest, root))
    inputs_path = regular(root, DOC + "/paper.inputs.json")
    build_path = regular(root, DOC + "/paper.build.json")
    qa_path = regular(root, DOC + "/PDF_QA.json")
    inputs, build, qa = read(inputs_path), read(build_path), read(qa_path)
    if type(inputs) is not dict or type(build) is not dict or type(qa) is not dict:
        raise ValueError("PAPER_RECEIPT_OBJECTS_REQUIRED")
    commit = inputs.get("evidence_commit")
    if type(commit) is not str or re.fullmatch("[0-9a-f]{40}", commit) is None or build.get("evidence_commit") != commit:
        raise ValueError("IMMUTABLE_PAPER_EVIDENCE_COMMIT_REQUIRED")
    if build.get("inputs_sha256") != sha(inputs_path):
        raise ValueError("PAPER_INPUT_MANIFEST_BINDING")
    files = inputs.get("files")
    if type(files) is not dict or not REQUIRED_INPUTS <= set(files) or not len(files) <= 256:
        raise ValueError("COMPLETE_PAPER_EVIDENCE_INPUTS_REQUIRED")
    observed = {}
    for name, expected in files.items():
        path = regular(root, name)
        if not hash_string(expected) or sha(path) != expected:
            raise ValueError("PAPER_INPUT_CHANGED:" + name)
        observed[name] = expected
    outputs = build.get("outputs")
    if type(outputs) is not dict or set(outputs) != OUTPUTS:
        raise ValueError("COMPLETE_PAPER_OUTPUT_SET_REQUIRED")
    for name, expected in outputs.items():
        path = regular(root, DOC + "/" + name)
        if not hash_string(expected) or sha(path) != expected:
            raise ValueError("PAPER_OUTPUT_CHANGED:" + name)
        observed[DOC + "/" + name] = expected
    pdf = regular(root, DOC + "/paper.pdf")
    if not pdf.read_bytes().startswith(b"%PDF-"):
        raise ValueError("PDF_DOCUMENT_REQUIRED")
    if qa.get("schema") != "agi-alpha/next009-pdf-visual-qa/v1":
        raise ValueError("SEPARATE_PDF_QA_SCHEMA_REQUIRED")
    if qa.get("pdf_sha256") != outputs["paper.pdf"] or qa.get("source_sha256") != outputs["paper.tex"]:
        raise ValueError("PDF_QA_MUST_BIND_CURRENT_PDF_AND_TEX")
    count = qa.get("page_count")
    inspected = qa.get("inspected_pages")
    if type(count) is not int or not 1 <= count <= 1000 or type(inspected) is not list or any(type(p) is not int for p in inspected) or inspected != list(range(1, count + 1)):
        raise ValueError("EVERY_PDF_PAGE_MUST_HAVE_RECORDED_INSPECTION")
    if qa.get("accepted") is not True or type(qa.get("render_tool")) is not str or not qa["render_tool"].strip():
        raise ValueError("COMPLETED_ACCEPTED_RENDERED_PDF_QA_REQUIRED")
    if str(qa.get("status", "")).upper() in {"PENDING", "UNKNOWN", "UNINSPECTED", "REJECTED"}:
        raise ValueError("PENDING_OR_REJECTED_PDF_QA_IS_NOT_A_PASS")
    pdfinfo = shutil.which("pdfinfo")
    if pdfinfo is None:
        raise ValueError("PDFINFO_REQUIRED_FOR_ACTUAL_PAGE_COUNT")
    info = subprocess.check_output([pdfinfo, str(pdf)], text=True, timeout=15)
    actual_pages = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    if actual_pages is None or int(actual_pages.group(1)) != count:
        raise ValueError("ACTUAL_PDF_PAGE_COUNT_DISAGREES_WITH_QA")
    version = subprocess.run([pdfinfo, "-v"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, check=True, timeout=10).stdout.splitlines()[0]
    html = regular(root, DOC + "/paper.html").read_text()
    parser = ReadingEdition()
    parser.feed(html)
    if not re.search(r"<html\b", html, re.IGNORECASE) or parser.headings < 3 or parser.paragraphs < 8 or parser.visible_characters < 2000 or parser.external_resources:
        raise ValueError("SELF_CONTAINED_RENDERED_READING_EDITION_REQUIRED")
    observed[DOC + "/paper.inputs.json"] = sha(inputs_path)
    observed[DOC + "/paper.build.json"] = sha(build_path)
    observed[DOC + "/PDF_QA.json"] = sha(qa_path)
    for name, expected in observed.items():
        if sha(regular(root, name)) != expected:
            raise ValueError("PAPER_BINDING_CHANGED_DURING_CHECK:" + name)
    return {"schema": "agi-alpha/next009-paper-binding-check/v1", "accepted": True,
            "evidence_commit": commit, "evidence_files_checked": len(files),
            "outputs": outputs, "page_count": count, "inspected_pages": inspected,
            "pdf_qa_sha256": sha(qa_path), "pdfinfo_version": version,
            "actual_pdf_page_count_checked": True, "build_inspection_status": build.get("visual_inspection"),
            "separate_qa_required_and_accepted": True,
            "reading_edition": {"headings": parser.headings, "paragraphs": parser.paragraphs,
                                "visible_characters": parser.visible_characters, "external_resources": parser.external_resources},
            "archive_restoration": restored, "files": observed,
            "scope": "Mechanical evidence/output identity, actual PDF page count, complete declared visual-inspection coverage and basic rendered-reading structure. This checker does not itself perform visual inspection, certify scientific/commercial conclusions, or convert pending rendering into accepted QA."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore-archives", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("FRESH_PAPER_CHECK_OUTPUT_REQUIRED")
    error = None
    try:
        report = check(args.root, args.restore_archives)
    except Exception as caught:
        error = caught
        report = {"schema": "agi-alpha/next009-paper-binding-check/v1", "accepted": False,
                  "error": {"type": type(caught).__name__, "message": str(caught)},
                  "scope": "Missing, pending or failed paper/QA bindings are not accepted."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"accepted": report["accepted"], "output": str(args.output), "error": report.get("error")}))
    return 0 if error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
