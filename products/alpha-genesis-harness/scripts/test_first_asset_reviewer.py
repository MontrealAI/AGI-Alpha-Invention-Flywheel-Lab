"""Independent arithmetic and adversarial refusal for the first Ω ALPHA asset audit."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import types

MODULE=Path(__file__).with_name('first_asset_reviewer.py')
spec=importlib.util.spec_from_file_location('first_asset_reviewer', MODULE)
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class OracleTests(unittest.TestCase):
    def test_window_exhaustive_and_boundary(self):
        row={f'c{i}':v for i,v in enumerate((500,500,20,30,20,30))}
        row.update(ready=0, until=6)
        self.assertEqual(review.oracle_window(row), {'start':2, 'total':50})
        row.update(ready=4,until=6)
        self.assertEqual(review.oracle_window(row),{'start':4,'total':50})
        row.update(ready=0,until=1)
        self.assertEqual(review.oracle_window(row),{'start':-1,'total':-1})
        with self.assertRaisesRegex(ValueError,'INVALID_WINDOW_INTERVAL'):
            review.oracle_window({**row,'ready':-2})

    def test_quote_ties_and_absence(self):
        row={'cad':80,'usd':80,'eur':-1,'gbp':-1,'usd_rate':10000,'eur_rate':20000,'gbp_rate':20000}
        self.assertEqual(review.oracle_quote(row),{'currency':'CAD','scaled_cad':800000})
        row['cad']=-1
        self.assertEqual(review.oracle_quote(row),{'currency':'USD','scaled_cad':800000})
        row['usd']=-1
        self.assertEqual(review.oracle_quote(row),{'currency':'NONE','scaled_cad':-1})
        row['usd']=1
        row['usd_rate']=-1
        with self.assertRaisesRegex(ValueError,'NEGATIVE_EXCHANGE_FACTOR'):
            review.oracle_quote(row)

    def test_catalogue_equality_and_ambiguity(self):
        f=lambda mag,error,reviewed: {'m':mag,'error':error,'floor':6000,'reviewed':reviewed}
        self.assertEqual(review.oracle_catalogue(f(6100,100,True)),{'status':'include'})
        self.assertEqual(review.oracle_catalogue(f(5800,100,True)),{'status':'exclude'})
        self.assertEqual(review.oracle_catalogue(f(6000,100,True)),{'status':'defer'})
        self.assertEqual(review.oracle_catalogue(f(6100,100,False)),{'status':'defer'})
        self.assertEqual(review.oracle_catalogue(f(6100,-1,True)),{'status':'defer'})
        with self.assertRaisesRegex(ValueError,'REVIEWED_BOOLEAN_REQUIRED'):
            review.oracle_catalogue(f(6100,100,1))

    def test_strict_structural_comparison(self):
        self.assertFalse(review.exact_equal({'x':True},{'x':1}))
        self.assertTrue(review.exact_equal({'x':[1,{'b':'c'}]},{'x':[1,{'b':'c'}]}))
        self.assertFalse(review.exact_equal({'x':[1]},{'x':[1.0]}))

    def test_conditional_proxy_never_claims_actual_emissions_or_money(self):
        row={f'c{i}':v for i,v in enumerate((100,100,20,20,10,10))}
        row.update(ready=0,until=6)
        result=review.window_proxy([{'input':row}])
        self.assertEqual(result['counterfactual_total_gco2_per_notional_kwh'],'90')
        self.assertIn('No workload was scheduled',result['not_observed'])

    def test_source_cohort_preserves_registered_order_and_binds_expected_inputs(self):
        from datetime import datetime, timedelta, timezone
        start=datetime(2026,11,14,tzinfo=timezone.utc)
        intervals=[]
        for i in range(84):
            t=start+timedelta(minutes=30*i)
            intervals.append({'from':t.isoformat(),'to':(t+timedelta(minutes=30)).isoformat(),
                              'intensity':{'actual':(i//6)*9+(i%6)*11}})
        records={'electricity':{'snapshot':{'body':json.dumps({'data':intervals})}}}
        rows=review.source_cohort(records,'window')
        self.assertEqual(len(rows),14)
        self.assertEqual(rows[0]['c0'],0)
        self.assertEqual(rows[13]['c5'],13*9+55)
        self.assertEqual(rows[13]['ready'],13%3)

        quotes=[]
        for i in range(8):
            quotes.append({'FXUSDCAD':{'v':'1.42231'},'FXEURCAD':{'v':'1.59221'},
                           'FXGBPCAD':{'v':'1.81117'}})
        records['exchange-rates']={'snapshot':{'body':json.dumps({'observations':quotes})}}
        rate_rows=review.source_cohort(records,'quote')
        self.assertEqual(rate_rows[0]['usd_rate'],14223)
        self.assertEqual(len(rate_rows),8)

        events=[{'properties':{'mag':6+i/10,'magError':.1,'status':'reviewed'}} for i in range(8)]
        records['seismic-archive']={'snapshot':{'body':json.dumps({'features':events})}}
        self.assertEqual(len(review.source_cohort(records,'catalogue')),8)

    def test_full_independent_replay_and_sealed_input_mutation(self):
        from datetime import datetime,timedelta,timezone
        source=[]
        start=datetime(2026,11,14,tzinfo=timezone.utc)
        for i in range(84):
            t=start+timedelta(minutes=30*i)
            source.append({'from':t.isoformat(),'to':(t+timedelta(minutes=30)).isoformat(),
                          'intensity':{'actual':(i//6)*14+((5-i%6)%6)*13}})
        payload=json.dumps({'data':source})
        sources={'electricity':{'label':'Actual public archive candidate','url':'https://example.org/data',
                 'snapshot':{'body':payload,'sha256':hashlib.sha256(payload.encode()).hexdigest()}}}
        cases=review.source_cohort(sources,'window')
        canonical=lambda obj: json.dumps(obj,sort_keys=True,separators=(',',':'))
        fake_digest=lambda obj: hashlib.sha256(canonical(obj).encode()).hexdigest()
        bridge=types.ModuleType('bridge')
        workflow=types.ModuleType('bridge.workflows')
        instruments=types.ModuleType('bridge.instruments')
        workflow.digest=fake_digest
        instruments.evaluate=lambda a, row, max_ops: {'output':review.oracle_window(row)}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            spec={'economic_mission':{'sources':sources}}
            asset='{"type":"declarative"}\n'
            register={'spec_sha256':fake_digest(spec),'successor_sha256':'example-hash'}
            result={'status':'complete','choice':{'contract':'window'},
                    'verification':{'passed':True},
                    'spec_sha256':register['spec_sha256'],
                    'successor_sha256':register['successor_sha256'],
                    'frozen':{'sha256':hashlib.sha256(asset.encode()).hexdigest()}}
            for k, v in [('qualification_comparison',cases[3:-2] + review.boundary_inputs('window', cases[0])),('fresh_transfer',cases[-2:])]:
                result[k]={'cases':[{'input':x,'expected':review.oracle_window(x)} for x in v]}
            objects={'SOURCES.json':sources,'MISSION.json':spec,
                     'REGISTRATION.json':register,'RESULT.json':result,
                     'ARCHIVE.json':{'state':{'spec':{'max_operations':100}},'files':{'asset.json':asset}}}
            for name,obj in objects.items(): (root/name).write_text(json.dumps(obj))
            (root/'asset.json').write_text(asset)
            with patch.dict(sys.modules,{'bridge':bridge,'bridge.workflows':workflow,
                                         'bridge.instruments':instruments}):
                result_qualified=review.audit(root)
                self.assertEqual(result_qualified['status'],'VERIFIED_BOUNDED_ARITHMETIC_ASSET')
                self.assertEqual(result_qualified['economic_usefulness'],
                                 'NOT_ESTABLISHED_WITHOUT_REAL_WORKFLOW_AND_COMPLETE_COST')
                self.assertTrue(result_qualified['fresh_transfer']['passed'] if 'fresh_transfer' in result_qualified else result_qualified['independent_execution']['fresh_transfer']['passed'])
                objects['RESULT.json']['qualification_comparison']['cases'][0]['input']['c0']+=1
                (root/'RESULT.json').write_text(json.dumps(objects['RESULT.json']))
                with self.assertRaisesRegex(ValueError,'SOURCE_COHORT_INPUT_MUTATED_OR_REORDERED'):
                    review.audit(root)

    def test_public_bytes_tampering_detected(self):
        raw='{"data":[42]}'
        src={'s':{'label':'example','url':'https://example.org/retrospective',
                  'snapshot':{'body':raw,'sha256':hashlib.sha256(raw.encode()).hexdigest()}}}
        self.assertEqual(len(review.audit_sources(src)),1)
        src['s']['snapshot']['body']=raw+' '
        with self.assertRaisesRegex(ValueError,'SOURCE_SHA256_MISMATCH'):
            review.audit_sources(src)
        src['s']['snapshot']['body']=raw
        src['s']['url']='http://example.org/data'
        with self.assertRaisesRegex(ValueError,'INVALID_PRIMARY_SOURCE_URL'):
            review.audit_sources(src)

    def test_noncompleted_mission_has_no_asset_claim(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            payload='{"data":[42]}'
            sources={'s':{'label':'x','url':'https://example.com/s','snapshot':{
                 'body':payload,'sha256':hashlib.sha256(payload.encode()).hexdigest()}}}
            (root/'SOURCES.json').write_text(json.dumps(sources))
            (root/'RESULT.json').write_text(json.dumps({'status':'needs_review'}))
            result=review.audit(root)
            self.assertEqual(result['status'],'NO_QUALIFIED_ARTIFACT')
            self.assertFalse(result['collected_money_verified'])

if __name__=='__main__':unittest.main()
