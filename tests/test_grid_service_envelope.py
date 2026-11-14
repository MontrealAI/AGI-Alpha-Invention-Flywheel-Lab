"""Independent checker regression and negative-mutation tests.

Set GRID_ENVELOPE_WITNESS and RTS_DATA for a retained feasible development
witness. Confirmation data is never solved or searched by these tests.
"""
import copy
import json
import os
import tempfile
from pathlib import Path
import unittest

from grid_service_envelope.verify import verify

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get('RTS_DATA',ROOT/'campaign/grid-service-envelope-20261104/data'))
WITNESS=Path(os.environ.get('GRID_ENVELOPE_WITNESS',ROOT/'.tmp/development-amended.json'))

def load_development_witness(path, required=False):
    def unavailable(message):
        if required:raise AssertionError(message)
        raise unittest.SkipTest(message)
    if not path.exists():unavailable('No feasible development witness provided')
    witness=json.loads(path.read_text())
    if witness.get('solver_status')!=0:unavailable('Development witness reports no feasible solution')
    if witness.get('day')!='2020-01-01':unavailable('Tests restricted to development day')
    return witness

class MalformedWitnessTests(unittest.TestCase):
    def test_required_missing_witness_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AssertionError):
                load_development_witness(Path(tmp)/'missing.json',required=True)

    def test_required_infeasible_witness_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'infeasible.json'
            path.write_text(json.dumps({'solver_status':2,'day':'2020-01-01'}))
            with self.assertRaises(AssertionError):
                load_development_witness(path,required=True)

    def test_empty_rejected(self):
        self.assertFalse(verify({},DATA)['accepted'])

    def test_solver_failure_rejected(self):
        r=verify({'solver_status':2},DATA)
        self.assertFalse(r['accepted'])
        self.assertEqual(r['error'],'solver_success')

    def test_unreadable_input_rejected(self):
        self.assertFalse(verify('/no/such/witness.json',DATA)['accepted'])

class WitnessTamperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=load_development_witness(WITNESS,required=os.environ.get('GRID_ENVELOPE_REQUIRE_WITNESS')=='1')
        result=verify(cls.original,DATA)
        if not result['accepted']:raise AssertionError('Baseline witness fails independent check: '+str(result.get('error')))

    def rejected(self,modify):
        candidate=copy.deepcopy(self.original); modify(candidate)
        self.assertFalse(verify(candidate,DATA)['accepted'])

    def test_original_passes_without_mutation(self):
        before=copy.deepcopy(self.original)
        result=verify(self.original,DATA)
        self.assertTrue(result['accepted']);self.assertFalse(result['optimality_independently_verified'])
        self.assertEqual(before,self.original)

    def test_nonfinite_values(self):
        for value in (float('nan'),float('inf'),-float('inf')):
            with self.subTest(value=value):
                self.rejected(lambda w:w['work'].__setitem__(0,value))
                self.rejected(lambda w:w['plans']['normal']['theta'][0].__setitem__(0,value))

    def test_scenario_missing(self):
        self.rejected(lambda w:w['plans'].pop('battery_failure_8_24'))

    def test_scenario_extra(self):
        self.rejected(lambda w:w['plans'].__setitem__('invented',w['plans']['normal']))

    def test_shape_change(self):
        self.rejected(lambda w:w['plans']['normal']['generation'][0].pop())

    def test_unmet_deadline(self):
        self.rejected(lambda w:w['work'].__setitem__(0,w['work'][0]-0.01))

    def test_work_moved_before_release(self):
        def mutate(w):
            w['work'][0]+=0.01;w['work'][12]-=0.01
        self.rejected(mutate)

    def test_trip_grid_injection(self):
        self.rejected(lambda w:w['plans']['connection_trip_8_14']['grid'].__setitem__(8,0.1))

    def test_backup_during_failure(self):
        self.rejected(lambda w:w['plans']['backup_failure_8_24']['backup'].__setitem__(8,0.1))

    def test_battery_during_failure(self):
        self.rejected(lambda w:w['plans']['battery_failure_8_24']['discharge'].__setitem__(8,0.1))

    def test_wrong_stress(self):
        self.rejected(lambda w:w['plans'].__setitem__('line_A1_out_load_110pct_8_24',copy.deepcopy(w['plans']['normal'])))

    def test_wrong_fault_identity(self):
        self.rejected(lambda w:w.__setitem__('largest_thermal_uid','invented'))

    def test_nonanticipativity(self):
        self.rejected(lambda w:w['plans']['backup_failure_8_24']['soc'].__setitem__(7,w['plans']['backup_failure_8_24']['soc'][7]+0.1))

    def test_network_flow_corruption(self):
        self.rejected(lambda w:w['plans']['normal']['theta'][10].__setitem__(1,w['plans']['normal']['theta'][10][1]+0.001))

    def test_soc_corruption(self):
        self.rejected(lambda w:w['plans']['normal']['soc'].__setitem__(13,w['plans']['normal']['soc'][13]+0.1))

    def test_cost_corruption(self):
        self.rejected(lambda w:w.__setitem__('worst_daily_opex_usd',w['worst_daily_opex_usd']+10))

    def test_certificate_corruption(self):
        self.rejected(lambda w:w['optimization'].__setitem__('dual_objective',w['optimization']['dual_objective']-100))

    def test_source_bytes_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            for source in DATA.iterdir():
                if source.name=='bus.csv':
                    (target/source.name).write_bytes(source.read_bytes()+b'\n')
                elif source.is_file():(target/source.name).symlink_to(source.resolve())
            result=verify(self.original,target)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['error'],'source_hash_bus.csv')

    def test_manifest_tampered(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            manifest=json.loads((DATA/'SOURCE_MANIFEST.json').read_text())
            manifest['commit']='not-pinned'
            (target/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest))
            result=verify(self.original,target)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['error'],'source_manifest_hash')

    def test_fractional_commitment(self):
        if 'thermal_commitment' not in self.original:self.skipTest('Original all-on specification')
        self.rejected(lambda w:w['thermal_commitment'].__setitem__(0,0.5))

if __name__=='__main__':unittest.main()
