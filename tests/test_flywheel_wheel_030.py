"""Purpose-bound negative controls for presentation of the existing native enterprise."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock
from xml.etree import ElementTree
from flywheel_wheel.readout import EvidenceError, SCHEMA, canonical, empty_snapshot, sha, snapshot_from_rederived, strict_json, live_readout
from flywheel_wheel.render import render_svg, render_html
from flywheel_wheel.__main__ import main, publish

H='a'*64
F='b'*64

def fixtures():
    report={'schema':'agi-alpha/connected014-report/v1','scope':'CONDITIONAL_SIMULATION',
            'source_sha256':H,'frozen_sha256':F,'worlds':2,'all_independent_audits_passed':True,
            'actual_commerce':{'customers':0,'collections':0,'profit':None},
            'outcomes':{'operating_implementation':'EXECUTED_WITH_INDEPENDENT_FINANCIAL_AND_OPERATING_SEMANTIC_AUDIT',
                        'commercial_result':'CONDITIONAL_SUCCESS',
                        'growth_result':'CONDITIONAL_INCREASE_IN_PROFITABLE_DELIVERY','billion_native_scale':'NOT_ESTABLISHED'}}
    audit={'schema':'agi-alpha/connected014-package-audit/v1',
           'scope':'NATIVE_FINANCE_AND_OPERATING_SEMANTICS_WITH_ARTIFACT_REEXECUTION_AND_REPORT_REDERIVATION',
           'accepted':True,'source_sha256':H,'worlds':2}
    businesses=[]
    for i,profit in enumerate((2000000,-1000000)):
        businesses.append({'business_reference':f'case-{i}','complete':True,'scope':'CONDITIONAL_SIMULATION',
                            'verification':{'stored_audit_accepted':True},
                            'actual_external_commerce':{'customers':0,'collections_microUSD':0,'profit_microUSD':None},
                            'financial_state_microUSD':{'profit':profit,'cash':9000000+i*1000000},
                            'trailing_twelve_month_profit_microUSD':None,
                            'recorded_counts':{'offers':2,'accepted_orders':2,'settled_orders':i}})
    board={'schema':'agi-alpha/connected-scoreboard/v1','scope':'RECORDED_CONDITIONAL_SIMULATION',
           'source_sha256':H,'frozen_sha256':F,'report_sha256':sha(report),
           'world_count':2,'target_status':'NOT_ESTABLISHED_BY_THIS_SCOREBOARD','businesses':businesses}
    return audit,report,board

class WheelTests(unittest.TestCase):
    def test_circular_architecture_has_three_concentric_ring_groups_and_accessible_svg(self):
        s=render_svg(empty_snapshot());t=ElementTree.fromstring(s)
        self.assertEqual(t.attrib['viewBox'],'0 0 2100 1300')
        self.assertIn('TRANSFORMATIONAL',s)
        self.assertIn('COMMERCE',s)
        self.assertIn('PRODUCTION',s)
        self.assertIn('ARCHITECTURE ONLY',s)
        self.assertGreater(s.count(' A '),8)
    def test_all_phases_are_unknown_without_evidence(self):
        r=empty_snapshot();self.assertFalse(r['funding_authority']);self.assertIsNone(r['real_customers'])
        self.assertEqual(sum(len(v) for v in r['rings'].values()),12)
        self.assertTrue(all(x=='NOT_EVIDENCED' for ring in r['rings'].values() for x in ring.values()))
    def test_report_and_output_do_not_claim_real_commerce(self):
        r=snapshot_from_rederived(*fixtures());self.assertEqual(r['real_customers'],0)
        self.assertEqual(r['invention_claim'],'NOT_ESTABLISHED_BY_NATIVE_COMMERCIAL_AUDIT')
        self.assertEqual(r['productive_claim'],'NOT_ESTABLISHED_BY_NATIVE_COMMERCIAL_AUDIT')
        self.assertFalse(r['funding_authority'])
        self.assertEqual(r['worlds'][0]['modeled_profit_microUSD'],2000000)
        self.assertEqual(r['worlds'][1]['modeled_profit_microUSD'],-1000000)
        self.assertNotIn('available_to_invest',r)
        self.assertIn('SIMULATED BUSINESSES',render_svg(r))
    def test_no_collections_means_no_collect_or_reinvest_claim(self):
        a,r,b=fixtures()
        for x in b['businesses']:
            x['recorded_counts']['settled_orders']=0
        s=snapshot_from_rederived(a,r,b)
        self.assertEqual(s['rings']['commerce']['Collect'],'NO_VERIFIED_SETTLED_ORDERS')
        self.assertEqual(s['rings']['commerce']['Reinvest'],'NOT_ESTABLISHED_IN_THIS_COHORT')
    def test_no_observed_deliveries_means_no_deliver_claim(self):
        a,r,b=fixtures()
        for x in b['businesses']:
            x['recorded_counts']['accepted_orders']=0
        self.assertEqual(snapshot_from_rederived(a,r,b)['rings']['commerce']['Deliver'],'NO_VERIFIED_ACCEPTED_DELIVERIES')
    def test_html_accessibility_and_no_active_controls(self):
        html=render_html(snapshot_from_rederived(*fixtures()))
        self.assertIn('role="img"',html)
        self.assertIn('individually, never pooled',html)
        self.assertIn('No execution, collection, investment, release or authority',html)
        self.assertNotIn('<script',html)
        self.assertNotIn('<button',html)
    def test_reject_falsified_canonical_audit(self):
        a,r,b=fixtures();a['accepted']=False
        with self.assertRaisesRegex(EvidenceError,'CANONICAL_ACCEPTED'):snapshot_from_rederived(a,r,b)
    def test_reject_fake_audit_scope(self):
        a,r,b=fixtures();a['scope']='stored receipt only'
        with self.assertRaisesRegex(EvidenceError,'CANONICAL_ACCEPTED'):snapshot_from_rederived(a,r,b)
    def test_reject_source_mismatch(self):
        a,r,b=fixtures();b['source_sha256']='f'*64
        with self.assertRaisesRegex(EvidenceError,'MISMATCHED_SOURCE'):snapshot_from_rederived(a,r,b)
    def test_reject_freeze_mismatch(self):
        a,r,b=fixtures();b['frozen_sha256']='c'*64
        with self.assertRaisesRegex(EvidenceError,'MISMATCHED_FREEZE'):snapshot_from_rederived(a,r,b)
    def test_reject_missing_one_world(self):
        a,r,b=fixtures();b['businesses'].pop()
        with self.assertRaisesRegex(EvidenceError,'WORLD_BUSINESS_COUNT'):snapshot_from_rederived(a,r,b)
    def test_reject_duplicate_worlds(self):
        a,r,b=fixtures();b['businesses'][1]['business_reference']='case-0'
        with self.assertRaisesRegex(EvidenceError,'DUPLICATED_BUSINESS'):snapshot_from_rederived(a,r,b)
    def test_reject_relabelled_actual_customers(self):
        a,r,b=fixtures();b['businesses'][1]['actual_external_commerce']['customers']=2
        with self.assertRaisesRegex(EvidenceError,'UNSUPPORTED_REAL_COMMERCE'):snapshot_from_rederived(a,r,b)
    def test_reject_booked_real_profit(self):
        a,r,b=fixtures();r['actual_commerce']['profit']=1000000;b['report_sha256']=sha(r)
        with self.assertRaisesRegex(EvidenceError,'NON_SIMULATED_CLAIM'):snapshot_from_rederived(a,r,b)
    def test_reject_annualization_short_horizon(self):
        a,r,b=fixtures();b['businesses'][0]['trailing_twelve_month_profit_microUSD']=1234
        with self.assertRaisesRegex(EvidenceError,'SHORT_HORIZON'):snapshot_from_rederived(a,r,b)
    def test_reject_unqualified_invention_or_scale(self):
        a,r,b=fixtures();r['outcomes']['billion_native_scale']='ESTABLISHED';b['report_sha256']=sha(r)
        with self.assertRaisesRegex(EvidenceError,'SCALE_CLAIM'):snapshot_from_rederived(a,r,b)
    def test_reject_bad_operating_claim(self):
        a,r,b=fixtures();r['outcomes']['operating_implementation']='DOCUMENT_ONLY';b['report_sha256']=sha(r)
        with self.assertRaisesRegex(EvidenceError,'OPERATING_CLAIM'):snapshot_from_rederived(a,r,b)
    def test_reject_stale_stored_business_audit(self):
        a,r,b=fixtures();b['businesses'][0]['verification']['stored_audit_accepted']=False
        with self.assertRaisesRegex(EvidenceError,'STORED_BUSINESS_AUDIT'):snapshot_from_rederived(a,r,b)
    def test_reject_non_integer_account_profit(self):
        a,r,b=fixtures();b['businesses'][1]['financial_state_microUSD']['profit']=1.0
        with self.assertRaisesRegex(EvidenceError,'INTEGER_NATIVE_FINANCIAL'):snapshot_from_rederived(a,r,b)
    def test_refuse_a_wheel_conferring_financial_authority(self):
        r=empty_snapshot();r['funding_authority']=True
        with self.assertRaisesRegex(EvidenceError,'READ_ONLY_WHEEL'):render_svg(r)
    def test_reject_duplicate_json_and_nonfinite(self):
        with self.assertRaisesRegex(EvidenceError,'DUPLICATE'):strict_json('{"a":1,"a":2}')
        with self.assertRaisesRegex(EvidenceError,'NONFINITE'):strict_json('{"a":NaN}')
    def test_architecture_publishes_three_create_only_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            name=Path(d)/'wheel'
            self.assertEqual(main(['architecture','--output',str(name)]),0)
            self.assertEqual({p.name for p in name.iterdir()},{'index.html','wheel.svg','snapshot.json'})
            self.assertEqual(json.loads((name/'snapshot.json').read_text())['scope'],'ARCHITECTURE_ONLY_NO_ENTERPRISE_INPUT')
            self.assertEqual(main(['architecture','--output',str(name)]),2)
    def test_reject_output_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            here=Path(d);(here/'real').mkdir();(here/'alias').symlink_to(here/'real')
            with self.assertRaisesRegex(EvidenceError,'FRESH_NORMAL_OUTPUT'):publish(empty_snapshot(),here/'alias'/'sub')
    def test_mocked_canonical_invocation_is_not_a_real_validation(self):
        a,r,b=fixtures()
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);(path/'source'/'connected_enterprise').mkdir(parents=True)
            (path/'source'/'connected_enterprise'/'runner.py').write_text('pass')
            for n in ('FROZEN.json','REPORT.json','COMPLETE.json'): (path/n).write_text('{}')
            (path/'REPORT.json').write_bytes(canonical(r))
            with mock.patch('flywheel_wheel.readout._invoke',side_effect=[a,b]) as invoke:
                s=live_readout(path,timeout=7)
                self.assertEqual(s['worlds'][0]['id'],'case-0')
                self.assertEqual(invoke.call_count,2)
                self.assertEqual(invoke.call_args_list[0].args[0][3],'audit')
                self.assertEqual(invoke.call_args_list[1].args[0][3],'scoreboard')
    def test_no_fabricated_report_from_a_partial_enterprise(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'source').mkdir()
            with self.assertRaisesRegex(EvidenceError,'COMPLETE_ENTERPRISE_INPUT'):live_readout(d)
    def test_enforced_timeout_limit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);(path/'source'/'connected_enterprise').mkdir(parents=True)
            (path/'source'/'connected_enterprise'/'runner.py').write_text('pass')
            for n in ('FROZEN.json','REPORT.json','COMPLETE.json'):(path/n).write_text('{}')
            with self.assertRaisesRegex(EvidenceError,'FINITE_AUDIT_TIMEOUT'):live_readout(path,timeout=901)

if __name__=='__main__': unittest.main()
