"""RADAR205: prospective exact-instant controls, not a historical result rewrite."""
import unittest
from datetime import datetime
from frontier_radar import core, replay


def instant(value):
    return core.instant(value)


def src(day="2026-11-20", when=None):
    row = {"date": day, "url": "https://example.org/authoritative"}
    if when is not None:
        row["available_at"] = when
    return row


def record():
    return {
        "id": "radar205", "title": "Date-only alert", "as_of": "2026-11-20",
        "priority": 5, "move": "Research only", "experiment": "Review measured evidence",
        "stop_threshold": "No admissible source",
        "sources": [src()], "recommendation": "BUILD", "capability_verified": True,
        "ownership_supported": True, "demand_observed": False, "delivery_verified": False,
        "urgency": {"reason": "Fixed cutoff", "certainty": "fixed_deadline",
                    "source_url": "https://example.org/authoritative",
                    "expires_at": "2026-11-23T14:00:00Z"},
    }


def milestone(name, day, when=None, source_when=None):
    row = {"id": name, "title": name, "announced_at": day,
           "importance": 3, "relevance": 3, "change": name, "evidence": name,
           "sources": [src(day, source_when)]}
    if when is not None:
        row["announced_at_instant"] = when
    return row


class Intraday205(unittest.TestCase):
    friday_morning = instant("2026-11-20T08:00:00-05:00")

    def test_no_date_only_friday_morning_alert(self):
        r = record()
        early = core.assess(r, self.friday_morning)
        self.assertEqual("UNAVAILABLE", early["decision"])
        self.assertFalse(early["alert"])
        self.assertFalse(core.assess(r, self.friday_morning, history=True)["alert"])
        after = instant("2026-11-20T19:00:00-05:00")  # Nov 21 00:00 UTC
        self.assertTrue(core.evidence_available(r, after))
        self.assertTrue(core.assess(r, after)["alert"])

    def test_earlier_explicit_timestamp_is_admissible(self):
        r = record()
        r["as_of_instant"] = "2026-11-20T12:00:00Z"
        r["sources"][0]["available_at"] = "2026-11-20T12:30:00Z"
        self.assertTrue(core.assess(r, self.friday_morning)["alert"])
        r["sources"].append(src(when="2026-11-20T14:00:00Z"))
        self.assertFalse(core.assess(r, self.friday_morning)["alert"])
        self.assertTrue(core.assess(r, instant("2026-11-20T14:01:00Z"))["alert"])

    def test_bad_timestamp_never_falls_back_to_same_day(self):
        for value in ("2026-11-20T10:00:00", "2026-11-21T00:00:00Z",
                      "2026-11-20T17:00:00Z", "bad", ""):
            with self.subTest(value=value):
                r = record()
                r["as_of_instant"] = value
                r["sources"][0]["available_at"] = "2026-11-20T10:00:00Z"
                self.assertEqual("UNAVAILABLE", core.assess(r, self.friday_morning)["decision"])
        r = record()
        r["as_of_instant"] = "2026-11-20T10:00:00Z"
        r["sources"][0]["available_at"] = "2026-11-20T10:00:00"  # naive source
        self.assertFalse(core.assess(r, self.friday_morning)["alert"])

    def test_utc_crossover_and_friday_briefing(self):
        a = {"cutoff": "2026-11-20", "milestones": [
            milestone("yesterday", "2026-11-19"),
            milestone("same_day_unproven", "2026-11-20"),
            milestone("same_day_proven", "2026-11-20",
                      "2026-11-20T12:00:00Z", "2026-11-20T12:05:00Z"),
        ]}
        self.assertEqual(["yesterday", "same_day_proven"],
                         [x["id"] for x in core.atlas_at(a, self.friday_morning)])
        txt = core.briefing(a, [record()], self.friday_morning)
        self.assertIn("same_day_proven", txt)
        self.assertNotIn("same_day_unproven", txt)
        self.assertNotIn("Date-only alert", txt)
        after = instant("2026-11-20T19:00:00-05:00")
        self.assertEqual(3, len(core.atlas_at(a, after)))
        self.assertIn("Date-only alert", core.briefing(a, [record()], after))

    def test_historical_replay_does_not_peek_into_same_day(self):
        a = {"cutoff": "2026-11-20", "milestones": [
            milestone("same_day", "2026-11-20")]}
        q = replay.run(a, [record()], self.friday_morning)
        self.assertEqual(0, q["metrics"]["milestones_available_at_final_cutoff"])
        self.assertEqual(0, q["metrics"]["decision_records_available_at_final_cutoff"])
        self.assertEqual(0, q["metrics"]["alerts_emitted_by_replay"])

    def test_timezone_is_required(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            core.atlas_at({"milestones": [milestone("today", "2026-11-20")]},
                          datetime(2026, 11, 20, 13))


if __name__ == "__main__":
    unittest.main()
