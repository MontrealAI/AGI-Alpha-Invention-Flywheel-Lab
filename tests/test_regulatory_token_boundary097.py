"""Source-bound N0–N6 token-window regressions, frozen at d33d7e74.

These are *synthetic*, noncommercial and separate from C0–C13/H0–H9.
No reclassification of original failed real-source A0–A2.
"""
import unittest
from research import regulatory_citation097 as r

DOC="tbs-directive-2025"
URL=r.ALLOWED[DOC][0]
QUOTE="Signed control assertion."

def run(text, anchor="SEC-A", stop="SEC-B", quote=QUOTE):
    raw=("<html><body>"+text+"</body></html>").encode("utf-8")
    d=r.document(DOC,URL,raw)
    return r.packet({DOC:d},[r.make_claim("N",d,anchor,stop,quote)])

class ExactLexicalBoundaries(unittest.TestCase):
    def test_N0_embedded_start_is_not_a_section(self):
        with self.assertRaisesRegex(ValueError,"MISSING_OR_DUPLICATE_ANCHOR"):
            run("XSEC-A "+QUOTE+" SEC-B")

    def test_N1_embedded_stop_is_not_a_section_end(self):
        with self.assertRaisesRegex(ValueError,"MISSING_OR_DUPLICATE_ANCHOR"):
            run("SEC-A "+QUOTE+" SEC-BETA")

    def test_N2_numbered_section_prefixes_do_not_count(self):
        for text in ("16.1.1 "+QUOTE+" 6.1.2",
                     "6.1.1.1 "+QUOTE+" 6.1.2",
                     "6.1.1 "+QUOTE+" 6.1.2.1"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                run(text,anchor="6.1.1",stop="6.1.2")
        self.assertEqual(run("6.1.1: "+QUOTE+" 6.1.2.",anchor="6.1.1",stop="6.1.2")["accepted"],1)

    def test_N3_quote_substring_in_another_word_does_not_count(self):
        with self.assertRaisesRegex(ValueError,"QUOTE_NOT_IN_BOUND_SECTION"):
            run("SEC-A pre"+QUOTE+" SEC-B")

    def test_N4_true_sections_crossreferences_and_duplicates(self):
        self.assertEqual(run("SEC-A "+QUOTE+" SEC-B")["accepted"],1)
        self.assertEqual(run("A reference to SEC-A occurs here. SEC-A "+QUOTE+" SEC-B")["accepted"],1)
        with self.assertRaisesRegex(ValueError,"MULTIPLE_VALID_WINDOWS"):
            run("SEC-A "+QUOTE+" SEC-B other SEC-A "+QUOTE+" SEC-B")

    def test_N5_normal_punctuation_remains_eligible(self):
        for text in ("(SEC-A): "+QUOTE+" [SEC-B].",
                     "SEC-A: "+QUOTE+" SEC-B;",
                     "SEC-A — "+QUOTE+" SEC-B"):
            with self.subTest(text=text):
                self.assertEqual(run(text)["accepted"],1)

    def test_N6_bounded_substrings_cannot_forge_full_quote_or_stop(self):
        for text in ("SEC-A "+QUOTE+" extraSEC-B",
                     "SEC-A "+QUOTE+" SEC-B-EXTRA"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                run(text)

if __name__ == "__main__":
    unittest.main()
