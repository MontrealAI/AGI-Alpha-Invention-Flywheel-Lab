# SPDX-License-Identifier: Apache-2.0
"""Exercise evidence-bound presentation using the actual local runner and journal."""

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.mission_outcomes import assemble_outcome, validate_contract
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime
from bridge.workflows import digest, encoded
from test_mission_evidence import bind, construct, new_spec, record, respond, table_plan, WRONG_QUERY


class MissionOutcomeTests(unittest.TestCase):
    def processor(self, responses):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        service = UniversalMissionService(FixtureRuntime(responses), root.name)
        self.addCleanup(service.close)
        return service

    def run_case(self, requirements, actions, **overrides):
        draft = "All pooled sessions were independently verified at 187/50 L/min."
        service = self.processor([respond(*actions, summary=draft)])
        spec = new_spec(requirements, **overrides)
        state = service.step(service.submit(spec)["id"])
        return service, state, state["outcome"]

    def test_verified_quantity_assembled_from_real_receipt_and_not_from_draft(self):
        draft = {"tool": "write_document", "name": "proposal.md", "content": "138461.54 mg/L is the final result."}
        _, state, outcome = self.run_case(table_plan(), [draft, construct(), bind()])
        self.assertEqual(outcome["status"], "VERIFIED")
        self.assertTrue(outcome["quantitative_report_ready"])
        self.assertEqual(outcome["independent_acceptance"], "NOT_ESTABLISHED")
        self.assertEqual(outcome["unresolved"], [])
        self.assertEqual(outcome["revision_sha256"], state["spec_hash"])
        self.assertEqual(outcome["contract_sha256"], digest(outcome["contract"]))
        self.assertEqual(outcome["contract"]["required_claims"], ["concentration"])
        self.assertEqual(outcome["contract"]["original_ambition"], state["objective"])
        result, = outcome["conclusions"]
        self.assertEqual((result["id"], result["value"], result["unit"]), ("concentration", "16600/13", "mg/L"))
        self.assertEqual(result["execution_sha256"], state["evidence"]["claims"][0]["execution_receipt"]["sha256"])
        self.assertNotIn(b"187/50", encoded(outcome))
        self.assertNotIn(b"138461.54", encoded(outcome))
        self.assertNotIn(b"reference\":", encoded(outcome["contract"]))
        self.assertIn("proposal.md", state["artifacts"])
        self.assertTrue(any(event["kind"] == "route_proposed" and "187/50" in event["detail"]["summary"]
                            for event in state["events"]))

    def test_french_missing_duration_uses_approved_row_identity_without_a_rate(self):
        data = {"logs": [
            {"litres": 47, "minutes": 17, "session": "ligne-9"},
            {"litres": 61, "minutes": None, "session": "ligne-11"},
            {"litres": 79, "minutes": 33, "session": "ligne-14"},
        ]}
        plan = {"approved_tables": {"line_log": data}, "evidence": {"inputs": {"line_log": record(data)}, "claims": [{
            "id": "flow_rate", "dataset": "line_log", "tool": "run_table", "unit": "L/min", "dimension": "volume_per_time",
            "locator": ["rows", 0, 0], "version": "input-v1", "required_fields": [["logs", "minutes"]], "requires": {},
        }]}}
        draft = {"tool": "write_document", "name": "proposal.md", "content": "Débit vérifié 187/50 L/min."}
        plan["approved_schemas"] = {"line_log": {
            "tables": {"logs": {"litres": "INTEGER", "minutes": "INTEGER", "session": "TEXT"}},
            "primary_keys": {"logs": ["session"]},
        }}
        _, _, outcome = self.run_case(plan, [draft], language="fr")
        self.assertEqual(outcome["status"], "ABSTAIN")
        self.assertIn("observation requise manque", outcome["message"])
        self.assertFalse(outcome["quantitative_report_ready"])
        self.assertEqual(outcome["conclusions"], [])
        unresolved, = outcome["unresolved"]
        self.assertEqual(unresolved["reason"], "REQUIRED_FIELD_MISSING")
        self.assertEqual(unresolved["missing"], [{"path": ["logs", "minutes"], "row_index": 1,
                                                  "row_key": {"session": "ligne-11"},
                                                  "label": "logs[1].minutes (session=ligne-11)"}])
        self.assertNotIn(b"187/50", encoded(outcome))

    def test_eligible_partial_result_and_missing_dataset_are_separate(self):
        plan = table_plan()
        required = plan["evidence"]["claims"]
        required.append({**required[0], "id": "other_concentration", "dataset": "pending"})
        _, _, outcome = self.run_case(plan, [construct(), bind()])
        self.assertEqual(outcome["status"], "PARTIAL")
        self.assertFalse(outcome["quantitative_report_ready"])
        self.assertEqual([item["id"] for item in outcome["conclusions"]], ["concentration"])
        unresolved, = outcome["unresolved"]
        self.assertEqual(unresolved["reason"], "AUTHORIZED_INPUT_MISSING")
        self.assertEqual(unresolved["missing"], [{"dataset": "pending", "label": "pending"}])
        self.assertNotIn("value", unresolved)

    def test_report_keeps_executed_quantity_and_declared_tolerance(self):
        plan = table_plan(reference={"value": "16613/13", "tolerance": "1", "source": "Separate bounded reference"})
        _, _, outcome = self.run_case(plan, [construct(), bind()])
        result, = outcome["conclusions"]
        self.assertEqual(outcome["status"], "VERIFIED")
        self.assertEqual((result["value"], result["reference_tolerance"]), ("16600/13", "1"))
        self.assertEqual(result["assumptions"], {"additive_volumes": True, "solute_conserved": True})
        self.assertNotIn(b"16613/13", encoded(outcome))

    def test_wrong_reference_fixture_and_stale_operation_never_publish_values(self):
        wrong = construct(WRONG_QUERY)
        for actions, reason in (
            ([wrong, bind()], "REFERENCE_DISAGREES"),
            ([construct(), bind(data={"fixtures": {"batches": []}})], "INPUT_ORIGIN_INELIGIBLE"),
            ([construct(), bind(), wrong], "EXECUTION_OPERATION_STALE"),
        ):
            with self.subTest(reason=reason):
                _, _, outcome = self.run_case(table_plan(), actions)
                self.assertEqual(outcome["status"], "BLOCKED")
                self.assertEqual(outcome["unresolved"][0]["reason"], reason)
                self.assertNotIn("value", outcome["unresolved"][0])
                self.assertEqual(outcome["conclusions"], [])

    def test_other_revision_and_forged_projection_are_rejected(self):
        service, prior, _ = self.run_case(table_plan(), [construct(), bind()])
        child = service.revise(prior["id"], new_spec(table_plan()))
        pasted = assemble_outcome(child, prior["evidence"])
        self.assertEqual(pasted["status"], "BLOCKED")
        self.assertEqual(pasted["unresolved"][0]["reason"], "OUTCOME_EVIDENCE_SCOPE_MISMATCH")
        altered = deepcopy(prior["evidence"])
        altered["claims"][0]["value"] = "42"
        self.assertEqual(assemble_outcome(prior, altered)["status"], "BLOCKED")
        altered = deepcopy(prior["evidence"])
        altered["claims"][0]["event_sha256"] = "0" * 64
        self.assertEqual(assemble_outcome(prior, altered)["status"], "BLOCKED")

    def test_cached_projection_cannot_restore_a_claim_after_new_refusal_or_overwrite(self):
        requirements = table_plan()
        required = requirements["evidence"]["claims"]
        required.append({**required[0], "id": "second", "dataset": "unknown"})
        for action in (bind(data={"fixtures": {"batches": []}}), construct(WRONG_QUERY)):
            with self.subTest(tool=action["tool"]):
                service = self.processor([respond(construct(), bind()), respond(action)])
                ident = service.submit(new_spec(requirements))["id"]
                earlier = service.step(ident)
                self.assertEqual(earlier["outcome"]["status"], "PARTIAL")
                current = service.step(ident)
                stale = assemble_outcome(current, earlier["evidence"])
                self.assertEqual(stale["status"], "BLOCKED")
                self.assertEqual(stale["conclusions"], [])

    def test_source_bound_calculation_and_qualitative_work_stay_available_for_review(self):
        plan = table_plan()
        del plan["evidence"]["claims"][0]["reference"]
        _, state, outcome = self.run_case(plan, [construct(), bind()])
        self.assertEqual(state["evidence"]["claims"][0]["status"], "SOURCE_BOUND")
        self.assertEqual(outcome["status"], "UNVERIFIED")
        self.assertEqual(outcome["unresolved"][0]["reason"], "INDEPENDENT_REFERENCE_REQUIRED")
        self.assertFalse(outcome["conclusions"])
        self.assertNotIn("value", outcome["unresolved"][0])
        writer = {"tool": "write_document", "name": "concept.md", "content": "A useful design outline."}
        _, state, outcome = self.run_case({}, [writer], ambition="Design a garden.")
        self.assertEqual(state["status"], "needs_review")
        self.assertEqual(outcome["status"], "UNVERIFIED")
        self.assertEqual(outcome["unresolved"], [])
        self.assertIn("concept.md", state["artifacts"])

    def test_operator_contract_cannot_promote_outcomes_or_drop_registered_claims(self):
        requirements = table_plan()
        validate_contract({"deliverable": "An exact mixture report", "required_claims": ["concentration"],
                           "criteria": ["Preserve mass"], "verification": "Compare with a separate reference."}, requirements)
        for declaration in ({"accepted": True}, {"required_claims": []}, {"required_claims": ["unknown"]},
                            {"criteria": "unknown"}, {"deliverable": ""}):
            with self.subTest(declaration=declaration), self.assertRaises(BridgeError) as error:
                validate_contract(declaration, requirements)
            self.assertEqual(error.exception.code, "MISSION_OUTCOME_CONTRACT")

    def test_queued_work_is_pending_and_revoked_authority_blocks_it(self):
        service = self.processor([])
        state = service.submit(new_spec(table_plan()))
        self.assertEqual(assemble_outcome(state, state["evidence"])["status"], "PENDING")
        self.assertEqual(assemble_outcome(state, state["evidence"], authority="revoked")["status"], "BLOCKED")
