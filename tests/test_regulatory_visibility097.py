"""Prospectively registered H0-H9 explicit-hidden-HTML adversarial controls.

Only in-scope HTML attributes and inline style are examined. This is not browser/CSS
visibility, accessibility certification, legal review, real commerce or a buyer test.
Fixed before the implementation: VISIBILITY_AMENDMENT.md at b16fcf244800ea8a2e0b1ac42aaf74c805b7b677.
"""
import unittest

from research import regulatory_citation097 as r


QUOTE = "Signed control assertion."


def doc(fragment):
    html = "<html><body>SEC-A before " + fragment + " SEC-B after</body></html>"
    return r.document("tbs-directive-2025", r.ALLOWED["tbs-directive-2025"][0],
                      html.encode("utf-8"))


def verified(fragment):
    d = doc(fragment)
    return r.packet({d["id"]: d}, [r.make_claim("H", d, "SEC-A", "SEC-B", QUOTE)])


class ExplicitHiddenExclusion(unittest.TestCase):
    def refused(self, markup):
        with self.subTest(markup=markup), self.assertRaisesRegex(
            ValueError, "QUOTE_NOT_IN_BOUND_SECTION"
        ):
            verified(markup)

    def test_H0_boolean_hidden_attribute(self):
        self.refused('<div hidden>' + QUOTE + '</div>')
        self.refused('<div hidden="">' + QUOTE + '</div>')
        self.refused('<p HIDDEN="hidden">' + QUOTE + '</p>')

    def test_H1_aria_hidden_true_is_excluded(self):
        self.refused('<div aria-hidden="true">' + QUOTE + '</div>')
        self.refused('<section aria-HIDDEN=" TrUe "><b>' + QUOTE + '</b></section>')

    def test_H2_inline_display_none(self):
        self.refused('<div style="display:none">' + QUOTE + '</div>')
        self.refused('<div style="color:red; DISPLAY : none !important">' + QUOTE + '</div>')
        self.refused('<div style="display: none; display: none">' + QUOTE + '</div>')

    def test_H3_inline_visibility_hidden_or_collapse(self):
        self.refused('<div style="visibility:hidden">' + QUOTE + '</div>')
        self.refused('<section style="VISIBILITY: collapse;"><em>' + QUOTE + '</em></section>')

    def test_H4_suppress_nested_descendants_but_not_visible_sibling(self):
        self.refused('<div hidden><span><b>' + QUOTE + '</b></span></div>')
        self.refused('<div hidden>other <p>' + QUOTE + '</p></div>')
        value = verified('<div hidden><span>' + QUOTE + '</span></div>'
                         '<p>' + QUOTE + '</p>')
        self.assertEqual(value["accepted"], 1)

    def test_H5_exposed_siblings_and_void_self_closing(self):
        for markup in (
            '<input type="hidden"/><span>' + QUOTE + '</span>',
            '<img hidden src="nonexistent"/><p>' + QUOTE + '</p>',
            '<div aria-hidden="false"><b>' + QUOTE + '</b></div>',
            '<div style="display:block; visibility:visible">' + QUOTE + '</div>',
            '<div hidden><span>other</span></div><p>' + QUOTE + '</p>',
        ):
            with self.subTest(markup=markup):
                self.assertEqual(verified(markup)["accepted"], 1)

    def test_H6_unrecognized_inline_visibility_fails_closed(self):
        for markup in (
            '<div style="display:var(--unknown)">' + QUOTE + '</div>',
            '<div style="display:/*untrusted*/block">' + QUOTE + '</div>',
            '<div style="visibility:var(--state)">' + QUOTE + '</div>',
            '<div style="content-visibility:auto">' + QUOTE + '</div>',
        ):
            self.refused(markup)

    def test_H7_original_script_and_style_exclusions_remain(self):
        self.refused('<script>' + QUOTE + '</script>')
        self.refused('<style>' + QUOTE + '</style>')
        self.refused('<noscript>' + QUOTE + '</noscript>')
        self.refused('<template><p>' + QUOTE + '</p></template>')
        self.refused('<svg><text>' + QUOTE + '</text></svg>')

    def test_H8_visible_quote_outside_hidden_anchor_is_still_refused(self):
        d = doc('different <div hidden>' + QUOTE + '</div>')
        assert QUOTE not in d["text"]
        with self.assertRaisesRegex(ValueError, "QUOTE_NOT_IN_BOUND_SECTION"):
            r.packet({d["id"]: d}, [r.make_claim("H", d, "SEC-A", "SEC-B", QUOTE)])

    def test_H9_packet_replay_remains_exact_and_deterministic(self):
        fragment = '<div hidden>' + QUOTE + '</div><p>' + QUOTE + '</p>'
        d = doc(fragment)
        claims = [r.make_claim("H", d, "SEC-A", "SEC-B", QUOTE)]
        p = r.packet({d["id"]: d}, claims)
        self.assertTrue(r.verify_packet(p, {d["id"]: d}, claims))


if __name__ == "__main__":
    unittest.main()
