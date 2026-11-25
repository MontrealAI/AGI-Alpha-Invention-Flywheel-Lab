# SPDX-License-Identifier: Apache-2.0
"""Score exact frozen prediction records without the candidate's assessor."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


FINGERPRINTS = {
    "inputs": "c41c0ea88d10b000b9bb260965011014799cbc7970f1b25624685d69f2a894fc",
    "reference": "a84e3bc64d7f0b7bcf790e4566b68a55d0cdbf570e2571b64e2a0305264ae95d",
    "local_predictions": "482297a34e54a20ff5a3d37e8afdfe457bee9721cf7d940a097bff9a7a2bd437",
    "included_predictions": "42229fff063b93b41cf2cdad3e6b4fa536e12f03f1432f522ef165c1ee972899",
}
FIELDS = ("order", "actors", "access", "irrevocable")


def read_exact(path, fingerprint):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != fingerprint:
        raise ValueError(f"Unexpected SHA-256 for {path.name}")
    return json.loads(raw)


def same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def disposition(record, family):
    if record is None:
        return "uninterpreted"
    desired = ["commit", "signal", "choose", "leader", "referee", "follower",
               family == "public_offer", True, True]
    order = record["order"] if record["order"] is not None else [None] * 3
    observed = order + record["actors"] + record["access"] + [record["irrevocable"]]
    if len(observed) != len(desired):
        raise ValueError("Malformed case record")
    if any(value is not None and not same(value, target) for value, target in zip(observed, desired)):
        return "blocked"
    return "unresolved" if any(value is None for value in observed) else "qualified"


def grade(cases, refs, predictions):
    ids = [case["id"] for case in cases]
    if ids != [row["id"] for row in predictions] or ids != list(refs) or len(set(ids)) != len(ids):
        raise ValueError("Frozen case and prediction rosters differ")
    exact, correct, false_proposals, differences = 0, 0, [], {}
    for case, row in zip(cases, predictions):
        ident, family = case["id"], case["family"]
        reference, prediction = refs[ident], row["record"]
        expected = disposition(reference, family)
        actual = disposition(prediction, family)
        correct += actual == expected
        if actual == "qualified" and expected != "qualified":
            false_proposals.append(ident)
        if same(reference, prediction):
            exact += 1
        else:
            changed = [name for name in FIELDS if prediction is None or not same(reference[name], prediction[name])]
            differences[ident] = {"differing_fields": changed, "reference": expected, "actual": actual}
    return {"exact_records": exact, "expected_dispositions": correct,
            "false_scope_proposals": false_proposals, "differences": differences}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in FINGERPRINTS:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    data = {name: read_exact(getattr(args, name), fingerprint) for name, fingerprint in FINGERPRINTS.items()}
    cases = data["inputs"]
    refs = {ref["id"]: ref["record"] for ref in data["reference"]}
    arms = {**data["local_predictions"]["arms"], "included_direct": data["included_predictions"]["records"]}
    payload = {
        "schema": "frontier/independent-strategic-holdout-score/v1",
        "method": "Independent exact canonical JSON values and literal event-role-access scope rules. Known conflicts block, missing fields remain unresolved, malformed predictions are uninterpreted.",
        "custody": "Separate authorship and checking in a shared administration environment. Input and reference frozen before exposure. References released only after all prediction hashes froze.",
        "scorer_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "frozen_sha256": FINGERPRINTS,
        "cases": len(cases),
        "results": {arm: grade(cases, refs, predictions) for arm, predictions in arms.items()},
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
