# SPDX-License-Identifier: Apache-2.0

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge import mission_schema_context as schema, mission_tools
from bridge.adapters import BridgeError
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime
from bridge.workflows import digest, encoded
from test_universal_missions import propose, specification


class MissionSchemaContextTests(unittest.TestCase):
    @staticmethod
    def requirements(data, *, origin="AUTHORIZED_MISSION_INPUT", required=None):
        return {"approved_tables": {"ledger-id": data}, "evidence": {
            "inputs": {"ledger-id": {"kind": "table", "origin": origin, "version": "ledger-v1", "sha256": digest(data), "facts": {}}},
            "claims": [{"dataset": "ledger-id", "tool": "run_table", "required_fields": required or [],
                        "reference": {"value": "PRIVATE-ORACLE"}}],
        }}

    def test_bound_query_uses_the_actual_table_name_and_preserves_query(self):
        tables = {"ledger": [{"lane": "north", "revision": 1, "admitted": 4},
                             {"lane": "north", "revision": 2, "admitted": 6},
                             {"lane": "south", "revision": 1, "admitted": 7}]}
        requirements = self.requirements(tables)
        view = schema.constructor_context(requirements)["datasets"]["ledger-id"]
        self.assertEqual(view["schema"], {"ledger": {"lane": "TEXT", "revision": "INTEGER", "admitted": "INTEGER"}})
        self.assertEqual(view["sha256"], digest(tables))
        self.assertEqual(view["version"], "ledger-v1")
        self.assertNotIn(b"north", encoded(view))
        self.assertNotIn(b"PRIVATE-ORACLE", encoded(view))
        action = {"tool": "construct_table", "name": "select.json", "dataset": "ledger-id", "sql": """
            WITH choices AS (SELECT admitted, ROW_NUMBER() OVER (PARTITION BY lane ORDER BY revision DESC) AS position FROM ledger)
            SELECT SUM(admitted) FROM choices WHERE position=1
        """}
        bound = schema.bind_table_construction(action, requirements)
        self.assertEqual(bound["sql"], action["sql"])
        self.assertEqual(bound["schema"], view["schema"])
        storage = {}

        def write(name, payload, kind):
            storage[name] = (payload.encode(), kind)
            return {"artifact": name}

        def run(operation):
            return mission_tools.execute(operation, read=lambda name: storage[name][0], write=write,
                                         kind=lambda name: storage.get(name, (None, None))[1],
                                         approved_tables=requirements["approved_tables"])

        run(bound)
        dispatch = {"tool": "run_table", "name": "select.json", "input": {"dataset": "ledger-id"}}
        schema.verify_table_input_schema(dispatch, requirements, bound["schema"])
        self.assertEqual(run(dispatch)["rows"], [[13]])
        with self.assertRaisesRegex(BridgeError, r"ledger\(admitted, lane, revision\)"):
            schema.verify_table_input_schema(dispatch, requirements, {"events": {"score": "INTEGER"}})

        wrong_query = {**bound, "sql": "SELECT amount FROM ledger"}
        with self.assertRaisesRegex(ValueError, "TABLE_SQL_ERROR") as caught:
            run(wrong_query)
        feedback = schema.table_feedback(action, requirements, caught.exception)
        self.assertIn("Approved tables and columns: ledger(admitted, lane, revision)", str(feedback))

    def test_field_metadata_exact_names_and_missing_observation(self):
        tables = {"samples": [{"count": 2, "site": "nord"}, {"count": None, "site": "sud"}],
                  "sites": [{"key": "nord"}, {"key": "sud"}]}
        req = self.requirements(tables, required=[["samples", "count"]])
        req["approved_schemas"] = {"ledger-id": {
            "tables": {"samples": {"count": "INTEGER", "site": "TEXT"}, "sites": {"key": "TEXT"}},
            "fields": {"samples": {"count": {"unit": "observations", "dimension": "count", "temporal_basis": "UTC",
                                             "range": [0, 50], "nullable": True}}},
            "primary_keys": {"sites": ["key"]},
            "relationships": [{"from": ["samples", "site"], "to": ["sites", "key"]}],
            "approved_transformations": ["Aggregate within a solution of the reconciled sample scope"],
        }}
        schema.validate_declarations(req)
        info = schema.inspect_dataset(req, "ledger-id", include_examples=True)
        self.assertEqual(info["status"], "AVAILABLE")
        count = info["tables"]["samples"]["fields"]["count"]
        self.assertEqual((count["missing_rows"], count["null_rows"]), (0, 1))
        self.assertEqual(count["declared"]["unit"], "observations")
        self.assertEqual(info["missing_requirements"], [{"path": ["samples", "count"], "unavailable_rows": 1}])
        self.assertEqual(info["primary_keys"], {"sites": ["key"]})
        self.assertEqual(info["relationships"][0]["to"], ["sites", "key"])
        self.assertEqual(info["tables"]["samples"]["examples"], tables["samples"])

    def test_inference_preserves_unsupported_and_missing_data_without_casting(self):
        data = {"measurements": [{"ambiguous": 2, "unknown": None, "present": True},
                                 {"ambiguous": "3", "extra": 0.1, "present": False}]}
        req = self.requirements(data, required=[["measurements", "needed"]])
        info = schema.inspect_dataset(req, "ledger-id")
        fields = info["tables"]["measurements"]["fields"]
        self.assertEqual(info["status"], "CONFLICT")
        self.assertNotIn("schema", info)
        self.assertEqual(fields["ambiguous"]["observed_types"], ["INTEGER", "TEXT"])
        self.assertEqual(fields["present"]["observed_types"], ["BOOLEAN"])
        self.assertEqual(fields["extra"]["observed_types"], ["JSON_NUMBER"])
        self.assertEqual(fields["unknown"]["null_rows"], 1)
        self.assertEqual(fields["needed"]["missing_rows"], 2)
        self.assertEqual(info["missing_requirements"], [{"path": ["measurements", "needed"], "unavailable_rows": 2}])
        with self.assertRaisesRegex(BridgeError, "approved relational schema is unavailable"):
            schema.bind_table_construction({"tool": "construct_table", "name": "query.json", "dataset": "ledger-id", "sql": "SELECT 1"}, req)

    def test_ineligible_changed_or_unknown_source_has_no_shape(self):
        data = {"restricted_table": [{"restricted_field": 1}]}
        for origin in ("DEVELOPMENT_FIXTURE", "SYNTHETIC_EXAMPLE", "SIMULATION_OUTPUT"):
            with self.subTest(origin=origin):
                info = schema.inspect_dataset(self.requirements(data, origin=origin), "ledger-id", include_examples=True)
                self.assertEqual(info, {"status": "REJECTED", "issues": [{"code": "INPUT_ORIGIN_INELIGIBLE"}]})
        req = self.requirements(data)
        req["evidence"]["inputs"]["ledger-id"]["sha256"] = "0" * 64
        self.assertEqual(schema.inspect_dataset(req, "ledger-id")["issues"], [{"code": "INPUT_BYTES_CHANGED"}])
        with self.assertRaises(BridgeError) as caught:
            schema.inspect_dataset({**req, "confirmation": {"hidden": data}}, "hidden")
        self.assertEqual(caught.exception.code, "TABLE_DATASET_AUTHORITY")

    def test_declaration_does_not_authorize_unknown_input_or_erase_discrepancies(self):
        req = self.requirements({"observations": [{"duration": 2}, {"duration": None}]})
        spec = {"tables": {"observations": {"duration": "INTEGER"}},
                "fields": {"observations": {"duration": {"nullable": False, "range": [3, 17]}}}}
        req["approved_schemas"] = {"hidden": spec}
        with self.assertRaisesRegex(BridgeError, "current dataset grant"):
            schema.validate_declarations(req)
        req["approved_schemas"] = {"ledger-id": spec}
        schema.validate_declarations(req)
        info = schema.inspect_dataset(req, "ledger-id")
        self.assertNotIn("schema", info)
        self.assertEqual({item["code"] for item in info["issues"]},
                         {"APPROVED_FIELD_NULLABILITY_CONFLICT", "APPROVED_FIELD_RANGE_CONFLICT"})

    def test_explicit_table_cannot_verify_against_a_conflicting_approved_declaration(self):
        data = {"readings": [{"count": 12, "note": None}]}
        explicit = {"readings": {"count": "INTEGER", "note": "TEXT"}}
        construct = {"tool": "construct_table", "name": "query.json", "schema": explicit,
                     "sql": "SELECT SUM(count) FROM readings"}
        dispatch = {"tool": "run_table", "name": "query.json", "input": {"dataset": "ledger-id"}}
        annotation = {"id": "total", "unit": "observations", "dimension": "count"}
        claim = {**annotation, "dataset": "ledger-id", "tool": "run_table", "locator": ["rows", 0, 0],
                 "version": "ledger-v1", "requires": {}, "required_fields": [["readings", "count"]],
                 "reference": {"value": "12", "source": "Independent sum of the recorded counts"}}
        declarations = [
            ("APPROVED_FIELD_RANGE_CONFLICT", {"tables": explicit, "fields": {"readings": {"count": {"range": [0, 10]}}}}),
            ("APPROVED_FIELD_NULLABILITY_CONFLICT", {"tables": explicit, "fields": {"readings": {"note": {"nullable": False}}}}),
            ("APPROVED_FIELD_TYPE_CONFLICT", {"tables": {"readings": {"count": "TEXT", "note": "TEXT"}}}),
            (None, {"tables": explicit}),
            (None, None),  # A legacy null-only column has no inferable type.
        ]
        controls = [(conflict, declaration, delivery) for conflict, declaration in declarations for delivery in (True, False)]
        for conflict, declaration, delivery in controls:
            with self.subTest(conflict=conflict, declaration=declaration, delivery=delivery), TemporaryDirectory() as directory:
                requirements = self.requirements(data)
                requirements["evidence"]["claims"] = [claim]
                if declaration is not None:
                    requirements["approved_schemas"] = {"ledger-id": declaration}
                spec = specification(tools=["construct_table", "run_table"], requirements=requirements)
                runtime = FixtureRuntime([propose(construct, {**dispatch, "claim": annotation})])
                service = UniversalMissionService(runtime, Path(directory), schema_delivery=delivery)
                try:
                    with patch.object(mission_tools, "_run", wraps=mission_tools._run) as worker:
                        result = service.step(service.submit(spec)["id"])
                finally:
                    service.close()
                self.assertEqual(result["artifacts"]["query.json"]["kind"], "table_instrument")
                worker_data = [call.args[1] for call in worker.call_args_list]
                report = result["evidence"]["claims"][0]
                if conflict:
                    with self.assertRaises(BridgeError) as refused:
                        schema.verify_table_input_schema(dispatch, requirements, explicit)
                    self.assertEqual(refused.exception.code, conflict)
                    self.assertEqual(worker_data, [{"readings": []}])
                    self.assertEqual(report["status"], "REJECTED")
                    self.assertNotIn("execution_receipt", report)
                    self.assertEqual(result["outcome"]["conclusions"], [])
                else:
                    self.assertEqual(worker_data, [{"readings": []}, data])
                    self.assertEqual((report["status"], report["value"]), ("VERIFIED", "12"))

    def test_claim_linked_dataset_schema_wins_the_context_budget(self):
        req = self.requirements({"samples": [{"site": "a", "count": 1}]})
        req["approved_tables"].update({f"a{index}": {"extra": [{"v": index}]} for index in range(20)})
        req["confirmations"] = {"PRIVATE-UNRELATED": {"x": []}}
        result = schema.constructor_context(req, max_bytes=640)
        self.assertLessEqual(len(encoded(result)), 640)
        self.assertGreater(result["omitted_datasets"], 0)
        self.assertIn("schema", result["datasets"]["ledger-id"])
        self.assertNotIn(b"PRIVATE-UNRELATED", encoded(result))

    def test_value_input_is_inspectable_but_cannot_be_a_table_grant(self):
        values = {"routing": {"attempts": 3}, "tags": ["a"], "rate": None}
        req = {"evidence": {"inputs": {"record": {"kind": "values", "origin": "AUTHORIZED_MISSION_INPUT",
               "version": "v1", "sha256": digest(values), "facts": {}, "values": values}},
               "claims": [{"dataset": "record", "tool": "run_instrument", "required_fields": [["routing", "duration"]]}]}}
        info = schema.inspect_dataset(req, "record")
        self.assertEqual(info["kind"], "values")
        self.assertIn({"path": ["rate"], "type": None, "null": True}, info["fields"])
        self.assertEqual(info["issues"], [{"code": "REQUIRED_FIELD_MISSING", "path": ["routing", "duration"]}])
        with self.assertRaises(BridgeError):
            schema.bind_table_construction({"tool": "construct_table", "name": "query.json", "dataset": "record", "sql": "SELECT 1"}, req)


if __name__ == "__main__":
    unittest.main()
