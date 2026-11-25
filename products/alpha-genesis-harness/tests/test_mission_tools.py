# SPDX-License-Identifier: Apache-2.0
"""Exercise the real read-only evaluator and the exported table artifact path."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge import mission_tools
from bridge.output_schema import prepare_schema, validate_output


TABLES = {"readings": [{"zone": "est", "count": 4}, {"zone": "ouest", "count": 6}, {"zone": "est", "count": 11}]}
CANDIDATE = {"tool": "construct_table", "name": "total.json", "schema": {"readings": {"zone": "TEXT", "count": "INTEGER"}},
             "sql": "SELECT zone, SUM(count) FROM readings GROUP BY zone ORDER BY zone"}


class TableInstrumentTests(unittest.TestCase):
    def setUp(self):
        self.files = {}
        self.approved = {"regional-counts": TABLES}

    def read(self, name):
        return self.files[name]["raw"]

    def kind(self, name):
        return self.files.get(name, {}).get("kind")

    def write(self, name, content, kind):
        raw = content.encode()
        self.files[name] = {"raw": raw, "kind": kind}
        return {"artifact": name, "bytes": len(raw), "sha256": sha256(raw).hexdigest(), "kind": kind}

    def execute(self, action):
        return mission_tools.execute(action, read=self.read, write=self.write, kind=self.kind, approved_tables=self.approved)

    def test_constructs_and_runs_a_new_query_against_authorized_data(self):
        artifact = self.execute(CANDIDATE)
        self.assertEqual(artifact["status"], "CANDIDATE_VALIDATED_ON_EMPTY_TABLES")
        self.assertEqual(artifact["qualification"], "UNVERIFIED")
        self.assertIsNone(artifact["previous_sha256"])
        execution = self.execute({"tool": "run_table", "name": "total.json", "input": {"dataset": "regional-counts"}})
        expected = [[zone, sum(item["count"] for item in TABLES["readings"] if item["zone"] == zone)]
                    for zone in sorted({item["zone"] for item in TABLES["readings"]})]
        self.assertEqual(execution["rows"], expected)
        self.assertEqual(execution["artifact_sha256"], artifact["sha256"])
        self.assertEqual(execution["input_origin"], "OPERATOR_APPROVED_DATASET")
        self.assertEqual(execution["qualification"], "UNVERIFIED")
        self.assertEqual(execution["evaluator_sha256"], mission_tools.EVALUATOR_SHA256)

    def test_refused_candidate_and_actual_fixture_failure_are_repairable(self):
        with self.assertRaisesRegex(ValueError, "TABLE_SQL_ERROR"):
            self.execute({**CANDIDATE, "sql": "SELECT missing FROM readings"})
        self.assertNotIn("total.json", self.files)
        original = self.execute({**CANDIDATE, "sql": "SELECT zone, AVG(count) FROM readings GROUP BY zone ORDER BY zone"})
        dev = {"tool": "run_table", "name": "total.json", "input": {"fixtures": TABLES}}
        # This test reaches SQLite with real rows. AVG generates a floating-point
        # result disallowed by the original portable evaluator contract.
        with self.assertRaisesRegex(ValueError, "TABLE_OUTPUT_LIMIT"):
            self.execute(dev)
        revised = self.execute(CANDIDATE)
        self.assertEqual(revised["previous_sha256"], original["sha256"])
        self.assertNotEqual(revised["sha256"], original["sha256"])
        result = self.execute(dev)
        self.assertEqual(result["input_origin"], "MODEL_DEVELOPMENT_FIXTURE")
        self.assertEqual(result["rows"], [["est", 15], ["ouest", 6]])

    def test_model_data_does_not_grant_authority_and_reuse_cannot_change_kind(self):
        self.execute(CANDIDATE)
        base = {"tool": "run_table", "name": "total.json"}
        with self.assertRaisesRegex(ValueError, "TABLE_DATASET_AUTHORITY"):
            self.execute({**base, "input": {"dataset": "held-confirmation"}})
        with self.assertRaisesRegex(ValueError, "TABLE_ACTION"):
            self.execute({**base, "input": {"dataset": "regional-counts", "fixtures": TABLES}})
        with self.assertRaisesRegex(ValueError, "TABLE_INPUT"):
            self.execute({**base, "input": {"fixtures": {"readings": [{"zone": "est", "count": True}]}}})
        self.write("evidence.json", "{}", "source")
        with self.assertRaisesRegex(ValueError, "TABLE_ARTIFACT_KIND"):
            self.execute({**CANDIDATE, "name": "evidence.json"})
        with self.assertRaisesRegex(ValueError, "TABLE_ARTIFACT_NAME"):
            self.execute({**CANDIDATE, "name": "../total.json"})

    def test_existing_read_only_engine_protects_ambient_storage(self):
        for sql in ("DELETE FROM readings", "SELECT name FROM sqlite_schema", "SELECT current_date"):
            with self.subTest(sql=sql), self.assertRaisesRegex(ValueError, "TABLE_(READ_ONLY|SQL_ERROR)"):
                self.execute({**CANDIDATE, "sql": sql})
        self.assertEqual(self.files, {})

    def test_generation_schemas_accept_the_exact_supported_syntax(self):
        for action in (CANDIDATE, {"tool": "run_table", "name": "total.json", "input": {"dataset": "regional-counts"}}):
            properties = {"tool": {"const": action["tool"]}, "name": {"type": "string"},
                          **mission_tools.tool_schemas()[action["tool"]]}
            schema = prepare_schema({"type": "object", "properties": properties, "required": list(properties),
                                     "additionalProperties": False})
            validate_output(action, schema)

    def test_portable_runner_reproduces_bound_output_and_refuses_engine_drift(self):
        self.execute(CANDIDATE)
        resolved = self.execute({"tool": "run_table", "name": "total.json", "input": {"dataset": "regional-counts"}})
        source = Path(mission_tools.__file__).resolve()
        engine = source.with_name("relational.py")
        if not engine.is_file():
            engine = PRODUCT.parent / "frontier-member-tools" / "inventor" / "relational.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            shipped_runner = shutil.copyfile(source, path / "mission_tools.py")
            shutil.copyfile(engine, path / "relational.py")
            (path / "total.json").write_bytes(self.read("total.json"))
            (path / "tables.json").write_text(json.dumps(TABLES), encoding="utf-8")
            command = [sys.executable, "-I", "-S", str(shipped_runner), str(path / "total.json"), str(path / "tables.json")]
            result = subprocess.run(command, capture_output=True, check=True)
            replayed = json.loads(result.stdout)
            for key in ("artifact_sha256", "input_sha256", "output_sha256", "rows"):
                self.assertEqual(replayed[key], resolved[key])
            with (path / "relational.py").open("ab") as stream:
                stream.write(b"\n# Different source identity\n")
            refused = subprocess.run(command, capture_output=True, check=False)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(refused.stderr.strip(), b"TABLE_ENGINE_IDENTITY")


if __name__ == "__main__":
    unittest.main()
