"""Preregistered C0-C9 public-regulatory citation adversarial tests.

Synthetic fixed fixtures only; no external buyer, policy interpretation, financial account,
new secret or real authority. See campaign/regulatory-citation097/PROTOCOL.md.
"""
from copy import deepcopy
import unittest

from research import regulatory_citation097 as r


def fixture(source="SEC-A Signed control assertion. SEC-B unrelated"):
    data = ("<html><body><h1>Sample</h1><p>" + source +
            "</p></body></html>").encode("utf-8")
    return r.document("tbs-directive-2025", r.ALLOWED["tbs-directive-2025"][0], data)


def claim(doc, excerpt="Signed control assertion.", start="SEC-A", end="SEC-B", code="C"):
    return r.make_claim(code, doc, start, end, excerpt)


class ExactPassageWitness(unittest.TestCase):
    def test_C0_valid_bounded_quote(self):
        d = fixture()
        out = r.packet({d["id"]: d}, [claim(d)])
        self.assertEqual(out["accepted"], 1)
        self.assertEqual(len(out["packet_sha256"]), 64)
        self.assertTrue(r.verify_packet(out, {d["id"]: d}, [claim(d)]))

    def test_C1_text_in_wrong_section_must_fail(self):
        d = fixture("SEC-A distinct control. SEC-B Signed control assertion.")
        self.assertIn("Signed control assertion.", d["text"])  # simple search can find it
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({d["id"]: d}, [claim(d)])

    def test_C2_fabricated_quote_refused(self):
        d = fixture()
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({d["id"]: d}, [claim(d, "Claim never in the document.")])

    def test_C3_swapped_source_hash_refused(self):
        d = fixture()
        changed = claim(d)
        changed["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "STALE_OR_SWAPPED_SOURCE"):
            r.packet({d["id"]: d}, [changed])

    def test_C4_byte_mutation_invalidates_prior_claim(self):
        d = fixture()
        old = claim(d)
        d2 = fixture("SEC-A Signed control assertion. SEC-B unrelated UPDATED")
        self.assertNotEqual(d["sha256"], d2["sha256"])
        with self.assertRaisesRegex(ValueError, "STALE_OR_SWAPPED_SOURCE"):
            r.packet({d2["id"]: d2}, [old])

    def test_C5_missing_or_duplicate_anchors_refused(self):
        for txt in ("SEC-A Signed control assertion.",
                    "SEC-A Signed control assertion. SEC-A SEC-B"):
            with self.subTest(txt=txt), self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE_ANCHOR"):
                d = fixture(txt)
                r.packet({d["id"]: d}, [claim(d)])

    def test_C6_invisible_char_and_confusable_refused(self):
        d = fixture()
        with self.assertRaisesRegex(ValueError, "INVALID_TEXT_OR_INVISIBLE_CHAR"):
            r.packet({d["id"]: d}, [claim(d, "Signed\u200b control assertion.")])
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({d["id"]: d}, [claim(d, "Ѕigned control assertion.")])  # Cyrillic S

    def test_C7_hidden_script_and_style_not_evidence(self):
        raw = b"<html><body>SEC-A other. <script>Signed control assertion.</script>" \
              b"<style>Signed control assertion.</style> SEC-B</body></html>"
        d = r.document("tbs-directive-2025", r.ALLOWED["tbs-directive-2025"][0], raw)
        self.assertNotIn("Signed control assertion.", d["text"])
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({d["id"]: d}, [claim(d)])

    def test_C8_url_and_document_reference_binding(self):
        d = fixture()
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_DOCUMENT_OR_URL"):
            r.document(d["id"], "https://evil.example.invalid/", b"<html><body>sample</body></html>")
        c = claim(d)
        c["url"] = r.ALLOWED["ssc-challenge-2026"][0]
        with self.assertRaisesRegex(ValueError, "DOCUMENT_REFERENCE_MISMATCH"):
            r.packet({d["id"]: d}, [c])
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_OR_UNSAFE_URL"):
            r.retrieve("http://127.0.0.1/")
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_OR_UNSAFE_URL"):
            r.retrieve("https://evil.example.invalid/")

    def test_C9_packet_determinism_replay_and_no_duplicate_ids(self):
        d = fixture()
        a = claim(d, code="A")
        b = claim(d, code="B")
        result = r.packet({d["id"]: d}, [b, a])
        self.assertEqual(result, r.packet({d["id"]: d}, [a, b]))
        tampered = deepcopy(result)
        tampered["accepted_claims"][0]["status"] = "UNCHECKED"
        with self.assertRaisesRegex(ValueError, "PACKET_OR_SOURCE_REPLAY_MISMATCH"):
            r.verify_packet(tampered, {d["id"]: d}, [a, b])
        with self.assertRaisesRegex(ValueError, "DUPLICATE_CLAIM_ID"):
            r.packet({d["id"]: d}, [a, a])

    def test_C10_prior_cross_reference_must_not_invalidate_unique_section(self):
        d = fixture("Intro mentions SEC-A as a cross reference. SEC-A Signed control assertion. SEC-B")
        out = r.packet({d["id"]: d}, [claim(d)])
        self.assertEqual(out["accepted"], 1)

    def test_C11_duplicate_inside_candidate_and_missing_stop_rejected(self):
        duplicate = fixture("SEC-A Signed control assertion. SEC-A SEC-B")
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE_ANCHOR"):
            r.packet({duplicate["id"]: duplicate}, [claim(duplicate)])
        absent_stop = fixture("SEC-A Signed control assertion.")
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATE_ANCHOR"):
            r.packet({absent_stop["id"]: absent_stop}, [claim(absent_stop)])

    def test_C12_two_independent_valid_windows_are_ambiguous(self):
        d = fixture("SEC-A Signed control assertion. SEC-B other text SEC-A Signed control assertion. SEC-B")
        with self.assertRaisesRegex(ValueError, "MULTIPLE_VALID_WINDOWS"):
            r.packet({d["id"]: d}, [claim(d)])

    def test_C13_quote_outside_local_window_or_hidden_refused(self):
        d = fixture("SEC-A different text. SEC-B Signed control assertion.")
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({d["id"]: d}, [claim(d)])
        blob = (b"<html><body>SEC-A other. <script>Signed control assertion.</script>"
                b" SEC-B</body></html>")
        hidden = r.document("tbs-directive-2025", r.ALLOWED["tbs-directive-2025"][0], blob)
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({hidden["id"]: hidden}, [claim(hidden)])


if __name__ == "__main__":
    unittest.main()
