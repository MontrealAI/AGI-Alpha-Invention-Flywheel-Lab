# SPDX-License-Identifier: Apache-2.0
"""Adversarial transfer-audit tests; these authored receipts are not live evidence."""
import copy
import hashlib
import unittest

from bridge.adapters import BridgeError
from bridge.frontier_transfer import (METRICS, STAGES, adjudicate, public_contract,
                                     mission_assessment, mission_registration,
                                     qualify, register, summarize_costs)
from bridge.workflows import digest


def specification():
    def task(objective, family, fn):
        return {"objective": objective, "family": family, "acceptance": "Return the independently specified result.",
                "development": [{"input": {"x": 1}, "expected": {"value": fn(1)}}],
                "qualification": [{"input": {"x": x}, "expected": {"value": fn(x)}} for x in (13, -7)]}
    return {"first": task("Compute a test linear response", "linear-response", lambda x: 2 * x),
            "second": task("Compute a test energy response", "quadratic-response", lambda x: x * x + 1),
            "comparison": {"inventor": "test-inventor", "source_sha256": digest("source"),
                "environment_sha256": digest("environment"), "information_sha256": digest("ordinary tools and facts"),
                "budget": {"model_calls": 10}, "metric": "model_calls", "currency": "CAD"}}


def costs(calls, amount=None, *, human=0):
    return [{"stage": stage, "metrics": {key: calls if stage == "construction" and key == "model_calls"
                else human if stage == "construction" and key == "human_seconds" else 0 for key in METRICS},
             "amount_minor": amount if stage == "construction" else (0 if amount is not None else None),
             "basis": "unknown" if amount is None else "measured",
             "note": "Authored disjoint test cost; not a billing observation."} for stage in STAGES]


def evidence(record):
    first_sha = digest("first executable")
    policy = record["spec"]["comparison"]
    arms = {}
    for name, calls in (("first", 6), ("with_asset", 3), ("without_asset", 10)):
        stage = "first" if name == "first" else "second"
        candidate = first_sha if stage == "first" else digest("constructed " + name)
        operation = (lambda x: {"value": 2 * x["x"]}) if stage == "first" else (lambda x: {"value": x["x"] ** 2 + 1})
        arms[name] = {"origin": "live", "status": "complete", "inventor": policy["inventor"],
            **{key: policy[key] for key in ("source_sha256", "environment_sha256", "information_sha256")},
            "budget_sha256": record["budget_sha256"], "candidate_sha256": candidate,
            "retained_asset_sha256": first_sha if name == "with_asset" else None,
            "trace_sha256": digest("trace " + name), "all_attempts_recorded": True, "human_interventions": 0,
            "qualification": qualify(record, stage, candidate, operation, checker_sha256=digest("test checker")),
            "costs": costs(calls)}
    return {"arms": arms, "distinctness_review": {"origin": "independent_review", "reviewer": "test-reviewer",
        "evidence_sha256": digest("test semantic review"), "rationale": "Authored different-outcome audit fixture.",
        "different_objective": True, "first_contract_sha256": record["contracts"]["first"]["sha256"],
        "second_contract_sha256": record["contracts"]["second"]["sha256"]}}


class FrontierTransferTests(unittest.TestCase):
    def setUp(self):
        self.registration = register(specification())
        self.evidence = evidence(self.registration)

    def assess(self, **kwargs):
        return adjudicate(self.registration, self.evidence,
                          current_asset_sha256=kwargs.pop("current_asset_sha256", digest("first executable")),
                          current_source_sha256=kwargs.pop("current_source_sha256", digest("source")), **kwargs)

    def test_frozen_builder_view_does_not_expose_qualification(self):
        visible = public_contract(self.registration, "second")
        self.assertNotIn("qualification", visible)
        self.assertNotIn("qualification_sha256", visible)
        self.assertEqual(visible["development"][0]["input"], {"x": 1})
        visible["development"][0]["expected"]["value"] = 123
        self.assertEqual(self.registration["spec"]["second"]["development"][0]["expected"], {"value": 2})
        modified = copy.deepcopy(self.registration)
        modified["spec"]["second"]["qualification"][0]["expected"] = {"value": 999}
        with self.assertRaisesRegex(BridgeError, "changed"):
            public_contract(modified, "second")

    def test_new_names_do_not_turn_repeat_calculations_into_inventions(self):
        for same in ("objective", "family", "qualification"):
            spec = specification()
            spec["second"][same] = copy.deepcopy(spec["first"][same])
            with self.subTest(same=same), self.assertRaises(BridgeError):
                register(spec)
        spec = specification()
        spec["second"]["objective"] = "  COMPUTE A TEST LINEAR RESPONSE  "
        with self.assertRaises(BridgeError):
            register(spec)

    def test_holdout_overlap_is_rejected_even_with_different_expected_answer(self):
        spec = specification()
        spec["first"]["qualification"][0]["input"] = {"x": 1}
        with self.assertRaisesRegex(BridgeError, "distinct"):
            register(spec)

    def test_checker_gets_only_inputs_and_retains_failures_in_denominator(self):
        seen = []
        def execute(data):
            seen.append(copy.deepcopy(data))
            data["expected"] = "not supplied"
            if data["x"] < 0:
                raise RuntimeError("private expected-answer text should not escape")
            return {"value": data["x"] * 2}
        result = qualify(self.registration, "first", digest("first"), execute, checker_sha256=digest("checker"))
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["passed"], 1)
        self.assertEqual(seen, [{"x": 13}, {"x": -7}])
        self.assertEqual(result["checks"][1]["error"], "RuntimeError")
        self.assertNotIn("expected", self.registration["spec"]["first"]["qualification"][0]["input"])
        self.assertNotIn("private expected-answer", str(result))

    def test_integer_float_equivalence_retains_valid_qualification(self):
        arm = self.evidence["arms"]["first"]
        arm["qualification"] = qualify(self.registration, "first", arm["candidate_sha256"],
            lambda data: {"value": float(2 * data["x"])}, checker_sha256=digest("checker"))
        self.assertTrue(self.assess()["accepted"]["first"])

    def test_false_pass_counter_or_output_hash_is_not_qualification(self):
        receipt = self.evidence["arms"]["with_asset"]["qualification"]
        receipt["checks"][0]["output_sha256"] = digest("incorrect output")
        receipt["sha256"] = digest({key: value for key, value in receipt.items() if key != "sha256"})
        result = self.assess()
        self.assertFalse(result["accepted"]["with_asset"])
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "not_established")

    def test_unknown_money_does_not_block_observed_resource_difference(self):
        result = self.assess()
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "supported_by_recorded_comparison")
        self.assertEqual(result["resource_comparison"]["incremental_second_saving"], 7)
        self.assertEqual(result["resource_comparison"]["first_plus_second"], 9)
        self.assertIsNone(result["monetary_comparison"]["first_plus_second_minor"])
        for claim in ("FIRST_USEFUL_OUTCOME", "NET_MONETARY_BENEFIT", "MONETIZATION", "INVENTOR_IMPROVEMENT"):
            self.assertEqual(result["verdicts"][claim], "not_established")

    def test_acquisition_and_failed_attempts_can_erase_incremental_advantage(self):
        rows = self.evidence["arms"]["first"]["costs"]
        next(row for row in rows if row["stage"] == "failed_attempts")["metrics"]["model_calls"] = 4
        result = self.assess()
        self.assertEqual(result["resource_comparison"]["incremental_second_saving"], 7)
        self.assertEqual(result["resource_comparison"]["first_plus_second"], 13)
        self.assertEqual(result["resource_comparison"]["acquisition_inclusive_saving"], -3)
        self.assertEqual(result["verdicts"]["ACQUISITION_INCLUSIVE_RESOURCE_ADVANTAGE"], "not_established")
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "supported_by_recorded_comparison")

    def test_resource_stage_omission_is_unknown_not_zero(self):
        self.evidence["arms"]["with_asset"]["costs"].pop()
        result = self.assess()
        self.assertIsNone(result["resource_comparison"]["incremental_second_saving"])
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
        self.assertIn("maintenance", result["costs"]["with_asset"]["missing_stages"])

    def test_fixture_and_developer_work_never_become_autonomous_live_transfer(self):
        for origin in ("fixture", "developer"):
            self.evidence["arms"]["with_asset"]["origin"] = origin
            result = self.assess()
            self.assertEqual(result["verdicts"]["ENGINEERING_CORRECTNESS"], "passed_recorded_checks")
            self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
            self.assertEqual(result["verdicts"]["STRICT_AUTONOMOUS_CONSTRUCTION"], "not_established")

    def test_different_test_outputs_still_need_a_bound_independent_semantic_review(self):
        for change in ({"different_objective": False}, {"reviewer": "test-inventor"},
                       {"second_contract_sha256": digest("another test")}, {"origin": "model_claim"}):
            prior = copy.deepcopy(self.evidence["distinctness_review"])
            self.evidence["distinctness_review"].update(change)
            with self.subTest(change=change):
                self.assertEqual(self.assess()["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
            self.evidence["distinctness_review"] = prior

    def test_source_asset_and_information_drift_block_comparison(self):
        for key in ("current_asset_sha256", "current_source_sha256"):
            with self.subTest(key=key):
                self.assertEqual(self.assess(**{key: digest("changed")})["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
        self.evidence["arms"]["without_asset"]["information_sha256"] = digest("less information")
        self.assertEqual(self.assess()["verdicts"]["CAPABILITY_TRANSFER"], "not_established")

    def test_control_leakage_and_unchanged_asset_do_not_pass(self):
        self.evidence["arms"]["without_asset"]["retained_asset_sha256"] = digest("first executable")
        self.assertEqual(self.assess()["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
        self.evidence["arms"]["without_asset"]["retained_asset_sha256"] = None
        arm = self.evidence["arms"]["with_asset"]
        arm["candidate_sha256"] = digest("first executable")
        arm["qualification"] = qualify(self.registration, "second", arm["candidate_sha256"],
            lambda data: {"value": data["x"] ** 2 + 1}, checker_sha256=digest("checker"))
        self.assertEqual(self.assess()["verdicts"]["CAPABILITY_TRANSFER"], "not_established")

    def test_failed_control_only_supports_registered_budget_difference(self):
        arm = self.evidence["arms"]["without_asset"]
        arm["status"] = "failed"
        arm["qualification"] = qualify(self.registration, "second", arm["candidate_sha256"],
            lambda data: {"value": 0}, checker_sha256=digest("checker"))
        result = self.assess()
        self.assertTrue(result["resource_comparison"]["control_exhausted_registered_budget"])
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "supported_by_recorded_comparison")
        self.assertEqual(result["verdicts"]["ACQUISITION_INCLUSIVE_RESOURCE_ADVANTAGE"], "not_established")
        arm["costs"] = costs(2)
        self.assertEqual(self.assess()["verdicts"]["CAPABILITY_TRANSFER"], "not_established")

    def test_intervention_counts_or_time_prevent_strict_autonomy(self):
        self.evidence["arms"]["with_asset"]["human_interventions"] = 1
        self.assertEqual(self.assess()["verdicts"]["STRICT_AUTONOMOUS_CONSTRUCTION"], "not_established")
        self.evidence["arms"]["with_asset"]["human_interventions"] = 0
        self.evidence["arms"]["with_asset"]["costs"] = costs(3, human=2)
        self.assertEqual(self.assess()["verdicts"]["STRICT_AUTONOMOUS_CONSTRUCTION"], "not_established")

    def test_monetary_assumptions_cannot_become_measured_economic_benefit(self):
        rows = costs(3, 500)
        rows[0]["basis"] = "assumed"
        result = summarize_costs(rows)
        self.assertEqual(result["total_cost_minor"], 500)
        self.assertIsNone(result["measured_cost_minor"])
        self.assertEqual(result["assumed_cost_stages"], ["acquisition"])
        rows[0]["basis"] = "unknown"
        with self.assertRaisesRegex(BridgeError, "Unknown monetary"):
            summarize_costs(rows)

    def test_duplicate_stage_negative_nan_and_fractional_calls_fail(self):
        for mutate in (lambda rows: rows.__setitem__(1, copy.deepcopy(rows[0])),
                       lambda rows: rows[0]["metrics"].update(cpu_seconds=-1),
                       lambda rows: rows[0]["metrics"].update(wall_seconds=float("nan")),
                       lambda rows: rows[0]["metrics"].update(model_calls=0.5)):
            rows = costs(1)
            mutate(rows)
            with self.assertRaises(BridgeError):
                summarize_costs(rows)

    def test_missing_baselines_do_not_make_up_a_human_cost_or_revenue(self):
        result = self.assess()
        self.assertIsNone(result["monetary_comparison"]["conventional_two_outcomes_minor"])
        self.assertEqual(result["verdicts"]["HUMAN_PRODUCTIVITY_COMPARISON"], "not_established")
        self.assertEqual(result["verdicts"]["MONETIZATION"], "not_established")
        self.assertTrue(any("has not been run" in issue for issue in result["issues"]))


class MissionTransferIntegrationTests(unittest.TestCase):
    def state(self):
        from bridge.frontier_mission import source_identity
        spec = specification()
        state = {"contracts": {stage: {**spec[stage], "review": {"reviewer": "operator",
                  "basis": "Authored test contract.", "limitations": "Not real economic evidence."}}
                  for stage in ("first", "second")},
                 "runtime_identity": {"origin": "fixture"}, "route": {"provider": "test", "model": "fixture"},
                 "max_attempts": 10, "max_output_tokens": 3072, "source_identity": source_identity(), "events": [], "builds": {}}
        first_sha = None
        for name in ("first", "with_asset", "without_asset"):
            stage = "first" if name == "first" else "second"
            source = "# " + name + "\ndef solve(data):\n    return data\n"
            sha = hashlib.sha256(source.encode()).hexdigest()
            if name == "first":
                first_sha = sha
            cases = state["contracts"][stage]["qualification"]
            raw = {"source_sha256": sha, "cases_sha256": digest(cases), "passed": True,
                   "passed_count": len(cases), "total": len(cases), "wall_seconds": 0.2, "cpu_seconds": 0.1,
                   "cases": [{"input_sha256": digest(case["input"]), "expected_sha256": digest(case["expected"]),
                              "actual": copy.deepcopy(case["expected"]), "passed": True} for case in cases]}
            state["builds"][name] = {"source": source, "source_sha256": sha, "qualified": True, "status": "qualified",
                "retained_sha256": first_sha if name == "with_asset" else None,
                "frozen": {"source_sha256": sha, "qualification_sha256": digest(cases)},
                "qualification": raw, "sources": {key: value for key, value in state["source_identity"].items()
                                                      if key in {"frontier_builder.py", "forge_sandbox.py"}},
                "route": copy.deepcopy(state["route"]), "contract_sha256": digest(state["contracts"][stage]),
                "allocation": {"max_attempts": 10, "max_output_tokens": 3072},
                "attempts": [{"status": "development_passed", "dispatch": "completed", "model_wall_seconds": 0.5,
                    "usage": {"input_tokens": 11, "output_tokens": 7}, "development": {"wall_seconds": 0.1}}],
                "totals": {"model_calls": 1, "unknown_dispatches": 0}, "interventions": [],
                "provenance": "configured_model_responses; caller must identify real or fixture transport"}
        state["transfer_registration"] = mission_registration(state)
        return state

    def test_actual_answer_replay_is_integrated_without_claiming_live_economics(self):
        state = self.state()
        result = mission_assessment(state)
        self.assertTrue(all(result["accepted"].values()))
        self.assertEqual(result["verdicts"]["ENGINEERING_CORRECTNESS"], "passed_recorded_checks")
        self.assertEqual(result["recorded_evidence"]["arms"]["first"]["origin"], "fixture")
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
        self.assertIsNone(result["costs"]["first"]["resources"]["model_calls"])
        self.assertEqual(result["costs"]["first"]["known_resources"]["model_calls"], 1)
        self.assertIn("acquisition", result["costs"]["first"]["unknown_resource_stages"]["model_calls"])
        self.assertIsNone(result["monetary_comparison"]["first_plus_second_minor"])

    def test_tampered_recorded_answer_frozen_contract_or_source_cannot_requalify(self):
        state = self.state()
        state["builds"]["with_asset"]["qualification"]["cases"][0]["actual"] = "incorrect"
        self.assertFalse(mission_assessment(state)["accepted"]["with_asset"])
        state = self.state()
        state["builds"]["first"]["source"] += "# changed"
        self.assertFalse(mission_assessment(state)["accepted"]["first"])
        state = self.state()
        state["contracts"]["second"]["qualification"][0]["expected"] = "revised after observing result"
        with self.assertRaisesRegex(BridgeError, "changed after registration"):
            mission_assessment(state)

    def test_live_origin_requires_exact_runtime_manifest_binding(self):
        state = self.state()
        state["runtime_identity"] = {"origin": "live_local_model", "model_weights_sha256": digest("weights"),
                                     "server_sha256": digest("server"), "python": "test"}
        state["transfer_registration"] = mission_registration(state)
        for build in state["builds"].values():
            build["execution_provenance"] = "live_local_model"
            build["runtime_identity_sha256"] = digest(state["runtime_identity"])
        result = mission_assessment(state)
        self.assertEqual(result["recorded_evidence"]["arms"]["first"]["origin"], "live")
        self.assertEqual(result["verdicts"]["CAPABILITY_TRANSFER"], "not_established")
        state["builds"]["first"]["runtime_identity_sha256"] = digest("different runtime")
        self.assertEqual(mission_assessment(state)["recorded_evidence"]["arms"]["first"]["origin"], "developer")

    def test_failed_discovery_and_build_dispatch_costs_remain_unknown(self):
        state = self.state()
        state["events"] = [{"kind": "discovery", "stage": "first", "status": "failed",
                            "wall_seconds": 1, "model_usage": None}]
        state["builds"]["first"]["attempts"][0]["dispatch"] = "unknown"
        state["builds"]["first"]["totals"]["unknown_dispatches"] = 1
        result = mission_assessment(state)
        arm = result["recorded_evidence"]["arms"]["first"]
        self.assertFalse(arm["all_attempts_recorded"])
        discovery = next(row for row in arm["costs"] if row["stage"] == "discovery")
        self.assertIsNone(discovery["metrics"]["model_calls"])
        self.assertIsNone(discovery["metrics"]["input_tokens"])
        self.assertEqual(result["verdicts"]["STRICT_AUTONOMOUS_CONSTRUCTION"], "not_established")

    def test_trace_allocation_information_and_runtime_cannot_be_assumed_matching(self):
        for field, value, identity in (("allocation", {"max_attempts": 100, "max_output_tokens": 3072}, "budget_sha256"),
                                       ("contract_sha256", digest("different task"), "information_sha256"),
                                       ("route", {"provider": "other", "model": "different"}, "environment_sha256"),
                                       ("sources", {"frontier_builder.py": digest("changed")}, "source_sha256")):
            state = self.state()
            state["builds"]["with_asset"][field] = value
            result = mission_assessment(state)
            receipt = result["recorded_evidence"]["arms"]["with_asset"]
            expected = (state["transfer_registration"]["budget_sha256"] if identity == "budget_sha256"
                        else state["transfer_registration"]["spec"]["comparison"][identity])
            with self.subTest(field=field):
                self.assertNotEqual(receipt[identity], expected)
                self.assertFalse(result["matched"]["with_asset"])


if __name__ == "__main__":
    unittest.main()
