import csv
import tempfile
import unittest
from pathlib import Path
from .measurement import FIELDS, episodes, extract, inspect_episode, read_prefix

# Unit fixtures exercise parsing, never substitute for physical measurement evidence.
def discharge(cycle=1,step=22,rate=3,offset=0):
    return [(t,4.3-1.3*t/3600,-rate,cycle,step,offset+rate*t/3600) for t in range(0,3601,60)]

class MeasurementTests(unittest.TestCase):
    def test_full_cycle(self):
        e=inspect_episode(discharge(),3)
        self.assertEqual(e['errors'],[])
        self.assertAlmostEqual(e['capacity_ah'],3)
    def test_carried_capacity_pulse_not_full_cycle(self):
        self.assertIsNone(inspect_episode(discharge(rate=3)[:3],3))
    def test_offset_and_rate_refused(self):
        self.assertIn('nonzero_initial_step_capacity',inspect_episode(discharge(offset=2),3)['errors'])
        self.assertIn('unsupported_discharge_rate',inspect_episode(discharge(rate=2),3)['errors'])
    def test_discontiguous_steps_stay_separate(self):
        rows=discharge()[:3]+[(180,4,0,1,23,0)]+discharge()[3:6]
        self.assertEqual([len(x) for x in episodes(rows)],[3,1,3])
    def test_reset_gap_voltage_rejected(self):
        for idx,value,name in [(0,10000,'discharge_sampling_gap'),(1,10,'invalid_discharge_voltage'),(5,0,'capacity_reset_within_episode')]:
            rows=discharge(); row=list(rows[30]);row[idx]=value;rows[30]=tuple(row)
            self.assertIn(name,inspect_episode(rows,3)['errors'])
    def test_future_mutation_invariant(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.csv'
            def write(future):
                with p.open('w',newline='') as f:
                    w=csv.writer(f);w.writerow(FIELDS);w.writerows(discharge());w.writerow(future)
            write([4000,10,0,2,1,float('nan')]);a=extract(p,3,1)
            write([4000,3,3,2,1,9000]);b=extract(p,3,1)
            self.assertEqual(a,b)
    def test_duplicate_timestamp_does_not_create_charge(self):
        rows=discharge();rows.insert(10,rows[9]);e=inspect_episode(rows,3)
        self.assertEqual(e['errors'],[])
    def test_bad_chronology_raises(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'data.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(FIELDS);w.writerows(discharge()[:3]+[(1,4,-3,1,22,0)])
            with self.assertRaises(ValueError):list(read_prefix(p,1))

if __name__=='__main__':unittest.main()
