"""Measure known-development decisions and fee-only shortcut controls."""

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from game import Game, compare, digest_document


def examples(path):
    return [json.loads(row) for row in path.read_bytes().splitlines()]


def metrics(predictions, truth, pairs):
    matched = {identity for identity, row in predictions.items() if row["decision"] == truth[identity]["label"]}
    opportunity_loss = []
    for identity, row in predictions.items():
        record = truth[identity]
        values = record["exact"]
        opportunity_loss.append(Fraction(values[record["label"]]["value"]) - Fraction(values[row["decision"]]["value"]))
    return {"correct": len(matched), "cases": len(truth), "both_pair_members_correct": sum(
                all(identity in matched for identity in pair) for pair in pairs), "pairs": len(pairs),
            "mean_opportunity_loss": str(sum(opportunity_loss) / len(truth))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train", type=Path)
    parser.add_argument("development", type=Path)
    parser.add_argument("predictions", type=Path)
    args = parser.parse_args()
    train = examples(args.train)
    cases = examples(args.development)
    expected = {sample["input"]["id"]: sample for sample in cases}
    pairs = [[item["input"]["id"] for item in cases[i:i+2]] for i in range(0, len(cases), 2)]
    record = json.loads(args.predictions.read_bytes())
    if record["training_example_sha256"] != sha256(args.train.read_bytes()).hexdigest():
        raise ValueError("Predictions used a different training example set")
    outcomes = {}
    for name, results in record["arms"].items():
        predictions = {row["id"]: row for row in results}
        if (set(predictions) != set(expected) or len(results) != len(expected) or any(
                row["input_sha256"] != digest_document(expected[identity]["input"])
                for identity, row in predictions.items())):
            raise ValueError("Predictions differ from the development roster")
        outcomes[name] = metrics(predictions, expected, pairs)
        outcomes[name].update({"pairs_with_buy_score_decrease_when_fee_increases": sum(
            predictions[low]["probability_buy"] > predictions[high]["probability_buy"] for low, high in pairs),
            "observed_batched_seconds": sum(row["batch_share_seconds"] for row in results)})

    def fee_rule(record, threshold):
        return "BUY" if record["input"]["fee"] < threshold else "SKIP"

    threshold = max(range(34), key=lambda candidate: sum(fee_rule(row, candidate) == row["label"] for row in train))
    cheap = {identity: {"decision": fee_rule(row, threshold)} for identity, row in expected.items()}
    outcomes["fee_only_train_calibrated"] = {**metrics(cheap, expected, pairs), "threshold": threshold}
    started = perf_counter()
    reference = {identity: {"decision": compare(Game.from_document(item["input"]))[0]}
                 for identity, item in expected.items()}
    outcomes["standalone_exact_solver"] = {**metrics(reference, expected, pairs), "elapsed_seconds": perf_counter() - started}
    print(json.dumps({"schema": "frontier/strategic-development-evaluation-v1",
                      "scope": "Known development split, disjoint from fitting and excluded from independent confirmation",
                      "predictions_sha256": sha256(args.predictions.read_bytes()).hexdigest(),
                      "development_sha256": sha256(args.development.read_bytes()).hexdigest(),
                      "adapter_sha256": record["adapter_sha256"], "outcomes": outcomes}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
