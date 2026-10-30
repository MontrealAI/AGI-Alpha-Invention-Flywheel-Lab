import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from adaptive_enterprise.checkers import audit_delivery
from adaptive_enterprise.instruments import (SOURCE_PATHS,apply_source_extension,canonical,cents,compare_methods,digest,
    execute_job,execute_offer,execute_plan,infer_plan,load_jobs,prepare_services,produce,retain_failure,synthetic_raw)
from adaptive_enterprise.strategies import offer_catalog
from adaptive_enterprise.strategies import adjudicate_and_adapt

ROOT=Path(__file__).resolve().parents[1]


class AdaptiveInstrumentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='adaptive012-instruments-');cls.root=Path(cls.temp.name)
        for name in SOURCE_PATHS:
            target=cls.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
        cls.manifest=prepare_services(cls.root,'packets')

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_actual_fresh_artifacts_and_separate_scoped_readiness(self):
        self.assertEqual(len(self.manifest['jobs']),104)
        self.assertEqual(len(load_jobs(self.root,self.manifest)),104)
        artifacts=[json.loads((self.root/job['artifact']).read_text()) for job in self.manifest['jobs']]
        self.assertEqual(sum(a['outcome_scope']=='intake_readiness' for a in artifacts),3)
        self.assertEqual(sum(a['method']=='canonical' for a in artifacts),72)
        self.assertEqual(sum(a['method']=='generated_schema' for a in artifacts),21)
        self.assertEqual(sum(a['method']=='operations_bundle' for a in artifacts),8)
        self.assertEqual(len({key for job in self.manifest['jobs'] for key in job['work_keys']}),96)
        self.assertTrue(all(job['accepted'] for job in self.manifest['jobs']))

    def test_fresh_field_names_generate_new_executable_mapping(self):
        for index in [11,18,101,202]:
            raw=synthetic_raw('reconciliation',index);plan=infer_plan(raw)
            self.assertEqual(plan['status'],'READY')
            self.assertEqual(plan['mapping']['invoices']['id'],f'field_{index}_a')
            self.assertGreater(plan['search']['candidates_tested'],1)
            normalized=execute_plan(raw,plan)
            self.assertEqual(len(normalized['invoices']),len(raw['tables']['invoices']))
            self.assertTrue(audit_delivery('reconciliation',raw,produce(raw))['accepted'])

    def test_registered_fresh_cohort_changes_actual_sources_and_mappings(self):
        ordinary=synthetic_raw('reconciliation',9)
        first=synthetic_raw('reconciliation',9,cohort_seed=12001201)
        again=synthetic_raw('reconciliation',9,cohort_seed=12001201)
        alternate=synthetic_raw('reconciliation',9,cohort_seed=12001202)
        self.assertEqual(first,again);self.assertNotEqual(first,ordinary);self.assertNotEqual(first,alternate)
        self.assertNotEqual(set(first['tables']['invoices'][0]),set(ordinary['tables']['invoices'][0]))
        self.assertNotEqual(infer_plan(first)['mapping'],infer_plan(alternate)['mapping'])
        for raw in [first,alternate]:
            self.assertTrue(audit_delivery('reconciliation',raw,produce(raw))['accepted'])
        self.assertTrue(audit_delivery('reconciliation',synthetic_raw('reconciliation',0,12001201),produce(synthetic_raw('reconciliation',0,12001201),'canonical'))['accepted'])

    def test_canonical_work_remains_available_before_investment(self):
        for index in range(8):
            raw=synthetic_raw('reconciliation',index)
            artifact=produce(raw,'canonical')
            self.assertTrue(audit_delivery('reconciliation',raw,artifact)['accepted'])
        with self.assertRaises(ValueError):produce(synthetic_raw('reconciliation',9),'canonical')

    def test_exact_unit_conversion_and_no_float_money(self):
        self.assertEqual(cents('10.01','USD'),1001)
        self.assertEqual(cents('1001','cents'),1001)
        for value,unit in [(10.01,'USD'),('1.001','USD'),(True,'cents'),('NaN','USD'),('4','UNKNOWN'),(-1,'cents')]:
            with self.subTest(value=value,unit=unit),self.assertRaises(ValueError):cents(value,unit)

    def test_missing_units_are_not_inferred(self):
        raw=synthetic_raw('reconciliation',15);plan=infer_plan(raw)
        self.assertEqual(plan['status'],'BLOCKED');self.assertIsNone(plan['mapping'])
        with self.assertRaises(ValueError):produce(raw,'generated_schema')
        staged=produce(raw,'staged_readiness')
        self.assertFalse(staged['useful_outcome']['production_ready'])
        self.assertTrue(audit_delivery('reconciliation',raw,staged)['accepted'])
        staged['outcome_scope']='complete_outcome'
        self.assertFalse(audit_delivery('reconciliation',raw,staged)['accepted'])

    def test_new_customer_evidence_is_required_before_extension(self):
        raw=synthetic_raw('reconciliation',15)
        facts={'source_id':'synthetic-customer-unit-document-15','origin':'SIMULATED_CUSTOMER_SUPPLIED','prior_source_sha256':digest(raw),
               'units':{'invoices':{'field_15_c':'USD'},'payments':{'field_15_c':'USD'}}}
        extended,receipt=apply_source_extension(raw,facts)
        self.assertEqual(raw['units'],{'invoices':{},'payments':{}})
        self.assertNotEqual(receipt['prior_source_sha256'],receipt['new_source_sha256'])
        self.assertTrue(audit_delivery('reconciliation',extended,produce(extended))['accepted'])
        facts['origin']='SELLER_GUESSED'
        with self.assertRaises(ValueError):apply_source_extension(raw,facts)

    def test_retained_constraints_change_search_on_fresh_source(self):
        failed=synthetic_raw('reconciliation',15)
        original=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='canonical')
        failure=adjudicate_and_adapt(failed,original,produce(failed,'staged_readiness'))['adjudication']
        memory=retain_failure(failed,failure)
        raw=synthetic_raw('reconciliation',18)
        comparison=compare_methods(raw,memory)
        methods=comparison['methods']
        self.assertTrue(all(item['accepted'] for item in methods.values()))
        self.assertEqual(len({item['useful_outcome_sha256'] for item in methods.values()}),1)
        self.assertEqual(methods['retained']['plan']['search']['retained_constraints_used'],memory['constraints'])
        self.assertEqual(methods['retained']['mapping_stage_row_visits'],methods['ordinary_reuse']['mapping_stage_row_visits'])
        self.assertLess(methods['retained']['plan']['search']['candidates_tested'],methods['generated']['plan']['search']['candidates_tested'])
        self.assertIn('no superiority',comparison['conclusion'])

    def test_fabricated_memory_and_failure_rejected(self):
        raw=synthetic_raw('reconciliation',18)
        with self.assertRaises(ValueError):retain_failure(raw,{'accepted':True})
        with self.assertRaises(ValueError):retain_failure(raw,{'accepted':False,'input_content_sha256':digest(raw),'errors':['self-asserted']})
        with self.assertRaises(ValueError):infer_plan(raw,{'schema':'adaptive012/retained-constraints/v1','constraints':['skip_checker']})

    def test_ambiguous_structural_identity_blocks_full_production(self):
        raw=synthetic_raw('reconciliation',9)
        raw['tables']['invoices']=[{'a':'I1','b':'I1','c':100}]
        raw['tables']['payments']=[{'x':'P1','y':'I1','z':100}]
        raw['units']={'invoices':{'c':'cents'},'payments':{'z':'cents'}}
        plan=infer_plan(raw)
        self.assertEqual(plan['status'],'BLOCKED')
        self.assertEqual(plan['failure'],'AMBIGUOUS_MAPPING')

    def test_actual_offer_method_controls_production_applicability(self):
        job=next(j for j in self.manifest['jobs'] if j['id']=='adaptive012-reconciliation-009')
        canonical_offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='canonical')
        generated_offer=next(o for o in offer_catalog() if o['service_id']=='reconciliation' and o['method']=='generated_schema')
        self.assertFalse(execute_offer(self.root,self.manifest,canonical_offer,job['id'])['accepted'])
        checked=execute_offer(self.root,self.manifest,generated_offer,job['id'])
        self.assertTrue(checked['accepted']);self.assertEqual(checked['artifact_sha256'],job['artifact_sha256'])
        self.assertEqual(checked['native_delivered_artifact_sha256'],job['artifact_sha256'])
        self.assertIn('byte identity is not claimed',checked['execution_binding'])

    def test_all_service_outputs_reexecute_without_model_calls(self):
        for service in ['reconciliation','kpi_variance','evidence_matrix','operations_bundle']:
            job=next(j for j in self.manifest['jobs'] if j['service_id']==service)
            receipt=execute_job(self.root,job)
            self.assertTrue(receipt['accepted']);self.assertTrue(receipt['reexecuted']);self.assertEqual(receipt['model_calls'],0)

    def test_scope_source_hash_duplicate_and_unknown_fields_fail(self):
        for kind in ['scope','hash','duplicate','unknown']:
            manifest=copy.deepcopy(self.manifest)
            if kind=='scope':manifest['scope']='OBSERVED'
            elif kind=='hash':manifest['jobs'][0]['artifact_sha256']='0'*64
            elif kind=='duplicate':manifest['jobs'].append(copy.deepcopy(manifest['jobs'][0]))
            else:manifest['free_success']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):load_jobs(self.root,manifest)

    def test_output_overwrite_and_traversal_refused(self):
        for target in ['packets','../escape','/tmp/escape']:
            with self.subTest(target=target),self.assertRaises(ValueError):prepare_services(self.root,target)


if __name__=='__main__':unittest.main()
