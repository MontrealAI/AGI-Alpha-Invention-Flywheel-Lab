"""Historical replay invariants; cases are controls, not live gold labels."""
from datetime import datetime
import json
import unittest

from frontier_radar import core, replay


def stamp(value):
    return core.instant(value)


def source(url, day, available=None):
    row = {"url": url, "title": url, "date": day}
    if available is not None:
        row["available_at"] = available
    return row


def milestone(name, day="2026-07-02", refs=None):
    return {"id": name, "title": name, "announced_at": day,
            "sources": refs or [source("https://example.com/" + name, day)]}


def record(name="risk", day="2026-07-02", refs=None):
    return {"id": name, "title": name, "as_of": day, "recommendation": "SELL",
            "capability_verified": True, "ownership_supported": True,
            "demand_observed": False, "delivery_verified": True,
            "urgency": {"expires_at": "2026-07-03T11:00:00Z", "reason": "closed soon", "certainty": "fixed_deadline",
                        "source_url": (refs or [source("https://example.com/" + name, day)])[0]["url"]},
            "move": "Offer X after verification", "alternative": "incumbent plus reviewer",
            "ownership": "matching code", "experiment": "compare real outputs",
            "pass_threshold": "20% less total effort", "stop_threshold": "any wrong output",
            "sources": refs or [source("https://example.com/" + name, day)]}


class TestReplay(unittest.TestCase):
    def test_date_tz_and_silence(self):
        a = {"cutoff": "2026-07-02", "milestones": [milestone("risk")]}
        r = record()
        cutoff = stamp("2026-07-02T23:59:59.999999Z")
        self.assertTrue(core.assess(r, cutoff)["alert"])  # live gate could alert
        q = replay.run(a, [r], cutoff)
        case = q["cases"][0]
        self.assertEqual("TEST", case["radar_decision"])
        self.assertFalse(case["alert_emitted"])
        self.assertTrue(case["digest_mentions_related_release"])
        self.assertIsNone(case["digest_decision"])
        self.assertEqual(1, q["metrics"]["same_window_related_headline_and_complete_radar_record_count"])
        self.assertIsNone(q["metrics"]["false_alerts"])
        self.assertEqual(0, q["metrics"]["alerts_emitted_by_replay"])
        json.dumps(q, allow_nan=False)
        with self.assertRaisesRegex(ValueError, "timezone"):
            replay.run(a, [r], datetime(2026, 7, 2))
        with self.assertRaisesRegex(ValueError, "coverage start"):
            replay.run(a, [r], stamp("2026-06-30T23:59:59Z"))

    def test_withholds_until_full_date_or_timestamp(self):
        delayed = source("https://example.com/delayed", "2026-07-03")
        early = source("https://example.com/early", "2026-07-02", "2026-07-02T10:00:00Z")
        stamped_milestone = milestone("early", refs=[early])
        stamped_milestone["announced_at_instant"] = "2026-07-02T10:00:00Z"
        r = record("early", refs=[early])
        r["as_of_instant"] = "2026-07-02T10:00:00Z"
        a = {"cutoff": "2026-07-03",
             "milestones": [milestone("risk"), milestone("late", refs=[delayed]), stamped_milestone]}
        q = replay.run(a, [r, record("risk"), record("late", refs=[delayed])],
                       stamp("2026-07-02T06:01:00-04:00"))
        self.assertEqual(["early"], [x["id"] for x in q["windows"][-1]["digest"]])
        self.assertEqual(["early"], [x["id"] for x in q["cases"]])
        self.assertNotIn('"id": "late"', json.dumps(q))

    def test_future_sources_cannot_leak_earlier_records(self):
        a = {"cutoff": "2026-07-10", "milestones": [milestone("first"), milestone("future", "2026-07-09")]}
        future_src = source("https://example.com/future", "2026-07-09")
        r = record("mixed", refs=[future_src])
        q = replay.run(a, [r], stamp("2026-07-10T23:59:59.999999Z"))
        self.assertEqual(2, q["metrics"]["cutoffs"])
        self.assertEqual([], q["windows"][0]["radar"])
        self.assertEqual(["first"], [x["id"] for x in q["windows"][0]["digest"]])
        self.assertEqual(["mixed"], [x["id"] for x in q["cases"]])

    def test_fixed_digest_selection_and_partial_coverage(self):
        items = [milestone(k) for k in ("z", "y", "x", "w", "v")]
        items[0]["importance"] = 100  # digest intentionally ignores this.
        a = {"cutoff": "2026-07-07", "milestones": items}
        q = replay.run(a, [], stamp("2026-07-08T08:00:00Z"))
        self.assertTrue(q["atlas_cutoff_precedes_run_date"])
        self.assertEqual(["v", "w", "x", "y"], [r["id"] for r in q["windows"][0]["digest"]])
        self.assertNotEqual(q["metrics"]["digest_headline_impressions_across_cutoffs"],
                            q["metrics"]["distinct_digest_headlines"])

    def test_retrospective_link_does_not_move_decision_back_to_headline(self):
        a = {"cutoff": "2026-07-24", "milestones": [milestone("risk")]}
        r = record(day="2026-07-23", refs=a["milestones"][0]["sources"])
        q = replay.run(a, [r], stamp("2026-07-24T00:00:00Z"))
        self.assertEqual(0, q["metrics"]["same_window_related_headline_and_complete_radar_record_count"])
        self.assertEqual([], q["windows"][0]["radar"])
        self.assertEqual(["risk"], q["retrospective_review"][0]["related_milestones_seen_in_digest"])


if __name__ == "__main__":
    unittest.main()
