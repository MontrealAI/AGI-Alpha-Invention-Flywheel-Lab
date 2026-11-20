import unittest
from copy import deepcopy
from datetime import datetime, timezone

from frontier_radar import core


class GateTests(unittest.TestCase):
    now = core.instant("2026-11-20T14:00:00-05:00")

    def fixture(self):
        return {
            "id": "control", "as_of": "2026-11-20",
            "sources": [{"date": "2026-11-20", "url": "https://example.org/fixture"}],
            "recommendation": "BUILD",
            "capability_verified": True, "ownership_supported": True,
            "demand_observed": False, "delivery_verified": False,
            "urgency": {"reason": "Trial terms close on Monday", "certainty": "fixed_deadline",
                        "source_url": "https://example.org/fixture", "expires_at": "2026-11-23T15:00:00-05:00"},
        }

    def test_three_gates_and_early_deadline(self):
        self.assertTrue(core.assess(self.fixture(), self.now)["alert"])
        for field, v in (("capability_verified", False), ("ownership_supported", False), ("urgency", None)):
            with self.subTest(field=field):
                r = self.fixture()
                r[field] = v
                self.assertFalse(core.assess(r, self.now)["alert"])

    def test_sell_is_not_allowed_on_inferred_demand(self):
        r = self.fixture()
        r["recommendation"] = "SELL"
        self.assertEqual(core.assess(r, self.now)["decision"], "TEST")
        r["demand_observed"] = r["delivery_verified"] = True
        self.assertEqual(core.assess(r, self.now)["decision"], "SELL")

    def test_replay_is_silent_and_no_hindsight(self):
        r = self.fixture()
        self.assertFalse(core.assess(r, self.now, history=True)["alert"])
        r["sources"] = [{"date": "2026-11-21"}]
        self.assertEqual(core.assess(r, self.now, history=True)["decision"], "UNAVAILABLE")

    def test_expired_and_friday_first(self):
        for deadline in ("2026-11-19T23:00:00Z", "2026-11-27T14:00:01Z"):
            r = self.fixture()
            r["urgency"]["expires_at"] = deadline
            self.assertFalse(core.assess(r, self.now)["alert"])

    def test_at_least_through_is_not_fixed_deadline(self):
        r = self.fixture()
        r["urgency"].update(certainty="lower_bound", reason="At least through November 21",
                            expires_at="2026-11-21T23:59:00Z")
        self.assertFalse(core.assess(r, self.now)["alert"])
        r["urgency"].update(certainty="fixed_deadline", expires_at="2026-11-30T23:59:00Z")
        self.assertFalse(core.assess(r, self.now)["alert"])

    def test_deadline_requires_a_dated_source(self):
        r = self.fixture()
        r["urgency"]["source_url"] = "https://example.org/not-reviewed"
        self.assertFalse(core.assess(r, self.now)["alert"])

    def test_dst_transition(self):
        start = core.instant("2026-10-30T09:00:00-04:00")
        target = core.next_friday(start)
        self.assertEqual(target.astimezone(timezone.utc).isoformat(), "2026-11-06T13:00:00+00:00")

    def test_unreviewed_stale_candidate_silent(self):
        r = self.fixture()
        r["as_of"] = "2026-11-11"
        self.assertFalse(core.assess(r, self.now)["alert"])

    def test_pass_not_promoted(self):
        r = deepcopy(self.fixture())
        r["recommendation"] = "PASS"
        self.assertFalse(core.assess(r, self.now)["alert"])


if __name__ == "__main__":
    unittest.main()
