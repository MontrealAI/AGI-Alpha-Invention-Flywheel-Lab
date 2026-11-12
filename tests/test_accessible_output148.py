"""Falsifiable offline structural accessibility regressions: no WCAG certificate."""
import copy
import json
import unittest

from research.accessible_output148 import gate as g


def record():
    return {
        "schema": g.RECORD_SCHEMA,
        "document_id": "public-demo",
        "model_label": "declared-model-a",
        "lang": "en-CA",
        "title": "Public service information",
        "blocks": [
            {"kind": "heading", "level": 2, "text": "Eligibility"},
            {"kind": "paragraph", "text": "This is a synthetic fixture, not public advice."},
            {"kind": "link", "label": "Read official accessibility guidance",
             "href": "https://www.canada.ca/en.html"},
            {"kind": "image", "src": "https://example.org/figure.png",
             "alt": "Flow diagram showing two decision branches",
             "caption": "Example flow diagram"},
            {"kind": "table", "caption": "Example conditions",
             "headers": ["Condition", "Status"],
             "rows": [["One", "Yes"], ["Two", "No"]]},
        ],
    }


def raw(obj):
    return g.canonical(obj)


def triplet(obj=None):
    rec = raw(record() if obj is None else obj)
    html, receipt = g.compile_bytes(rec)
    return rec, html, receipt


class AccessibilityGate148Tests(unittest.TestCase):
    def fail_record(self, obj):
        with self.assertRaises(ValueError):
            g.compile_bytes(raw(obj))

    def test_01_valid_structured_document(self):
        t = triplet()
        v = g.audit_bytes(*t)
        self.assertTrue(v["accepted"])
        self.assertEqual(v["structure"]["links"], 1)
        self.assertEqual(v["structure"]["tables"], 1)

    def test_02_html_and_attribute_injection_is_escaped(self):
        x = record()
        x["blocks"][1]["text"] = '<script>alert("x")</script> & test'
        x["blocks"][0]["text"] = '" onclick="bad'
        html, _ = g.compile_bytes(raw(x))
        self.assertIn(b"&lt;script&gt;", html)
        self.assertNotIn(b"<script>", html)
        self.assertNotIn(b" onclick=", html)
        self.assertTrue(g.audit_bytes(raw(x), html, g.compile_bytes(raw(x))[1])["accepted"])

    def test_03_unknown_raw_html_field_rejected(self):
        x = record()
        x["blocks"][1]["html"] = "<script>evil()</script>"
        self.fail_record(x)

    def test_04_missing_image_alt_rejected(self):
        x = record()
        x["blocks"][3]["alt"] = ""
        self.fail_record(x)

    def test_05_generic_image_alt_rejected(self):
        x = record()
        x["blocks"][3]["alt"] = "image"
        self.fail_record(x)

    def test_06_uninformative_link_rejected(self):
        x = record()
        x["blocks"][2]["label"] = "click here"
        self.fail_record(x)

    def test_07_unsafe_javascript_link_rejected(self):
        x = record()
        x["blocks"][2]["href"] = "javascript:alert(1)"
        self.fail_record(x)

    def test_08_unsafe_https_userinfo_rejected(self):
        x = record()
        x["blocks"][2]["href"] = "https://user:secret@example.org/data"
        self.fail_record(x)

    def test_09_heading_skip_rejected(self):
        x = record()
        x["blocks"][0]["level"] = 3
        self.fail_record(x)

    def test_10_heading_bool_not_integer(self):
        x = record()
        x["blocks"][0]["level"] = True
        self.fail_record(x)

    def test_11_missing_table_header_rejected(self):
        x = record()
        x["blocks"][4]["headers"] = []
        self.fail_record(x)

    def test_12_table_width_mismatch_rejected(self):
        x = record()
        x["blocks"][4]["rows"][0].append("Extra")
        self.fail_record(x)

    def test_13_missing_table_caption_rejected(self):
        x = record()
        x["blocks"][4]["caption"] = ""
        self.fail_record(x)

    def test_14_invalid_language_rejected(self):
        x = record()
        x["lang"] = "zz"
        self.fail_record(x)

    def test_15_tampered_html_rejected(self):
        a, b, c = triplet()
        with self.assertRaisesRegex(ValueError, "HTML_SOURCE_BINDING_FAILED"):
            g.audit_bytes(a, b.replace(b"<main>", b'<main aria-hidden="true">'), c)

    def test_16_tampered_receipt_rejected(self):
        a, b, c = triplet()
        j = g.strict_load(c)
        j["wcag_conformance"] = "FULLY_MEETS"
        with self.assertRaisesRegex(ValueError, "RECEIPT_SOURCE_BINDING_FAILED"):
            g.audit_bytes(a, b, raw(j))

    def test_17_missing_receipt_rejected(self):
        a, b, _ = triplet()
        with self.assertRaises(Exception):
            g.audit_bytes(a, b, b"")

    def test_18_source_changed_without_new_receipt_rejected(self):
        a, b, c = triplet()
        x = record()
        x["title"] = "Different title"
        with self.assertRaisesRegex(ValueError, "HTML_SOURCE_BINDING_FAILED"):
            g.audit_bytes(raw(x), b, c)

    def test_19_baseline_document_identity_mismatch(self):
        x = record()
        x["document_id"] = "different-public-doc"
        with self.assertRaisesRegex(ValueError, "DOCUMENT_IDENTITY_CHANGED"):
            g.compare_bytes(triplet(), triplet(x))

    def test_20_model_change_structurally_valid_but_unverified(self):
        x = record()
        x["model_label"] = "declared-model-b"
        v = g.compare_bytes(triplet(), triplet(x))
        self.assertTrue(v["accepted"])
        self.assertTrue(v["requires_semantic_and_assistive_technology_review"])
        self.assertEqual(v["commercial_verdict"], "NOT_ESTABLISHED")

    def test_21_candidate_loses_an_image_rejected(self):
        x = record()
        x["model_label"] = "declared-model-b"
        x["blocks"].pop(3)
        with self.assertRaisesRegex(ValueError, "STRUCTURAL_ROLE_COUNT_REGRESSED_IMAGE"):
            g.compare_bytes(triplet(), triplet(x))

    def test_22_candidate_loses_a_table_rejected(self):
        x = record()
        x["model_label"] = "declared-model-b"
        x["blocks"].pop(4)
        with self.assertRaisesRegex(ValueError, "STRUCTURAL_ROLE_COUNT_REGRESSED_TABLE"):
            g.compare_bytes(triplet(), triplet(x))

    def test_23_duplicate_source_json_key_rejected(self):
        x = raw(record()).decode("utf-8")
        x = x.replace('"schema":', '"schema":"forged", "schema":', 1)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            g.compile_bytes(x.encode("utf-8"))

    def test_24_nonfinite_json_number_rejected(self):
        x = raw(record()).decode("utf-8")
        x = x.replace('"blocks":', '"blocks":NaN,"previous_blocks":', 1)
        with self.assertRaises(ValueError):
            g.compile_bytes(x.encode("utf-8"))

    def test_25_conformance_and_human_evidence_never_claimed(self):
        _, _, c = triplet()
        receipt = g.strict_load(c)
        self.assertEqual(receipt["wcag_conformance"], "NOT_ASSESSED")
        self.assertEqual(receipt["assistive_technology_testing"], "NOT_PERFORMED")
        self.assertEqual(receipt["customer_acceptance"], "NOT_ESTABLISHED")
        self.assertEqual(receipt["paid_commerce"], "NONE")
        self.assertEqual(receipt["model_identity_authentication"], "NOT_PROVIDED")

    def test_26_html_parser_detects_duplicate_main(self):
        _, html, _ = triplet()
        with self.assertRaises(ValueError):
            g.inspect_html(html.replace(b"</main>", b"</main><main></main>"))

    def test_27_html_parser_detects_missing_table_scope(self):
        _, html, _ = triplet()
        with self.assertRaisesRegex(ValueError, "HEADER_SCOPE_MISSING"):
            g.inspect_html(html.replace(b'<th scope="col">', b"<th>", 1))

    def test_28_unknown_block_kind_rejected(self):
        x = record()
        x["blocks"].append({"kind": "raw_html", "text": "<button>not safe</button>"})
        self.fail_record(x)

    def test_29_structural_role_same_count_can_change_meaning(self):
        x = record()
        x["model_label"] = "declared-model-b"
        x["blocks"][1]["text"] = "Different potentially inaccurate statement."
        v = g.compare_bytes(triplet(), triplet(x))
        self.assertTrue(v["accepted"])
        self.assertTrue(v["changed_html"])
        self.assertTrue(v["requires_semantic_and_assistive_technology_review"])

    def test_30_source_language_changed_fails_version_gate(self):
        # A change to document language is *not* approved solely by structural HTML audit.
        x = record()
        x["model_label"] = "declared-model-b"
        x["lang"] = "fr-CA"
        with self.assertRaisesRegex(ValueError, "DOCUMENT_LANGUAGE_CHANGED_BETWEEN_RELEASES"):
            g.compare_bytes(triplet(), triplet(x))

    def test_31_multi_path_provenance_is_not_signature(self):
        _, _, c = triplet()
        self.assertIn("DECLARED", "DECLARED")
        self.assertEqual(g.strict_load(c)["declared_model_label_unverified"], "declared-model-a")


if __name__ == "__main__":
    unittest.main()
