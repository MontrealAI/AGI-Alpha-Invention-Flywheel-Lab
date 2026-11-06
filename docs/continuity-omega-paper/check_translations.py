#!/usr/bin/env python3
"""Check structural EN/FR parity, not semantic translation quality.

Vérifier la parité structurelle EN/FR, sans prétendre certifier la traduction.
The separate editorial review covers meaning, terminology and layout.
La révision éditoriale distincte porte sur le sens, la terminologie et la mise en page.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PAIRS = ("README", "REVIEW", "SOURCE_MAP", "EVIDENCE")
EDITION = "1.1.1"
TITLES = {"en": "CONTINUITY", "fr": "CONTINUITÉ"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def math_signature(text):
    # Explicit thousands grouping has the same numeric value in EN and FR.
    text = re.sub(r"(?<=\d)\{,\}(?=\d{3}(?:\D|$))", "", text)
    return re.sub(r"(?<=\d)\\,(?=\d{3}(?:\D|$))", "", text)


def structural_signature(source):
    """Quantities are checked in math; translated prose still needs review."""
    envs = Counter(re.findall(r"\\begin\{([^}]+)\}", source))
    return {
        "labels": re.findall(r"\\label\{([^}]+)\}", source),
        "bibliography": re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", source),
        "citations": Counter(key.strip() for group in re.findall(r"\\cite(?:\[[^\]]*\])*\{([^}]+)\}", source) for key in group.split(",")),
        "headings": Counter(re.findall(r"\\(section|subsection|subsubsection)(\*?)\{", source)),
        "environments": {key: envs[key] for key in ("proposition", "proof", "definition", "equation", "tabularx", "longtable", "tikzpicture")},
        "source_hashes": Counter(re.findall(r"\b[0-9a-f]{40,64}\b", source)),
        "inline_math": [math_signature(text) for text in re.findall(r"(?<!\\)\$(?!\$)(.*?)(?<!\\)\$", source)],
        "source_urls": re.findall(r"\\url\{([^}]+)\}", source),
        "code_identifiers": re.findall(r"\\texttt\{([^}]+)\}", source),
        "list_items": len(re.findall(r"\\item\b", source)),
        "table_rows": [len(re.findall(r"\\\\", body)) for _, body in re.findall(r"\\begin\{(tabularx|longtable)\}(.*?)\\end\{\1\}", source, re.S)],
        "equations": [re.sub(r"\s+", "", re.sub(r"\\text\{[^{}]*\}", r"\\text{LOCALIZED}", text)) for text in re.findall(r"\\begin\{equation\}(.*?)\\end\{equation\}", source, re.S)],
    }


def check_current_title(source, language):
    """Guard the current title while preserving authentic cited historical titles."""
    title = TITLES[language]
    slots = {
        "cover": r"\bfseries " + title + r"}\par",
        "running header": r"\fancyhead[L]{\sffamily\small\color{muted}" + title + r" $\Omega$}",
        "body macro": r"\newcommand{\om}{" + title + r" $\Omega$}",
        "PDF metadata": r"pdftitle={" + title + r" \unichar{937}",
    }
    for label, expected in slots.items():
        require(expected in source, f"Localized {language} title missing in {label} / titre localisé absent: {label}")
    series_label = "INTELLIGENCE TRANSFORMATIONNELLE" if language == "fr" else "TRANSFORMATIONAL INTELLIGENCE"
    series_slots = {
        "cover series label": r"\hfill " + series_label + r" $\infty$}\par",
        "running footer label": r"\fancyfoot[L]{\sffamily\scriptsize\color{muted}" + series_label + r" $\infty$}",
    }
    for label, expected in series_slots.items():
        require(expected in source, f"Localized {language} display label missing in {label} / libellé localisé absent: {label}")
    edition_labels = {
        "en": ("RESEARCH EDITION ", "Research edition ", "Bilingual edition "),
        "fr": ("ÉDITION DE RECHERCHE ", "Édition de recherche ", "Édition bilingue "),
    }
    for label in edition_labels[language]:
        require(re.search(re.escape(label + EDITION) + r"(?=[}.])", source) is not None,
                "Exact current edition missing / édition courante exacte absente: " + label)
    if language == "fr":
        current = source.split(r"\begin{thebibliography}", 1)[0]
        require(re.search(r"\bCONTINUITY\b", current) is None,
                "English title remains in current French manuscript / titre anglais restant dans l’article français courant")
    return len(slots)


def check_source_pair(english, french):
    check_current_title(english, "en")
    check_current_title(french, "fr")
    en, fr = structural_signature(english), structural_signature(french)
    for key in en:
        require(en[key] == fr[key], f"EN/FR manuscript mismatch / écart entre les articles: {key}")
    require("pdflang={en}" in english, "English PDF language metadata missing / langue du PDF anglais absente")
    require(re.search(r"pdflang=\{fr(?:-CA)?\}", french) is not None,
            "French PDF language metadata missing / langue du PDF français absente")
    return {"labels": len(en["labels"]), "references": len(en["bibliography"]),
            "display_equations": len(en["equations"]), "inline_math": len(en["inline_math"]),
            "source_urls": len(en["source_urls"]), "code_identifiers": len(en["code_identifiers"]),
            "list_items": en["list_items"], "table_rows": sum(en["table_rows"]),
            "propositions": en["environments"]["proposition"], "localized_title_slots": 8,
            "localized_series_label_slots": 4,
            "current_edition_slots": 6}


def check_claim_pair(english, french):
    require(english.get("edition") == EDITION and french.get("edition") == EDITION,
            "Current claim-register edition required / édition courante des registres requise")
    for language, record in (("en", english), ("fr", french)):
        require(isinstance(record.get("title"), str) and record["title"].startswith(TITLES[language] + " Ω"),
                "Localized claim-register title required / titre localisé du registre requis: " + language)
    for key in ("schema_version", "edition", "reviewed_on", "sources"):
        require(english.get(key) == french.get(key), f"Claim-register identity mismatch / écart du registre: {key}")
    require(english.get("language") == "en" and french.get("language") == "fr",
            "Claim-register languages must be en/fr / langues des registres incorrectes")
    require(english["status_definitions"].keys() == french["status_definitions"].keys(),
            "Status-token mismatch / écart des codes de statut")
    require(len(english["claims"]) == len(french["claims"]), "Claim count mismatch / nombre d'affirmations différent")
    for en, fr in zip(english["claims"], french["claims"]):
        require(en.keys() == fr.keys(), f"Claim fields differ / champs différents: {en.get('id')}")
        for key in ("id", "status", "source"):
            require(en[key] == fr[key], f"Protected claim field changed / champ protégé modifié: {en['id']}.{key}")
        for key in ("text", "evidence", "limits"):
            require(isinstance(fr[key], str) and bool(fr[key].strip()), f"Missing French claim prose / texte français absent: {en['id']}.{key}")
            # Claim prose deliberately retains the original literal number format.
            # Compare each field in order, rather than pooling unrelated claims.
            numbers = r"\d+(?:[.,]\d+)*"
            require(re.findall(numbers, en[key]) == re.findall(numbers, fr[key]),
                    f"Claim numeric literals changed / valeurs numériques modifiées: {en['id']}.{key}")
        for key in ("text", "evidence", "limits"):
            pattern = r"\b[0-9a-f]{40,64}\b|\beq:[A-Za-z]+\b|\b(?:PASS_SYNTHETIC_ONLY|TIE|HOLD|NO DEPLOY|NOT_ESTABLISHED)\b"
            require(Counter(re.findall(pattern, en[key])) == Counter(re.findall(pattern, fr[key])),
                    f"Protected evidence token changed / identifiant probant modifié: {en['id']}.{key}")
    return len(english["claims"])


def check(root=ROOT):
    sources = [(root / name).read_text(encoding="utf-8") for name in ("CONTINUITY_OMEGA.tex", "CONTINUITY_OMEGA_FR.tex")]
    counts = check_source_pair(*sources)
    claims = [json.loads((root / name).read_text(encoding="utf-8")) for name in ("CLAIMS.json", "CLAIMS.fr.json")]
    counts["claims"] = check_claim_pair(*claims)
    for stem in PAIRS:
        for suffix, other in ((".md", ".fr.md"), (".fr.md", ".md")):
            body = (root / (stem + suffix)).read_text(encoding="utf-8")
            require(stem + other in body, f"Missing reciprocal language link / lien réciproque absent: {stem + suffix}")
    for language, suffix in (("en", ""), ("fr", ".fr")):
        guide = (root / ("README" + suffix + ".md")).read_text(encoding="utf-8")
        citation = (root / ("CITATION" + suffix + ".cff")).read_text(encoding="utf-8")
        require(guide.startswith("# " + TITLES[language] + " Ω\n"),
                "Localized entry-guide title required / titre localisé du guide requis: " + language)
        require('title: "' + TITLES[language] + " Ω" in citation and "version: " + EDITION in citation,
                "Localized citation title/current edition required / titre de citation localisé et édition courante requis: " + language)
    counts["documentation_pairs"] = len(PAIRS)
    counts["localized_metadata_titles"] = 6
    return counts


def self_test():
    english = (ROOT / "CONTINUITY_OMEGA.tex").read_text(encoding="utf-8")
    french = (ROOT / "CONTINUITY_OMEGA_FR.tex").read_text(encoding="utf-8")
    en = json.loads((ROOT / "CLAIMS.json").read_text())
    fr = json.loads((ROOT / "CLAIMS.fr.json").read_text())
    check_source_pair(english, french)
    check_claim_pair(en, fr)
    altered = json.loads(json.dumps(fr))
    altered["claims"][0]["status"] = "not-established"
    altered_number = json.loads(json.dumps(fr))
    claim = next(item for item in altered_number["claims"] if item["id"] == "R01")
    require("29" in claim["text"], "Numeric mutation target missing / cible numérique absente")
    claim["text"] = claim["text"].replace("29", "290", 1)
    altered_title = json.loads(json.dumps(fr))
    altered_title["title"] = altered_title["title"].replace("CONTINUITÉ", "CONTINUITY", 1)
    probes = (
        ("untranslated French cover title", lambda: check_source_pair(english, french.replace(r"\bfseries CONTINUITÉ}\par", r"\bfseries CONTINUITY}\par", 1))),
        ("untranslated French running title", lambda: check_source_pair(english, french.replace(r"\color{muted}CONTINUITÉ $\Omega$", r"\color{muted}CONTINUITY $\Omega$", 1))),
        ("untranslated French body title", lambda: check_source_pair(english, french.replace(r"\newcommand{\om}{CONTINUITÉ", r"\newcommand{\om}{CONTINUITY", 1))),
        ("untranslated French PDF title", lambda: check_source_pair(english, french.replace(r"pdftitle={CONTINUITÉ", r"pdftitle={CONTINUITY", 1))),
        ("untranslated French claim title", lambda: check_claim_pair(en, altered_title)),
        ("untranslated French cover series label", lambda: check_source_pair(english, french.replace(r"\hfill INTELLIGENCE TRANSFORMATIONNELLE", r"\hfill TRANSFORMATIONAL INTELLIGENCE", 1))),
        ("untranslated French running footer label", lambda: check_source_pair(english, french.replace(r"\color{muted}INTELLIGENCE TRANSFORMATIONNELLE", r"\color{muted}TRANSFORMATIONAL INTELLIGENCE", 1))),
        ("stale English cover edition", lambda: check_source_pair(english.replace("RESEARCH EDITION " + EDITION, "RESEARCH EDITION 1.1", 1), french)),
        ("stale French running edition", lambda: check_source_pair(english, french.replace("Édition de recherche " + EDITION, "Édition de recherche 1.1.0", 1))),
        ("missing French proposition", lambda: check_source_pair(english, french.replace("\\begin{proposition}", "\\begin{definition}", 1))),
        ("altered capacity inequality", lambda: check_source_pair(english, french.replace("\\left\\lfloor\\frac{C}{q}\\right\\rfloor", "\\left\\lfloor\\frac{C}{q+1}\\right\\rfloor", 1))),
        ("altered claim status", lambda: check_claim_pair(en, altered)),
        ("altered claim numeric literal", lambda: check_claim_pair(en, altered_number)),
    )
    for label, probe in probes:
        try:
            probe()
        except ValueError:
            continue
        raise ValueError(f"Mutation was not rejected / mutation non rejetée: {label}")
    return [label for label, _ in probes]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="Reject title, mathematics and evidence regressions / rejeter les régressions de titre, mathématiques et preuves")
    args = parser.parse_args()
    result = {"status": "STRUCTURAL_LANGUAGE_PARITY_PASSED", **check(),
              "scope_en": "Structural checks enforce localized current titles and preserve mathematical expressions, evidence identities, claim statuses and claim numeric literals. Editorial review is still needed for meaning.",
              "scope_fr": "Les contrôles structurels imposent les titres courants localisés et préservent les expressions mathématiques, les identités des preuves, les statuts et les valeurs numériques des affirmations. Le sens exige une révision éditoriale."}
    if args.self_test:
        result["rejected_mutations"] = self_test()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(f"Language check failed / contrôle linguistique échoué: {error}")
