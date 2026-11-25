# SPDX-License-Identifier: Apache-2.0
"""Exercise real tool primitives with authored and historical model proposals."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import BridgeError
from bridge.mission_evidence import assess_claims
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime
from bridge.workflows import digest


MIXTURE = {"batches": [
    {"volume": 75000, "volume_unit": "mL", "concentration": 240, "concentration_unit": "g/L"},
    {"volume": 160, "volume_unit": "L", "concentration": 95000, "concentration_unit": "mg/L"},
    {"volume": 25000, "volume_unit": "mL", "concentration": 0, "concentration_unit": "mg/L"},
]}
TABLE_SCHEMA = {"batches": {"volume": "INTEGER", "volume_unit": "TEXT", "concentration": "INTEGER", "concentration_unit": "TEXT"}}
QUERY = (
    "WITH normalized AS (SELECT CASE WHEN volume_unit = 'L' THEN volume * 1000 ELSE volume END AS v, "
    "CASE WHEN concentration_unit = 'g/L' THEN concentration * 1000 ELSE concentration END AS c FROM batches) "
    "SELECT CAST(SUM(v*c) AS TEXT) || '/' || CAST(SUM(v)*100 AS TEXT) FROM normalized"
)
WRONG_QUERY = QUERY.replace("THEN concentration * 1000", "THEN concentration * 100000")


def reference_value(data):
    litres, mass_mg = [], []
    for row in data["batches"]:
        v = Fraction(row["volume"], 100 * (1000 if row["volume_unit"] == "mL" else 1))
        c = Fraction(row["concentration"], 100) * (1000 if row["concentration_unit"] == "g/L" else 1)
        litres.append(v)
        mass_mg.append(v*c)
    return {"volume": sum(litres), "mass": sum(mass_mg), "concentration": sum(mass_mg)/sum(litres)}


def record(data, *, origin="AUTHORIZED_MISSION_INPUT", kind="table", **overrides):
    result = {"kind": kind, "origin": origin, "version": "input-v1", "sha256": digest(data),
              "facts": {"additive_volumes": True, "solute_conserved": True}, **overrides}
    if kind == "values":
        result["values"] = data
    return result


def table_plan(data=MIXTURE, **claim_overrides):
    claim = {"id": "concentration", "dataset": "ledger", "tool": "run_table", "locator": ["rows", 0, 0],
             "unit": "mg/L", "dimension": "mass/volume", "version": "input-v1",
             "requires": {"additive_volumes": True, "solute_conserved": True},
             "required_fields": [["batches", name] for name in TABLE_SCHEMA["batches"]],
             "reference": {"value": str(reference_value(data)["concentration"]), "source": "Separate exact Fraction recomputation"},
             **claim_overrides}
    return {"approved_tables": {"ledger": data}, "evidence": {"inputs": {"ledger": record(data)}, "claims": [claim]}}


def new_spec(requirements, **overrides):
    return {"ambition": "Use the registered ledger to reconcile the requested genuine numerical result.",
            "language": "en", "provider": "fixture", "model": "authored-proposal",
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "max_turns": 5, "max_actions": 20, "max_output_tokens": 1024, "requirements": requirements, **overrides}


def construct(sql=QUERY, schema=TABLE_SCHEMA):
    return {"tool": "construct_table", "name": "ledger.json", "schema": schema, "sql": sql}


def bind(*, data=None, unit="mg/L", dimension="mass/volume", value=None):
    claim = {"id": "concentration", "unit": unit, "dimension": dimension}
    if value is not None:
        claim["value"] = value
    return {"tool": "run_table", "name": "ledger.json", "input": {"dataset": "ledger"} if data is None else data,
            "claim": claim}


def respond(*actions, summary="Record the attempted calculation.", done=True):
    return {"summary": summary, "actions": list(actions), "done": done}


class MissionEvidenceTests(unittest.TestCase):
    def service(self, responses):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        runtime = FixtureRuntime(responses)
        service = UniversalMissionService(runtime, temporary.name)
        self.addCleanup(service.close)
        return service, runtime

    def run_actions(self, actions, requirements=None):
        service, _ = self.service([respond(*actions)])
        mission = service.submit(new_spec(table_plan() if requirements is None else requirements))
        return service.step(mission["id"])

    def test_exact_unit_normalization_on_historical_and_distinct_rows(self):
        # The first row set is public historical evidence, from the m06 held case.
        # The second is a different engineering regression, not a hidden holdout.
        distinct = {"batches": [
            {"volume": 35000, "volume_unit": "mL", "concentration": 4000, "concentration_unit": "mg/L"},
            {"volume": 72, "volume_unit": "L", "concentration": 480, "concentration_unit": "g/L"},
            {"volume": 10, "volume_unit": "L", "concentration": 0, "concentration_unit": "mg/L"},
        ]}
        for data, mass, volume in ((MIXTURE, Fraction(3320), Fraction(13, 5)),
                                   (distinct, Fraction(3470), Fraction(117, 100))):
            with self.subTest(data=data):
                actual = self.run_actions([construct(), bind()], table_plan(data))
                self.assertEqual(actual["status"], "needs_review")
                result = actual["evidence"]["claims"][0]
                self.assertEqual(result["status"], "VERIFIED")
                self.assertEqual(Fraction(result["value"]) * volume, mass)
                evidence = result["execution_receipt"]
                self.assertEqual(evidence["input"]["sha256"], digest(data))
                self.assertEqual(evidence["revision_sha256"], actual["spec_hash"])
                self.assertEqual(evidence["operation"]["artifact_sha256"], actual["artifacts"]["ledger.json"]["sha256"])
                self.assertEqual(actual["qualification"], "UNVERIFIED")

    def test_wrong_prose_and_replayed_development_fixture_never_supply_a_claim(self):
        unsupported = {"tool": "write_document", "name": "result.md", "content": "Claimed concentration: 138461.54 mg/L"}
        count_fixture = {"tool": "run_table", "name": "ledger.json", "input": {"fixtures": {"samples": [{"n": 2}]}}}
        construction = construct("SELECT n FROM samples", {"samples": {"n": "INTEGER"}})
        view = self.run_actions([unsupported, construction, count_fixture, {**count_fixture, "claim": bind()["claim"]}])
        tool_events = [x["detail"]["outcome"] for x in view["events"] if x["kind"] == "tool_completed"]
        actual = next(x for x in tool_events if "rows" in x)
        self.assertEqual(actual["rows"], [[2]])
        self.assertEqual(actual["input_origin"], "MODEL_DEVELOPMENT_FIXTURE")
        self.assertEqual(view["evidence"]["claims"][0]["reason"], "INPUT_ORIGIN_INELIGIBLE")
        self.assertNotIn("value", view["evidence"]["claims"][0])
        self.assertEqual(view["status"], "ready")

    def test_frozen_reference_is_private_from_constructor_and_repair_is_possible(self):
        wrong = construct(WRONG_QUERY)
        service, runtime = self.service([
            respond(wrong, bind()),
            respond(construct(), bind(value="138461.54")),
            respond(bind()),
        ])
        ident = service.submit(new_spec(table_plan()))["id"]
        for reason in ("REFERENCE_DISAGREES", "CLAIM_CONTRADICTS_EXECUTED_RESULT"):
            view = service.step(ident)
            self.assertEqual(view["status"], "ready")
            result = view["evidence"]["claims"][0]
            self.assertEqual(result["reason"], reason)
            self.assertNotIn("value", result)
        view = service.step(ident)
        self.assertEqual(view["evidence"]["claims"][0]["value"], "16600/13")
        self.assertNotIn('"reference":', runtime.calls[0]["prompt"])
        self.assertNotIn("Separate exact Fraction recomputation", runtime.calls[2]["prompt"])
        self.assertIn("CLAIM_CONTRADICTS_EXECUTED_RESULT", runtime.calls[2]["prompt"])

    def test_pre_action_scope_denials_are_distinct(self):
        changed = deepcopy(table_plan())
        changed["approved_tables"]["ledger"]["batches"][0]["concentration"] = 11
        stale = deepcopy(table_plan())
        stale["evidence"]["inputs"]["ledger"]["version"] = "input-v2"
        inapplicable = deepcopy(table_plan())
        inapplicable["evidence"]["inputs"]["ledger"]["facts"]["additive_volumes"] = False
        missing = deepcopy(table_plan())
        missing["approved_tables"]["ledger"]["batches"][0]["concentration"] = None
        missing["evidence"]["inputs"]["ledger"]["sha256"] = digest(missing["approved_tables"]["ledger"])
        wrong_dataset = deepcopy(table_plan())
        wrong_dataset["approved_tables"]["other"] = MIXTURE
        for plan, action, reason, status in (
            (changed, bind(), "INPUT_BYTES_CHANGED", "REJECTED"),
            (stale, bind(), "INPUT_VERSION_MISMATCH", "REJECTED"),
            (inapplicable, bind(), "INPUT_ASSUMPTIONS_INCOMPATIBLE", "REJECTED"),
            (missing, bind(), "REQUIRED_FIELD_MISSING", "ABSTAIN"),
            (wrong_dataset, bind(data={"dataset": "other"}), "CLAIM_DATASET_MISMATCH", "REJECTED"),
            (table_plan(), bind(unit="g/L"), "CLAIM_UNITS_MISMATCH", "REJECTED"),
        ):
            with self.subTest(reason=reason):
                result = self.run_actions([construct(), action], plan)
                claim = result["evidence"]["claims"][0]
                self.assertEqual((claim["status"], claim["reason"]), (status, reason))
                self.assertFalse(any(e["kind"] == "tool_completed" and e["detail"]["tool"] == "run_table" for e in result["events"]))

    def test_unapproved_lineage_and_missing_source_abstention(self):
        plan = deepcopy(table_plan())
        plan["evidence"]["inputs"]["fixture"] = record({"seed": 1}, kind="values", origin="SYNTHETIC_EXAMPLE")
        plan["evidence"]["inputs"]["ledger"].update(origin="DERIVED_DATA", parents={"fixture": digest({"seed": 1})})
        result = self.run_actions([construct(), bind()], plan)
        self.assertEqual(result["evidence"]["claims"][0]["reason"], "INPUT_ORIGIN_INELIGIBLE")
        absent = table_plan()
        absent["approved_tables"] = {}
        result = self.run_actions([], absent)
        self.assertEqual(result["evidence"]["status"], "ABSTAIN")
        self.assertEqual(result["evidence"]["claims"][0]["reason"], "AUTHORIZED_INPUT_MISSING")
        self.assertTrue(any(e["kind"] == "awaiting_evidence" for e in result["events"]))

    def test_mission_ids_artifact_revisions_and_receipt_tampering(self):
        service, _ = self.service([respond(construct(), bind())])
        ident = service.submit(new_spec(table_plan()))["id"]
        view = service.step(ident)
        changed = deepcopy(view)
        executed = next(e for e in changed["events"] if e["kind"] == "tool_completed" and e["detail"]["tool"] == "run_table")
        executed["detail"]["outcome"]["rows"] = [["16600/13"]]
        self.assertEqual(assess_claims(changed, lambda name: None)["claims"][0]["reason"], "EXECUTION_RECEIPT_CHANGED")
        other = deepcopy(view)
        other["id"] = "wf_" + "7"*24
        self.assertEqual(assess_claims(other, lambda name: None)["claims"][0]["reason"], "EXECUTION_SCOPE_MISMATCH")
        revision = self.run_actions([construct(), bind(), construct(WRONG_QUERY)])
        self.assertEqual(revision["evidence"]["claims"][0]["reason"], "EXECUTION_OPERATION_STALE")
        moved = service.import_archive(service.export(ident), new_spec(table_plan()))
        self.assertEqual(moved["evidence"]["claims"][0]["reason"], "NO_BOUND_EXECUTION")

    def test_bound_arithmetic_uses_operator_bytes_and_does_not_invent_independent_acceptance(self):
        values = {"capacity": 60, "used": 9}
        requirements = {"evidence": {"inputs": {"usage": record(values, kind="values")}, "claims": [{
            "id": "rate", "dataset": "usage", "tool": "run_instrument", "locator": ["output", "rate"],
            "unit": "%", "dimension": "proportion", "version": "input-v1", "requires": {},
            "required_fields": [["capacity"], ["used"]],
        }]}}
        write = {"tool": "construct_instrument", "name": "usage.json", "spec": {"name": "Usage", "inputs": ["capacity", "used"],
            "outputs": {"rate": {"op": "div", "args": [{"op": "mul", "args": [100, {"field": "used"}]}, {"field": "capacity"}]}}}}
        bound = {"tool": "run_instrument", "name": "usage.json", "input": {"dataset": "usage"},
                 "claim": {"id": "rate", "unit": "%", "dimension": "proportion"}}
        result = self.run_actions([write, bound], requirements)
        claim = result["evidence"]["claims"][0]
        self.assertEqual((claim["status"], claim["value"]), ("SOURCE_BOUND", "15"))
        self.assertEqual(result["status"], "needs_review")
        protected = deepcopy(requirements)
        protected["evidence"]["inputs"]["usage"]["origin"] = "PROTECTED_CONFIRMATION_DATA"
        with self.assertRaises(BridgeError) as error:
            self.service([])[0].submit(new_spec(protected))
        self.assertEqual(error.exception.code, "MISSION_EVIDENCE_PLAN")

    def test_formula_claim_is_withdrawn_through_restart_and_requires_fresh_bound_run(self):
        values = {"reading": 3}
        requirements = {"evidence": {"inputs": {"observed": record(values, kind="values")}, "claims": [{
            "id": "calibration", "dataset": "observed", "tool": "run_instrument", "locator": ["output", "result"],
            "unit": "points", "dimension": "score", "version": "input-v1", "requires": {},
            "reference": {"value": "3", "source": "Separate exact arithmetic"},
        }]}}
        name = "calibration.json"
        write = {"tool": "construct_instrument", "name": name,
                 "spec": {"inputs": ["reading"], "outputs": {"result": {"field": "reading"}}}}
        invalid = {**write, "spec": {"inputs": ["reading"], "outputs": {"result": {"op": "if", "args": [True, 9]}}}}
        compute = {"tool": "run_instrument", "name": name, "input": {"dataset": "observed"},
                   "claim": {"id": "calibration", "unit": "points", "dimension": "score"}}
        report = {"tool": "write_document", "name": "notes.md", "content": "Checked the synthetic observation."}
        spec = new_spec(requirements, acceptance=[{"artifact": "notes.md", "kind": "document", "min_chars": 10}])
        service, _ = self.service([respond(write, compute, done=False), respond(invalid)])
        ident = service.submit(spec)["id"]
        verified = service.step(ident)
        self.assertEqual(verified["status"], "ready")
        self.assertEqual(verified["outcome"]["status"], "VERIFIED")
        historical = verified["evidence"]["claims"][0]["execution_receipt"]
        prior_sha = verified["artifacts"][name]["sha256"]

        rejected = service.step(ident)
        root = service.root
        self.assertEqual(service.pause(ident)["status"], "paused")
        service.close()
        opened = UniversalMissionService(FixtureRuntime([respond(write), respond(compute, report)]), root)
        self.addCleanup(opened.close)
        for withheld in (rejected, opened.get(ident)):
            self.assertEqual(withheld["evidence"]["status"], "REJECTED")
            claim = withheld["evidence"]["claims"][0]
            self.assertEqual(claim["reason"], "INSTRUMENT_REPAIR_REQUIRED")
            self.assertNotIn("value", claim)
            self.assertFalse(withheld["outcome"]["quantitative_report_ready"])
            self.assertEqual(withheld["outcome"]["conclusions"], [])
            self.assertEqual(withheld["outcome"]["unresolved"][0]["reason"], "INSTRUMENT_REPAIR_REQUIRED")
            dispositions = [event["detail"] for event in withheld["events"] if event["kind"] == "claim_dispositions"]
            self.assertEqual(dispositions[-1]["claims"][0]["reason"], "INSTRUMENT_REPAIR_REQUIRED")
            self.assertTrue(any(event["detail"].get("outcome", {}).get("claim_execution") == historical
                                for event in withheld["events"]))

        opened.resume(ident, background=False)
        rebuilt = opened.step(ident)
        self.assertEqual(rebuilt["artifacts"][name]["sha256"], prior_sha)
        self.assertEqual(rebuilt["evidence"]["claims"][0]["reason"], "EXECUTION_OPERATION_STALE")
        self.assertEqual(rebuilt["outcome"]["conclusions"], [])
        self.assertEqual(rebuilt["status"], "ready")
        recovered = opened.step(ident)
        self.assertEqual(recovered["status"], "needs_review")
        self.assertEqual(recovered["evidence"]["claims"][0]["value"], "3")
        self.assertEqual(recovered["outcome"]["status"], "VERIFIED")
        self.assertNotEqual(recovered["outcome"]["conclusions"][0]["event_sha256"],
                            verified["outcome"]["conclusions"][0]["event_sha256"])

    def test_large_execution_attachment_stays_bound_and_visible_claim_survives_prompt_excerpt(self):
        data = {"entries": [{"score": i, "note": "n"*250} for i in range(1, 34)]}
        plan = {"approved_tables": {"ledger": data}, "evidence": {"inputs": {"ledger": record(data)}, "claims": [{
            "id": "first_score", "dataset": "ledger", "tool": "run_table", "locator": ["rows", 0, 0],
            "unit": "point", "dimension": "score", "version": "input-v1", "requires": {},
            "reference": {"value": "1", "source": "Separate reference witness"},
        }]}}
        write = construct("SELECT score, note FROM entries ORDER BY score", {"entries": {"score": "INTEGER", "note": "TEXT"}})
        calculate = {**bind(), "claim": {"id": "first_score", "unit": "point", "dimension": "score"}}
        service, runtime = self.service([respond(write, calculate)])
        ident = service.submit(new_spec(plan))["id"]
        view = service.step(ident)
        prompt = json.loads(runtime.calls[0]["prompt"].split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
        self.assertTrue(prompt["operator_requirements"]["truncated"])
        self.assertEqual(prompt["registered_claims"][0]["id"], "first_score")
        self.assertNotIn("reference", prompt["registered_claims"][0])
        claim = view["evidence"]["claims"][0]
        self.assertEqual((claim["status"], claim["value"]), ("VERIFIED", "1"))
        attachment = claim["execution_receipt"]["result_artifact"]
        self.assertIn(attachment["artifact"], service.export(ident)["files"])
        tampered = assess_claims(view, lambda _: b'{"rows":[[1]]}')
        self.assertEqual(tampered["claims"][0]["reason"], "EXECUTION_RESULT_CHANGED")


if __name__ == "__main__":
    unittest.main()
