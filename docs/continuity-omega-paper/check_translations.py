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


def check_source_pair(english, french):
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
            "propositions": en["environments"]["proposition"]}


def check_claim_pair(english, french):
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
    counts["documentation_pairs"] = len(PAIRS)
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
    probes = (
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
    parser.add_argument("--self-test", action="store_true", help="Check four deliberate translation regressions / tester quatre altérations volontaires")
    args = parser.parse_args()
    result = {"status": "STRUCTURAL_LANGUAGE_PARITY_PASSED", **check(),
              "scope_en": "Structural checks preserve mathematical expressions, evidence identities, claim statuses and claim numeric literals. Editorial review is still needed for meaning.",
              "scope_fr": "Les contrôles structurels préservent les expressions mathématiques, les identités des preuves, les statuts et les valeurs numériques des affirmations. Le sens exige une révision éditoriale."}
    if args.self_test:
        result["rejected_mutations"] = self_test()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        raise SystemExit(f"Language check failed / contrôle linguistique échoué: {error}")
