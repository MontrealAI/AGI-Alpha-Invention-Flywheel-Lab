"""Executable independent-check tests; all cases use invented synthetic data."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from continuity_omega.demo import case_for
from continuity_omega.engine import construct,DrillRejected,digest
from continuity_omega.checker import audit

ROOT=Path(__file__).resolve().parents[1]

class ContinuityTests(unittest.TestCase):
    def test_positive_independent_replay(self):
        inp=case_for();handoff,passport=construct(inp)
        out=audit(inp,handoff,passport)
        self.assertEqual(out['verdict'],'PASS_SYNTHETIC_ONLY')
        self.assertEqual((out['replayed_orders'],out['replayed_units']),(2,1900))
        self.assertEqual(passport['economics']['modeled_contribution'],650)
        self.assertEqual(handoff['supplier_available_units_in_window'],2100)
        self.assertFalse(passport['evidence_boundary']['real_customer_acceptance'])

    def test_checker_requires_actual_lowercase_sha256_specification_digest(self):
        c=case_for();h,p=construct(c)
        c['source_events'][0]['spec_sha256']='x'*64  # correct length, never hex
        c['source_seal']=digest(c['source_events'])  # forged source seal
        h['source_events_sha256']=c['source_seal']
        h['orders'][0]['spec_sha256']='x'*64
        h['idempotency_key']=digest([c['exercise_id'],c['source_seal'],h['supplier_id'],h['required_units']])
        p['source_events_sha256']=c['source_seal']
        p['handoff_sha256']=digest(h)
        result=audit(c,h,p)
        self.assertEqual(result['verdict'],'FAIL')
        self.assertIn('SPEC_PROVENANCE_MISSING',result['failures'])

    def test_checker_preserves_required_original_business_promise(self):
        c=case_for();h,p=construct(c)
        c['objective']['no_lost_orders']=False
        r=audit(c,h,p)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertIn('OUTCOME_CHARTER_RELAXED',r['failures'])

    def test_checker_does_not_accept_wrong_source_schema(self):
        c=case_for();h,p=construct(c)
        c['schema']='continuity-omega/unspecified'
        r=audit(c,h,p)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertIn('INPUT_SCHEMA',r['failures'])

    def test_checker_detects_duplicate_supplier_identity(self):
        c=case_for();h,p=construct(c)
        c['suppliers'][1]['supplier_id']=c['suppliers'][0]['supplier_id']
        r=audit(c,h,p)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertIn('DUPLICATE_SUPPLIER_IDENTITY',r['failures'])

    def test_source_changes_do_not_silently_pass(self):
        c=case_for('tampered_source')
        with self.assertRaisesRegex(DrillRejected,'seal'):construct(c)

    def test_deleted_or_fabricated_restored_orders_are_reported_not_trusted(self):
        for scenario,expected in [('missing_from_restored','MISSING_FROM_RESTORED_SNAPSHOT'),
                                  ('extra_restored','UNSUPPORTED_RESTORED_ORDER')]:
            with self.subTest(scenario=scenario):
                c=case_for(scenario);h,p=construct(c)
                self.assertIn(expected,[v['issue'] for v in p['restoration_findings']])
                self.assertEqual(audit(c,h,p)['verdict'],'PASS_SYNTHETIC_ONLY')

    def test_negative_frozen_scenarios_decline(self):
        for scenario in ['overbooked','correlated_outage','unqualified','late','buyer_declines',
                         'uneconomic','unapproved_sharing','no_order_source']:
            with self.subTest(case=scenario):
                with self.assertRaises(DrillRejected):construct(case_for(scenario))

    def test_falsified_handoff_fails_independent_replay(self):
        c=case_for();h,p=construct(c)
        h['orders'][0]['units']-=1
        p['handoff_sha256']=digest(h) # attacker updates superficial hash too
        r=audit(c,h,p)
        self.assertEqual(r['verdict'],'FAIL')
        self.assertIn('HANDOFF_DOES_NOT_MATCH_ORIGINAL_COMMITMENTS',r['failures'])

    def test_checker_never_turns_negative_reservations_into_free_capacity(self):
        c=case_for();h,p=construct(c)
        c['suppliers'][0]['capacity_units']=1800
        c['suppliers'][0]['existing_reservations'][0]['units']=-100
        h['supplier_available_units_in_window']=1900
        p['handoff_sha256']=digest(h)
        result=audit(c,h,p)
        self.assertEqual(result['verdict'],'FAIL')
        self.assertIn('SUPPLIER_RESERVATION_INVALID',result['failures'])

    def test_checker_requires_buyer_eligibility_even_after_preparation(self):
        c=case_for();h,p=construct(c)
        c['buyer']['simulated_eligibility']=False
        result=audit(c,h,p)
        self.assertEqual(result['verdict'],'FAIL')
        self.assertIn('BUYER_SYNTHETIC_ELIGIBILITY_MISSING',result['failures'])

    def test_supplier_overbooking_in_frozen_source_rejected(self):
        c=case_for();h,p=construct(c)
        c['suppliers'][0]['existing_reservations'][0]['units']=1500
        self.assertIn('SUPPLIER_CAPACITY_OVERBOOKED',audit(c,h,p)['failures'])

    def test_false_real_world_proof_rejected(self):
        c=case_for();h,p=construct(c)
        p['evidence_boundary']['real_supplier_consent']=True
        self.assertIn('IMPROPER_REAL_WORLD_CLAIM_REAL_SUPPLIER_CONSENT',audit(c,h,p)['failures'])

    def test_order_omitted_from_generated_package_fails(self):
        c=case_for();h,p=construct(c)
        h['orders']=h['orders'][:1]
        self.assertNotEqual(audit(c,h,p)['verdict'],'PASS_SYNTHETIC_ONLY')

    def test_provenance_chain_amendment(self):
        c=case_for();h,p=construct(c)
        a=next(x for x in h['orders'] if x['order_id']=='LBL-100')
        self.assertEqual(a['source_sequences'],[1,4]);self.assertEqual(a['units'],1100)

    def test_duplicate_event_rejected(self):
        c=case_for();c['source_events'].insert(1,copy.deepcopy(c['source_events'][0]))
        for i,e in enumerate(c['source_events'],1):e['sequence']=i
        c['source_seal']=digest(c['source_events'])
        with self.assertRaisesRegex(DrillRejected,'duplicate acceptance'):construct(c)

    def test_over_fulfillment_rejected(self):
        c=case_for();c['source_events'].append({'sequence':6,'type':'FULFILL','order_id':'LBL-200','quantity':1000})
        c['source_seal']=digest(c['source_events'])
        with self.assertRaises(DrillRejected):construct(c)

    def test_unknown_change_rejected(self):
        c=case_for();c['source_events'].append({'sequence':6,'type':'ELEVATE','order_id':'LBL-200'})
        c['source_seal']=digest(c['source_events'])
        with self.assertRaises(DrillRejected):construct(c)

    def test_deadline_rejection(self):
        c=case_for();c['source_events'][1]['deadline_hours']=12;c['source_seal']=digest(c['source_events'])
        with self.assertRaises(DrillRejected):construct(c)

    def test_snapshot_duplicates_rejected(self):
        c=case_for();c['restored_snapshot'].append(copy.deepcopy(c['restored_snapshot'][0]))
        with self.assertRaises(DrillRejected):construct(c)

    def test_privilege_grant_rejected(self):
        c=case_for();c['mode']='LIVE'
        with self.assertRaises(DrillRejected):construct(c)
        c=case_for();c['real_authority']=True
        with self.assertRaises(DrillRejected):construct(c)

    def test_rights_string_cannot_replace_boolean(self):
        c=case_for();c['scope_rights_declared']='yes'
        with self.assertRaises(DrillRejected):construct(c)

    def test_simulated_commitment_must_be_explicit(self):
        c=case_for();c['suppliers'][0].pop('simulated_commitment')
        with self.assertRaises(DrillRejected):construct(c)

    def test_conventional_benchmark_not_overclaimed(self):
        c=case_for();h,p=construct(c)
        self.assertEqual(p['comparison']['incremental_advantage'],'NOT_ESTABLISHED')
        self.assertFalse(any(p['evidence_boundary'].values()))

    def test_idempotent_generated_evidence(self):
        c=case_for();self.assertEqual(construct(c),construct(c))
        self.assertEqual(audit(c,*construct(c)),audit(c,*construct(c)))

    def test_supplier_cheaper_alternative_checked(self):
        c=case_for();h,p=construct(c)
        c['suppliers'][1]['capacity_units']=3000
        self.assertIn('BETTER_DECLARED_SUPPLIER_IGNORED',audit(c,h,p)['failures'])

    def test_buyer_price_violation_detected(self):
        c=case_for();h,p=construct(c)
        c['buyer']['maximum_offer']=5600
        self.assertIn('UNVIABLE_OR_UNAFFORDABLE_OFFER',audit(c,h,p)['failures'])

    def test_cli_works_from_extracted_project_without_overwriting(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'output'
            a=subprocess.run([sys.executable,'-m','continuity_omega','demo','--out',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stderr+a.stdout)
            self.assertTrue((p/'PASSPORT.md').exists())
            b=subprocess.run([sys.executable,'-m','continuity_omega','verify','--in-dir',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(b.returncode,0,b.stderr+b.stdout)
            c=subprocess.run([sys.executable,'-m','continuity_omega','demo','--out',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertNotEqual(c.returncode,0)
            self.assertEqual(json.loads((p/'AUDIT.json').read_text())['verdict'],'PASS_SYNTHETIC_ONLY')

    def test_cli_bad_case_is_not_commercial_success(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad'
            x=subprocess.run([sys.executable,'-m','continuity_omega','demo','--case','overbooked','--out',str(p)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(x.returncode,2,x.stderr+x.stdout)
            self.assertFalse((p/'HANDOFF.json').exists())
            self.assertEqual(json.loads((p/'REJECTION.json').read_text())['verdict'],'REJECTED_BEFORE_HANDOFF')

if __name__=='__main__':unittest.main()
