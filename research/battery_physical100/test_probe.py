import unittest

from research.battery_physical100.probe import inspect_csv


class ProbeTests(unittest.TestCase):
    def test_measured_values_preserved(self):
        report = inspect_csv(b"cycle,capacity,label\n1,2.9,discharge\n2,2.8,discharge\n")
        self.assertEqual(report["rows"], 2)
        self.assertEqual(report["column_stats"]["capacity"]["minimum"], 2.8)
        self.assertEqual(report["column_stats"]["label"]["nonnumeric"], 2)

    def test_invalid_tables_refused(self):
        for data in [b"", b"a,a\n1,2\n", b"a,b\n1\n", b"a\nnan\n", b"a\n"]:
            with self.subTest(data=data), self.assertRaises(ValueError):
                inspect_csv(data)


if __name__ == "__main__":
    unittest.main()
