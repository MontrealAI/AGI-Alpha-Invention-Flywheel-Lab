"""Exact economic semantics, synthesis, strategy and real native fault tests."""
import copy
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import ExitStack, contextmanager
from mechanism_harness import market_cases as cases_module

from commercial.ledger import digest
from mechanism_harness import market_program as v,mechanism_synthesis as s,mechanism_campaign as c,mechanism_native as n
from mechanism_harness.market_cases import market

PILOT=((1337,'substitute'),)
ORIGINAL_MARKET=cases_module.market

@contextmanager
def small_native_fixture():
    # Four-type engineering fixtures only; registered V3 confirmation is unchanged.
    def small(*args,**kwargs):
        kwargs['width']=2
        return ORIGINAL_MARKET(*args,**kwargs)
    with ExitStack() as stack:
        stack.enter_context(patch.object(c,'CASES',PILOT))
        stack.enter_context(patch.object(c,'market',side_effect=small))
        stack.enter_context(patch.object(cases_module,'market',side_effect=small))
        yield


class MechanismSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=market(1337,'substitute');cls.built=s.synthesize(cls.m);cls.p=cls.built['program']
    def test_all_private_deviations_checked(self):
        r=v.verify(self.m,self.p);self.assertTrue(r['accepted']);self.assertEqual(r['deviation_checks'],72)
    def test_new_allocation_payment_program(self):
        menu={(r['outcome_id'],r['price_cents']) for r in self.p['rules']}
        self.assertGreater(len(menu),2)
    def test_actual_buyer_can_choose_any_report(self):
        for t,r in zip(self.m['types'],self.p['rules']):
            x=v.buyer_choose(self.m,self.p,{k:t[k] for k in ('values','budget_cents','outside_utility')})
            self.assertEqual((x['outcome_id'],x['price_cents']),(r['outcome_id'],r['price_cents']))
    def test_no_demand_no_trade(self):
        x=v.buyer_choose(self.m,self.p,{'values':[0]*4,'budget_cents':9999,'outside_utility':0})
        self.assertTrue(x['declined'])
    def test_budget_is_not_ignored(self):
        x=v.buyer_choose(self.m,self.p,{'values':[0,9999,9999,9999],'budget_cents':0,'outside_utility':0})
        self.assertTrue(x['declined'])
    def test_copycat_is_not_forced_to_lose(self):
        for t in self.m['types']:
            private=n.private_type(t,self.m,self.p,'copycat')
            self.assertTrue(v.buyer_choose(self.m,self.p,private)['declined'])
    def test_unknown_type_can_refuse(self):
        self.assertTrue(v.buyer_choose(self.m,self.p,{'values':[0,1,2,3],'budget_cents':100,'outside_utility':4})['declined'])
    def test_economic_input_changes_invalidate_program(self):
        changed=copy.deepcopy(self.m);changed['types'][0]['budget_cents']+=1
        with self.assertRaisesRegex(ValueError,'SOURCE_BOUND'):v.verify(changed,self.p)
    def test_false_numeric_money_rejected(self):
        for bad in (-1,True,1.5):
            p=copy.deepcopy(self.p);p['rules'][0]['price_cents']=bad
            with self.assertRaises(ValueError):v.verify(self.m,p)
    def test_missing_type_rejected(self):
        p=copy.deepcopy(self.p);p['rules'].pop()
        with self.assertRaises(ValueError):v.verify(self.m,p)
    def test_unserved_buyer_cannot_be_charged(self):
        p=v.null_program(self.m);p['rules'][0]['price_cents']=1
        self.assertFalse(v.verify(self.m,p)['accepted'])
    def test_solver_cannot_certify_itself(self):
        with patch.object(s,'solve_relaxation',side_effect=AssertionError('solver called')):
            self.assertTrue(v.verify(self.m,self.p)['accepted'])
    def test_incentive_corruption_detected(self):
        p=copy.deepcopy(self.p)
        for r in p['rules']:
            if r['outcome_id']!='outside':r['price_cents']+=500;break
        self.assertFalse(v.verify(self.m,p)['accepted'])
    def test_forced_payment_and_bad_schema_fail_closed(self):
        m=copy.deepcopy(self.m);m['outcomes'][0]['cost_cents']=1
        with self.assertRaises(ValueError):s.synthesize(m)
    def test_conventional_full_solver_is_first_class(self):
        full=s.synthesize(self.m,mode='full')
        self.assertEqual(Fraction(full['verification']['expected_contribution_cents']),Fraction(self.built['verification']['expected_contribution_cents']))
    def test_strong_separate_and_bundle_controls(self):
        for restriction in ('separate','bundle'):
            r=s.synthesize(self.m,mode='full',restriction=restriction)
            self.assertTrue(v.verify(self.m,r['program'])['accepted'])
            self.assertGreaterEqual(Fraction(self.built['verification']['expected_contribution_cents']),Fraction(r['verification']['expected_contribution_cents']))

class CounterexampleLearning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=market(1337,'substitute');cls.r=s.synthesize(cls.m);cls.memory=s.retain(cls.m,cls.r)
    def test_violations_drive_actual_reconstruction(self):
        self.assertGreater(self.r['history'][0]['verified_incentive_failures'],0)
        self.assertEqual(self.r['history'][-1]['verified_incentive_failures'],0)
    def test_learned_objects_are_economic_constraints(self):
        self.assertTrue(self.memory['pairs']);self.assertTrue(self.memory['parents'])
    def test_retained_constraints_rechecked_on_new_market(self):
        fresh=market(1338,'substitute');r=s.synthesize(fresh,memory=self.memory)
        self.assertTrue(v.verify(fresh,r['program'])['accepted'])
        self.assertGreater(r['initial_pairs'],0)
    def test_unknown_inheritance_fails(self):
        memory=copy.deepcopy(self.memory);memory['pairs'].append(['missing','type-001'])
        with self.assertRaises(ValueError):s.synthesize(self.m,memory=memory)
    def test_incompatible_memory_is_not_force_applied(self):
        fresh=market(1338,'substitute',width=2)
        self.assertEqual(s.inherited_pairs(fresh,self.memory),set())
    def test_exhausted_search_is_not_promoted(self):
        m=copy.deepcopy(self.m);m['limits']['max_rounds']=1
        r=s.synthesize(m)
        self.assertEqual(r['status'],'UNRESOLVED');self.assertIsNone(r['program'])
        with self.assertRaises(ValueError):s.retain(m,r)
    def test_unverified_program_cannot_create_memory(self):
        r=copy.deepcopy(self.r);r['program']['rules'][0]['price_cents']=1
        with self.assertRaises(ValueError):s.retain(self.m,r)
    def test_registered_resource_bound_enforced(self):
        m=copy.deepcopy(self.m);m['limits']['max_rows']=1
        with self.assertRaisesRegex(ValueError,'ROW_BOUND'):s.synthesize(m)
    def test_large_cost_makes_nonentry_valid(self):
        m=copy.deepcopy(self.m)
        for o in m['outcomes'][1:]:o['cost_cents']=100000
        r=s.synthesize(m,mode='full')
        self.assertTrue(all(x['outcome_id']=='outside' for x in r['program']['rules']))

class UnresolvedCampaignAccounting(unittest.TestCase):
    @staticmethod
    def bounded_market(seed, family):
        result = ORIGINAL_MARKET(seed, family, width=2)
        if seed == c.CASES[1][0]:
            result['limits']['max_rounds'] = 1
        return result

    @classmethod
    def setUpClass(cls):
        with patch.object(c, 'market', cls.bounded_market):
            cls.report = c.execute()
        cls.report['source'] = c.source_identity()

    def test_partial_case_charges_every_arm_without_transferring_unverified_work(self):
        report = self.report
        first, limited, final = report['cases']
        self.assertEqual([row['status'] for row in report['cases']],
                         ['VERIFIED', 'UNRESOLVED', 'VERIFIED'])
        self.assertIsNone(limited['runs']['cold']['program'])
        self.assertTrue(all(run['program'] is not None for name, run in limited['runs'].items()
                            if name != 'cold'))
        self.assertEqual(report['completed_cases'], 2)
        self.assertNotIn('expected_gain_over_standard_cents', limited)
        self.assertEqual(final['memory_before'], first['memory_after'])
        expected = {}
        for total, counter in [('total_rows_built', 'total_rows_built'),
                               ('total_deviation_checks', 'deviation_checks'),
                               ('construction_cpu_ns', 'construction_cpu_ns')]:
            expected[total] = {arm: sum(row['runs'][arm][counter] for row in report['cases'])
                               for arm in first['runs']}
            self.assertEqual(report[total], expected[total])
        inherited_prior = first['runs']['inherited']['total_rows_built']
        self.assertEqual(limited['prior_discovery_rows'], inherited_prior)
        self.assertEqual(final['prior_discovery_rows'],
                         inherited_prior + limited['runs']['inherited']['total_rows_built'])
        rows = expected['total_rows_built']
        self.assertEqual(report['constraint_transfer_rows_saved'], rows['cold'] - rows['inherited'])
        with patch.object(c, 'market', self.bounded_market):
            self.assertTrue(c.audit(report)['accepted'])

    def test_audit_rejects_omitted_work_and_inconsistent_recorded_timing(self):
        for total, counter in [('total_rows_built', 'total_rows_built'),
                               ('total_deviation_checks', 'deviation_checks'),
                               ('construction_cpu_ns', 'construction_cpu_ns')]:
            with self.subTest(total=total):
                forged = copy.deepcopy(self.report)
                forged[total]['cold'] -= forged['cases'][1]['runs']['cold'][counter]
                with patch.object(c, 'market', self.bounded_market):
                    with self.assertRaisesRegex(ValueError, 'CAMPAIGN_RESOURCE'):
                        c.audit(forged)
        forged = copy.deepcopy(self.report)
        run = forged['cases'][1]['runs']['cold']
        forged['construction_cpu_ns']['cold'] -= run['construction_cpu_ns'] + 1
        run['construction_cpu_ns'] = -1
        with self.assertRaisesRegex(ValueError, 'CAMPAIGN_RESOURCE'):
            c.audit(forged)
        forged = copy.deepcopy(self.report)
        forged['cases'][1]['runs']['cold']['history'][0]['solver_cpu_ns'] = False
        with self.assertRaisesRegex(ValueError, 'CAMPAIGN_RESOURCE'):
            c.audit(forged)


class NativeExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='omega-v3-unit-');cls.path=Path(cls.tmp.name)/'central'
        cls.original=staticmethod(c.execute)
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:cls.original(PILOT)):
            cls.result=n.run(cls.path)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_actual_acceptance_and_native_account(self):
        with small_native_fixture():self.assertTrue(n.audit(self.path)['accepted'])
        self.assertGreater(self.result['settled_buyers'],0)
        self.assertEqual(self.result['actual_revenue_usd'],0)
    def test_resume_never_reseeds(self):
        before=(self.path/'NATIVE_EXPORT.json').read_bytes()
        with small_native_fixture():again=n.run(self.path,resume=True)
        self.assertEqual(again,self.result);self.assertEqual(before,(self.path/'NATIVE_EXPORT.json').read_bytes())
    def test_revenue_or_profit_tamper_rejected(self):
        old=n.read(self.path/'REPORT.json');r=copy.deepcopy(old);r['native_summary']['profit']+=1
        n.save(self.path/'REPORT.json',r)
        try:
            with small_native_fixture(),self.assertRaisesRegex(ValueError,'SUMMARY'):n.audit(self.path)
        finally:n.save(self.path/'REPORT.json',old)
    def test_refusal_cannot_be_faked_by_cash_flag(self):
        file=self.path/'order-001.json';old=n.read(file);r=copy.deepcopy(old);r['affordable']=not r['affordable'];n.save(file,r)
        try:
            with small_native_fixture(),self.assertRaisesRegex(ValueError,'CASH'):n.audit(self.path)
        finally:n.save(file,old)
    def test_source_change_blocks_resume(self):
        with patch.object(n,'source_identity',return_value={'changed':'0'*64}),self.assertRaisesRegex(ValueError,'SOURCE'):n.run(self.path,resume=True)
    def test_failed_acceptance_refunds_without_income(self):
        out=Path(self.tmp.name)/'rejected'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            r=n.run(out,stress='failed_acceptance')
        self.assertGreater(r['refunded_buyers'],0);self.assertEqual(r['native_summary']['collections'],0)
        self.assertLess(r['native_summary']['profit'],0)
    def test_no_demand_spending_remains_visible(self):
        out=Path(self.tmp.name)/'no-demand'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            r=n.run(out,stress='no_demand')
        self.assertEqual(r['settled_buyers'],0);self.assertLess(r['native_summary']['profit'],0)
    def test_native_audit_checks_recorded_study_costs(self):
        path = self.path / 'STUDY.json'
        original = path.read_bytes()
        study = n.read(path)
        study['construction_cpu_ns']['inherited'] += 1
        try:
            n.save(path, study)
            with small_native_fixture(), self.assertRaisesRegex(ValueError, 'CAMPAIGN_RESOURCE_TOTAL'):
                n.audit(self.path)
        finally:
            path.write_bytes(original)

    def test_required_fee_omission_fails_independent_audit(self):
        original=n.JournalAccount.cost
        def missing(account,ident,amount,day):
            if ident.startswith('v3-fee-'):return None
            return original(account,ident,amount,day)
        out=Path(self.tmp.name)/'omit-fee'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)),patch.object(n.JournalAccount,'cost',missing),self.assertRaisesRegex(ValueError,'MISSING_OR_EXTRA_REQUIRED_DEBIT'):
            n.run(out)

if __name__=='__main__':unittest.main()
