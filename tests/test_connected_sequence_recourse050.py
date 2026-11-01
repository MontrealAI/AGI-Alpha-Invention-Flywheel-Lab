import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adaptive_enterprise.instruments import prepare_complete_offer_services,load_jobs
from connected_enterprise.engine import run_world,validate_config
from connected_enterprise.sequence_window import compare_window,future_recourse_envelope
from connected_enterprise.verify import audit

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('composed_recourse_fixture050',ROOT/'tests/test_connected_composed_window049.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class FutureRecourseEnvelopeTests(unittest.TestCase):
    def test_native_clock_excludes_prepaid_prefix_and_terminal_horizon(self):
        cfg={'horizon_days':14,'refusal_recourse_policy':{'schema':'connected-refusal-recourse/v1','daily_planning_cost':7}}
        for now,future,count,first,last in ((0,48,2,24,48),(23,71,2,24,48),(24,72,2,48,72),(24,24,0,None,None),(25,48,1,48,48),(311,359,1,312,312),(335,359,0,None,None),(336,360,0,None,None)):
            result=future_recourse_envelope(cfg,now,future)
            self.assertEqual((result['future_native_planning_events'],result['first_future_planning_hour'],result['last_future_planning_hour']),(count,first,last))
            self.assertEqual(result['mandatory_cost_microUSD'],count*7)
            self.assertEqual(result['total_cash_bound_microUSD'],count*7)

    def test_selective_minimum_and_optional_upper_bound_are_distinct(self):
        cfg={'horizon_days':20,'refusal_recourse_policy':{'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':11,'daily_evaluation_cost':3}}
        result=future_recourse_envelope(cfg,48,120)
        self.assertEqual(result['future_native_planning_events'],3)
        self.assertEqual(result['mandatory_cost_microUSD'],9)
        self.assertEqual(result['optional_allowance_cash_bound_microUSD'],33)
        self.assertEqual(result['total_cash_bound_microUSD'],42)

    def test_absent_policy_has_no_new_metadata_and_invalid_policy_is_not_free(self):
        self.assertIsNone(future_recourse_envelope({'horizon_days':14},0,48))
        for policy in ({'schema':'unknown','daily_planning_cost':1},{'schema':'connected-refusal-recourse/v1','daily_planning_cost':0},{'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':1,'daily_evaluation_cost':False}):
            with self.assertRaises(ValueError):future_recourse_envelope({'horizon_days':14,'refusal_recourse_policy':policy},0,48)

    def test_known_fees_close_the_entire_future_cash_window(self):
        for policy in ({'schema':'connected-refusal-recourse/v1','daily_planning_cost':750000000},{'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':1,'daily_evaluation_cost':750000000}):
            case=fixture.ComposedWindowForecasts();case.setUp()
            self.assertTrue(case.options())
            case.cfg['refusal_recourse_policy']=policy;validate_config(case.cfg)
            seen=[]
            def record(*args,**kwargs):
                result=compare_window(*args,**kwargs);seen.append(result);return result
            with patch('connected_enterprise.sequence_planning.compare_window',side_effect=record):
                self.assertEqual(case.options(),[])
            self.assertTrue(seen)
            for result in seen:
                envelope=result['future_recourse_cost']
                self.assertEqual(envelope['future_native_planning_events'],2)
                self.assertGreater(envelope['mandatory_cost_microUSD'],case.obs['summary']['available'])
                self.assertTrue(all(route['future_delivery_cash_limit']==0 for route in result['routes']))

    def test_shared_fixed_cost_is_not_multiplied_or_double_charged_to_increment(self):
        case=fixture.ComposedWindowForecasts();case.setUp();baseline=case.options()
        def economic(rows):
            return [{k:row[k] for k in ('id','kind','upfront_cost','future_net_cash','later_liabilities')} for row in rows]
        for policy in ({'schema':'connected-refusal-recourse/v1','daily_planning_cost':10},{'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':10,'daily_evaluation_cost':5}):
            case.cfg['refusal_recourse_policy']=policy;rows=case.options()
            self.assertEqual(economic(rows),economic(baseline))
            for option in rows:
                forecast=option['execution']['forecast']['forecast'];envelope=forecast['future_recourse_cost']
                expected=20 if policy['schema'].endswith('/v1') else 30
                self.assertEqual(envelope['total_cash_bound_microUSD'],expected)
                self.assertTrue(all(route['future_recourse_cash_bound_microUSD']==expected for route in forecast['routes']))


class NativeSequenceRecourseCompatibility(unittest.TestCase):
    def test_prepaid_v1_and_selective_v2_audit_resume_and_reject_forecast_tampering(self):
        with tempfile.TemporaryDirectory(prefix='.sequence-recourse050-',dir=ROOT) as temporary:
            folder=Path(temporary)
            manifest=prepare_complete_offer_services(ROOT,str(folder.relative_to(ROOT)/'services'),cohort_seed=261101051,packet_jobs=8,packet_rows=12)
            for name,policy in (('v1',{'schema':'connected-refusal-recourse/v1','daily_planning_cost':10000}),('v2',{'schema':'connected-selective-refusal-recourse/v2','daily_planning_cost':10000,'daily_evaluation_cost':5000})):
                # New053 regression control: explicit six-place admission and
                # disjoint owned/prospect requests. The old shared-work study
                # factory remains unchanged and no longer certifies these
                # impossible five-day future prospects.
                cfg=fixture.admitted_control(manifest,load_jobs(ROOT,manifest),maximum=6)
                for profile in cfg['complete_offer_policy']['profiles']:
                    for atom in profile['atoms']:
                        atom['values']={s:150000000 if s=='receivables_packet' else 45000000 for s in profile['services']}
                cfg['horizon_days']=5;cfg['refusal_recourse_policy']=policy
                path=folder/name
                paused=run_world(ROOT,manifest,cfg,261101051,'competitive_growth',path,stop_after_events=2)
                self.assertFalse(paused['complete'])
                result=run_world(ROOT,manifest,cfg,261101051,'competitive_growth',path)
                self.assertTrue(audit(ROOT,manifest,result)['accepted'])
                resumed=run_world(ROOT,manifest,cfg,261101051,'competitive_growth',path)
                self.assertEqual(result['owned_account'],resumed['owned_account'])
                if name=='v1':
                    self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='prepaid_finite_refusal_recourse'),50000)
                else:
                    self.assertEqual(sum(c['amount'] for c in result['costs'] if c['category']=='selective_recourse_public_evaluation'),25000)
                    self.assertFalse(any(c['category']=='prepaid_finite_refusal_recourse' for c in result['costs']))
                forecasts=[o for w in result['joint_actions'].values() for o in w['allocation']['investments'] if 'forecast' in o.get('execution',{}) and 'future_recourse_cost' in o['execution']['forecast'].get('forecast',{})]
                self.assertTrue(forecasts)
                altered=copy.deepcopy(result)
                target=next(o for w in altered['joint_actions'].values() for o in w['allocation']['investments'] if 'forecast' in o.get('execution',{}) and 'future_recourse_cost' in o['execution']['forecast'].get('forecast',{}))
                target['execution']['forecast']['forecast']['future_recourse_cost']['total_cash_bound_microUSD']+=1
                with self.assertRaises(ValueError):audit(ROOT,manifest,altered)


if __name__=='__main__':
    unittest.main()
