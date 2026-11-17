import unittest
from datetime import datetime, timezone

from qualify_sources import FEEDS, FEED_KEYS, qualify


START = datetime(2026, 11, 17, 10, tzinfo=timezone.utc)
END = datetime(2026, 11, 17, 11, tzinfo=timezone.utc)
CLEAN = {"revision": "a" * 40, "clean": True, "status": "PASS"}


def observations():
    rows = []
    for key in FEED_KEYS:
        repo = FEEDS[key][0]
        for release in (True, False):
            query = "releases?per_page=3" if release else "commits?per_page=1&until=2026-10-13T23:59:59Z"
            rows.append({"feed": key, "role": "Published release" if release else "Earlier snapshot",
                         "version": "v1" if release else "a" * 40, "publisher": repo.split("/")[0],
                         "origin": f"https://api.github.com/repos/{repo}/{query}",
                         "url": f"https://github.com/{repo}/" + ("releases/tag/v1" if release else "commit/" + "a" * 40),
                         "text": "Published material", "source_response_sha256": "a" * 64,
                         "event_at": "2026-09-01T00:00:00Z" if release else "2026-10-10T00:00:00Z",
                         "published_at": "2026-09-01T00:00:00Z" if release else None,
                         "retrieved_at": "2026-11-17T10:30:00Z"})
    return rows


class LiveSourcesQualificationTests(unittest.TestCase):
    def test_success_only_claims_dated_source_acquisition(self):
        rows = observations()
        report = qualify({"sources": rows, "failures": []}, START, END, CLEAN)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["capability_comparison"], "unresolved")
        self.assertFalse(any(r["reported_event_inside_window"] for r in report["observations"]))
        self.assertIsNone(report["observations"][1]["published_at"])
        self.assertNotIn("text", report["observations"][0])

    def test_failures_preserve_other_observations_and_never_use_canned_evidence(self):
        data = {"sources": observations()[:2], "failures": [{"feed": "distribution", "role": "current", "reason": "HTTP failure"}]}
        report = qualify(data, START, END, CLEAN)
        self.assertEqual((report["status"], len(report["observations"]), len(report["missing_roles"])), ("BLOCKED", 2, 2))
        data = {"sources": observations(), "failures": []}
        for edit in ({"retrieved_at": "2025-01-01T00:00:00Z"}, {"origin": "https://other.invalid"},
                     {"published_at": None}, {"source_response_sha256": "bad"}):
            with self.subTest(edit=edit):
                broken = {"sources": [data["sources"][0] | edit, *data["sources"][1:]], "failures": []}
                self.assertEqual(qualify(broken, START, END, CLEAN)["status"], "FAIL")
        self.assertEqual(qualify(data, START, END, {"status": "BLOCKED"})["status"], "BLOCKED")
