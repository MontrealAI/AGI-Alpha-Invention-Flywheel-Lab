"""Adversarial offline source/measurement admission regressions for Electrolysis131."""
import unittest
from datetime import datetime
from campaign.electrolysis131 import physical_scope as p


MODEL = b"""
P = max(P, 0);
P = min(P, stack.P_max_kW);
stack.P_rated_kW     = 60;
stack.P_max_kW       = 52;
stack.turndown_ratio = 0.30;
stack.P_min_kW       = stack.P_max_kW * stack.turndown_ratio;
"""


class Electrolysis131Tests(unittest.TestCase):
    def test_registered_paths_and_source_commit(self):
        self.assertEqual(len(p.PINS), 9)
        self.assertEqual(len(p.COMMIT), 40)
        self.assertTrue(all(len(x)==40 for x in p.PINS.values()))
        self.assertNotIn("hydrogen_flow.txt", tuple(k for k in p.PINS if "inputs" in k))

    def test_git_blob_hash_is_the_real_git_format(self):
        # Known Git object fixture: empty blob SHA1 from Git.
        self.assertEqual(p.git_blob_sha(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")
        self.assertEqual(p.git_blob_sha(b"hello\\n"),
                         "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_changed_or_unknown_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "PINNED_UPSTREAM_BLOB_CHANGED"):
            p.verify_source("data/experiment/stack_power.txt", b"0\\n")
        with self.assertRaisesRegex(ValueError, "UNREGISTERED"):
            p.verify_source("private/financial_key.txt", b"data")
        with self.assertRaisesRegex(ValueError, "OVERSIZE"):
            p.verify_source("data/experiment/stack_power.txt", b"x"*(p.MAX_BYTES+1))

    def test_no_missing_or_nonfinite_measurement(self):
        self.assertEqual(p.parse_float_lines(b"0\\n-1.3\\n2e-5\\n"), [0., -1.3, .00002])
        for bad in (b"", b"0\\n\\n1\\n", b"0\\nnan\\n", b"Inf\\n", b"1\\nx\\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    p.parse_float_lines(bad)

    def test_timestamp_order_and_one_hz(self):
        start=datetime(2025,11,5,13,34,25)
        txt=b"".join((f"05-Nov-2025 13:34:{i:02d}\\n").encode() for i in range(30))
        self.assertEqual(p.read_times(txt)[0], start)
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATED_SECOND"):
            p.read_times(txt.replace(b"13:34:15", b"13:34:14"))
        with self.assertRaisesRegex(ValueError, "MISSING_OR_DUPLICATED_SECOND"):
            p.read_times(txt[:-len(b"05-Nov-2025 13:34:29\\n")])

    def test_explicit_source_physical_bounds(self):
        r=p.parse_model_bound(MODEL)
        self.assertEqual(r["declared_model_max_kW"], 52.0)
        self.assertAlmostEqual(r["declared_model_min_turndown_kW"], 15.6)
        for altered in (MODEL.replace(b"P_max_kW       = 52", b"P_max_kW       = 65"),
                        MODEL.replace(b"P = min(P, stack.P_max_kW);", b""),
                        MODEL.replace(b"turndown_ratio = 0.30", b"turndown_ratio = 1.0")):
            with self.subTest(altered=altered):
                try:
                    bound=p.parse_model_bound(altered)
                except ValueError:
                    continue
                self.assertNotEqual(bound, r)

    def test_scope_does_not_claim_commerce_or_actuation(self):
        self.assertFalse(hasattr(p, "execute_device"))
        self.assertNotIn("financial", tuple(p.PINS))
        self.assertTrue(p.UPSTREAM.startswith("HydrogenDude/"))


if __name__ == "__main__":
    unittest.main()
