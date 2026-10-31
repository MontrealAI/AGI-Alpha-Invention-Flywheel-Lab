# Generic historical suites lack the separately pinned physics environment.
# The mandatory isolated campaign step requires all 14 battery tests, no skips.
import importlib.util
import os
import unittest
if importlib.util.find_spec('pybamm') is None:
    if os.environ.get('BATTERY_QUALIFICATION_REQUIRED') == '1':
        raise ImportError('MANDATORY_BATTERY_DEPENDENCY_MISSING')
    raise unittest.SkipTest('Battery physics/native tests run in mandatory isolated campaign environment')
"""Native admission/finance engineering, not market demand or invention proof."""
import copy,tempfile,unittest
from pathlib import Path
from connected_enterprise.research_service import manifest,run_paid,check,KIND
from connected_enterprise.finance import JournalAccount
ROOT=Path(__file__).resolve().parents[1]

def job(ident,temp):
 return {'id':ident,'kind':KIND,'request':{'schema':'battery-physics-service/v1','parameter_set':'Ai2020','temperature_K':temp,'initial_soc':.1,'target_soc':.8,'maximum_seconds':3600,'maximum_current_A':4.,'maximum_voltage_V':4.2,'maximum_temperature_K':318.15,'minimum_anode_potential_V':0.02},'allowed_policy_kinds':['anode'],'cost_envelope_microUSD':{k:1_000_000 for k in ('discovery','construction','criticism','repair','production','verification','report','support')},'max_attempts':2,'construction':{'mode':'provided_policy_evaluation'},'scope':'SIMULATED_PROTOCOL_EVALUATION_REPORT_NOT_PHYSICAL_SAFETY'}

class PendingBattery(unittest.TestCase):
 def test_pending_paid_real_physics_native_collection_successor(self):
  jobs=[job('initial',298.15),job('fresh',300.15)];m=manifest(ROOT,jobs)
  self.assertNotIn('artifact',m['jobs'][0]);self.assertNotIn('accepted',m['jobs'][0])
  with tempfile.TemporaryDirectory(dir=ROOT,prefix='.battery-native-') as tmp:
   path=Path(tmp)/'account.sqlite'
   a=JournalAccount(ROOT,m,path,opening=500_000_000,working=1_000_000,contract='BATTERY_ENGINEERING_NOT_DEMAND_PROOF')
   try:
    before=a.export()['ledger']['summary']
    with self.assertRaisesRegex(ValueError,'INSUFFICIENT'):run_paid(ROOT,a,'initial',{'kind':'anode','current_A':4.},allow_seed=False)
    self.assertEqual(a.export()['ledger']['summary'],before)
    # Distinct attempt after rejected native spend; no free retry on prior id.
    r=run_paid(ROOT,a,'initial',{'kind':'anode','current_A':4.},attempt=1,allow_seed=True)
    payload=r['payload'];self.assertTrue(r['acceptance']['accepted']);self.assertGreater(r['invocation_resources']['process_cpu_seconds'],0)
    self.assertEqual(a.export()['ledger']['summary']['profit'],-8_000_000)
    with self.assertRaises(ValueError):run_paid(ROOT,a,'initial',{'kind':'anode','current_A':4.},attempt=1,allow_seed=True)
    bad=copy.deepcopy(payload);bad['payment']['status']='REJECTED'
    with self.assertRaises(ValueError):check(ROOT,m,jobs[0],bad,a.export()['ledger']['actions'])
    bad=copy.deepcopy(payload);bad['result']['request_sha256']='0'*64
    with self.assertRaises(ValueError):check(ROOT,m,jobs[0],bad,a.export()['ledger']['actions'])
    a.execute('wallet',{'buyer':'buyer','amount':200_000_000},0)
    a.execute('offer',{'id':'order','buyer':'buyer','price':100_000_000,'job_id':'initial','deadline':10},0)
    for event in ('consent','fund'):
     a.execute('event',{'id':'order','action':event,'event_id':'order-'+event},0)
    a.execute('event',{'id':'order','action':'prepare','event_id':'order-prepare','research_payload':payload},0)
    a.execute('event',{'id':'order','action':'release','event_id':'order-release'},1)
    self.assertTrue(a.audit()['accepted']);before=a.export()['ledger']['summary'];self.assertGreaterEqual(before['unrestrictedEarned'],8_000_000)
    r2=run_paid(ROOT,a,'fresh',{'kind':'anode','current_A':4.},day=1,allow_seed=False,expected_net=1)
    self.assertEqual(r2['payload']['payment']['funding'],'EARNED')
    self.assertEqual(before['cash']-a.export()['ledger']['summary']['cash'],8_000_000)
    with self.assertRaises(ValueError):check(ROOT,m,jobs[1],payload,a.export()['ledger']['actions'])
    self.assertTrue(a.audit()['accepted']);final=a.export()['ledger']['summary']
   finally:a.close()
   a=JournalAccount(ROOT,m,path,opening=500_000_000,working=1_000_000,contract='BATTERY_ENGINEERING_NOT_DEMAND_PROOF')
   try:self.assertEqual(a.export()['ledger']['summary'],final);self.assertTrue(a.audit()['accepted'])
   finally:a.close()
 def test_failed_prepaid_attempt_and_request_rename_refused(self):
  j=job('failure',298.15);m=manifest(ROOT,[j]);renamed=copy.deepcopy(j);renamed['id']='renamed'
  with self.assertRaisesRegex(ValueError,'UNIQUE_RESEARCH'):manifest(ROOT,[j,renamed])
  with tempfile.TemporaryDirectory(dir=ROOT,prefix='.battery-failure-') as tmp:
   a=JournalAccount(ROOT,m,Path(tmp)/'account.sqlite',opening=100_000_000,working=1_000_000,contract='FAILURE_COST_ENGINEERING')
   try:
    with self.assertRaises(ValueError) as failed:run_paid(ROOT,a,'failure',{'kind':'unknown'},allow_seed=True)
    self.assertEqual(failed.exception.research_resources['status'],'FAILED')
    self.assertTrue(list(Path(tmp).glob('*.research-resources-*.json')))
    self.assertEqual(a.export()['ledger']['summary']['profit'],-8_000_000)
    with self.assertRaisesRegex(ValueError,'ALREADY'):run_paid(ROOT,a,'failure',{'kind':'anode','current_A':4.},allow_seed=True)
    self.assertTrue(a.audit()['accepted'])
   finally:a.close()
 def test_constructor_is_after_native_payment_and_replayed(self):
  j=job('constructed',300.15);j['allowed_policy_kinds']=['envelope']
  j['construction']={'mode':'known_envelope','training_requests':[job('t1',298.15)['request'],job('t2',308.15)['request']],'oracle_current_A':4.,'safety_factor':.95}
  m=manifest(ROOT,[j])
  with tempfile.TemporaryDirectory(dir=ROOT,prefix='.battery-construct-') as tmp:
   a=JournalAccount(ROOT,m,Path(tmp)/'account.sqlite',opening=100_000_000,working=1_000_000,contract='PAID_KNOWN_CONSTRUCTION_NOT_INVENTION')
   try:
    r=run_paid(ROOT,a,j['id'],allow_seed=True)
    self.assertTrue(r['acceptance']['accepted']);self.assertEqual(r['payload']['result']['policy'],r['payload']['construction']['policy'])
    self.assertIn('construction_verification_resources',r['acceptance']['verification'])
    self.assertEqual(a.export()['ledger']['summary']['profit'],-8_000_000)
    bad=copy.deepcopy(r['payload']);bad['construction']['policy']['safety_factor']=.9
    with self.assertRaises(ValueError):check(ROOT,m,j,bad,a.export()['ledger']['actions'])
    self.assertTrue(a.audit()['accepted'])
   finally:a.close()
 def test_import_path_mismatch_before_payment(self):
  from unittest.mock import patch
  from battery_service import physics
  from connected_enterprise.research_service import sources
  with patch.object(physics,'__file__',str(ROOT/'unbound.py')):
   with self.assertRaisesRegex(ValueError,'IMPORTED_SOURCE'):sources(ROOT)
 def test_telemetry_never_writes_for_wrong_account_or_masks_failure(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory(dir=ROOT,prefix='.battery-telemetry-') as tmp:
   with self.assertRaisesRegex(ValueError,'CANONICAL'):run_paid(ROOT,SimpleNamespace(path=Path(tmp)/'forged'),'x')
   self.assertEqual(list(Path(tmp).iterdir()),[])
   m=manifest(ROOT,[job('t',298.15)])
   a=JournalAccount(ROOT,m,Path(tmp)/'account.sqlite',opening=100_000_000,working=1_000_000,contract='TELEMETRY_BOUNDARY')
   try:
    with patch('connected_enterprise.research_service._run_paid',side_effect=ValueError('ORIGINAL_EXECUTION_FAILURE')),patch('commercial.persistence.atomic_bytes',side_effect=OSError('RECEIPT_DISK_FAILURE')):
     with self.assertRaisesRegex(ValueError,'ORIGINAL_EXECUTION_FAILURE') as failed:run_paid(ROOT,a,'t')
    self.assertEqual(failed.exception.research_resources['non_authoritative_receipt_write_error'],'OSError')
    self.assertEqual(a.export()['ledger']['summary']['profit'],0)
   finally:a.close()
