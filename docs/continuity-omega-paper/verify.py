#!/usr/bin/env python3
"""Check local publication identity, recorded scope, and authored arithmetic.

This does not rerun the source prototypes, authenticate their inputs, certify
cyber resilience, or establish demand, revenue, or independent assessment.
Python's standard library and Poppler's pdfinfo/pdftotext are sufficient.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import unicodedata


ROOT = Path(__file__).resolve().parent
CANONICAL_PDF = "CONTINUITY_OMEGA.pdf"
LANGUAGE_FILES = {
    "en": ("CONTINUITY_OMEGA.pdf", "CONTINUITY_OMEGA.tex"),
    "fr": ("CONTINUITY_OMEGA_FR.pdf", "CONTINUITY_OMEGA_FR.tex"),
}
SOURCE_COMMITS = {
    "pr277": "84c4288b4726a17a90f8462d1d6faf8b5f8f00b5",
    "pr278": "a755d0375693465f8f31c0c919cc186eae74bbcc",
}
EXPECTED_SCOPE = (
    "Pinned, supplied Git source bytes; offline and synthetic only; separate "
    "checker code under shared authorship; no LLM invocation, production "
    "recovery, physical output, commerce, or third-party certification."
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_object(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read JSON from {path.name}: {error}") from error
    require(isinstance(value, dict), f"{path.name} must contain a JSON object")
    return value


def sha256(path):
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def excluded(relative):
    return (
        relative == "PUBLICATION.json"
        or "build" in PurePosixPath(relative).parts
        or "__pycache__" in PurePosixPath(relative).parts
        or relative.endswith((".pyc", ".pyo"))
    )


def check_manifest(manifest):
    require(manifest.get("edition") == "1.1.1", "Expected bilingual publication edition 1.1.1 / édition bilingue attendue: 1.1.1")
    require(manifest.get("title", "").startswith("CONTINUITY Ω") and manifest.get("title_fr", "").startswith("CONTINUITÉ Ω"),
            "Localized publication titles required / titres localisés de publication requis")
    pages = manifest.get("pages")
    require(type(pages) is int and pages > 0, "Manifest pages must be a positive integer")
    files = manifest.get("files")
    require(isinstance(files, dict) and bool(files), "Manifest files must be a nonempty path-to-SHA-256 object")
    required = {
        CANONICAL_PDF, "CONTINUITY_OMEGA.tex", "verify.py", "pooling_example.py",
        "evidence/REPRODUCTION.json", "evidence/POOLING.json",
        "CONTINUITY_OMEGA_FR.pdf", "CONTINUITY_OMEGA_FR.tex", "check_translations.py",
        "README.fr.md", "REVIEW.fr.md", "SOURCE_MAP.fr.md", "CLAIMS.fr.json", "TRANSLATION.md",
        "EVIDENCE.md", "EVIDENCE.fr.md", "CITATION.fr.cff",
    }
    require(required <= files.keys(), f"Manifest omits required files: {sorted(required - files.keys())}")
    for relative, expected in files.items():
        require(isinstance(relative, str), "Every manifest path must be a string")
        path = PurePosixPath(relative)
        require(
            bool(relative) and not path.is_absolute() and ".." not in path.parts
            and "\\" not in relative and path.as_posix() == relative,
            f"Manifest path is not a canonical package-relative path: {relative!r}",
        )
        require(not excluded(relative), f"Manifest includes an excluded artifact: {relative}")
        require(
            isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected),
            f"Invalid SHA-256 for {relative}",
        )
        actual_path = (ROOT / relative).resolve()
        require(actual_path.is_relative_to(ROOT), f"Manifest path escapes the publication directory: {relative}")
        require(actual_path.is_file(), f"Manifest file is missing: {relative}")
        require(sha256(actual_path) == expected, f"SHA-256 mismatch: {relative}")
    actual_files = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file() and not excluded(path.relative_to(ROOT).as_posix())
    }
    require(
        actual_files == files.keys(),
        f"Manifest inventory differs: unlisted={sorted(actual_files - files.keys())}; "
        f"missing={sorted(files.keys() - actual_files)}",
    )
    require(
        manifest.get("pdf_sha256") == files[CANONICAL_PDF],
        "Manifest pdf_sha256 does not match its canonical PDF file entry",
    )
    languages = manifest.get("languages")
    require(isinstance(languages, dict) and set(languages) == set(LANGUAGE_FILES), "Expected complete en/fr language inventory")
    for language, (pdf_name, source_name) in LANGUAGE_FILES.items():
        entry = languages[language]
        require(isinstance(entry, dict), f"Missing language metadata: {language}")
        require(entry.get("pdf") == pdf_name and entry.get("source") == source_name, f"Wrong language filenames: {language}")
        require(type(entry.get("pages")) is int and entry["pages"] > 0, f"Invalid page count: {language}")
        require(entry.get("pdf_sha256") == files[pdf_name], f"Language PDF hash differs: {language}")
        require(type(entry.get("pdf_bytes")) is int and entry["pdf_bytes"] == (ROOT / pdf_name).stat().st_size, f"Language PDF size differs: {language}")
    require(manifest["pages"] == languages["en"]["pages"] and manifest["pdf_sha256"] == languages["en"]["pdf_sha256"]
            and manifest["pdf_bytes"] == languages["en"]["pdf_bytes"], "English compatibility metadata differs")
    return len(files), languages


def run_tool(program, arguments):
    executable = shutil.which(program)
    require(executable is not None, f"Required command is unavailable: {program}")
    try:
        result = subprocess.run(
            [executable, *arguments], cwd=ROOT, capture_output=True,
            encoding="utf-8", env={**os.environ, "LC_ALL": "C"}, timeout=60,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as error:
        raise ValueError(f"Cannot run {program}: {error}") from error
    require(result.returncode == 0, f"{program} failed: {result.stderr.strip()}")
    return result.stdout


def check_pdf_title(pdf_name, language, expected_pages):
    title = "CONTINUITÉ" if language == "fr" else "CONTINUITY"
    series_label = "INTELLIGENCE TRANSFORMATIONNELLE ∞" if language == "fr" else "TRANSFORMATIONAL INTELLIGENCE ∞"
    info = unicodedata.normalize("NFKC", run_tool("pdfinfo", [str(ROOT / pdf_name)]))
    require(re.search(r"^Title:\s+" + re.escape(title + " Ω"), info, re.M) is not None,
            "Canonical PDF metadata title is not localized / titre PDF non localisé: " + language)
    extracted = unicodedata.normalize("NFKC", run_tool("pdftotext", ["-layout", "-enc", "UTF-8", str(ROOT / pdf_name), "-"]))
    pages = extracted.split("\f")
    if not pages[-1].strip():
        pages.pop()
    require(len(pages) == expected_pages, "Extracted PDF page inventory differs / nombre de pages extraites différent")
    require(re.search(r"\b" + title + r"\b", pages[0]) is not None and "Ω" in pages[0],
            "Canonical cover title is absent / titre de couverture absent: " + language)
    require(re.search(r"(?<![\d.])1\.1\.1(?![\d.])", pages[0]) is not None,
            "Canonical cover edition is stale / édition de couverture périmée: " + language)
    require(series_label in pages[0],
            "Canonical cover series label is not localized / libellé de série non localisé sur la couverture: " + language)
    if language == "fr":
        require(re.search(r"\bCONTINUITY\b", pages[0]) is None,
                "English main title on French cover / titre anglais sur la couverture française")
    for page_number, page in enumerate(pages[1:], 2):
        first_line = next((line.strip() for line in page.splitlines() if line.strip()), "")
        require(first_line.startswith(title + " Ω"),
                f"Running title is not localized / en-tête non localisé: {language}, PDF page {page_number}")
        require(first_line.endswith("1.1.1"),
                f"Running edition is stale / édition d’en-tête périmée: {language}, PDF page {page_number}")
        last_line = next((line.strip() for line in reversed(page.splitlines()) if line.strip()), "")
        require(last_line.startswith(series_label),
                f"Running footer label is not localized / libellé de pied de page non localisé: {language}, PDF page {page_number}")


def check_title_qa(manifest):
    record = manifest.get("title_correction_qa")
    require(isinstance(record, dict) and record.get("schema") == "continuity-omega-paper/title-correction-checks/v1"
            and record.get("edition") == "1.1.1", "Current title-correction QA missing / contrôle courant du titre absent")
    require(record.get("titles") == {"en": "CONTINUITY Ω", "fr": "CONTINUITÉ Ω"},
            "Current localized QA titles differ / titres localisés du contrôle différents")
    require(record.get("pdfs") == manifest["languages"], "Title QA PDF identities differ / identités PDF du contrôle différentes")
    historical = {
        "evidence/QA.json": "7b597bce9a04c5cc8c6fa0279cac7ec9b7d0655c2417ac3b351fffa866e9776d",
        "evidence/TRANSLATION_QA.json": "68779584c43a1c6972908d0fb01e4364b30b92a6144fdda9248a1de8bb236ac1",
        "evidence/REPRODUCTION.json": "ab0bf43dc3a08f8c343f847b2c2174b0a82fdc5655b5873d20cd7763c144184b",
        "evidence/COUNTEREXAMPLES.json": "2b62c84eb324dc4e2c60403be10d3b5c63c5324ff7622e74ce859663e64d1729",
        "evidence/POOLING.json": "29a181652556fa9461a82ece3e7fe7b2e5d33e643ff79dfd3f80ee0070ae023b",
    }
    require(record.get("preserved_historical_evidence") == historical,
            "Historical QA/evidence identity list differs / liste des identités historiques différente")
    require(all(manifest["files"].get(name) == expected for name, expected in historical.items()),
            "Historical QA/evidence bytes changed / octets des preuves historiques modifiés")
    require(record.get("live_deployment_verified") is False,
            "Local title QA must not claim live deployment / aucun déploiement ne doit être affirmé par ce contrôle local")


def check_pdf_pages(pdf_name, expected_pages):
    info = run_tool("pdfinfo", [str(ROOT / pdf_name)])
    match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    require(match is not None, "pdfinfo did not report the canonical PDF page count")
    require(int(match.group(1)) == expected_pages, "Canonical PDF page count differs from the manifest")


def require_boolean_vector(actual, expected, label):
    require(
        isinstance(actual, list) and all(type(value) is bool for value in actual)
        and actual == expected,
        f"Recorded {label} differs from the declared case vector",
    )


def check_reproduction(record):
    require(record.get("schema") == "continuity-omega-paper/reproduction/v1", "Unknown reproduction schema")
    require(record.get("source_bytes_unchanged") is True, "Recorded source-bytes-unchanged boundary is missing")
    require(record.get("reproduction_scope") == EXPECTED_SCOPE, "Recorded offline/synthetic scope has changed")
    tests = record.get("tests")
    require(isinstance(tests, dict), "Reproduction tests record is missing")
    for name, count in (("pr278", 29), ("pr277", 9)):
        suite = tests.get(name)
        require(isinstance(suite, dict), f"Missing {name} test record")
        require(type(suite.get("passed")) is int and suite["passed"] == count, f"Expected {count} recorded {name} passes")
        require(type(suite.get("failed")) is int and suite["failed"] == 0, f"Expected zero recorded {name} failures")
        require(suite.get("commit") == SOURCE_COMMITS[name], f"Recorded {name} source revision changed")
    require(type(tests.get("total_passed")) is int and tests["total_passed"] == 38, "Recorded total must be 38 distinct implementation tests")
    recovery = record.get("pr277")
    require(isinstance(recovery, dict), "Missing PR277 case record")
    require(type(recovery.get("fixture_count")) is int and recovery["fixture_count"] == 4, "Expected four recorded PR277 fixtures")
    vector = [True, False, False, False]
    require_boolean_vector(recovery.get("candidate_verdicts"), vector, "candidate decisions")
    require_boolean_vector(recovery.get("competent_comparator_verdicts"), vector, "competent conventional decisions")
    require(recovery.get("result") == "TIE; HOLD / NO DEPLOY", "Recorded conventional tie or no-deployment boundary changed")
    handoff = record.get("pr278")
    require(isinstance(handoff, dict), "Missing PR278 case record")
    require(type(handoff.get("demo_cases")) is int and handoff["demo_cases"] == 12, "Expected 12 recorded PR278 CLI cases")
    passing = handoff.get("pass_cases")
    rejected = handoff.get("rejected_cases")
    require(isinstance(passing, list) and all(isinstance(x, str) for x in passing), "Recorded pass_cases must be case names")
    require(isinstance(rejected, list) and all(isinstance(x, str) for x in rejected), "Recorded rejected_cases must be case names")
    require(
        len(passing) == 3 and set(passing) == {"nominal", "missing_from_restored", "extra_restored"},
        "Expected the three declared synthetic handoff passes",
    )
    require(
        len(rejected) == 9 and set(rejected) == {
            "tampered_source", "overbooked", "correlated_outage", "unqualified",
            "late", "buyer_declines", "uneconomic", "unapproved_sharing", "no_order_source",
        },
        "Expected the nine declared synthetic handoff refusals",
    )
    require(not set(passing) & set(rejected), "A CLI case is recorded as both passing and rejected")
    require(handoff.get("nominal_and_cli_verification") == "PASS_SYNTHETIC_ONLY", "Recorded nominal verification must retain its synthetic-only qualifier")


def check_pooling(record):
    spec = importlib.util.spec_from_file_location("continuity_publication_pooling", ROOT / "pooling_example.py")
    require(spec is not None and spec.loader is not None, "Cannot load pooling_example.py")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    expected = module.illustration()
    require(
        json.dumps(record, sort_keys=True) == json.dumps(expected, sort_keys=True),
        "Authored pooling illustration differs from evidence/POOLING.json",
    )


def check_tex_references(source_name):
    source = (ROOT / source_name).read_text(encoding="utf-8")
    citations = {
        key.strip()
        for group in re.findall(r"\\cite(?:\[[^\]]*\])*\{([^}]+)\}", source)
        for key in group.split(",")
    }
    bibliography = set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", source))
    labels = set(re.findall(r"\\label\{([^}]+)\}", source))
    references = set(re.findall(r"\\(?:ref|eqref|pageref)\{([^}]+)\}", source))
    require(citations <= bibliography, f"Undefined local citation keys: {sorted(citations - bibliography)}")
    require(references <= labels, f"Undefined local reference keys: {sorted(references - labels)}")


def check_build_text(pdf_name):
    rebuilt = ROOT / "build" / pdf_name
    require(rebuilt.is_file(), "Rebuilt PDF is missing; run python3 build.py first")
    texts = []
    for pdf in (ROOT / pdf_name, rebuilt):
        text = run_tool("pdftotext", ["-layout", "-enc", "UTF-8", str(pdf), "-"])
        require(bool(text.strip()), f"No manuscript text extracted from {pdf}")
        texts.append(" ".join(unicodedata.normalize("NFKC", text).split()))
    require(texts[0] == texts[1], "Rebuilt manuscript text differs from the canonical PDF (after Unicode/whitespace normalization)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-build", action="store_true", help="Compare rebuilt text for both languages / comparer le texte des deux PDF reconstruits")
    args = parser.parse_args()
    manifest = read_object(ROOT / "PUBLICATION.json")
    count, languages = check_manifest(manifest)
    check_title_qa(manifest)
    check_reproduction(read_object(ROOT / "evidence" / "REPRODUCTION.json"))
    check_pooling(read_object(ROOT / "evidence" / "POOLING.json"))
    for language, (pdf_name, source_name) in LANGUAGE_FILES.items():
        check_pdf_pages(pdf_name, languages[language]["pages"])
        check_pdf_title(pdf_name, language, languages[language]["pages"])
        check_tex_references(source_name)
        if args.check_build:
            check_build_text(pdf_name)
    from check_translations import check as check_translations
    parity = check_translations(ROOT)
    print(f"Publication consistency passed / cohérence vérifiée: edition 1.1.1, EN {languages['en']['pages']} pages, FR {languages['fr']['pages']} pages, {count} file hashes / empreintes.")
    print("Structural language parity / parité structurelle:", json.dumps(parity, sort_keys=True))
    print("Recorded evidence agrees: 29 + 9 implementation tests; four-case conventional tie; 12 supplied CLI cases (3 passes, 9 refusals).")
    print("Authored pooling arithmetic matches its record; local citation and reference keys resolve.")
    if args.check_build:
        print("Rebuilt and canonical PDF text agree after Unicode/whitespace normalization.")
    print("These are local consistency checks, not a source-prototype rerun, an external truth check, operational certification, or evidence of real commerce.")
    print("Ces contrôles établissent la cohérence locale, sans certifier la vérité externe, la résilience opérationnelle ou une activité commerciale réelle.")


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"Publication verification failed: {error}", file=sys.stderr)
        sys.exit(1)
