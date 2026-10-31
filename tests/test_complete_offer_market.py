import copy
import unittest
from connected_enterprise.complete_offer_market import *


def policy():
    return {'schema':SCHEMA,'selection':'menu','profiles':[{'id':'close','services':['reconciliation','receivables_packet'],
        'price_grids':{'reconciliation':[10,20],'receivables_packet':[30,50]},
        'atoms':[{'weight_bps':5000,'budget_microUSD':40,'values':{'reconciliation':20,'receivables_packet':60}},
                 {'weight_bps':5000,'budget_microUSD':100,'values':{'reconciliation':40,'receivables_packet':90}}],
        'outside_options':[{'name':'self','provider':'self_service','service_id':'reconciliation','price':5,'quality_bps':10000,'delay_cost':10}]}]}

class CompleteOfferMarketTests(unittest.TestCase):
    def test_shared_forecast_actual_choice(self):
        ctx=market_context(policy(),'b',0)
        self.assertEqual(win_probability(ctx,'receivables_packet',30),1)
        for i in (0,1):self.assertEqual(actual_choice(ctx,i,ctx['profile']['atoms'][i]['budget_microUSD'],'receivables_packet',30,.4)['provider'],'us')
    def test_budget_blocks_but_does_not_force_lower_scope(self):
        ctx=market_context(policy(),'b',0)
        self.assertEqual(win_probability(ctx,'receivables_packet',50),.5)
        self.assertNotEqual(actual_choice(ctx,0,40,'receivables_packet',50,.1)['provider'],'us')
    def test_no_bid_keeps_outside_and_refusal(self):
        ctx=market_context(policy(),'b',0)
        self.assertEqual(actual_choice(ctx,0,40,None,None,.1)['provider'],'self_service')
        self.assertEqual(actual_choice(ctx,0,0,None,None,.1)['provider'],'decline')
    def test_scope_not_in_request_cannot_win(self):
        self.assertEqual(win_probability(market_context(policy(),'b',0),'CFO',10),0)
    def test_forecast_receives_no_private_budget(self):
        ctx=market_context(policy(),'b',0);ctx['remaining_budget']=3
        with self.assertRaises(ValueError):win_probability(ctx,'reconciliation',10)
    def test_observed_spend_not_future_cash(self):
        ctx=market_context(policy(),'b',45)
        self.assertEqual(win_probability(ctx,'receivables_packet',50),1)
        with self.assertRaises(ValueError):actual_choice(ctx,0,41,None,None,.1)
    def test_values_independent_of_quote_grid(self):
        p=policy();before=copy.deepcopy(p['profiles'][0]['atoms']);p['profiles'][0]['price_grids']['receivables_packet']=[100,200];validate_policy(p)
        self.assertEqual(before,p['profiles'][0]['atoms']);self.assertEqual(win_probability(market_context(p,'b',0),'receivables_packet',200),0)
    def test_tie_forecast_matches_uniform_execution(self):
        p=policy();p['profiles'][0]['outside_options']=[]
        ctx=market_context(p,'b',0)
        self.assertEqual(win_probability(ctx,'reconciliation',20),.75)
        self.assertEqual({actual_choice(ctx,0,40,'reconciliation',20,x)['provider'] for x in (.1,.9)},{'us','decline'})
