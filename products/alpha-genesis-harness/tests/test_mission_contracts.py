"""Semantic regressions for the local mission capability dispatcher."""

from copy import deepcopy
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.mission_contracts import assess, assess_composition, compare_requirements, describe, endpoint_requirements, invoke


POINT = {
    "issued_at": "2024-11-29T00:00:00Z", "valid_at": "2024-11-30T00:00:00Z",
    "latitude": "45.50", "longitude": "-73.50",
}
NOAA = {
    "version": "1.0.0", "source": "NOAA GFS public archive", "quantity": "air_temperature_at_2m",
    "result_kind": "model_forecast", "unit": "K", "time_basis": "UTC", "grid_degrees": "0.25", **POINT,
}
BATCH = {
    "schema": "frontier/endpoint-screen-v1",
    "source": "Authorized synthetic boundary test",
    "scope": {"model": "versioned-model", "workload": "test-token-generation", "system": "one-fixture"},
    "cutoff": "2026-11-23", "minimum_tokens_per_s": "100", "maximum_p90_ttft_ms": "500",
    "rows": [
        {"id": "limit", "load": 140, "published": "2026-11-23", "tokens_per_s": "100", "p90_ttft_ms": "500.000"},
        {"id": "too-slow", "load": 160, "published": "2026-11-23", "tokens_per_s": "100", "p90_ttft_ms": "500.000000000000000000000001"},
        {"id": "after", "load": 180, "published": "2026-11-24", "tokens_per_s": "110", "p90_ttft_ms": "100"},
        {"id": "unchecked", "load": 200, "published": "2026-11-23", "tokens_per_s": "140", "p90_ttft_ms": None},
    ],
}
BOUND = {"use": "verified_batch"}


class CapabilityContractsTests(unittest.TestCase):
    def test_noaa_permanent_french_twelve_hour_regression(self):
        # The operator's typed evidence for « du 29 novembre à 00 UTC à midi
        # UTC ». The model substitutes an f024 point that fits its own tool.
        mission = {**NOAA, "valid_at": "2024-11-29T12:00:00Z", "longitude": "-73.6"}
        result = invoke("noaa-archive", mission, POINT)
        self.assertFalse(result["executed"])
        self.assertEqual(result["decision"]["status"], "INCOMPATIBLE")
        self.assertEqual(result["decision"]["reason"], "NOAA_F024_REQUIRES_EXACTLY_24_HOURS")
        self.assertEqual(result["decision"]["source_revision"], "6a635b77012fb45b4d96c404a33fa04327c19674")

    def test_noaa_off_grid_within_correct_horizon_is_incompatible(self):
        mission = {**NOAA, "longitude": "-73.6"}
        self.assertEqual(assess("noaa-archive", mission, POINT)["reason"], "POINT_NOT_ON_NATIVE_QUARTER_DEGREE_GRID")
        mission = {**NOAA, "latitude": "45.500000000001"}
        self.assertEqual(assess("noaa-archive", mission, POINT)["reason"], "POINT_NOT_ON_NATIVE_QUARTER_DEGREE_GRID")

    def test_noaa_equivalent_utc_and_longitude_representations_can_match(self):
        proposal = {**POINT, "issued_at": "2024-11-29T00:00+00:00", "longitude": "286.50"}
        decision = assess("noaa-archive", NOAA, proposal)
        self.assertEqual(decision["status"], "COMPATIBLE")
        self.assertEqual(decision["evidence_status"], "ARCHIVE_BYTES_UNCHECKED")
        run = invoke("noaa-archive", NOAA, proposal)
        self.assertFalse(run["executed"])
        self.assertEqual(run["decision"]["status"], "UNAUTHORIZED")

    def test_noaa_rejects_unsupported_quantities_origins_versions_and_clocks(self):
        for label, value in (("quantity", "precipitation"), ("result_kind", "observation"), ("version", "2.0.0"),
                             ("time_basis", "America/Toronto"), ("source", "arbitrary provider"), ("grid_degrees", "0.50")):
            with self.subTest(label=label):
                decision = assess("noaa-archive", {**NOAA, label: value}, POINT)
                self.assertEqual(decision["status"], "INCOMPATIBLE")
                self.assertEqual(decision["fields"], [label])
        self.assertEqual(assess("noaa-archive", {**NOAA, "unit": "°C"}, POINT)["status"], "ADAPTATION_REQUIRED")
        self.assertEqual(assess("noaa-archive", {**NOAA, "issued_at": "2024-11-29T00:00:00-05:00"},
                                POINT)["reason"], "UTC_TIMESTAMP_REQUIRED")
        self.assertEqual(assess("noaa-archive", {**NOAA, "issued_at": "2024-11-29T01:00Z"},
                                POINT)["reason"], "UNSUPPORTED_NOAA_ISSUE_CYCLE")

    def test_noaa_refuses_changed_time_or_coordinates_without_rounding(self):
        actual = assess("noaa-archive", NOAA, {**POINT, "latitude": "45.75"})
        self.assertEqual(actual["reason"], "POINT_DIFFERS_FROM_OPERATOR_REQUIREMENT")
        actual = assess("noaa-archive", NOAA, {**POINT, "longitude": -73.5})
        self.assertEqual(actual["reason"], "EXACT_DECIMAL_COORDINATE_REQUIRED")

    def test_tool_arguments_cannot_supply_missing_authoritative_facts(self):
        self.assertEqual(assess("noaa-archive", None, {**POINT, "requirements": NOAA})["status"], "UNDETERMINED")
        self.assertEqual(assess("noaa-archive", {"source": NOAA["source"]}, POINT)["status"], "MISSING_INPUT")
        self.assertEqual(assess("noaa-archive", NOAA, POINT, authorized=False)["status"], "UNAUTHORIZED")
        self.assertEqual(assess("unused-capability", NOAA, POINT)["status"], "UNDETERMINED")

    def test_endpoint_rejects_missing_bound_evidence_and_changed_model_limits(self):
        facts = endpoint_requirements(BATCH)
        self.assertEqual(assess("endpoint-screen", None, {"batch": BATCH})["status"], "UNDETERMINED")
        self.assertEqual(assess("endpoint-screen", {**facts, "batch": None}, BOUND)["status"], "MISSING_INPUT")
        self.assertEqual(assess("endpoint-screen", {**facts, "latency_unit": "seconds"}, BOUND)["status"], "INCOMPATIBLE")
        changed = {**BATCH, "scope": {**BATCH["scope"], "model": "a-different-model"}}
        self.assertEqual(assess("endpoint-screen", facts, {"batch": changed})["fields"], ["scope"])
        changed = {**BATCH, "minimum_tokens_per_s": "50"}
        self.assertEqual(assess("endpoint-screen", facts, {"batch": changed})["fields"], ["minimum_tokens_per_s"])

    def test_endpoint_rejects_same_scope_measurement_tampering_before_execution(self):
        facts = endpoint_requirements(BATCH)
        altered = deepcopy(BATCH)
        altered["rows"][1]["p90_ttft_ms"] = "200"
        with patch("bridge.mission_contracts.subprocess.run") as run:
            verdict = invoke("endpoint-screen", facts, {"batch": altered})
            self.assertEqual(verdict["decision"]["reason"], "BATCH_IDENTITY_MISMATCH")
            self.assertFalse(verdict["executed"])
            run.assert_not_called()

    def test_endpoint_bounds_ambiguous_load_or_bad_publication_dates(self):
        facts = endpoint_requirements(BATCH)
        for changed, reason in [
            ({**BATCH["rows"][0], "load": 160}, "ENDPOINT_AMBIGUOUS_LOAD_OR_ID"),
            ({**BATCH["rows"][0], "published": "2025-02-29"}, "ENDPOINT_MEASUREMENT_ROW"),
            ({**BATCH["rows"][0], "load": True}, "ENDPOINT_MEASUREMENT_ROW"),
        ]:
            with self.subTest(reason=reason, row=changed):
                batch = {**BATCH, "rows": [changed, *BATCH["rows"][1:]]}
                self.assertEqual(assess("endpoint-screen", facts, {"batch": batch})["reason"], reason)

    @unittest.skipUnless(shutil.which("node"), "Endpoint's qualified screened calculation requires Node.")
    def test_guarded_dispatch_executes_published_screen_and_keeps_operating_abstention(self):
        result = invoke("endpoint-screen", endpoint_requirements(BATCH), BOUND)
        self.assertTrue(result["executed"])
        self.assertEqual(result["decision"]["status"], "COMPATIBLE")
        self.assertEqual(result["output"]["highest_tested_load"], 140)
        self.assertEqual(result["output"]["operating_adoption"], "ABSTAIN")
        self.assertEqual([row["disposition"] for row in result["output"]["rows"]],
                         ["qualified", "above-ceiling", "not-yet-documented", "missing-measurement"])

    def test_composition_requires_registry_ports_and_consistent_order(self):
        link = {"producer": "noaa-archive", "output": "temperature", "consumer": "endpoint-screen",
                "input": "batch", "producer_step": 0, "consumer_step": 1}
        self.assertEqual(assess_composition([link])["status"], "INCOMPATIBLE")
        self.assertIn("time_basis", assess_composition([link])["fields"])
        self.assertEqual(assess_composition([{**link, "consumer_step": 0}])["reason"], "INVALID_COMPOSITION_ORDER")
        self.assertEqual(assess_composition([{**link, "output": "invented-interface"}])["status"], "UNDETERMINED")
        self.assertEqual(assess_composition([link], authorized=False)["status"], "UNAUTHORIZED")

    def test_generic_facts_distinguish_missing_provenance_units_and_dimensions(self):
        required = {"unit": "mm", "time_basis": "UTC", "dimensions": ["x", "y"], "provenance": "approved_record"}
        self.assertEqual(compare_requirements(required, required)["status"], "COMPATIBLE")
        missing = dict(required)
        missing.pop("provenance")
        self.assertEqual(compare_requirements(required, missing)["fields"], ["provenance"])
        self.assertEqual(compare_requirements(required, {**required, "unit": "m", "dimensions": ["y", "x"]})["fields"],
                         ["dimensions", "unit"])
        self.assertEqual(compare_requirements({"dimensions": [1]}, {"dimensions": [True]})["status"], "INCOMPATIBLE")

    def test_public_descriptions_are_detached(self):
        contracts = {record["id"]: record for record in describe()}
        contracts["noaa-archive"]["scope"]["forecast_horizon_hours"] = 12
        fresh = {record["id"]: record for record in describe()}
        self.assertEqual(fresh["noaa-archive"]["scope"]["forecast_horizon_hours"], 24)
        self.assertEqual(fresh["endpoint-screen"]["dispatch"], "local")


if __name__ == "__main__":
    unittest.main()
