"""FIRST-CASH207 deterministic source-only acceptance; no revenue or customer simulation."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "docs" / "frontier-unseen-advantage-sample.html"
SHOP = "https://www.quebecartificialintelligence.com/shop/p/frontier-the-unseen-advantage"
GITHUB_PREFIX = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/"


class ContentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.sheets: list[str] = []
        self.tags: list[str] = []
        self.langs: list[str] = []
        self.unsafe_attributes: list[str] = []
        self.errors: list[str] = []
        self.sections: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        a = dict(attrs)
        if tag == "a":
            self.links.append(a.get("href", ""))
        if tag == "article" and "sheet" in a.get("class", "").split():
            self.sheets.append(a.get("data-page", ""))
        if tag == "section" and a.get("lang") in ("en", "fr"):
            self.sections.append((tag, a["lang"]))
        if "lang" in a:
            self.langs.append(a["lang"])
        self.unsafe_attributes.extend(key for key, _ in attrs if key.lower().startswith("on"))


class SampleContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = PAGE.read_text(encoding="utf-8")
        cls.parser = ContentParser()
        cls.parser.feed(cls.content)

    def test_ten_numbered_print_pages(self):
        self.assertEqual([str(i) for i in range(1, 11)], self.parser.sheets)
        self.assertIn("break-after:page", self.content)
        self.assertIn("@page{size:A4;margin:0}", self.content)

    def test_meaningful_parallel_bilingual_structure(self):
        self.assertEqual(10, self.parser.langs.count("en"))
        self.assertEqual(10, self.parser.langs.count("fr"))
        self.assertEqual(10, len(re.findall(r'<h[12]\b', self.content)))
        self.assertIn("ÉCHANTILLON", self.content)
        self.assertIn("NOT A CUSTOMER", self.content)

    def test_matched_component_benefit_not_pipeline_or_profit(self):
        for value in ("24 / 24", "2.244×", "1.009×", "208.27", "92.82",
                      "208,27", "92,82", "whole", "observed", "UNKNOWN",
                      "INCONNU", "no customer", "Aucun paiement client"):
            self.assertIn(value.lower(), self.content.lower())
        self.assertIn("not an end-to-end Reader speedup", self.content)

    def test_competent_four_way_choices_and_no_go(self):
        for needle in ("A. Dossier", "B. Technical patch", "C. Machine asset",
                       "D. No deploy", "Human + conventional software",
                       "NO DEPLOY", "Commercial011", "compounding"):
            self.assertIn(needle.lower(), self.content.lower())

    def test_no_live_actions_or_untrusted_resources(self):
        self.assertTrue(self.parser.links)
        self.assertFalse(set(self.parser.tags) & {"script", "form", "iframe",
                                                  "input", "object", "embed",
                                                  "video", "audio", "img"})
        self.assertFalse(self.parser.unsafe_attributes)
        self.assertFalse(re.search(r'url\s*\(|@import|fetch\s*\(', self.content, re.I))
        for link in self.parser.links:
            self.assertTrue(link.startswith(GITHUB_PREFIX) or link == SHOP, link)
            parts = urlsplit(link)
            self.assertEqual("https", parts.scheme)
            self.assertFalse(parts.username or parts.password)

    def test_immutable_primary_technical_evidence_present(self):
        technical = ("https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/"
                     "blob/0da09f16c29b7ee0758f016e47d42808e3e8ab58/"
                     "docs/frontier-omega-ignition/continuation/beneficiary-pursuit/REPORT.md")
        self.assertIn(technical, self.parser.links)
        self.assertIn(SHOP, self.parser.links)


if __name__ == "__main__":
    unittest.main()
