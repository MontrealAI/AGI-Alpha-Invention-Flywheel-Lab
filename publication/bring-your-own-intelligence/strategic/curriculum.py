# SPDX-License-Identifier: Apache-2.0
"""Generate small, separate bilingual training and development transcripts."""

import argparse
from itertools import product
import json
from pathlib import Path
import random

from protocols import EVENTS, FAMILIES, validate


ROLES = {
    "en": {"leader": "the Leader", "follower": "the Follower", "referee": "the Referee"},
    "fr": {"leader": "le Chef", "follower": "le Répondant", "referee": "l’Arbitre"},
}
ACTIONS = {
    "en": {
        "private_signaling": ("records the hidden state", "sends the cue", "makes the final move"),
        "public_offer": ("sets the initial quote", "reads out the disclosure", "makes the binding response"),
    },
    "fr": {
        "private_signaling": ("fixe l’état caché", "envoie le signal", "joue le coup final"),
        "public_offer": ("fixe le prix initial", "communique l’avis", "donne la réponse définitive"),
    },
}


def record(family, kind):
    row = {"order": list(EVENTS), "actors": ["leader", "referee", "follower"],
           "access": [family == "public_offer", True], "irrevocable": True}
    if kind == "late":
        row["order"] = ["commit", "choose", "signal"]
        row["access"] = [False, False]
    elif kind == "early":
        row["order"] = ["signal", "commit", "choose"]
    elif kind == "revision":
        row["irrevocable"] = False
    elif kind == "other_actor":
        row["actors"][1] = "leader"
    elif kind == "different_audience":
        row["access"] = [True, False]
    elif kind == "omitted_commitment":
        row["irrevocable"] = None
    elif kind == "omitted_audience":
        row["access"][0] = None
    elif kind == "omitted_order":
        row["order"] = None
        row["access"] = [None, None]
    return validate(row)


def render(family, lang, gold, index, development):
    actors = ROLES[lang]
    clauses = {event: f"{actors[actor]} {action}" for event, actor, action in
               zip(EVENTS, gold["actors"], ACTIONS[lang][family])}
    order = gold["order"]
    if order is None:
        phrase = {
            (False, "en"): "The committee notes these assignments without specifying their sequence: ",
            (False, "fr"): "Le comité indique les attributions sans préciser leur chronologie : ",
            (True, "en"): "The timeline was omitted from a file listing the duties as follows: ",
            (True, "fr"): "Le procès-verbal omet le déroulement, tout en consignant les rôles : ",
        }[development, lang]
        text = phrase + ", ".join(clauses.values()) + "."
    elif development:
        earliest, middle, latest = (clauses[event] for event in order)
        text = (f"Although the notes first mention that {latest}, this follows the episode in which {middle}. "
                f"Before both of those moments, {earliest}." if lang == "en" else
                f"Bien que le compte rendu commence lorsque {latest}, cet acte suit le moment où {middle}. "
                f"Plus tôt que ces deux épisodes, {earliest}.")
    elif index % 2:
        first, second, third = (clauses[event] for event in order)
        text = (f"Initially {first}; afterwards {second}; finally {third}." if lang == "en" else
                f"Au début {first}, puis {second}, et enfin {third}.")
    else:
        first, second, third = (clauses[event] for event in order)
        text = (f"First {first}. Next {second}. Only later {third}." if lang == "en" else
                f"D’abord {first}. Ensuite {second}. Plus tard {third}.")
    if gold["order"] != ["commit", "choose", "signal"]:
        for role, seen in zip(("leader", "follower"), gold["access"]):
            if seen is None:
                continue
            if lang == "en":
                text += f" Before the final response, {actors[role]} " + ("has access to the signal." if seen else "has no access to the signal.")
            else:
                text += f" Avant la réponse finale, {actors[role]} " + ("reçoit le signal." if seen else "ne reçoit pas le signal.")
    locked = gold["irrevocable"]
    if locked is not None:
        if lang == "en":
            text += (" The initial commitment is binding and cannot be changed before the response." if locked else
                     " The rules allow replacement of the initial commitment before the final choice.")
        else:
            text += (" L’engagement ne peut plus être changé avant la réponse." if locked else
                     " Le règlement permet de modifier l’engagement avant le choix final.")
    return text


def samples(development):
    stage = "dev" if development else "train"
    rng = random.Random(84137 if development else 203051)
    kinds = (["compatible", "early", "omitted_order"] if development else
             ["compatible"] * 3 + ["late", "early", "revision", "other_actor",
                                   "different_audience", "omitted_commitment", "omitted_audience", "omitted_order"])
    rows = []
    for family, lang in product(FAMILIES, ("en", "fr")):
        for i, kind in enumerate(kinds):
            gold = record(family, kind)
            brief = render(family, lang, gold, i, development)
            # Vary canonical examples without introducing labels.
            if not development and i == 2:
                brief = ("The minutes state the following. " if lang == "en" else "Voici le procès-verbal. ") + brief
            ident = f"{stage}-{family}-{lang}-{i + 1:02d}"
            rows.append({"case": {"id": ident, "lang": lang, "family": family, "brief": brief}, "record": gold})
    rng.shuffle(rows)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True)
    for name, development in (("train", False), ("development", True)):
        rows = samples(development)
        texts = {row["case"]["brief"] for row in rows}
        if len(texts) != len(rows):
            raise ValueError(f"Duplicate prose in {name}")
        with (args.output / f"{name}.json").open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
