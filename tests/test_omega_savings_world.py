import copy
import unittest
from omega_savings.world import (USD, make_rule, technical_qualification, validate_rule,
    ContactRights, channel_quote, contract_for, candidate_campaign_sizes)
from omega_savings.policy import decide, empty_stats, validate_prior
from omega_savings.runner import registration


class WorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.technical = technical_qualification()

    def rule(self, world="positive"):
        return make_rule(11, world, technical=self.technical)

    def purchase(self, book, ident, channel, count, hour=0):
        q = channel_quote(channel, count, book.state['cursors'][channel], world=book.world)
        return book.purchase(ident, channel, count, hour, invoice=q, paid_microUSD=q['price_microUSD'])

    def observation(self):
        r = self.rule()
        return dict(hour=0, available=100000*USD, unrestricted_earned=0, payables=0, built=False, capability=0,
            channel_stats=empty_stats(), campaign_count=0, last_campaign_units=0, qualified_advanced=0,
            cash_profit=0, fixed_fraction_bps=1500,
            current_quotes={c: channel_quote(c,20,0,world=r['world']) for c in ('search','community','partner')})

    def test_paid_rights_expand_far_beyond_initial_pilot(self):
        r=self.rule(); b=ContactRights(11,r['world'])
        self.purchase(b,'a','community',20)
        first=b.expose('a',24,r,campaign=0,capability=1,price_index=1)
        self.purchase(b,'b','community',1000,48)
        second=b.expose('b',72,r,campaign=0,capability=1,price_index=1)
        self.assertGreater(second['fresh'],first['fresh'])
        self.assertGreater(sum(g['units'] for g in second['groups']),0)
        self.assertGreater(candidate_campaign_sizes(10**15)[-1],candidate_campaign_sizes(100000*USD)[-1])

    def test_paid_invoice_not_capacity_creates_contact_rights(self):
        r=self.rule(); b=ContactRights(11,r['world'])
        q=channel_quote('search',20,0,world=r['world'])
        with self.assertRaises(ValueError): b.purchase('a','search',20,0,invoice=q,paid_microUSD=0)
        with self.assertRaises(KeyError): b.expose('unpaid-capacity',24,r,campaign=0,capability=1,price_index=1)
        self.assertEqual(b.state['cursors']['search'],0)

    def test_expiry_overlap_and_exact_idempotence(self):
        r=self.rule(); r['world']['overlap_bps']=10000
        b=ContactRights(11,r['world'])
        row=self.purchase(b,'a','search',40)
        before=b.export()
        self.assertEqual(self.purchase_duplicate(b,row),row)
        self.assertEqual(b.export(),before)
        b.expose('a',24,r,campaign=0,capability=1,price_index=1)
        self.purchase(b,'b','community',40,48)
        overlap=b.expose('b',72,r,campaign=0,capability=1,price_index=1)
        self.assertEqual(overlap['fresh'],0);self.assertEqual(overlap['overlap'],40)
        self.purchase(b,'c','partner',40,100)
        expired=b.expose('c',1000,r,campaign=0,capability=1,price_index=1)
        self.assertEqual(expired['expired'],40)
        self.assertEqual(b.expose('c',1001,r,campaign=0,capability=1,price_index=1)['fresh'],0)

    def purchase_duplicate(self,b,row):
        req=row['request']
        return b.purchase('a',req['channel'],req['units'],req['hour'],invoice=req['invoice'],paid_microUSD=req['invoice']['price_microUSD'])

    def test_grouping_does_not_change_voluntary_demand_or_future_fates(self):
        r=self.rule(); big=ContactRights(11,r['world']); small=ContactRights(11,r['world'])
        self.purchase(big,'all','community',100)
        a=big.expose('all',24,r,campaign=0,capability=1,price_index=1)
        parts=[]
        for i in range(2):
            self.purchase(small,str(i),'community',50)
            parts.append(small.expose(str(i),24,r,campaign=0,capability=1,price_index=1))
        members=lambda rows: sorted((g['profile'],m['namespace'],m['index']) for x in rows for g in x['groups'] for m in g['members'])
        self.assertEqual(members([a]),members(parts))

    def test_explicit_independent_budgets_and_fixed_hardware(self):
        r=self.rule()
        one=contract_for(r,'c0t1p0a1u1l0');two=contract_for(r,'c0t1p2a1u1000000l0')
        self.assertEqual(one['budget_microUSD'],two['budget_microUSD'])
        self.assertNotEqual(one['price_microUSD'],two['price_microUSD'])
        self.assertEqual(two['units'],1000000)
        fixed=self.rule('fixed_hardware');b=ContactRights(11,fixed['world'])
        self.purchase(b,'a','community',200)
        self.assertEqual(b.expose('a',24,fixed,campaign=0,capability=1,price_index=1)['groups'],[])

    def test_invalid_probabilities_priors_and_registration_rejected(self):
        for prior in ({},{'alpha':0,'beta':2},{'alpha':float('nan'),'beta':1}):
            with self.assertRaises(ValueError):validate_prior(prior)
        with self.assertRaises(ValueError):decide('adaptive',self.observation(),prior={})
        r=self.rule();r['world']['default_bps']=9000;r['world']['refund_bps']=2000
        with self.assertRaises(ValueError):validate_rule(r)
        for kwargs in ({'seeds':[]},{'seeds':[701,701]},{'worlds':[]},{'policies':['adaptive','adaptive']}):
            with self.assertRaises(ValueError):registration(**kwargs)

    def test_same_observations_same_action_and_hidden_world_refused(self):
        o=self.observation()
        self.assertEqual(decide('adaptive',o),decide('ordinary',copy.deepcopy(o)))
        o['hidden_world']='positive'
        with self.assertRaises(ValueError):decide('adaptive',o)

    def test_unprofitable_acquisition_stops_and_capability_does_not_create_buyers(self):
        o=self.observation();o['built']=True;o['capability']=1
        for s in o['channel_stats'].values():
            s.update(contacted=100,purchased=100,settled_units=0,net_contribution=-1000*USD,spent=1000*USD,campaigns=2)
        self.assertEqual(decide('adaptive',o)['action'],'wait')
        self.assertEqual(decide('capability_only',o)['action'],'wait')

    def test_positive_profit_and_cash_do_not_erase_unsettled_invoices(self):
        o=self.observation()
        o.update(built=True,capability=0,payables=29_900_000,unrestricted_earned=20000*USD,
                 cash_profit=20000*USD,qualified_advanced=100)
        o['channel_stats']['community'].update(contacted=100,purchased=100,settled_units=20,
            net_contribution=15000*USD,spent=1000*USD,campaigns=2)
        for policy in ('adaptive','ordinary','fixed299','fixed_split'):
            self.assertEqual(decide(policy,o),{'action':'wait','reason':'unresolved_native_payables'})
        o['payables']=0
        self.assertEqual(decide('adaptive',o)['action'],'construct')


if __name__=='__main__':unittest.main()
