"""Replay exact strategic certificates and sample the announced policy."""

import argparse
import json
from pathlib import Path

from game import DECISIONS, PurchaseEnvironment, compare, digest_document, play, read_games


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--sample-seed", type=int)
    parser.add_argument("--retained", action="store_true", help="Cross-check with the pinned repository verifier")
    options = parser.parse_args()
    for game in read_games(options.input):
        world = PurchaseEnvironment(game)
        document = world.reset()
        decision, source = compare(game)
        _, reward, _, status = world.step(decision)
        result = {"id": game.id, "input_sha256": digest_document(document), "reference_decision": decision,
                  "exact_certificates": {mode: source[mode].document() for mode in DECISIONS},
                  "regret": str(-reward), "accepted": status["accepted"]}
        if options.retained:
            from generate import retained_check
            result["previous_verifier"] = {mode: retained_check(game, mode, source[mode]) for mode in DECISIONS}
        if options.sample_seed is not None:
            result["one_simulated_draw"] = play(game, decision, source[decision].policy, options.sample_seed)
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
