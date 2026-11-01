"""Adversarial tests for proof-bound, budget-balanced coalition discovery."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from commercial.outcome_market045 import solve,strict,verify,build,sha,canonical

FIX=Path(__file__).resolve().parents[1]/'campaign/market045/INPUT.json'

def scenario():
    return json.loads(FIX.read_text())

class CoalitionResearch(unittest.TestCase):
    def setUp(self):
        self.x=scenario();self.b=self.x['buyer'];self.bids=self.x['bids']
    def run_case(self):
        return solve(self.b,self.bids,self.x['price_cents'])
    def test_exact_combinatorial_opening_of_previously_unviable_offer(self):
        r=self.run_case();self.assertEqual(r['status'],'CONDITIONALLY_FEASIBLE_COALITION')
        c=r['winning_coalition'];self.assertEqual(c['bids'],['build-core','partner-reach','proof-check','trace-bridge'])
        self.assertEqual(c['enterprise_retained_gain_if_collected_cents'],10600)
        self.assertEqual(c['total_activation_cents'],5100)
        self.assertEqual(c['funded_noncollection_exposure_cents'],14100)
        self.assertEqual(c['buyer_declared_gain_over_outside_cents'],15100)
        self.assertEqual(sum(c['supplier_declared_gains_cents'].values()),8700)
        self.assertFalse(r['funding_authority']);self.assertIsNone(r['current_proof'])
        self.assertEqual(r['actual_collections_cents'],0)
    def test_direct_specialist_not_enough_under_same_price(self):
        k=self.bids[0];self.assertEqual(k['id'],'direct-incumbent')
        direct=[k, next(b for b in self.bids if b['id']=='proof-check')]
        self.assertEqual(solve(self.b,direct,59900)['status'],'NO_BID')
    def test_no_partner_means_no_distribution(self):
        without=[b for b in self.bids if b['id'] not in ('partner-reach','direct-incumbent')]
        self.assertEqual(solve(self.b,without,59900)['status'],'NO_BID')
    def test_no_interface_means_no_trace(self):
        without=[b for b in self.bids if b['id'] not in ('trace-bridge','direct-incumbent')]
        self.assertEqual(solve(self.b,without,59900)['status'],'NO_BID')
    def test_partner_absence_or_rights_loss_fails(self):
        for change in ('DENIED','UNKNOWN'):
            x=copy.deepcopy(self.bids)
            next(b for b in x if b['id']=='partner-reach')['rights']=change
            self.assertEqual(solve(self.b,x,59900)['status'],'NO_BID')
    def test_buyer_must_have_declared_budget_and_prefer_trade(self):
        for field,small in [('buyer_budget_cents',59000),('buyer_declared_value_cents',61000),('buyer_outside_surplus_cents',30000)]:
            x={**self.b,field:small}
            self.assertEqual(solve(x,self.bids,59900)['status'],'NO_BID')
    def test_unavailable_liquidity_blocks_not_future_collections(self):
        x={**self.b,'available_cash_cents':44000}
        self.assertEqual(solve(x,self.bids,59900)['status'],'NO_BID')
    def test_noncollection_exposure_is_funded_or_refused(self):
        x={**self.b,'max_noncollection_loss_cents':12000}
        self.assertEqual(solve(x,self.bids,59900)['status'],'NO_BID')
    def test_supplier_guarantee_covers_loss_and_cannot_disappear(self):
        x=copy.deepcopy(self.bids);x[1]['failure_guarantee_cents']=0
        with self.assertRaisesRegex(ValueError,'DOWNSIDE_COVERAGE'):solve(self.b,x,59900)
    def test_expired_bid_fails_instead_of_inheriting_permission(self):
        x=copy.deepcopy(self.bids)
        x[2]['expiry_day']=self.b['current_day']
        self.assertEqual(solve(self.b,x,59900)['status'],'NO_BID')
    def test_undisclosed_private_incentives_do_not_get_hallucinated(self):
        r=self.run_case()
        self.assertFalse(r['buyer_accepted']);self.assertFalse(r['suppliers_accepted'])
        self.assertIsNone(r['actual_profit_cents'])
        self.assertFalse(r['asset_capsule']['rights_authenticated'])
        self.assertTrue(r['asset_capsule']['requires_fresh_proof'])
    def test_same_provider_cannot_be_own_independent_checker(self):
        x=copy.deepcopy(self.bids)
        next(b for b in x if b['id']=='proof-check')['provider']='maker'
        self.assertEqual(solve(self.b,x,59900)['status'],'NO_BID')
    def test_bad_tag_duplicate_and_nonboolean_permission_rejected(self):
        for key,value in [('coverage',['delivery','delivery']),('rights',True),('settled_cost_cents',True)]:
            x=copy.deepcopy(self.bids);x[1][key]=value
            with self.assertRaises(ValueError):solve(self.b,x,59900)
    def test_no_unknown_dependencies_or_self_reference(self):
        for deps in (['unknown'],['trace-bridge']):
            x=copy.deepcopy(self.bids);x[2]['requires']=deps
            with self.assertRaises(ValueError):solve(self.b,x,59900)
    def test_fixed_max12_bids_and_max_participants(self):
        x=self.bids*3
        with self.assertRaises(ValueError):solve(self.b,x,59900)
        self.assertEqual(solve({**self.b,'maximum_counterparties':3},self.bids,59900)['status'],'NO_BID')
    def test_buyer_and_bid_misreports_not_claimed_truthful(self):
        r=self.run_case()
        self.assertIn('NOT_BAYESIAN_IC',r['claim_scope'])
    def test_nonfinite_duplicate_json_refused(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):strict(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):strict(b'{"a":NaN}')
    def test_permutation_invariance_in_tied_feasible_auction(self):
        r=self.run_case();x=solve(self.b,list(reversed(self.bids)),59900)
        self.assertEqual(r['winning_coalition'],x['winning_coalition'])
    def test_genuine_better_direct_specialist_wins(self):
        x=copy.deepcopy(self.bids)
        x[0]['settled_cost_cents']=3000
        r=solve(self.b,x,59900)
        self.assertIn('direct-incumbent',r['winning_coalition']['bids'])

class SourceBoundIntegration(unittest.TestCase):
    def setUp(self):
        try:
            from commercial.portable_offer import build as build_proof
        except ImportError:
            self.skipTest('requires exact PR78 portable_offer source; hosted checkout supplies it')
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        s=scenario();self.scenario=s
        build_proof(s['order'],self.root/'proof',price_cents=s['price_cents'])
    def test_verified_work_to_new_market_and_rederivation(self):
        x=self.scenario
        build(self.root/'proof',x['buyer'],x['bids'],self.root/'market')
        c=verify(self.root/'proof',self.root/'market')
        self.assertEqual(c['status'],'CONDITIONALLY_FEASIBLE_COALITION')
        self.assertFalse(c['cash_moved']);self.assertEqual(c['actual_customers'],0)
    def test_contract_changed_with_own_digest_is_still_refused(self):
        x=self.scenario;build(self.root/'proof',x['buyer'],x['bids'],self.root/'market')
        p=self.root/'market/COALITION.json';r=json.loads(p.read_bytes());r['result']['winning_coalition']['enterprise_retained_gain_if_collected_cents']+=1000000
        p.write_bytes(canonical(r))
        with self.assertRaisesRegex(ValueError,'CERTIFICATE'):verify(self.root/'proof',self.root/'market')
    def test_source_proof_mutation_is_refused(self):
        x=self.scenario;build(self.root/'proof',x['buyer'],x['bids'],self.root/'market')
        p=self.root/'proof/DELIVERY/reconciliation.json';p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):verify(self.root/'proof',self.root/'market')
    def test_external_digest_pin_is_monotone(self):
        x=self.scenario;build(self.root/'proof',x['buyer'],x['bids'],self.root/'market')
        pin=sha((self.root/'market/COALITION.json').read_bytes())
        self.assertTrue(verify(self.root/'proof',self.root/'market',expected_sha256=pin)['recomputed'])
        with self.assertRaisesRegex(ValueError,'EXTERNALLY_PINNED'):
            verify(self.root/'proof',self.root/'market',expected_sha256='0'*64)

if __name__=='__main__':unittest.main()

class FrozenSourceInventory(unittest.TestCase):
    def test_coalition_and_proof_are_frozen_together(self):
        try:
            from connected_enterprise.runner import source_paths
        except ImportError:
            self.skipTest('requires full PR78 repository source')
        root=Path(__file__).resolve().parents[1]
        names=set(source_paths(root))
        self.assertTrue({'commercial/outcome_market045.py','commercial/portable_offer.py',
            'commercial/partner_offer.py','campaign/market045/INPUT.json',
            'tests/test_outcome_market045.py'}<=names)
