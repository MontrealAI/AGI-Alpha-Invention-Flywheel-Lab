"""Frozen adverse review of the portable observer's source/reference trust boundary.

The original approved catalog is unchanged. A malicious *new* catalog can retain
its scope digest while replacing only a reference altitude; a new plan may then
self-hash that altered catalog. Binding two mutually altered documents is not
independent ephemeris verification. This test does not claim tampering occurred
in the original published receiver or in the Fink science records.
"""
import copy
import json
import unittest

from geometry import digest, mission_digest
from plan import build
from verify import verify
from pathlib import Path

HERE = Path(__file__).resolve().parent


class ReferenceIntegrityReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mission = json.loads((HERE / "mission.json").read_text())
        cls.catalog = json.loads((HERE / "catalog.json").read_text())

    def test_original_published_observer_remains_accepted(self):
        mission = {**self.mission, "max_slots": 1}
        plan = build(mission, self.catalog)
        self.assertTrue(verify(mission, self.catalog, plan)["accepted"])

    def test_self_bound_invented_reference_cannot_authorize_invisible_target(self):
        mission = {**self.mission, "max_slots": 1}
        catalog = copy.deepcopy(self.catalog)
        target = catalog["targets"][0]
        target_id = target["id"]
        slot = 0
        self.assertLess(catalog["reference"]["min_alt_deg"][target_id][slot], 0)
        catalog["reference"]["min_alt_deg"][target_id][slot] = 45.0
        # The unchanged scope digest covers observer, starts and pointing, but
        # not the reported reference angles. Neither is a signed trust root.
        self.assertEqual(catalog["reference"]["scope_sha256"],
                         self.catalog["reference"]["scope_sha256"])
        forged = {
            "scope": mission["scope"],
            "dispatch_authorized": False,
            "mission_sha256": mission_digest(mission),
            "catalog_sha256": digest(catalog),
            "objective": 1,
            "slots": [{
                "target_id": target_id,
                "utc": mission["slots_utc"][slot],
                "ra_deg": target["ra_deg"],
                "dec_deg": target["dec_deg"],
                "min_alt_deg": 45.0,
                "max_sun_alt_deg": catalog["reference"]["max_sun_alt_deg"][slot],
            }],
        }
        with self.assertRaisesRegex(ValueError, "reference|ephemeris|geometry"):
            verify(mission, catalog, forged)


if __name__ == "__main__":
    unittest.main()
