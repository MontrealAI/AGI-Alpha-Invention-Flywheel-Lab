# SPDX-License-Identifier: Apache-2.0
"""Known controls for revision order, exact geographic bounds and precision."""

import unittest

import ordinary
import specialist


def event(name, lon, revision=1, lat=0, mag="4.5", time=100):
    return {"id": name, "lon": lon, "lat": lat, "mag": mag, "time_ms": time, "updated_ms": revision}


def scoped(rows, **override):
    bounds = {"west": 175, "east": -175, "south": -10, "north": 10, "start_ms": 100,
              "end_ms": 200, "min_magnitude": "4.5", **override}
    return {"bounds": bounds, "records": rows}


class AuditTests(unittest.TestCase):
    def check_both(self, case, *, included=(), conflicting=()):
        expected = {"included": sorted(included), "conflicting": sorted(conflicting)}
        self.assertEqual(specialist.audit(case), expected)
        self.assertEqual(ordinary.audit(case), expected)
        self.assertEqual(specialist.audit({**case, "records": list(reversed(case["records"]))}), expected)

    def test_closed_geographic_and_half_open_time_boundaries(self):
        self.check_both(scoped([event("east", 175, lat=10), event("west", -175, lat=-10, time=199),
                                event("end", -180, time=200), event("out", 174)]), included=("east", "west"))

    def test_positive_and_negative_dateline_alias_are_same_physical_point(self):
        a, b = event("one", 180), event("one", -180)
        self.check_both(scoped([a, b], west=180, east=180), included=("one",))
        self.check_both(scoped([a, b], west=-180, east=-180), included=("one",))
        self.check_both(scoped([a, b], west=175, east=180), included=("one",))
        self.check_both(scoped([a, b], west=170, east=179))

    def test_latest_revision_can_withdraw_old_eligibility(self):
        self.check_both(scoped([event("moved", 180), event("moved", 140, revision=2), event("valid", 180),
                                event("missing", 180), event("missing", 180, revision=2, mag=None)]),
                        included=("valid",))

    def test_conflict_disclosed_and_cleared_only_by_higher_revision(self):
        self.check_both(scoped([event("stale", 180), event("stale", 170), event("stale", -179, revision=2),
                                event("conflict", 180), event("conflict", 170)]),
                        included=("stale",), conflicting=("conflict",))

    def test_exact_thresholds_expose_even_a_tiny_difference(self):
        self.check_both(scoped([event("eligible", "175.00000000000000000000000000000000001"),
                                event("outside", "174.99999999999999999999999999999999999"),
                                event("below", 180, mag="4.4999999999999999999999999999"),
                                event("alias", 180, mag="45e-1"), event("alias", -180, mag="4.5000")]),
                        included=("eligible", "alias"))

    def test_refuses_nonfinite_or_geographically_invalid_inputs(self):
        with self.assertRaises(ValueError):
            specialist.audit(scoped([event("impossible", 181)]))
        with self.assertRaises(ValueError):
            specialist.audit(scoped([event("unobserved", 180, mag="NaN")]))


if __name__ == "__main__":
    unittest.main()
