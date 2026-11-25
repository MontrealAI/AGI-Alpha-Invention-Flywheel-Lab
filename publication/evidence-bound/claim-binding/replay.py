#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the captured m06 proposals followed by an explicitly authored correction."""

from datetime import datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parent
BRIDGE_ROOT = HERE.parents[2] / "products" / "alpha-genesis-harness"
sys.path.insert(0, str(BRIDGE_ROOT))
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime
from bridge.workflows import digest


VERSION = "held-m06-authorized-data-v1"
SCHEMA = {"batches": {"volume_hundredths": "INTEGER", "volume_unit": "TEXT", "concentration_hundredths": "INTEGER", "concentration_unit": "TEXT"}}
SQL = """
WITH normalized AS (
    SELECT CASE volume_unit WHEN 'L' THEN volume_hundredths*1000 WHEN 'mL' THEN volume_hundredths END AS v,
           CASE concentration_unit WHEN 'g/L' THEN concentration_hundredths*1000 WHEN 'mg/L' THEN concentration_hundredths END AS c
    FROM batches
)
SELECT CAST(SUM(v*c) AS TEXT) || '/' || CAST(SUM(v)*100 AS TEXT),
       CAST(SUM(v*c) AS TEXT) || '/10000000', CAST(SUM(v) AS TEXT) || '/100000'
FROM normalized
HAVING SUM(v) > 0 AND COUNT(v) = COUNT(*) AND COUNT(c) = COUNT(*)
""".strip()


def reference(data):
    """Exact independent implementation on the original row fields and units."""
    volume_scale = {"mL": Fraction(1, 1000), "L": Fraction(1)}
    concentration_scale = {"g/L": 1000, "mg/L": 1}
    volumes = [Fraction(batch["volume_hundredths"], 100)*volume_scale[batch["volume_unit"]] for batch in data["batches"]]
    mass = sum(volume * Fraction(batch["concentration_hundredths"], 100) * concentration_scale[batch["concentration_unit"]]
               for volume, batch in zip(volumes, data["batches"], strict=True))
    volume = sum(volumes)
    return {"concentration": mass/volume, "mass": mass, "volume": volume}


def case_requirements(data):
    expected = reference(data)
    facts = {"volume_additive": True, "mass_conserved": True}
    metadata = {"kind": "table", "origin": "AUTHORIZED_MISSION_INPUT", "version": VERSION, "sha256": digest(data), "facts": facts}
    quantities = (("concentration", "mg/L", "mass/volume"), ("mass", "mg", "mass"), ("volume", "L", "volume"))
    claims = [
        {"id": ident, "dataset": "mixture", "tool": "run_table", "locator": ["rows", 0, column],
         "unit": unit, "dimension": dimension, "version": VERSION, "requires": facts,
         "required_fields": [["batches", key] for key in SCHEMA["batches"]],
         "reference": {"value": str(expected[ident]), "source": "Separate exact Fraction unit and mass reconciliation"}}
        for column, (ident, unit, dimension) in enumerate(quantities)
    ]
    return {"approved_tables": {"mixture": data}, "evidence": {"inputs": {"mixture": metadata}, "claims": claims}}


def correction(requirements):
    actions = [{"tool": "construct_table", "name": "reconciliation.json", "schema": SCHEMA, "sql": SQL}]
    actions.extend({"tool": "run_table", "name": "reconciliation.json", "input": {"dataset": claim["dataset"]},
                    "claim": {k: claim[k] for k in ("id", "unit", "dimension")}}
                   for claim in requirements["evidence"]["claims"])
    return {"summary": "Authored exact SQL correction over the approved records. Report from execution receipts.",
            "actions": actions, "done": True}


def run():
    raw = (HERE / "HISTORICAL-M06.json").read_bytes()
    history = json.loads(raw)
    data = history["approved_data"]
    requirements = case_requirements(data)
    captured = [item["decoded_proposal"] for item in history["model_proposals"]]
    elapsed_start = time.monotonic()
    with tempfile.TemporaryDirectory() as workspace:
        runtime = FixtureRuntime([*captured, correction(requirements)])
        service = UniversalMissionService(runtime, workspace)
        try:
            declared = service.submit({
                "ambition": history["ambition"], "language": "en", "provider": "fixture", "model": "captured-replay-and-authored-correction",
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                "max_turns": 3, "max_actions": 12, "max_output_tokens": 1024,
                "tools": ["construct_table", "run_table", "write_document"], "requirements": requirements,
            })
            after_prose, after_fixture, corrected = (service.step(declared["id"]) for _ in range(3))
        finally:
            service.close()
    found = next(item["detail"]["outcome"] for item in after_fixture["events"] if item["kind"] == "tool_completed"
                 and item["detail"]["tool"] == "run_table")
    assert found["input_origin"] == "MODEL_DEVELOPMENT_FIXTURE" and found["rows"] == [[2]]
    assert found["output_sha256"] == history["historical_fixture_output_sha256"]
    assert after_prose["evidence"]["status"] == after_fixture["evidence"]["status"] == "ABSTAIN"
    assert corrected["evidence"]["status"] == "VERIFIED" and corrected["status"] == "needs_review"
    assert corrected["qualification"] == "UNVERIFIED"
    claims = {claim["id"]: claim for claim in corrected["evidence"]["claims"]}
    assert Fraction(claims["concentration"]["value"]) * Fraction(claims["volume"]["value"]) == Fraction(claims["mass"]["value"])
    return {"scope": "Historical proposal replay and authored numerical repair on public m06. No live model requests.",
            "source_commit": history["source_commit"], "historical_replay_data_sha256": sha256(raw).hexdigest(),
            "execution_source_sha256": {name: sha256((BRIDGE_ROOT / "bridge" / name).read_bytes()).hexdigest()
                                        for name in ("mission_evidence.py", "universal_missions.py", "mission_tools.py")},
            "elapsed_seconds": round(time.monotonic() - elapsed_start, 6),
            "original_unsupported_prose": "138461.54 mg/L", "after_original_prose": after_prose["evidence"]["status"],
            "fixture_execution": {key: found[key] for key in ("input_origin", "rows", "input_sha256", "output_sha256")},
            "after_original_fixture": after_fixture["evidence"]["status"], "corrected_mission_state": corrected["status"],
            "corrected_mission_qualification": corrected["qualification"],
            "corrected_evidence": corrected["evidence"]}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))
