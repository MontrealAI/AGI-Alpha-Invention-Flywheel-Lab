"""Replay the registered scores using frozen case projections and reference dispositions."""

import json
from pathlib import Path

from score import grade, load_predictions


ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def main():
    expected = {
        "PRIMARY": {"direct": 14, "integrated": 14},
        "ADVERSE": {"integrated": 5},
        "CONFIRMATION": {"direct": 6, "integrated": 6},
    }
    for stage, arms in expected.items():
        cases = read(stage + "-OBSERVATIONS.json")["cases"]
        reference = read(stage + "-REFERENCE.json")
        for arm, count in arms.items():
            suffix = "-DIRECT.json" if arm == "direct" else "-PREDICTIONS.json"
            predictions, _ = load_predictions(ROOT / (stage + suffix))
            result = grade(cases, reference, predictions)
            assert result["whole_case_acceptance"] == count
            assert result["false_supported"] == 0
            print(stage, arm, f"{count}/{result['cases']}", "zero false supports")


if __name__ == "__main__":
    main()
