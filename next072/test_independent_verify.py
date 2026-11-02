"""Authored development challenges; no published workbook is opened here.

The constructor is imported only as a synthetic result producer in this test
module. The production independent verifier has no constructor imports.
"""
import copy
import itertools
import io
import math
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from .independent_verify import (
    POLICIES, PRIMARY_POLICY, REPO, VerificationFailure, cell_value, compare_tree, independent_trace,
    normal_hit_scores, object_hash, reconstruct, reference_hit_threshold,
    review_policy_source, split, verify_result, workbook_rows,
)


def synthetic_rows(number_interventions=8, pair_limit=None):
    genes = [f"readout-{i}" for i in range(6)]
    control = [6.0 - i for i in range(6)]
    interventions = [f"G{i:02d}" for i in range(number_interventions)]
    single = {name: [control[g] + math.sin((i + 1) * (g + 2) / 5)
                      + .03 * i * i / (g + 1) for g in range(6)]
              for i, name in enumerate(interventions)}
    records = []
    pairs = list(itertools.combinations(interventions, 2))
    for index, (a, b) in enumerate(pairs if pair_limit is None else pairs[:pair_limit]):
        for g, gene in enumerate(genes):
            residual = .08 * (1 + index / 19) * math.cos((index + 2) * (g + 1) / 9)
            records.append({"gene_name": gene, "pert_group": a + "+" + b, "seed": 1,
                "AB": single[a][g] + single[b][g] - control[g] + residual,
                "A": single[a][g], "B": single[b][g], "ctrl": control[g], "error": residual, "rank": g + 1})
    return records


class IndependentAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Constructor/evaluator are intentionally absent from the production
        # verifier. This cross-implementation comparison uses only authored data.
        from .data import prepare_records
        from .evaluate import run
        cls.records = synthetic_rows()
        cls.independent, cls.measurement = reconstruct(cls.records, expected_readouts=6)
        cls.produced = prepare_records(cls.records, expected_readouts=6)
        cls.result = run(cls.produced)

    def test_independent_mean_feature_and_forty_two_policy_recomputation(self):
        compare_tree(self.produced, self.independent)
        audit = verify_result(self.independent, self.result)
        self.assertEqual(audit["policies_verified"], 42)
        self.assertEqual(audit["policy_query_records_checked"], 210)
        self.assertEqual(audit["primary_policy"], PRIMARY_POLICY)
        self.assertEqual(audit["initial_references_per_policy"], 7)
        self.assertEqual(audit["initial_reveal_budget_per_policy"], 5)
        self.assertEqual(audit["final_reveal_budget_per_policy"], 0)
        self.assertEqual(audit["profile_counts"]["total_profiles_used_per_policy"], 21)

    def test_124_authored_pairs_preserve_all_six_batches_and_42_controls(self):
        from .data import prepare_records
        from .evaluate import run
        records = synthetic_rows(number_interventions=17, pair_limit=124)
        independently_prepared, _ = reconstruct(records, expected_readouts=6)
        result = run(prepare_records(records, expected_readouts=6))
        audit = verify_result(independently_prepared, result)
        self.assertEqual(audit["source_pairs"], 124)
        self.assertEqual(audit["policies_verified"], 42)
        self.assertEqual(audit["initial_references_per_policy"], 31)
        self.assertEqual(audit["initial_reveal_budget_per_policy"], 23)
        self.assertEqual(audit["policy_query_records_checked"], 966)
        self.assertEqual(audit["adaptive_query_batches"], 6)
        self.assertEqual(result["target_count"], 24)

    def test_independent_hit_objective_differs_from_ucb_and_handles_zero_deviation(self):
        scores, probabilities = normal_hit_scores([2.0, 1.5], [10.0, .1], 1.0)
        self.assertGreater(2.0 + 10.0, 1.5 + .1)
        self.assertLess(scores[0], scores[1])
        self.assertLess(probabilities[0], probabilities[1])
        zero_scores, zero_probabilities = normal_hit_scores([0.0, 1.0, 2.0], [0.0, 0.0, 0.0], 1.0)
        self.assertEqual(zero_scores.tolist(), [-1e12, 0.0, 1e12])
        self.assertEqual(zero_probabilities.tolist(), [0.0, .5, 1.0])
        tail_scores, tail_probabilities = normal_hit_scores([30.0, 40.0], [1.0, 1.0], 0.0)
        self.assertEqual(tail_probabilities.tolist(), [1.0, 1.0])
        self.assertLess(tail_scores[0], tail_scores[1])
        with self.assertRaises(VerificationFailure):
            normal_hit_scores([1.0], [-.1], 0.0)

    def test_nearest_rank_threshold_and_initial_reference_freeze(self):
        for values, expected in (([1], 1), ([3, 1], 3), ([3, 1, 2], 3), ([1, 4, 2, 3], 3)):
            self.assertEqual(reference_hit_threshold(values), expected)
        references = split(self.independent["pair_names"])[0]
        outcomes = dict(zip(self.independent["pair_names"], self.independent["outcomes"]))
        threshold = reference_hit_threshold(outcomes[name] for name in references)
        altered = copy.deepcopy(self.independent)
        altered["outcomes"] = [value if name in references else value + 1000
            for name, value in zip(altered["pair_names"], altered["outcomes"])]
        for policy in (PRIMARY_POLICY, "ordinary_equal_content", "static_probability_of_hit", "constant_features"):
            before, after = [independent_trace(prepared, policy) for prepared in (self.independent, altered)]
            self.assertEqual({row["hit_threshold_from_initial_references"] for row in before + after}, {threshold})
            self.assertEqual(after[-1]["references_available_before_batch"], 7 if policy == "static_probability_of_hit" else 11)

    def test_reversed_pair_does_not_change_labels_features_or_split(self):
        reverse = [dict(row, pert_group="+".join(reversed(row["pert_group"].split("+"))),
                        A=row["B"], B=row["A"]) for row in self.records]
        rebuilt, _ = reconstruct(reverse, expected_readouts=6)
        compare_tree(rebuilt, self.independent)
        self.assertEqual(split(rebuilt["pair_names"]), split(self.independent["pair_names"]))

    def test_all_invalid_rows_remain_in_failure_denominator(self):
        rows = copy.deepcopy(self.records)
        rows[0]["AB"] = None
        rows[1]["AB"] = float("nan")
        with self.assertRaises(VerificationFailure) as caught:
            reconstruct(rows, expected_readouts=6)
        self.assertEqual(caught.exception.detail["denominator"]["source_rows"], len(rows))
        self.assertEqual(caught.exception.detail["denominator"]["invalid_records"], 2)

    def test_duplicate_missing_conflicting_or_misranked_inputs_fail(self):
        wrong_single = copy.deepcopy(self.records)
        wrong_single[6]["A"] += 1
        wrong_single[6]["error"] -= 1
        wrong_rank = [dict(row, rank=7 - row["rank"]) for row in self.records]
        examples = (self.records + [self.records[0]], self.records[1:], wrong_single, wrong_rank)
        for rows in examples:
            with self.subTest(size=len(rows)), self.assertRaises(VerificationFailure):
                reconstruct(rows, expected_readouts=6)

    def test_independent_formula_cell_and_error_cell_rejection(self):
        namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        for body in ('<c r="A1"><f>1+1</f><v>2</v></c>', '<c r="A1" t="e"><v>#N/A</v></c>'):
            node = ET.fromstring(body.replace('<c ', '<c xmlns="' + namespace + '" '))
            with self.assertRaises(VerificationFailure):
                cell_value(node, [])
        node = ET.fromstring('<c xmlns="' + namespace + '" r="A1" t="inlineStr"><is><t>readout</t></is></c>')
        self.assertEqual(cell_value(node, []), "readout")

    def test_independent_ooxml_relationship_header_and_row_extraction(self):
        # In-memory XML schema fixture, not a new authored user workbook.
        stream = io.BytesIO()
        ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        columns = ["gene_name", "pert_group", "seed", "AB", "A", "B", "ctrl", "error", "rank"]
        values = ["readout", "A+B", 1, 8, 3, 4, 1, 2, 1]
        sheet = '<worksheet xmlns="' + ns + '"><sheetData>'
        for number, row in enumerate((columns, values), 1):
            sheet += f'<row r="{number}">'
            for j, value in enumerate(row):
                address = chr(65 + j) + str(number)
                sheet += (f'<c r="{address}" t="inlineStr"><is><t>{value}</t></is></c>' if isinstance(value, str)
                          else f'<c r="{address}"><v>{value}</v></c>')
            sheet += '</row>'
        sheet += '</sheetData></worksheet>'
        with ZipFile(stream, "w") as archive:
            archive.writestr("xl/workbook.xml", '<workbook xmlns="' + ns
                + '" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                  '<sheets><sheet name="source" sheetId="1" r:id="rId1"/></sheets></workbook>')
            archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            archive.writestr("xl/worksheets/sheet1.xml", sheet)
        stream.seek(0)
        self.assertEqual(list(workbook_rows(stream)), [dict(zip(columns, values))])

    def test_unrevealed_values_cannot_change_any_policy_trace(self):
        for policy in POLICIES:
            trace = independent_trace(self.independent, policy)
            references = set(split(self.independent["pair_names"])[0])
            exposed = references | {row["pair"] for row in trace}
            changed = copy.deepcopy(self.independent)
            changed["outcomes"] = [value if pair in exposed else 1000.0 - value
                                   for pair, value in zip(changed["pair_names"], changed["outcomes"])]
            self.assertEqual(trace, independent_trace(changed, policy))

    def test_hidden_first_batch_values_cannot_change_commitment(self):
        trace = independent_trace(self.independent, PRIMARY_POLICY)
        references = set(split(self.independent["pair_names"])[0])
        changed = copy.deepcopy(self.independent)
        changed["outcomes"] = [value if pair in references else 999 - value
                               for pair, value in zip(changed["pair_names"], changed["outcomes"])]
        other = independent_trace(changed, PRIMARY_POLICY)
        fields = ("pair", "prediction", "acquisition_index", "acquisition_deviation",
                  "hit_threshold_from_initial_references", "model_hit_probability")
        self.assertEqual([{key: row[key] for key in fields} for row in trace[:4]],
                         [{key: row[key] for key in fields} for row in other[:4]])

    def test_forged_reveal_target_metric_or_budget_fails(self):
        for mutation in ("value", "label", "metric", "budget", "duplicate", "missing_control", "primary", "threshold", "probability"):
            altered = copy.deepcopy(self.result)
            row = altered["receipts"][PRIMARY_POLICY][0]
            if mutation == "value": row["revealed_D"] += .1
            if mutation == "label": row["is_target_after_seal"] = not row["is_target_after_seal"]
            if mutation == "metric": altered["policy_results"][PRIMARY_POLICY]["discoveries"] += 1
            if mutation == "budget": row["remaining_budget_after"] += 1
            if mutation == "duplicate": altered["receipts"][PRIMARY_POLICY][1]["pair"] = row["pair"]
            if mutation == "missing_control": del altered["policy_results"]["hash_31"]
            if mutation == "primary": altered["primary_policy"] = "sequential_kernel"
            if mutation == "threshold": row["hit_threshold_from_initial_references"] += .1
            if mutation == "probability": row["model_hit_probability"] += .1
            with self.subTest(mutation=mutation), self.assertRaises(VerificationFailure):
                verify_result(self.independent, altered)

    def test_resealed_wrong_acquisition_is_rejected_independently(self):
        altered = copy.deepcopy(self.result)
        trace = altered["receipts"][PRIMARY_POLICY]
        trace[0]["prediction"] += .2
        unlabelled = [{key: value for key, value in row.items()
                      if key not in {"is_target_after_seal", "cumulative_discoveries_after_seal"}} for row in trace]
        altered["policy_results"][PRIMARY_POLICY]["sealed_selection_sha256"] = object_hash(unlabelled)
        with self.assertRaises(VerificationFailure):
            verify_result(self.independent, altered)

    def test_unsupported_physical_or_financial_admission_fails(self):
        for key in ("physical_or_biological_delivery_admission", "commercial_or_native_financial_admission"):
            altered = copy.deepcopy(self.result)
            altered[key] = "ACCEPTED"
            with self.assertRaises(VerificationFailure):
                verify_result(self.independent, altered)

    def test_reviewed_policy_has_only_declared_context(self):
        self.assertTrue(review_policy_source(REPO / "next072/policy.py")["accepted"])


class EconomicAdmissionTests(unittest.TestCase):
    def test_unknown_economics_remains_hold_and_no_transactions(self):
        from .economic_check import evaluate
        report = evaluate(research_artifact_accepted=True, allocation_boundary_met=True)
        self.assertEqual(report["economic_evidence_status"], "HOLD")
        self.assertEqual(report["scope_matched_financial_admission"], "NOT_ESTABLISHED")
        self.assertTrue(report["unknown_inputs"])
        self.assertEqual({row["capital_hypothesis_usd"] for row in report["capital_and_terms_comparisons"]}, {0, 100000, 1000000000})
        self.assertEqual(report["native_collections"], 0)
        self.assertEqual(report["generic_adaptive_platform_missing_means_claim"], "SOURCE_REJECTED")
        self.assertEqual(report["registered_primary_allocation_method"], "probability_of_hit")
        self.assertIn("public_complete_outcome_self_service", report["laboratory_choice_menu"])
        self.assertEqual(report["actual_new_assays_avoided_by_this_replay"], 0)
        self.assertEqual(report["capital_received"], 0)
        self.assertEqual(report["laboratory_choice_menu"]["separately_qualified_prospective_study"]["status"], "REFUSE")

    def test_future_collections_do_not_fund_setup(self):
        from .economic_check import ECONOMIC_INPUTS, cash_schedule
        params = dict.fromkeys(ECONOMIC_INPUTS, 0)
        params.update(setup_cash=10, analysis_price=1000, accepted_balance_collection=1000)
        result = cash_schedule(params, 0, False)
        self.assertEqual(result["events"][-1]["cash"], 990)
        self.assertEqual(result["status"], "REFUSE")
        self.assertEqual(result["maximum_cash_shortfall"], 10)

    def test_refundable_deposits_do_not_create_unprotected_working_cash(self):
        from .economic_check import ECONOMIC_INPUTS, cash_schedule
        params = dict.fromkeys(ECONOMIC_INPUTS, 0)
        params.update(analysis_price=50, customer_deposit_received=50, fulfillment_cash=110)
        result = cash_schedule(params, 100, True)
        self.assertEqual(result["events"][1]["cash"], 40)
        self.assertEqual(result["events"][1]["protected"], 50)
        self.assertEqual(result["maximum_cash_shortfall"], 10)
        self.assertEqual(result["status"], "REFUSE")

    def test_all_preexisting_protection_is_preserved_at_every_event(self):
        from .economic_check import ECONOMIC_INPUTS, cash_schedule
        params = dict.fromkeys(ECONOMIC_INPUTS, 0)
        params.update(committed_refund_reserve=30, collateral_reserve=40, warranty_reserve=50)
        result = cash_schedule(params, 100, False)
        self.assertEqual([row["protected"] for row in result["events"]], [120, 120, 120, 120])
        self.assertEqual(result["constraints"][0]["status"], "REFUSE")
        self.assertEqual(result["maximum_cash_shortfall"], 20)

    def test_better_complete_public_option_prevents_forced_analysis_sale(self):
        from .economic_check import ECONOMIC_INPUTS, evaluate
        params = dict.fromkeys(ECONOMIC_INPUTS, 0)
        params.update(analysis_price=100, buyer_analysis_value=1000, public_outcome_value=1000,
            human_same_algorithm_full_cost=200, investor_discounted_distribution=2000000000)
        report = evaluate(params, research_artifact_accepted=True, supplier_terms_accepted=True, financing_terms_accepted=True)
        self.assertEqual(report["laboratory_choice_menu"]["source_bound_analysis_offer"]["status"], "REFUSE")
        self.assertEqual(report["economic_evidence_status"], "REFUSE")

    def test_negative_report_never_changes_budget_crossing_acceptance(self):
        from .economic_check import evaluate
        report = evaluate(research_artifact_accepted=True, allocation_boundary_met=False)
        separate = report["report_and_allocation_service_are_separate"]
        self.assertEqual(separate["negative_analysis_report_technical_gate"]["status"], "PASS")
        self.assertEqual(separate["experimental_allocation_service_status"], "REFUSE")

    def test_known_unprofitable_offer_is_refused_at_any_capital(self):
        from .economic_check import ECONOMIC_INPUTS, evaluate
        params = dict.fromkeys(ECONOMIC_INPUTS, 0)
        params.update(analysis_price=100, compute_and_inference_cost=101,
            buyer_analysis_value=1000, human_same_algorithm_full_cost=200,
            investor_discounted_distribution=2000000000)
        report = evaluate(params, research_artifact_accepted=True, supplier_terms_accepted=True, financing_terms_accepted=True)
        self.assertEqual(report["economic_evidence_status"], "REFUSE")
        self.assertTrue(all(row["joint_entry_status"] == "REFUSE" for row in report["capital_and_terms_comparisons"]))

    def test_supplied_synthetic_payoffs_never_establish_native_admission(self):
        from .economic_check import ECONOMIC_INPUTS, evaluate
        params = dict.fromkeys(ECONOMIC_INPUTS, 0)
        params.update(analysis_price=100, buyer_analysis_value=1000,
            human_same_algorithm_full_cost=200, investor_discounted_distribution=2000000000)
        report = evaluate(params, research_artifact_accepted=True, supplier_terms_accepted=True, financing_terms_accepted=True)
        self.assertEqual(report["economic_evidence_status"], "CONDITIONAL_SCENARIO_ONLY")
        self.assertEqual(report["scope_matched_financial_admission"], "NOT_ESTABLISHED")
        self.assertEqual(report["native_collections"], 0)


if __name__ == "__main__":
    unittest.main()
