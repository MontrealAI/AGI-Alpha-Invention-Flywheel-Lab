"""Persist reproducible instruments after the original R5 confirmation.

The original result retained semantic matrices and acquisition receipt hashes,
but omitted full instrument objects that include timing. This disclosed replay
retains new serialized objects with new timing, verifies original semantic and
query identities, and never relabels the replay as fresh confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from portfolio071 import foundry
from portfolio071.verify_foundry import digest, oracle_for, treatment_reference


def retain(original, output):
    original, output = Path(original), Path(output)
    source = json.loads(original.read_text())
    if hashlib.sha256(Path(foundry.__file__).read_bytes()).hexdigest() != source["constructor_sha256"]:
        raise AssertionError("Frozen constructor changed before retention replay")
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for row in source["systems"]:
        matrix = row["matrix_revealed_after_construction"]
        queries = []
        model = foundry.identify(oracle_for(matrix, queries), row["dimension"])
        if model["transition"] != matrix or model["query_receipt_sha256"] != row["k1"]["query_receipt_sha256"]:
            raise AssertionError("Original acquisition semantic identity not reproduced")
        sensors = foundry.choose_sensors(model, **row["k1"]["sensor_task"])
        for key in ("accepted", "sensor_nodes", "cost_units", "achieved_separation"):
            if sensors[key] != row["k1"]["sensor_design"][key]:
                raise AssertionError("Retained instrument did not reproduce K1 sensor design")
        checked = None
        if row["k2"]["design"]["accepted"]:
            task = row["k2"]["request"]
            checked = treatment_reference(model["transition"], task["source_nodes"], task["protected_nodes"],
                                          task["horizon"], row["k2"]["design"]["fractions"])
            if checked["maximum_exposure"] > task["exposure_limit"] + 1e-8 or checked["max_mass_error"] > 1e-8:
                raise AssertionError("Original successor plan invalid on retained instrument")
        name = "instrument-%02d.json" % row["system"]
        raw = (json.dumps(model, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        (output / name).write_bytes(raw)
        rows.append({"system": row["system"], "file": name, "file_sha256": hashlib.sha256(raw).hexdigest(),
                     "canonical_instrument_sha256": digest(model),
                     "original_full_instrument_sha256": row["k1"]["instrument_sha256"],
                     "original_matrix_identity_reproduced": True, "original_query_receipt_sha256": model["query_receipt_sha256"],
                     "original_sensor_design_reproduced": True,
                     "original_successor_plan_accepted": checked is not None,
                     "scope": "Timing fields are new measurements; original full-object hash is historical, not claimed equal to the retained replay object."})
    index = {"schema": "portfolio071/foundry-retention-replay/v1", "stage": "POST_CONFIRMATION_SERIALIZATION_REPLAY_NOT_FRESH_CONFIRMATION",
             "original_results_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
             "original_results_modified": False, "constructor_sha256": source["constructor_sha256"],
             "retention_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "instrument_count": len(rows), "original_successor_plans_revalidated": sum(r["original_successor_plan_accepted"] for r in rows),
             "additional_acquisition_queries": sum(r["k1"]["query_count"] for r in source["systems"]),
             "disclosure": "Original confirmation saved matrix contents, query receipt hashes and design artifacts but omitted full instrument objects containing runtime measurements. This retention replay saves fresh serialized models, checks exact original matrix and query identities, and preserves the initial report unchanged. No claims use replay as an additional discovery campaign or blind holdout.",
             "instruments": rows}
    (output / "INDEX.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"instrument_count": len(rows), "original_successor_plans_revalidated": index["original_successor_plans_revalidated"],
                      "semantic_and_query_identity_matches": True, "new_blind_confirmation": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    retain(args.original, args.output)
