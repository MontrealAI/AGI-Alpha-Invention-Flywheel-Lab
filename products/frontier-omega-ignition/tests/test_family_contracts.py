"""The public family descriptions correspond to the installed data-only recipients."""
import base64
from hashlib import sha256
import json
import unittest

from ignition import construction
from ignition.family_contracts import assess, catalog, extracted_manifest
from ignition.research import _now, _signals


def compiled(kind, definition, payload, expected):
    contract = construction.freeze_contract({"kind": kind, "purpose": "Check the declared family interface",
        "definition": definition, "cases": [{"name": "input", "input": payload, "expected": expected}]})
    return construction.build(contract, {"kind": kind, "program": definition})


def mechanics(kind):
    family = catalog()[kind]
    return {key: family[key] for key in ("inputs", "operations", "outputs")}


class InstalledFamilyContract(unittest.TestCase):
    def test_family_catalog_covers_only_installed_builders_and_is_returned_by_value(self):
        self.assertEqual(set(catalog()), set(construction.KINDS))
        catalog()["manifest_audit"]["outputs"].append("mapped_json_rows")
        self.assertEqual(catalog()["manifest_audit"]["outputs"], ["path_discrepancy_report"])

    def test_row_operations_against_installed_worker(self):
        kind = "record_migration"
        plan = mechanics(kind)
        self.assertEqual(assess(kind, plan, requested_output="mapped_json_rows")["status"], "supported")
        definition = {"columns": [{"source": "left", "target": "copy", "type": "text"},
            {"sources": ["left", "right"], "separator": "-", "target": "both", "type": "text"},
            {"source": "right", "split": {"separator": "/", "index": 1}, "target": "index", "type": "integer"}],
            "extra_fields": "reject"}
        row = {"left": " a", "right": "Q/25"}
        out = {"copy": " a", "both": " a-Q/25", "index": 25}
        payload, expected = {"rows": [row, row]}, {"rows": [out, out]}
        worker = compiled(kind, definition, payload, expected)
        self.assertEqual(construction.execute(worker, payload), expected)
        for bad in ({"files": {}}, {"rows": [dict(row, extra=True)]}):
            with self.assertRaises(construction.ConstructionError):
                construction.execute(worker, bad)
        for invalid in (dict(plan, operations=["table_lookup"]), dict(plan, outputs=["path_discrepancy_report"]),
                        dict(plan, inputs=["flat_json_rows", "reference_rows"]), dict(plan, operations=[{}])):
            self.assertEqual(assess(kind, invalid)["status"], "unsupported")
        self.assertEqual(assess(kind, None)["status"], "unassessed")

    def test_manifest_comparison_against_installed_worker_and_independent_input(self):
        kind = "manifest_audit"
        plan = mechanics(kind)
        manifest = {name: sha256(b"sample").hexdigest() for name in ("a", "b", "c")}
        spec = {"kind": kind, "definition": {"manifest": manifest}}
        expected = {"ok": False, "matched": ["a"], "changed": ["b"], "missing": ["c"], "unexpected": ["d"]}
        payload = {"files": {p: base64.b64encode(v).decode() for p, v in {"a": b"sample", "b": b"", "d": b"d"}.items()}}
        self.assertEqual(construction.execute(compiled(kind, spec["definition"], payload, expected), payload), expected)
        self.assertEqual(assess(kind, plan, public_spec=spec, requested_output=plan["outputs"])["status"], "supported")
        self.assertEqual(assess(kind, plan, authorized_manifest=manifest)["status"], "supported")
        for args in ({}, {"authorized_manifest": {"d": "123"}}, {"public_spec": {"kind": "record_migration"}},
                     {"authorized_manifest": manifest, "requested_output": "mapped_json_rows"},
                     {"public_spec": {"kind": kind}, "authorized_manifest": manifest}):
            self.assertEqual(assess(kind, plan, **args)["status"], "unsupported")
        self.assertEqual(assess(kind, dict(plan, inputs=["named_file_bytes"]), public_spec=spec)["status"], "unsupported")


class OperatorSuppliedManifests(unittest.TestCase):
    digest = sha256(b"contents").hexdigest()
    other = sha256(b"other").hexdigest()

    def signal(self, text, **kwargs):
        record = {"url": "https://example.org/sums", "title": "Inventory", "publisher": "Publisher",
                  "text": text, "rights": "Public checksums supplied for offline review.", "retrieved_at": "2026-10-01"}
        return _signals([dict(record, **kwargs)], _now("2026-10-02"))[0]

    def test_exact_sha256sum_line_and_json_inventory_with_provenance(self):
        digest = self.digest
        line = self.signal(f"Description.\n{digest}  dir/example name\nSHA256 of other: {digest}")
        doc = self.signal(json.dumps({"manifest": {"other": digest}}), url="https://example.org/more")
        doc["id"] = "S2"
        ref = extracted_manifest([line, doc])
        self.assertEqual(ref["manifest"], {"dir/example name": digest, "other": digest})
        self.assertEqual(ref["sources"], [{"id": s["id"], "sha256": s["sha256"], "url": s["url"], "paths": [p]}
                                         for s, p in ((line, "dir/example name"), (doc, "other"))])
        self.assertEqual(ref["conflicts"], [])

    def test_conflicting_paths_withhold_the_inventory(self):
        for text in (f"{self.digest}  shared\n{self.other}  shared",
                     '{"manifest":{"shared":"' + self.digest + '","shared":"' + self.other + '"}}'):
            ref = extracted_manifest([self.signal(text)])
            self.assertEqual(ref["manifest"], {})
            self.assertEqual(ref["conflicts"], ["shared"])
        ref = extracted_manifest([self.signal(f"{self.digest}  shared"), self.signal(f"{self.other}  shared")])
        self.assertEqual(ref["conflicts"], ["shared"])
        self.assertEqual(ref["manifest"], {})

    def test_unusable_sources_and_ambiguous_syntax_supply_no_anchors(self):
        for sample in (f"Digest {self.digest} of file", f"{self.digest} file", f"{self.digest}  ../outside",
                       f"{self.digest.upper()}  file", json.dumps({"manifest": {"file": self.digest}, "extra": True}),
                       json.dumps({"manifest": {"file": self.digest, "unsafe/path/..": self.digest}})):
            self.assertFalse(extracted_manifest([self.signal(sample)])["manifest"])
        signal = self.signal(f"{self.digest}  file")
        for change in ({"event_pending": True}, {"current_observation": False}, {"access": "untested"},
                       {"status": "withdrawn"}, {"sha256": "0" * 64}, {"excerpt_truncated": True},
                       {"rights": "Unknown; citation and local evaluation only."}, {"origin": "model proposal"},
                       {"acquisition": "operator-authorized public repository"}):
            self.assertFalse(extracted_manifest([dict(signal, **change)])["manifest"])
