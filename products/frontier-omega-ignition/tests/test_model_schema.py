import json
import unittest

from ignition import model_schema
from ignition.provider import LocalProvider, ModelProvider, ProviderUnavailable
from bridge.output_schema import SchemaError, prepare_schema, validate_output


class WireGrammarTests(unittest.TestCase):
    def setUp(self):
        self.payload = {"candidates":[{"id":"C1"}],"signals":[{"id":"S1"}],
                        "mission":{"requirements":["Deliver the declared output"]}}
        self.response = {"decision":"defer","selected":None,"challenger":None,
                         "reason":"No usable comparative evidence","objections":[],"fit":[]}

    def test_actual_candidate_and_scope_are_structural_and_defer_is_possible(self):
        schema = prepare_schema(model_schema.for_stage("challenge", self.payload))
        validate_output(self.response,schema)
        objection = {"candidate":"C1","target":"answer","claim":"Historical evidence is incomplete",
                     "source":None,"quote":None}
        validate_output({**self.response, "objections":[objection]},schema)
        for edit in ({"candidate":"C2"},{"candidate":"nonexistent"},{"target":"historical evidence is incomplete"}):
            with self.assertRaises(SchemaError):
                validate_output({**self.response,"objections":[{**objection,**edit}]},schema)
        challenger = {k:"New route" for k in model_schema.CANDIDATE_FIELDS} | {"sources":["S1"]}
        validate_output({**self.response,"challenger":challenger,"selected":"C2",
                         "objections":[{**objection,"candidate":"C2","target":"set"}]},schema)
        with self.assertRaises(SchemaError):
            validate_output({**self.response,"selected":"C2"},schema)

    def test_keyed_coverage_excludes_the_observed_surplus_report_without_deciding_fit(self):
        requirements = ["Classify the files.", "Export the receiver."]
        tagged = {**self.payload, "mission": {"requirements": requirements},
                  "requirement_ids": {"R1": requirements[0], "R2": requirements[1]}}
        schema = prepare_schema(model_schema.for_stage("challenge", tagged))
        observation = {"check": "Compare an independently withheld output", "status": "unresolved"}
        full = {"R1": observation, "R2": {**observation, "status": "supported"}}
        validate_output({**self.response, "fit": full}, schema)
        validate_output(self.response, schema)  # No evidence; declining remains possible.
        old_rows = [{"requirement": r, **observation} for r in [*requirements, requirements[-1]]]
        for invalid in (old_rows, {"R1": observation}, {**full, "R3": observation},
                        {"R1": {**observation, "status": "guaranteed"}, "R2": observation}):
            with self.subTest(invalid=invalid), self.assertRaises(SchemaError):
                validate_output({**self.response, "fit": invalid}, schema)

    def test_exact_schema_checked_after_native_response_no_fallback(self):
        sent = []
        def sender(url, headers, body, timeout):
            sent.append(body)
            return {"model":"local","choices":[{"finish_reason":"stop","message":{
                    "content":json.dumps({**self.response,"decision":"autonomous victory"})}}]}
        route = LocalProvider("llama-cpp","local",8080,schema_output=True,sender=sender)
        request = route.request("challenge",self.payload)
        with self.assertRaisesRegex(ProviderUnavailable,"SCHEMA_RESPONSE"):
            route.propose("challenge",self.payload)
        self.assertEqual(len(sent),1)
        self.assertEqual(sent[0]["response_format"]["type"],"json_schema")
        self.assertEqual(request["response_schema_sha256"],route.receipts[0]["response_schema_sha256"])
        self.assertEqual(request["sha256"],route.receipts[0]["request_sha256"])
        self.assertEqual(route.receipts[0]["status"],"failed")

    def test_equal_schema_for_direct_and_full_construction(self):
        definition = {"columns":[{"source":"old","target":"new","type":"text"}],"extra_fields":"reject"}
        visible = {"kind":"record_migration","definition":definition}
        schema = prepare_schema(model_schema.for_stage("construct",visible))
        self.assertEqual(schema,model_schema.for_stage("direct_construct",visible))
        validate_output({"kind":"record_migration","program":definition},schema)
        with self.assertRaises(SchemaError):
            validate_output({"kind":"record_migration","program":{"shell":"do something"}},schema)
        with self.assertRaises(ProviderUnavailable):
            ModelProvider.from_environment({"IGNITION_MODEL_PROVIDER":"llama-cpp","IGNITION_MODEL_ID":"m",
                                            "IGNITION_MODEL_SCHEMA":"true"})

    def test_native_builders_can_reference_but_never_generate_trust_anchors(self):
        visible = {"kind": "manifest_audit", "definition": {"manifest": {"a": "a"*64}}}
        for stage in ("construct", "direct_construct", "repair"):
            schema = prepare_schema(model_schema.for_stage(stage, visible))
            validate_output({"kind": "manifest_audit", "program": {"use_frozen_manifest": True}}, schema)
            for program in (visible["definition"], {"manifest": {"a": "b"*64}}, {"use_frozen_manifest": False}):
                with self.assertRaises(SchemaError):
                    validate_output({"kind": "manifest_audit", "program": program}, schema)

    def test_discovery_allows_unsupported_hypothesis_and_no_evidence(self):
        s = prepare_schema(model_schema.for_stage("discover",{"signals":[]}))
        validate_output({"candidates":[],"favourite":None},s)
        speculative = {k:"new unknown operation" for k in model_schema.CANDIDATE_FIELDS} | {"sources":[]}
        validate_output({"candidates":[speculative],"favourite":"C1"},s)
