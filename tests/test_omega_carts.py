"""V4 feasible composed purchases and constructive repair regressions."""
import copy
from fractions import Fraction
import unittest
from unittest.mock import patch
from commercial.ledger import digest
from mechanism_harness.market_cases import market
from mechanism_harness import cart_program as v,cart_synthesis as s


def private(values,budget=9999,outside=0):
    return {'values':values,'budget_cents':budget,'outside_utility':outside}


def menu_program(m,entries):
    p=v.null_program(m);p['menu']=entries
    for t,r in zip(m['types'],p['rules']):
        choice=v.buyer_choose(m,p,{k:t[k] for k in ('values','budget_cents','outside_utility')})
        r.update(outcome_id=choice['outcome_id'],price_cents=choice['price_cents'])
    return p


class CartSemantics(unittest.TestCase):
    def setUp(self):
        self.m=market(1337,'substitute',width=2)
        self.p=menu_program(self.m,[{'outcome_id':o,'price_cents':p} for o,p in [('first',518),('second',823),('joint',1554)]])
    def test_preserved_213_cent_deviation(self):
        x=v.buyer_choose(self.m,self.p,private([0,600,900,3000]))
        self.assertEqual(x['price_cents'],1341);self.assertEqual(x['basket'],['first','second'])
        self.assertEqual(1554-x['price_cents'],213);self.assertEqual(x['outcome_id'],'joint')
    def test_verifier_rejects_assigned_joint_overcharge(self):
        m=copy.deepcopy(self.m);m['types'][0]['values']=[0,600,900,3000];m['types'][0]['budget_cents']=9999
        p=menu_program(m,self.p['menu']);p['rules'][0].update(outcome_id='joint',price_cents=1554)
        check=v.verify(m,p);self.assertFalse(check['accepted']);self.assertEqual(check['violations'][0]['gain_cents'],213)
    def test_affordable_cart_when_joint_quote_unaffordable(self):
        x=v.buyer_choose(self.m,self.p,private([0,600,900,3000],1341))
        self.assertEqual(x['price_cents'],1341)
        self.assertNotEqual(v.buyer_choose(self.m,self.p,private([0,600,900,3000],1340))['outcome_id'],'joint')
    def test_duplicate_goods_produced_once(self):
        p=menu_program(self.m,[{'outcome_id':'first','price_cents':1},{'outcome_id':'first','price_cents':1},{'outcome_id':'joint','price_cents':100}])
        x=v.buyer_choose(self.m,p,private([0,10,0,500]))
        self.assertEqual(x['services'],self.m['outcomes'][3]['services']);self.assertEqual(x['price_cents'],100)
    def test_more_expensive_duplicate_is_dominated(self):
        p=copy.deepcopy(self.p);p['menu'].append({'outcome_id':'first','price_cents':999})
        self.assertEqual(v.buyer_choose(self.m,p,private([0,600,900,3000])),v.buyer_choose(self.m,self.p,private([0,600,900,3000])))
    def test_no_demand_and_copycat_decline(self):
        self.assertTrue(v.buyer_choose(self.m,self.p,private([0,0,0,0]))['declined'])
        self.assertTrue(v.buyer_choose(self.m,self.p,private([0,600,900,3000],outside=1659))['declined'])
    def test_cart_fee_is_single_aggregate_checkout(self):
        x=v.buyer_choose(self.m,self.p,private([0,600,900,3000]))
        self.assertEqual(x['seller_contribution_cents'],1341-v.fee(1341,300)-290)
    def test_missing_union_rejected(self):
        m=copy.deepcopy(self.m);m['outcomes'].pop()
        for t in m['types']:t['values'].pop()
        with self.assertRaisesRegex(ValueError,'MISSING_PRODUCTIVE_UNION'):v.null_program(m)
    def test_duplicate_outcome_alias_rejected(self):
        m=copy.deepcopy(self.m);m['outcomes'][2]['services']=m['outcomes'][1]['services']
        with self.assertRaisesRegex(ValueError,'UNIQUE_SERVICE_SET'):v.null_program(m)
    def test_unknown_service_union_price_and_input_rejected(self):
        for bad in (-1,True,1.5):
            p=copy.deepcopy(self.p);p['menu'][0]['price_cents']=bad
            with self.assertRaises(ValueError):v.verify(self.m,p)
        p=copy.deepcopy(self.p);p['menu'][0]['outcome_id']='invented'
        with self.assertRaises(ValueError):v.verify(self.m,p)
        with self.assertRaises(ValueError):v.buyer_choose(self.m,self.p,private([0,10]))
    def test_market_identity_bound(self):
        m=copy.deepcopy(self.m);m['types'][0]['budget_cents']+=1
        with self.assertRaisesRegex(ValueError,'SOURCE_BOUND'):v.verify(m,self.p)
    def test_independent_oracle_does_not_call_dp_or_solver(self):
        with patch.object(v,'cheapest_carts',side_effect=AssertionError),patch.object(s,'solve_relaxation',side_effect=AssertionError):
            x=v.oracle_choose(self.m,self.p,private([0,600,900,3000]));self.assertEqual(x['price_cents'],1341)
            self.assertTrue(v.verify(self.m,self.p)['accepted'])
    def test_dp_matches_exhaustive_all_small_budgets(self):
        for budget in (0,1,517,518,823,1340,1341,1554,9999):
            for values in ([0,0,0,0],[0,600,900,3000],[0,900,800,900]):
                t=private(values,budget)
                self.assertEqual(v.buyer_choose(self.m,self.p,t),v.oracle_choose(self.m,self.p,t))


class CartConstruction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m=market(391103,'competitive');cls.r=s.synthesize(cls.m);cls.mem=s.retain(cls.m,cls.r)
    def test_verified_construction_and_strong_control(self):
        self.assertEqual(self.r['status'],'VERIFIED_FINITE_MECHANISM')
        self.assertTrue(v.verify(self.m,self.r['program'])['accepted'])
        full=s.synthesize(self.m,mode='full')
        self.assertEqual(Fraction(full['verification']['expected_contribution_cents']),Fraction(self.r['verification']['expected_contribution_cents']))
    def test_counterexamples_change_constructed_program(self):
        self.assertTrue(self.r['history'][0]['composition_failures'])
        self.assertFalse(self.r['history'][-1]['composition_failures'])
        self.assertNotEqual(self.r['history'][0]['candidate_sha256'],self.r['history'][-1]['candidate_sha256'])
    def test_retained_constraints_and_equal_content_reuse(self):
        fresh=market(1339,'competitive')
        retained=s.synthesize(fresh,memory=self.mem);reuse=s.synthesize(fresh,memory=copy.deepcopy(self.mem))
        self.assertGreater(retained['initial_pairs'],0)
        self.assertEqual(retained['program'],reuse['program'])
        self.assertTrue(v.verify(fresh,retained['program'])['accepted'])
    def test_composition_memory_requires_same_services(self):
        fresh=market(1339,'competitive',services=('different','reconciliation'))
        self.assertFalse(s.inherited_pairs(fresh,self.mem))
    def test_invalid_or_false_memory_rejected(self):
        memory=copy.deepcopy(self.mem);memory['pairs'].append(['first','missing'])
        with self.assertRaises(ValueError):s.synthesize(self.m,memory=memory)
        record=copy.deepcopy(self.r);record['program']['rules'][0]['price_cents']+=1
        with self.assertRaises(ValueError):s.retain(self.m,record)
    def test_finite_exhaustion_not_promoted(self):
        m=copy.deepcopy(self.m);m['limits']['max_rounds']=1
        r=s.synthesize(m);self.assertEqual(r['status'],'UNRESOLVED');self.assertIsNone(r['program'])
    def test_full_separate_bundle_comparators_feasible(self):
        for restriction in ('separate','bundle'):
            r=s.synthesize(self.m,mode='full',restriction=restriction)
            self.assertTrue(v.verify(self.m,r['program'])['accepted'])
            self.assertGreaterEqual(Fraction(self.r['verification']['expected_contribution_cents']),Fraction(r['verification']['expected_contribution_cents']))
    def test_unaffordable_attractive_outcome_does_not_force_participation(self):
        m=market(1340,'competitive',width=2)
        for t in m['types']:t['budget_cents']=1
        r=s.synthesize(m,mode='full');self.assertTrue(v.verify(m,r['program'])['accepted'])
        self.assertTrue(all(x['outcome_id']=='outside' for x in r['program']['rules']))
    def test_high_cost_nondelivery_and_resource_bound(self):
        m=market(1341,'substitute',width=2)
        for o in m['outcomes'][1:]:o['cost_cents']=100000
        r=s.synthesize(m,mode='full');self.assertTrue(all(x['outcome_id']=='outside' for x in r['program']['rules']))
        m['limits']['max_rows']=1
        with self.assertRaisesRegex(ValueError,'ROW_BOUND'):s.synthesize(m)

if __name__=='__main__':unittest.main()
