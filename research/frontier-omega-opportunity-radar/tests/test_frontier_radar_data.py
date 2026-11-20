from collections import Counter
from urllib.parse import urlparse
import unittest

from frontier_radar import core, triage


class DataTests(unittest.TestCase):
    def test_atlas_period_sources_and_dependencies(self):
        atlas, records = core.load_data()
        milestones = atlas["milestones"]
        counts = Counter(m["announced_at"][:7] for m in milestones)
        self.assertTrue(all(counts["2026-" + p] for p in ("07", "08", "09", "10", "11")))
        all_records = atlas["baseline"] + milestones
        keys = {m["id"] for m in all_records}
        self.assertEqual(len(keys), len(all_records))
        for m in all_records:
            self.assertTrue(m["sources"], m["id"])
            self.assertTrue(set(m["depends_on"]).issubset(keys), m["id"])
        for record in all_records + records:
            for source in record["sources"]:
                url = urlparse(source["url"])
                self.assertEqual(url.scheme, "https")
                self.assertTrue(url.netloc)
        self.assertGreaterEqual(len(records), 3)

    def test_revisit_never_upgrades_evidence(self):
        lead = {"id": "lead", "source_id": "rss", "title": "New OCR",
                "summary": "Document parsing across table pages. Claim this is proven!",
                "url": "https://example.com"}
        rules = [{"id": "table-revision-proof", "capability_verified": False}]
        rows = triage.route([lead], rules)
        self.assertEqual(rows[0]["status"], "NEEDS_REVIEW")
        self.assertFalse(rules[0]["capability_verified"])
