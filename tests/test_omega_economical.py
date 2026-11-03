"""Exact-search, inherited-order and producer-omission regressions."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanism_harness import inventor as i
from mechanism_harness import inventor_native as n
from mechanism_harness import economical_learning as e


class ExactDiscovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dev=i.inputs((180101,180102),i.TRAIN_INDICES)
        cls.result=e.learn(cls.dev)
        cls.reference=i.learn(cls.dev)

    def test_exact_winner_not_weaker_baseline(self):
        self.assertEqual(self.result['policy'],self.reference['policy'])
        self.assertEqual(len(self.result['development_candidates']),32)

    def test_pruning_costs_are_paid(self):
        self.assertGreater(self.result['acquisition_work'],0)
        self.assertLess(self.result['acquisition_work'],self.reference['acquisition_work'])
        self.assertTrue(any(x['status']=='PRUNED' for x in self.result['development_candidates']))
        self.assertGreater(self.result['verification_calls'],0)
        self.assertGreater(self.result['source_bytes_read'],0)

    def test_every_pruning_witness_is_sound(self):
        for row in self.result['development_candidates']:
            if row['status']=='PRUNED':
                self.assertGreaterEqual(e.key(row['policy'],row['work']),tuple(row['pruning_incumbent_key']))

    def test_replay_and_exhaustive_audit(self):
        self.assertTrue(e.audit_learning(self.dev,self.result)['optimum_established'])
        altered=copy.deepcopy(self.result);altered['acquisition_work']-=1
        with self.assertRaisesRegex(ValueError,'TRACE_CHANGED'):e.audit_learning(self.dev,altered)

    def test_candidate_omission_not_accepted_as_invention(self):
        order=e.order_from(self.result);order['programs'].pop()
        with self.assertRaises(ValueError):e.learn(i.inputs((180103,),(8,)),order)

    def test_duplicate_program_order_rejected(self):
        order=e.order_from(self.result);order['programs'][0]=order['programs'][1]
        with self.assertRaises(ValueError):e.learn(i.inputs((180103,),(8,)),order)

    def test_budget_exhaustion_does_not_approve_incumbent(self):
        result=e.learn(self.dev,max_evaluations=1)
        self.assertEqual(result['status'],'BUDGET_EXHAUSTED')
        self.assertIsNone(result['policy'])
        with self.assertRaises(ValueError):e.order_from(result)

    def test_missing_and_duplicate_data_refused(self):
        for dev in ([],[self.dev[0],self.dev[0]]):
            with self.assertRaises(ValueError):e.learn(dev)

    def test_invalid_controls_refused(self):
        for budget in (-1,True,2.0):
            with self.assertRaises(ValueError):e.learn(self.dev,max_evaluations=budget)
        with self.assertRaises(ValueError):e.learn(self.dev,prune=1)

    def test_prior_development_cannot_be_called_fresh(self):
        with self.assertRaisesRegex(ValueError,'FRESH'):e.learn(self.dev,e.order_from(self.result))

    def test_order_is_learned_from_observed_executions(self):
        order=e.order_from(self.result)
        self.assertEqual(order['programs'][0],i.digest(self.result['policy']))
        self.assertEqual(order['parent_sha256'],i.digest(self.result))
        self.assertEqual(set(order['programs']),{i.digest(p) for p in i.genomes()})

    def test_fresh_policy_and_refusal_parity(self):
        fresh=i.inputs((280101,),(8,9,14,15,22,23))
        checked=i.confirm(self.result,fresh)
        self.assertTrue(checked['promoted_in_scope'])
        self.assertTrue(checked['same_content_reuse_ties'])
        self.assertTrue(any(not r['new']['complete'] for r in checked['cases']))

    def test_declared_fixed_conventional_control_ties(self):
        raw=i.inputs((280102,),(8,))[0]
        ordinary=e.ordinary_measure(raw)
        learned=i.measure(raw,self.result['policy'])
        self.assertTrue(ordinary['accepted'])
        self.assertEqual(ordinary['outcome_sha256'],learned['outcome_sha256'])

    def test_negative_mapping_cost_cannot_justify_pruning(self):
        real=i.measure
        def broken(raw,p):return {**real(raw,p),'work':-1}
        with patch.object(i,'measure',broken),self.assertRaisesRegex(ValueError,'NONNEGATIVE'):e.learn(self.dev)


class CostCompleteness(unittest.TestCase):
    """All accounts are separate test fixtures, not the original production history."""
    def run_case(self, fault=None, *, indices=(8,), mutate=None):
        with tempfile.TemporaryDirectory(prefix='omega-v2-cost-') as d:
            path=Path(d);policy=i.policy(('unit','unique','text'),True)
            source={name:hashlib.sha256((i.ROOT/name).read_bytes()).hexdigest() for name in
                    ('mechanism_harness/inventor.py','mechanism_harness/inventor_native.py','mechanism_harness/inventor_cost_audit.py')}
            original=n.JournalAccount.cost
            def injected(account,ident,amount,day):
                if fault is None:return original(account,ident,amount,day)
                return fault(original,account,ident,amount,day)
            with patch.object(n,'INDEXES',indices),patch.object(n.JournalAccount,'cost',injected):
                result=n.operate(path,policy,source,0)
                if mutate:mutate(path,result)
                return n.audit_operation(path,result,source,policy),result

    def test_correct_account_passes(self):
        audit,result=self.run_case()
        self.assertTrue(audit['accepted'])
        self.assertLess(result['native_summary']['profit'],0)

    def test_missing_required_costs_rejected(self):
        for omitted in ('fee-8','annual-maintenance','modeled-tax'):
            def fault(real,account,ident,amount,day):
                if ident!=omitted:return real(account,ident,amount,day)
            with self.subTest(omitted=omitted),self.assertRaisesRegex(ValueError,'COST_CLOSURE'):
                self.run_case(fault)

    def test_wrong_fee_amount_rejected(self):
        def fault(real,account,ident,amount,day):
            return real(account,ident,amount+1 if ident=='fee-8' else amount,day)
        with self.assertRaisesRegex(ValueError,'COST_CLOSURE'):self.run_case(fault)

    def test_wrong_maintenance_day_rejected(self):
        def fault(real,account,ident,amount,day):
            return real(account,ident,amount,day-1 if ident=='annual-maintenance' else day)
        with self.assertRaisesRegex(ValueError,'COST_CLOSURE'):self.run_case(fault)

    def test_duplicate_economic_charge_different_id_rejected(self):
        def fault(real,account,ident,amount,day):
            receipt=real(account,ident,amount,day)
            if ident=='fee-8':real(account,'fee-8-duplicate',amount,day)
            return receipt
        with self.assertRaisesRegex(ValueError,'COST_CLOSURE'):self.run_case(fault)

    def test_positive_tax_cannot_be_omitted(self):
        def fault(real,account,ident,amount,day):
            if ident!='modeled-tax':return real(account,ident,amount,day)
            self.assertGreater(amount,0)
        with self.assertRaisesRegex(ValueError,'COST_CLOSURE'):
            self.run_case(fault,indices=(8,9,10,11,12,13,14,16))

    def test_tax_file_cannot_change_basis(self):
        def mutate(path,result):n.save(path/'TAX.json',{'amount':1})
        with self.assertRaisesRegex(ValueError,'TAX_DERIVATION'):self.run_case(mutate=mutate)

    def test_earned_successor_cannot_be_hidden_in_report(self):
        def mutate(path,result):
            self.assertIsNotNone(result['successor'])
            result['successor']=None;n.save(path/'NATIVE_RESULT.json',result)
        with self.assertRaisesRegex(ValueError,'COST_CLOSURE'):
            self.run_case(mutate=mutate,indices=(8,9,10,11,12,13,14,16))

    def test_clean_completed_resume_finances_unchanged(self):
        with tempfile.TemporaryDirectory(prefix='omega-v2-resume-') as d,patch.object(n,'INDEXES',(8,)):
            path=Path(d);p=i.policy(('unit','unique','text'),True);s={'fixture':'source-owned-unit-test'}
            first=n.operate(path,p,s,0);before=n.read(path/'NATIVE_EXPORT.json')
            second=n.operate(path,p,s,0)
            self.assertEqual(first,second);self.assertEqual(before,n.read(path/'NATIVE_EXPORT.json'))
            self.assertTrue(n.audit_operation(path,second,s,p)['accepted'])


if __name__=='__main__':unittest.main()
