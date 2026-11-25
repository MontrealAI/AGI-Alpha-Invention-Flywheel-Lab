"""Produce split, licensed synthetic supervision and replay pinned exact bounds."""

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path
import random
import sys

from game import DECISIONS, Game, compare, digest_document


ROOT = Path(__file__).resolve().parents[2]
OBSERVATION = ROOT / "mission-executor" / "game"
RETAINED_SOURCE = "c0a14ba028092db648516718f9127ae8166df63e"
RETAINED_VERIFIER_SHA256 = "740c3228348ad946acd3fa86771379aff4958dea413f7626db9db137205ac119"
TRAIN_SEED = 42073
DEVELOPMENT_SEED = 71291


def retained_check(game, decision, bounds):
    """Reduce a payoff row to one occupied lane in the retained verifier."""
    source = OBSERVATION / "observation.py"
    if sha256(source.read_bytes()).hexdigest() != RETAINED_VERIFIER_SHA256:
        raise ValueError("Unexpected retained verifier source")
    if str(OBSERVATION) not in sys.path:
        sys.path.insert(0, str(OBSERVATION))
    import observation
    if Path(observation.__file__).resolve() != source:
        raise ImportError("Conflicting observation module")

    offset = -min(0, min(min(row) for row in game.payoffs))
    count = len(game.payoffs)
    buy = decision == "BUY"
    channel = {f"c{column}": ({f"s{signal}": str(game.likelihood(column, signal)) for signal in (0, 1)}
                             if buy else {"s0": "1"}) for column in (0, 1)}
    base = observation.parse_game({
        "schema": observation.GAME_SCHEMA, "row_budget": 1,
        "scenarios": [{"id": f"c{column}", "column_budget": 0,
                       "weights": [row[column] + offset for row in game.payoffs]} for column in (0, 1)],
        "instruments": [{"id": "measurement", "cost": game.fee if buy else 0, "channel": channel}],
    })
    probabilities = (bounds.column0_probability, 1 - bounds.column0_probability)
    denominator = lcm(*(mass.denominator for _, mass in bounds.policy), *(p.denominator for p in probabilities))
    flows = tuple({} for _ in next(iter(channel.values())))
    for rows, mass in bounds.policy:
        for signal, row in enumerate(rows):
            action = tuple(int(index == row) for index in range(count))
            flows[signal][action] = flows[signal].get(action, 0) + int(mass * denominator)
    row_policy = {0: observation.InstrumentPolicy(denominator, flows)}
    zero = (0,) * count
    column_policy = {(index, zero): int(p * denominator) for index, p in enumerate(probabilities) if p}
    certificate = observation.pack(base, row_policy, column_policy, denominator)
    proof = observation.verify(base, certificate)
    if Fraction(proof["lower"]) != bounds.value + offset or Fraction(proof["upper"]) != bounds.value + offset:
        raise ArithmeticError("The retained verifier did not support this exact teacher target")
    return {"game_sha256": proof["game_sha256"], "certificate_sha256": proof["certificate_sha256"],
            "exact_value_after_shift": proof["lower"], "payoff_shift": offset}


def examples(split, pairs, seed):
    rng = random.Random(seed)
    originals = set()
    records = []
    training = split == "train"
    while len(records) < 2 * pairs:
        if training:
            a, b, c, d = (rng.randint(2, 16) for _ in range(4))
            q = rng.choice(range(57, 100, 2))
        else:
            a, b, c, d = (rng.randint(17, 23) for _ in range(4))
            q = rng.choice(range(58, 97, 2))
        rows = [(a, -b), (-c, d)]
        if rng.randrange(2):
            rows.reverse()
        key = (tuple(sorted(rows)), q)
        if key in originals:
            continue
        originals.add(key)
        game = Game("open", tuple(rows), (q, q), 0)
        _, bound = compare(game)
        worth = bound["BUY"].value - bound["SKIP"].value
        cutoff = (worth.numerator + worth.denominator - 1) // worth.denominator
        if not 0 < cutoff <= 28:
            continue
        fees = (max(0, cutoff - 1 - rng.randrange(3)), cutoff + rng.randrange(3))
        for fee in fees:
            game = Game(f"{split}-{len(records):04d}", tuple(rows), (q, q), fee)
            decision, bounds = compare(game)
            references = {action: retained_check(game, action, bounds[action]) for action in DECISIONS}
            records.append({"input": game.document(), "input_sha256": digest_document(game.document()),
                            "label": decision, "exact": {action: bounds[action].document() for action in DECISIONS},
                            "retained_verification": references})
    return records


def drive(out, train_pairs, development_pairs):
    out.mkdir(parents=True)
    report = {"schema": "frontier/strategic-purchase-data-v1", "retained_source": RETAINED_SOURCE,
              "description": "Procedurally generated perfect-information game rules and an unobserved adversary move."
                             " Opposite labels within a matched pair vary the acquisition fee.",
              "input_origin": "SYNTHETIC_LEARNING_ENVIRONMENT", "labels": "Exact rational minimax, cross-replayed",
              "training_distribution": "Two opposing payoff rows, magnitudes 2–16, odd symmetric accuracy 57–99%",
              "development_distribution": "Two opposing payoff rows, magnitudes 17–23, even symmetric accuracy 58–96%",
              "confirmation_excluded": True, "splits": {}}
    for split, pairs, seed in (("train", train_pairs, TRAIN_SEED),
                              ("development", development_pairs, DEVELOPMENT_SEED)):
        records = examples(split, pairs, seed)
        result = out / f"{split}.jsonl"
        raw = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in records).encode()
        result.write_bytes(raw)
        report["splits"][split] = {"file": result.name, "seed": seed, "sha256": sha256(raw).hexdigest(),
                                   "records": len(records), "labels": {label: sum(row["label"] == label for row in records)
                                                                       for label in DECISIONS},
                                   "retained_exact_verifications": 2 * len(records)}
    for source in (Path(__file__), Path(__file__).with_name("game.py"), OBSERVATION / "observation.py"):
        report.setdefault("source_sha256", {})[source.name] = sha256(source.read_bytes()).hexdigest()
    (out / "DATA.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--train-pairs", type=int, default=160)
    parser.add_argument("--development-pairs", type=int, default=32)
    options = parser.parse_args()
    if min(options.train_pairs, options.development_pairs) < 1:
        parser.error("Each split needs at least one pair")
    drive(options.output, options.train_pairs, options.development_pairs)


if __name__ == "__main__":
    main()
