#!/usr/bin/env python3
"""Check the same release facts using conventional XPath and exact case phrases."""

import argparse
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from lxml.html import document_fromstring


PAGES = {"en": "index.html", "fr": "fr.html"}
SMALL = {"en": {4: "Four", 6: "Six"}, "fr": {4: "quatre", 6: "six"}}


def unique(values):
    if len(values) != 1:
        raise ValueError("ambiguous XPath match")
    return values[0]


def fmt(value, language, grouping=False):
    text = f"{value:,}" if grouping else str(value)
    if language == "fr":
        text = text.replace(",", " ").replace(".", ",")
    return text.replace("-", "−")


def ordinary_game(page, language, sources):
    initial = sources["example-verification.json"]
    mission = sources["game-receipt.json"]
    evaluation = mission["evaluation"]
    template = unique(page.xpath("//template[@id='mission-public-runs']"))
    story = unique([item[language] for item in json.loads(template.text_content())
                    if item["capability"]["id"] == "game-theory-verified-strategic-allocation"])
    value = Decimal(initial["lower_numerator"]) / initial["denominator"]
    randomized = fmt(value, language)
    nominal = fmt(mission["example"]["nominal_policy_worst_case"], language)
    held = evaluation["candidate_qualified"]
    written_held = SMALL[language].get(held, str(held))
    pairs = fmt(max(case["implicit_pairs"] for case in evaluation["cases"]), language, grouping=True)
    if language == "en":
        expected = {
            "randomized-guarantee": f"randomizing guarantees {randomized} versus a ",
            "nominal-worst-case": f" versus a {nominal} worst case",
            "held-games": f". {written_held} independently authored test games",
            "max-pure-pairs": f"including one with {pairs} possible action pairs",
        }
    else:
        expected = {
            "randomized-guarantee": f"la stratégie aléatoire garantit {randomized}, contre ",
            "nominal-worst-case": f", contre {nominal} dans le pire cas",
            "held-games": f". Les {written_held} jeux d’essai conçus indépendamment",
            "max-pure-pairs": f"dont un comportant {pairs} paires d’actions possibles",
        }
    return [(identity, story, phrase) for identity, phrase in expected.items()]


def ordinary_opportunity(page, language, sources):
    radar = unique(page.xpath("//article[@data-opportunity='nisar-l2-quebec']")).text_content()
    translate = unique(page.xpath("//article[@data-opportunity='hy-mt3-q4']")).text_content()
    sites = sources["radar-control.json"]["sites"]
    montreal = sites["montreal"]["nisar"]
    quebec = sites["quebec-city"]["nisar"]
    fresh = sources["hy-mt3.json"]
    prior = sources["hy-mt2.json"]
    new_passes, old_passes = (sum(source["anchor_pass_by_use"].values()) for source in (fresh, prior))
    new_total, old_total = (len(source["rows"]) for source in (fresh, prior))
    m, q = montreal["query_hits"], quebec["query_hits"]
    m_early, q_early = (record["reference_before_window"] for record in (montreal, quebec))
    m_word = SMALL[language].get(m_early, str(m_early))
    q_word = SMALL[language].get(q_early, str(q_early))
    if language == "en":
        radar_phrases = (f"shortlists cover {m} Montréal", f"Montréal and {q} Québec City catalog",
                         f". {m_word} reference acquisitions at each point",
                         f". {q_word} reference acquisitions at each point")
        translation_phrases = (f"names and numbers in {new_passes}/", f"names and numbers in {new_passes}/{new_total} passages",
                               f"previous model preserved them in {old_passes}/",
                               f"previous model preserved them in {old_passes}/{old_total}.")
    else:
        radar_phrases = (f"repéré {m} produits à Montréal", f"Montréal et {q} à Québec.",
                         f"À chaque point, {m_word} acquisitions de référence",
                         f"À chaque point, {q_word} acquisitions de référence")
        translation_phrases = (f"noms et les chiffres attendus dans {new_passes} passages sur ",
                               f"dans {new_passes} passages sur {new_total}, contre ",
                               f"contre {old_passes} sur {old_total} pour le",
                               f"contre {old_passes} sur {old_total} pour le modèle précédent")
    keys = ("montreal-records", "quebec-records", "montreal-early-reference", "quebec-early-reference",
            "new-model-anchors", "new-model-denominator", "prior-model-anchors", "prior-model-denominator")
    return [(identity, section, phrase) for identity, section, phrase in zip(
        keys, (radar,) * 4 + (translate,) * 4, radar_phrases + translation_phrases, strict=True
    )]


def assess(plan, directory):
    evidence = {}
    for name, expected in plan["evidence_sha256"].items():
        raw = (directory / name).read_bytes()
        if sha256(raw).hexdigest() != expected:
            raise ValueError("source receipt mismatch")
        evidence[name] = json.loads(raw)
    actions = {"game": ordinary_game, "opportunity": ordinary_opportunity}
    claims = []
    page_sha256 = {}
    for language, filename in PAGES.items():
        raw = (directory / filename).read_bytes()
        page_sha256[language] = sha256(raw).hexdigest()
        page = document_fromstring(raw.decode("utf-8"))
        if page.get("lang") != language:
            raise ValueError("unexpected document language")
        for identity, text, phrase in actions[plan["job"]](page, language, evidence):
            normalized = " ".join(text.split()).casefold()
            occurrence = normalized.count(phrase.casefold())
            claims.append({"id": identity, "language": language, "rendered_witness": phrase if occurrence == 1 else None,
                           "decision": "PASS" if occurrence == 1 else "HOLD"})
    return {"claims": claims, "decision": "PASS" if all(r["decision"] == "PASS" for r in claims) else "HOLD",
            "evidence_sha256": plan["evidence_sha256"], "page_sha256": page_sha256}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.plan.read_bytes())
        output = assess(plan, args.evidence_directory)
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, OSError) as error:
        output = {"decision": "HOLD", "reason": str(error)}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    raise SystemExit(output["decision"] != "PASS")
