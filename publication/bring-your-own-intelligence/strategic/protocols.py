# SPDX-License-Identifier: Apache-2.0
"""A finite specification for evidence-gated strategic protocol formalization."""

from fractions import Fraction
from hashlib import file_digest
import json
from pathlib import Path
import sys


EVENTS = ("commit", "signal", "choose")
ACTORS = ("leader", "follower", "referee")
FAMILIES = ("private_signaling", "public_offer")
FIELDS = ("order", "actors", "access", "irrevocable")
PUBLICATION = Path(__file__).resolve().parents[2]
PRIOR = PUBLICATION / "evidence-bound" / "strategic"
sys.path.insert(0, str(PRIOR))
from game import Game, check, solve

TASK = """Extract a strategic protocol from the brief. Use only its facts. Return a single compact JSON object:
{"order":["commit","signal","choose"],"actors":["leader","referee","follower"],"access":[false,true],"irrevocable":true}
That example is one possible record, not a default. commit is the initial quote or fixed hidden choice, signal is the disclosure, choose is the final response. In order, list the three event IDs chronologically, or give null if a strict order is unresolved. actors lists the roles that perform commit, signal, choose in that ID order regardless of chronology. Use leader, follower, referee or null. French role names Chef, Répondant, Arbitre map to leader, follower, referee. access lists whether leader then follower see this signal before choose. Use true, false or null for missing facts. A signal not yet emitted cannot be seen. irrevocable is true only if the actor cannot revise the commitment before the final response, false if revision is allowed, null if unspecified. Infer only what is entailed. No prose outside the JSON."""


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def fingerprint(path):
    with Path(path).open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def single_case(case):
    if (not isinstance(case, dict) or set(case) != {"id", "lang", "family", "brief"}
            or not isinstance(case["id"], str) or not 1 <= len(case["id"]) <= 80
            or case["family"] not in FAMILIES or case["lang"] not in ("en", "fr")
            or not isinstance(case["brief"], str) or not 1 <= len(case["brief"]) <= 1800):
        raise ValueError("Invalid input brief")
    return case


def validate(record):
    if not isinstance(record, dict) or set(record) != set(FIELDS):
        raise ValueError("All four strategic fields must be present")
    order = record["order"]
    if order is not None and (not isinstance(order, list) or sorted(order, key=str) != sorted(EVENTS)):
        raise ValueError("Event order must list all three event IDs once or be null")
    actors = record["actors"]
    if not isinstance(actors, list) or len(actors) != 3 or any(actor not in (*ACTORS, None) for actor in actors):
        raise ValueError("Each event needs a declared actor or null")
    access = record["access"]
    if not isinstance(access, list) or len(access) != 2 or any(type(v) not in (bool, type(None)) for v in access):
        raise ValueError("Two observation facts must be boolean or null")
    if type(record["irrevocable"]) not in (bool, type(None)):
        raise ValueError("Irrevocability must be boolean or null")
    return record


def compatibility(family, record):
    validate(record)
    if family not in FAMILIES:
        raise ValueError("Unknown decision family")
    required = {"order": list(EVENTS), "actors": ["leader", "referee", "follower"],
                "access": [family == "public_offer", True], "irrevocable": True}
    missing, conflicts = [], []
    for field, expected in required.items():
        actual = record[field]
        if field in {"actors", "access"}:
            for i, want in enumerate(expected):
                _record_difference(actual[i], want, f"{field}[{i}]", missing, conflicts)
        else:
            _record_difference(actual, expected, field, missing, conflicts)
    status = "incompatible" if conflicts else "abstain" if missing else "compatible"
    return {"status": status, "conflicts": conflicts, "missing": missing}


def _record_difference(actual, expected, location, missing, conflicts):
    if actual is None:
        missing.append(location)
    elif actual != expected:
        conflicts.append(location)


def certified_policy(case, proposal, reviewed, inputs):
    """A proposal cannot activate a solver without a reviewed matching record."""
    single_case(case)
    validate(reviewed)
    if proposal is None:
        return {"status": "invalid_proposal"}
    validate(proposal)
    if proposal != reviewed:
        return {"status": "refused_disagreement",
                "fields": [field for field in FIELDS if proposal[field] != reviewed[field]]}
    scope = compatibility(case["family"], proposal)
    if scope["status"] != "compatible":
        return scope
    if inputs is None:
        return {"status": "abstain", "missing": ["approved_game_inputs"]}
    if case["family"] == "private_signaling":
        # The separately scoped experiment announces the respondent's
        # conditional policy before the adversary fixes one hidden state,
        # and always supplies the specified noisy signal at zero fee.
        game = Game.from_document(inputs)
        certificate = solve(game, "BUY")
        return {"status": "certified", "value": str(check(game, "BUY", certificate)),
                "certificate": certificate.document()}
    # Single take-it-or-leave-it response. Trade on equal valuation and price
    # is an explicit rule of the operator's exact reference game.
    price = Fraction(inputs["price"])
    value = Fraction(inputs["value"])
    return {"status": "certified", "response": "accept" if value >= price else "reject",
            "surplus": str(max(Fraction(0), value - price))}


class ProtocolEnvironment:
    """One reviewed, structured decision with an explicit penalty for false admission."""

    def __init__(self, case, reviewed, inputs=None):
        self.case = single_case(case)
        self.reviewed = validate(reviewed)
        self.inputs = inputs
        self.finished = True

    def reset(self):
        self.finished = False
        return dict(self.case)

    def step(self, proposal):
        if self.finished:
            raise ValueError("Reset the environment before stepping")
        self.finished = True
        outcome = certified_policy(self.case, proposal, self.reviewed, self.inputs)
        if proposal == self.reviewed:
            reward = 1
        elif (proposal is not None and compatibility(self.case["family"], proposal)["status"] == "compatible"
              and compatibility(self.case["family"], self.reviewed)["status"] != "compatible"):
            reward = -2
        else:
            reward = 0
        return None, reward, True, outcome
