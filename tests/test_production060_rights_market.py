import copy
from pathlib import Path
import unittest
from production060 import rights_market as rm

ROOT=Path(__file__).resolve().parents[1]


def case():
    binding={'production060/dispatch.py':'0'*64}
    costs={family:{k:0 for k in rm.COST_FIELDS} for family in rm.FAMILIES}
    for family,value in [('license',50),('transfer',40),('gainshare',20)]:costs[family]['construction']=value
    return {'schema':rm.SCHEMA,'scope':'CONDITIONAL_MODEL_NO_ACTUAL_RIGHTS_TRANSFER',
        'evidence':{'actual_purchase_count':0,'basis':'authored unit-test counterfactual, not customer evidence'},
        'source_binding':{'files':binding,'sha256':rm.digest(binding)},
        'project':{'id':'bespoke-productive-constructor','accepted':True,'scope':'test conditional complete outcome','requests':['request-1'],
            'module_entrypoint':'production060.dispatch.rolling_schedule','checker_entrypoint':'production060.acceptance.verify'},
        'available_microUSD':1000,'production_costs_microUSD':costs,
        'buyer_handling_microUSD':{'license':5,'transfer':20,'gainshare':5},
        'outside_options':{**{k:{'cost_microUSD':v,'cash_required_microUSD':v,'equivalent_outcome':True,'basis':'authored complete cost'} for k,v in [('human_build',120),('ordinary_self_build',110),('free_equal_content_copy',100)]},
            'withdraw':{'cost_microUSD':0,'cash_required_microUSD':0,'equivalent_outcome':False,'basis':'no purchase'}},
        'party_terms':{'contributor_minimum_microUSD':0,'capital_minimum_microUSD':0,'contributor_share_bps':0,'capital_share_bps':0},
        'prices_microUSD':[0,20,40,80],'gainshare_bps':[0,5000],
        'worlds':[{'id':'declared-buyer','weight':1,'value_microUSD':200,'budget_microUSD':200,'requested':True,
            'copy_after_delivery_cost_microUSD':5,'verified_incremental_gain_microUSD':100,'basis':'authored unit-test world'}],
        'selection':'declared_prior_expected_profit','settlement':{'payment_fixed_microUSD':0,'payment_bps':0,'positive_profit_tax_bps':0}}


def offer(c,family,fee,share=0):
    return next(o for o in rm.enumerate_contracts(c) if (o['family'],o['upfront_microUSD'],o['gainshare_bps'])==(family,fee,share))


class RightsMarketTests(unittest.TestCase):
    def test_each_product_can_be_selected_endogenously(self):
        c=case();self.assertEqual(rm.solve_market(c)['contract']['family'],'gainshare')
        for f in rm.FAMILIES:c['production_costs_microUSD'][f]['construction']={'license':50,'transfer':80,'gainshare':100}[f]
        c['worlds'][0]['verified_incremental_gain_microUSD']=0
        self.assertEqual(rm.solve_market(c)['contract']['family'],'license')
        c['production_costs_microUSD']['transfer']['construction']=20;c['buyer_handling_microUSD']['transfer']=0;c['buyer_handling_microUSD']['license']=50
        self.assertEqual(rm.solve_market(c)['contract']['family'],'transfer')

    def test_free_equal_content_copy_eliminates_exclusion_rent(self):
        c=case();c['outside_options']['free_equal_content_copy'].update(cost_microUSD=0,cash_required_microUSD=0)
        result=rm.solve_market(c)
        self.assertEqual(result['action'],'retain_cash')
        self.assertTrue(all(not rm.choose_buyer(c,o,c['worlds'][0])['buys'] for o in rm.enumerate_contracts(c)))

    def test_zero_value_or_absent_request_cannot_become_demand(self):
        for field,value in [('value_microUSD',0),('requested',False),('budget_microUSD',0)]:
            c=case();c['worlds'][0][field]=value
            self.assertEqual(rm.solve_market(c)['action'],'retain_cash')

    def test_unknown_direct_copy_or_support_is_not_zero(self):
        c=case();c['outside_options']['free_equal_content_copy']['cost_microUSD']=None
        result=rm.solve_market(c);self.assertEqual(result['action'],'retain_cash');self.assertTrue(result['incomplete_information_or_costs'])
        c=case()
        for row in c['production_costs_microUSD'].values():row['support']=None
        self.assertEqual(rm.solve_market(c)['action'],'retain_cash')
        self.assertFalse(rm.small_contract_frontier(c)['qualified'])

    def test_no_future_receipts_finance_present_work(self):
        c=case();c['available_microUSD']=0
        self.assertEqual(rm.solve_market(c)['action'],'retain_cash')

    def test_gainshare_requires_verified_gain_and_rejects_hindsight_cancellation(self):
        c=case();o=offer(c,'gainshare',0,5000)
        self.assertEqual(rm.invoice_amount(c,o,accepted=False),0)
        with self.assertRaises(ValueError):rm.invoice_amount(c,o,accepted=True)
        w=copy.deepcopy(c['worlds'][0]);w['id']='bad-realized-gain';w['verified_incremental_gain_microUSD']=0;c['worlds'].append(w)
        row=rm.evaluate_contract(c,o,w)
        self.assertTrue(row['execute']);self.assertLess(row['conditional_creator_surplus_microUSD'],0)
        self.assertEqual(row['cost_microUSD'],20)
        c['selection']='maximin'
        selected=rm.solve_market(c)
        self.assertNotEqual(selected['contract'],o)

    def test_ordinary_tie_removes_gainshare_premium(self):
        c=case();c['worlds'][0]['verified_incremental_gain_microUSD']=0
        self.assertEqual(rm.invoice_amount(c,offer(c,'gainshare',20,5000),verified_incremental_gain_microUSD=0,accepted=True),20)

    def test_buyer_can_defect_to_self_operation_without_forced_renewal(self):
        c=case();c['buyer_handling_microUSD']['license']=80
        choice=rm.choose_buyer(c,offer(c,'license',40),c['worlds'][0])
        self.assertEqual(choice['chosen'],'buy_then_self_operate')
        self.assertEqual(choice['utility_microUSD'],155)

    def test_unknown_post_delivery_self_operation_cannot_support_license(self):
        c=case();c['worlds'][0]['copy_after_delivery_cost_microUSD']=None
        o=offer(c,'license',40);row=rm.evaluate_contract(c,o,c['worlds'][0])
        self.assertFalse(row['execute'])
        self.assertEqual(row['buyer_choice']['status'],'UNKNOWN_COMPLETE_OUTSIDE_COST')
        with self.assertRaises(ValueError):rm.compile_constructor(c,o,'request-1')

    def test_outside_wins_ties(self):
        c=case();c['buyer_handling_microUSD']['transfer']=20
        self.assertFalse(rm.choose_buyer(c,offer(c,'transfer',80),c['worlds'][0])['buys'])

    def test_party_shares_conserve_only_actual_conditional_surplus(self):
        c=case();c['party_terms'].update(contributor_share_bps=2000,capital_share_bps=1000,contributor_minimum_microUSD=1,capital_minimum_microUSD=1)
        row=rm.evaluate_contract(c,offer(c,'gainshare',40,5000),c['worlds'][0])
        self.assertTrue(row['party_participation']);self.assertEqual(row['cash_conservation_microUSD'],0)
        self.assertEqual(row['conditional_collection_microUSD'],90)
        self.assertEqual(row['conditional_creator_surplus_microUSD'],49)
        self.assertEqual(row['contributor_surplus_microUSD'],14);self.assertEqual(row['capital_surplus_microUSD'],7)
        c['party_terms']['capital_minimum_microUSD']=100
        self.assertEqual(rm.solve_market(c)['action'],'retain_cash')
        rejected=rm.evaluate_contract(c,offer(c,'gainshare',40,5000),c['worlds'][0]);self.assertFalse(rejected['execute']);self.assertEqual(rejected['conditional_collection_microUSD'],0)
        with self.assertRaises(ValueError):rm.compile_constructor(c,offer(c,'gainshare',40,5000),'request-1')

    def test_small_contract_crossover_is_conditional_and_uses_best_ordinary(self):
        c=case();f=rm.small_contract_frontier(c,'transfer')
        self.assertEqual(f['enabled_value_interval_microUSD'],[62,99])
        c['outside_options']['free_equal_content_copy']['cost_microUSD']=0
        self.assertIsNone(rm.small_contract_frontier(c,'transfer')['enabled_value_interval_microUSD'])

    def test_current_public_measurements_do_not_invent_adoption(self):
        rows=[{'id':'cdp_o5_01s','accepted':True,'cpu_s':1,'kpis':{'load_count':9}}]
        c=rm.public_market(ROOT,rows)
        self.assertEqual(c['evidence']['anonymous_public_work_operators'],1)
        self.assertEqual(c['evidence']['actual_purchase_count'],0)
        self.assertEqual(rm.solve_market(c)['action'],'retain_cash')

    def test_generic_constructor_can_bind_new_capability_without_expert_answers(self):
        cap=rm.bind_capability(ROOT,capability_id='inventory-policy-constructor',module_paths=['production060/rights_market.py'],
            module_entrypoint='inventory061.construct',checker_entrypoint='inventory061.acceptance.verify',request_ids=['inventory-real-request'],acceptance_receipt_sha256='a'*64,scope='bounded test binding; independent productive acceptance is caller-owned')
        c=case();scenario={k:c[k] for k in ['available_microUSD','production_costs_microUSD','buyer_handling_microUSD','outside_options','party_terms','prices_microUSD','gainshare_bps','worlds','selection','settlement']}
        generic=rm.market_for_capability(cap,scenario);o=rm.enumerate_contracts(generic)[0];charter=rm.compile_constructor(generic,o,'inventory-real-request')
        self.assertEqual(charter['module'],'inventory061.construct');self.assertFalse(charter['rights']['exclusive']);self.assertFalse(charter['rights']['private_account_authority_inherited'])
        with self.assertRaises(ValueError):rm.compile_constructor(generic,o,'unregistered-request')

    def test_arbitrary_contract_or_source_swap_rejected(self):
        c=case();o=offer(c,'transfer',40);o['rights']['exclusive']=True
        with self.assertRaises(ValueError):rm.choose_buyer(c,o,c['worlds'][0])
        c=case();c['source_binding']['files']['production060/dispatch.py']='1'*64
        with self.assertRaises(ValueError):rm.solve_market(c)

    def test_no_boolean_money_or_unfunded_share_creation(self):
        c=case();c['available_microUSD']=True
        with self.assertRaises(ValueError):rm.solve_market(c)
        c=case();c['party_terms'].update(contributor_share_bps=9000,capital_share_bps=9000)
        with self.assertRaises(ValueError):rm.solve_market(c)

    def test_game_certificate_and_altered_claim_rejected(self):
        c=case();result=rm.solve_market(c);self.assertTrue(rm.audit_market(c,result)['accepted'])
        self.assertEqual(result['objective_gap_in_declared_qualified_family'],0)
        result['observed_industry_creation']=True
        with self.assertRaises(ValueError):rm.audit_market(c,result)


    def test_settlement_is_complete_and_unknown_is_not_zero(self):
        c=case();c['settlement']={'payment_fixed_microUSD':1,'payment_bps':1000,'positive_profit_tax_bps':2500}
        row=rm.evaluate_contract(c,offer(c,'gainshare',40,5000),c['worlds'][0])
        self.assertEqual(row['payment_fee_microUSD'],10);self.assertEqual(row['tax_provision_microUSD'],15)
        self.assertEqual(row['conditional_creator_surplus_microUSD'],45);self.assertEqual(row['cash_conservation_microUSD'],0)
        del c['settlement'];self.assertEqual(rm.solve_market(c)['action'],'retain_cash');self.assertFalse(rm.small_contract_frontier(c)['qualified'])


    def test_cost_frontier_respects_cash_at_lower_feasible_prices(self):
        c=case();c['settlement']={'payment_fixed_microUSD':0,'payment_bps':5000,'positive_profit_tax_bps':0}
        c['available_microUSD']=65;c['buyer_handling_microUSD']['gainshare']=0
        c['outside_options']['free_equal_content_copy'].update(cost_microUSD=1000,cash_required_microUSD=1000)
        c['outside_options']['ordinary_self_build'].update(cost_microUSD=1100,cash_required_microUSD=1100)
        c['outside_options']['human_build'].update(cost_microUSD=1200,cash_required_microUSD=1200)
        frontier=rm.small_contract_frontier(c,'gainshare')
        self.assertEqual(frontier['minimum_compensating_invoice_microUSD'],41)
        self.assertEqual(frontier['enabled_value_interval_microUSD'],[42,999])

    def test_project_count_bound_does_not_turn_TAM_into_buyers(self):
        result=rm.required_profitable_projects(3000000000000000,100000000,shared_cost_microUSD=10000000000)
        self.assertEqual(result['required_profitable_projects'],30000100)
        self.assertEqual(result['evidenced_collected_projects'],0)
        self.assertIsNone(rm.required_profitable_projects(3000000000000000,0)['required_profitable_projects'])


if __name__=='__main__':unittest.main()
