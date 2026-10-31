"""Exact finite game, native-state search and independent decision checks."""
import copy
import unittest
from commercial.ledger import digest
from connected_enterprise.strategic_game042 import SCHEMA,validate,solve,scenario_outcome
from connected_enterprise.opportunity_search040 import search,audit_history
from test_opportunity_search040 import fixture

M=1_000_000

def game():
    return {'schema':SCHEMA,'objective':'minimax_regret','max_downside_microUSD':4*M,
            'rival_margin_microUSD':2*M, 'supplier_minimum_microUSD':M,
            'scenarios':[
                {'id':'central','weight_bps':7000,'demand_bps':10000,'supplier_reliability_bps':10000,
                 'rival_responses':[{'id':'hold','rival_capture_bps':0,'response_cost_microUSD':0},
                                    {'id':'undercut','rival_capture_bps':5000,'response_cost_microUSD':2*M}]},
                {'id':'adverse','weight_bps':3000,'demand_bps':1000,'supplier_reliability_bps':5000,
                 'rival_responses':[{'id':'hold','rival_capture_bps':0,'response_cost_microUSD':0},
                                    {'id':'undercut','rival_capture_bps':6000,'response_cost_microUSD':5*M}]}]}

def basis():
    return {'continue_direct':{'count':0,'margin_microUSD':0,'complete_incremental_cost_microUSD':0,
                               'native_invoice_microUSD':0,'eligible':True},
            'partner_access':{'count':12,'margin_microUSD':8*M,'complete_incremental_cost_microUSD':2*M,
                              'native_invoice_microUSD':M,'eligible':True},
            'add_capacity':{'count':2,'margin_microUSD':8*M,'complete_incremental_cost_microUSD':3*M,
                            'native_invoice_microUSD':3*M,'eligible':True}}

class GameTheory042Tests(unittest.TestCase):
    def test_explicit_complete_finite_game(self):
        self.assertEqual(validate(game()),game())
        r=solve(game(),basis())
        self.assertEqual(r['selected'],'partner_access')
        self.assertFalse(r['no_current_native_funding_authority'] is False)
        self.assertEqual(set(r['eligible']),{'continue_direct','partner_access','add_capacity'})
        self.assertEqual(r['eligible']['partner_access']['scenarios']['central']['rival_action'],'undercut')
        self.assertEqual(r['eligible']['partner_access']['scenarios']['adverse']['rival_action'],'hold')
        self.assertIn('EXACT_FINITE',r['optimality_scope'])

    def test_rival_optimal_response_is_not_seller_favorite(self):
        g=game();a=basis()['partner_access'];s=g['scenarios'][0]
        r=scenario_outcome(a,s,g)
        self.assertEqual(r['rival_action'],'undercut')
        self.assertEqual(r['seller_net_microUSD'],46*M)
        self.assertGreater(r['rival_net_microUSD'],0)

    def test_follower_ties_pessimistically(self):
        g=game();g['rival_margin_microUSD']=0
        for s in g['scenarios']:
            s['rival_responses'][1]['response_cost_microUSD']=0
        r=scenario_outcome(basis()['partner_access'],g['scenarios'][0],g)
        self.assertEqual(r['rival_action'],'undercut')

    def test_downside_blocks_partner_even_if_central_is_lucrative(self):
        g=game();g['max_downside_microUSD']=0;g['scenarios'][1]['demand_bps']=0
        r=solve(g,basis())
        self.assertEqual(r['selected'],'continue_direct')
        self.assertEqual(r['excluded']['partner_access'],'DECLARED_MAX_DOWNSIDE_VIOLATION')

    def test_supplier_must_prefer_contract_to_declared_reservation(self):
        g=game();g['supplier_minimum_microUSD']=3*M
        r=solve(g,basis())
        self.assertNotEqual(r['selected'],'partner_access')
        self.assertEqual(r['excluded']['partner_access'],'DECLARED_SUPPLIER_OUTSIDE_OPTION_NOT_MET')

    def test_native_unrestricted_earnings_and_cash_are_binding(self):
        b=basis();b['partner_access']['eligible']=False
        r=solve(game(),b)
        self.assertNotIn('partner_access',r['eligible'])
        self.assertEqual(r['excluded']['partner_access'],'CURRENT_NATIVE_AVAILABLE_EARNINGS_INSUFFICIENT')

    def test_no_profitable_channel_under_adverse_market(self):
        g=game()
        for s in g['scenarios']:
            s['demand_bps']=0
        r=solve(g,basis())
        self.assertEqual(r['selected'],'continue_direct')
        self.assertEqual(r['scenario_best_attainable_net_microUSD'],{'central':0,'adverse':0})

    def test_cannot_invent_profit_from_absent_productive_work(self):
        b=basis();b['partner_access']['count']=0
        r=solve(game(),b)
        self.assertEqual(r['excluded']['partner_access'],'NO_PRODUCTIVE_OPPORTUNITY_OR_INCOMPLETE_COSTS')

    def test_full_incremental_cost_must_cover_native_invoice(self):
        b=basis();b['partner_access']['complete_incremental_cost_microUSD']=0
        r=solve(game(),b)
        self.assertNotIn('partner_access',r['eligible'])

    def test_boolean_floats_and_undeclared_parameters_rejected(self):
        g=game();g['max_downside_microUSD']=True
        with self.assertRaises(ValueError):solve(g,basis())
        g=game();g['scenarios'][0]['demand_bps']=.5
        with self.assertRaises(ValueError):solve(g,basis())
        g=game();g['extra']='magic'
        with self.assertRaises(ValueError):solve(g,basis())

    def test_weights_and_follower_actions_are_strict(self):
        g=game();g['scenarios'][0]['weight_bps']=6999
        with self.assertRaisesRegex(ValueError,'WEIGHTS'):solve(g,basis())
        g=game();g['scenarios'][0]['rival_responses'][1]['id']='hold'
        with self.assertRaisesRegex(ValueError,'DUPLICATE_RIVAL'):solve(g,basis())

    def test_explicit_hold_prevents_fictional_spend(self):
        b={'continue_direct':basis()['continue_direct']}
        r=solve(game(),b)
        self.assertEqual(r['selected'],'continue_direct')

    def test_solver_certificate_replay_deterministic(self):
        g=game();b=basis();r=solve(g,b)
        self.assertEqual(r,solve(copy.deepcopy(g),copy.deepcopy(b)))
        self.assertEqual(r['game_sha256'],digest(g))
        self.assertEqual(r['basis_sha256'],digest(b))

    def test_game_falls_back_to_incumbent_on_no_native_collection(self):
        st,p,j,bs,fn=fixture();st['config']['opportunity_policy']['game']=game()
        d=search(st,p,j,bs,1,0,fn)
        self.assertEqual(d['selected'],'continue_direct')
        self.assertEqual(d['game_certificate']['selected'],'continue_direct')
        self.assertTrue(d['game_certificate']['no_current_native_funding_authority'])

    def test_game_reacts_to_observed_profit_and_native_assets(self):
        st,p,j,bs,fn=fixture();st['config']['opportunity_policy']['game']=game()
        st['orders']=[{'outcome':'SETTLED','price':50*M,'complete_cost':5*M,'collection_time':24,
                      'offer':{'service_id':'reconciliation'}}]
        d=search(st,p,j,bs,2,0,fn)
        self.assertEqual(d['selected'],'partner_access')
        self.assertEqual(d['game_certificate']['game_sha256'],digest(game()))
        self.assertGreater(d['game_basis']['partner_access']['complete_incremental_cost_microUSD'],
                           d['game_basis']['partner_access']['native_invoice_microUSD'])

    def test_game_preserves_no_game_default_policy_byte_identity(self):
        st,p,j,bs,fn=fixture()
        d=search(st,p,j,bs,1,0,fn)
        self.assertEqual(d['selected'],'continue_direct')
        self.assertNotIn('game_basis',d)
        self.assertNotIn('game_certificate',d)

    def test_native_recorded_game_certificate_must_rederive(self):
        st,p,j,bs,fn=fixture();st['config']['opportunity_policy']['game']=game();st['config']['horizon_days']=2
        records=[];events=[]
        for day in range(2):
            p['event']['time']=24*day
            d=search(st,p,j,bs,1,0,fn);records.append(d)
            events.append({'kind':'OPPORTUNITY_SELECTION','time':24*day,'decision_sha256':d['id'],
                           'selected':d['selected'],'target_service_id':d['target_service_id']})
        result={'arm':'growth','config':st['config'],'decisions':records,'events':events,'orders':[],
                'investments':[],'summary':{'profit':0}}
        manifest={'jobs':[{'service_id':s,'accepted':True} for s in j]}
        self.assertEqual(audit_history(result,manifest)['opportunity_search_decisions_checked'],2)
        tampered=copy.deepcopy(result)
        tampered['decisions'][0]['game_certificate']['optimality_scope']='MAGIC'
        tampered['decisions'][0]['id']=digest({k:v for k,v in tampered['decisions'][0].items() if k!='id'})
        tampered['events'][0]['decision_sha256']=tampered['decisions'][0]['id']
        with self.assertRaisesRegex(ValueError,'GAME_CERTIFICATE_NOT_REDERIVABLE'):
            audit_history(tampered,manifest)

if __name__=='__main__':unittest.main()
