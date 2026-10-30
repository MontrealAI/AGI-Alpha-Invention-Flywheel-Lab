"""Counterexample-rich tests for opt-in growth hypotheses and original baseline."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from enterprise.scale import default_config, simulate_scale, validate_growth_intervention
from enterprise.growth_frontier import (
    ARMS, REGIMES, CAPITAL, DEVELOPMENT_SEEDS, CONFIRMATION_SEEDS,
    arm_policy, config_for, compact, hash_data
)


class TransformationalGrowthTests(unittest.TestCase):
    def cfg(self):
        c=default_config()
        c['months']=18
        return c

    def test_historical_source_baseline_is_byte_equivalent(self):
        c=self.cfg()
        a=simulate_scale(c,100)
        sha=hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(sha,'e1bd7baee81f835eee6804d7375144f2b427b32c4b91f08b022b12f6216a450f')

    def test_original_baseline_unchanged_by_opt_in_modes(self):
        c=self.cfg()
        legacy=simulate_scale(c,11)
        r=simulate_scale(c,11,intervention=arm_policy('keyed_legacy'))
        self.assertIsNone(legacy.get('intervention'))
        self.assertEqual(legacy['scope'],r['scope'])
        self.assertEqual(legacy['config_sha256'],r['config_sha256'])
        self.assertEqual(legacy['seed'],r['seed'])

    def test_simulated_funding_and_liabilities_conserve(self):
        for arm in ARMS:
            c=config_for('base',CAPITAL[0],arm);c['months']=24
            result=simulate_scale(c,51,intervention=arm_policy(arm))
            for row in result['monthly']:
                self.assertEqual(row['cash_cents'],c['opening_cash_cents']+
                    row['cumulative_collected_revenue_cents']-row['cumulative_cost_cents'])
                self.assertGreaterEqual(row['cash_cents'],row['restricted_cash_cents'])
                self.assertGreaterEqual(row['channel_investment_cents'],0)
                self.assertLessEqual(row['contacts'],c['maximum_monthly_contacts'])

    def test_new_cash_contract_is_costed_and_revenue_is_realized_only_after_output(self):
        c=self.cfg();c['settlement_months']=0;c['months']=14
        c['technical_acceptance_probability']=c['collection_probability']=1.
        c['refund_probability']=c['supplier_outage_probability']=0.
        pol=arm_policy('cash_contract')
        a=simulate_scale(c,17,intervention=pol)
        self.assertEqual(a['monthly'][0]['collected_revenue_cents'],a['monthly'][0]['cumulative_collected_revenue_cents'])
        self.assertGreater(a['monthly'][0]['collected_revenue_cents'],0)
        self.assertGreater(a['monthly'][0]['fast_clearing_fee_cents'],0)
        self.assertEqual(a['terminal_receivables_cents'],0)
        self.assertGreater(a['cumulative_cost_cents'],0)

    def test_cash_is_not_free_and_can_lose_to_baseline(self):
        c=self.cfg();c['settlement_months']=1
        baseline=simulate_scale(c,31,intervention=arm_policy('keyed_legacy'))
        c['settlement_months']=0
        accelerated=simulate_scale(c,31,intervention=arm_policy('cash_contract'))
        self.assertGreater(sum(x['fast_clearing_fee_cents'] for x in accelerated['monthly']),0)
        self.assertLess(accelerated['cumulative_profit_cents'],baseline['cumulative_profit_cents'])

    def test_no_market_or_no_production_no_channel_money_creation(self):
        c=self.cfg();c['initial_customers']=0;c['choice_probability']=0
        s=simulate_scale(c,99,intervention=arm_policy('paid_distribution'))
        self.assertEqual(s['cumulative_collected_revenue_cents'],0)
        self.assertTrue(all(x['channel_investment_cents']==0 for x in s['monthly']))

    def test_no_market_reach_does_not_buy_channel(self):
        c=self.cfg();c['reachable_market_customers']=c['initial_customers']
        s=simulate_scale(c,20,intervention=arm_policy('paid_distribution'))
        self.assertTrue(all(x['channel_investment_cents']==0 for x in s['monthly']))

    def test_channel_failure_exposes_zero_realized_capacity(self):
        c=config_for('channel_failure',CAPITAL[0],'paid_distribution')
        c['months']=24
        p=arm_policy('paid_distribution','channel_failure')
        a=simulate_scale(c,79,intervention=p)
        self.assertEqual(p['channel_realization_bps'],50)
        self.assertEqual(p['channel_tranche_cost_cents'],5_000_000)
        self.assertTrue(all(x['realized_channel_contacts_per_month'] <= x['purchased_channel_contacts_per_month'] for x in a['monthly']))
        self.assertTrue(all(x['cash_cents']>=x['restricted_cash_cents'] for x in a['monthly']))

    def test_channel_does_not_automatically_create_customers(self):
        c=self.cfg();c['qualification_probability']=0
        s=simulate_scale(c,91,intervention=arm_policy('paid_distribution'))
        self.assertTrue(all(r['new_activated']==0 for r in s['monthly']))
        self.assertTrue(all(r['channel_investment_cents']==0 for r in s['monthly']))

    def test_partial_realization_contacts_are_always_integers(self):
        c=self.cfg();c['months']=24
        p=arm_policy('paid_distribution');p['channel_realization_bps']=100
        for seed in (8101,8102,8103):
            run=simulate_scale(c,seed,intervention=p)
            for row in run['monthly']:
                self.assertIs(type(row['contacts']),int)
                self.assertIs(type(row['channel_investment_cents']),int)
                self.assertIs(type(row['purchased_channel_contacts_per_month']),int)
                self.assertIs(type(row['realized_channel_contacts_per_month']),int)

    def test_channel_expiry_does_not_accumulate_forever(self):
        p=arm_policy('paid_distribution');p['channel_duration_months']=2
        c=self.cfg()
        a=simulate_scale(c,77,intervention=p)
        for row in a['monthly']:
            self.assertLessEqual(row['purchased_channel_contacts_per_month'], 2*100*500)

    def test_source_identity_and_replay_are_deterministic(self):
        c=self.cfg();p=arm_policy('paid_distribution')
        self.assertEqual(simulate_scale(c,25,intervention=p),simulate_scale(c,25,intervention=p))
        self.assertEqual(hash_data(p),hash_data(copy.deepcopy(p)))

    def test_regimes_are_predeclared_and_seeds_disjoint(self):
        self.assertEqual(set(DEVELOPMENT_SEEDS)&set(CONFIRMATION_SEEDS),set())
        self.assertIn('channel_failure',REGIMES)
        self.assertEqual(len(ARMS),len(set(ARMS)))

    def test_injected_success_or_funding_is_rejected(self):
        c=self.cfg();p=arm_policy('paid_distribution')
        p['actual_sales']=1
        with self.assertRaises(ValueError):simulate_scale(c,1,intervention=p)
        del p['actual_sales']
        p['channel_realization_bps']=True
        with self.assertRaises(ValueError):simulate_scale(c,1,intervention=p)

    def test_uncosted_instant_contract_is_rejected(self):
        c=self.cfg();c['settlement_months']=0
        p=arm_policy('cash_contract');p['clearing_fee_bps']=0
        with self.assertRaises(ValueError):simulate_scale(c,1,intervention=p)

    def test_fees_require_contract(self):
        c=self.cfg();p=arm_policy('keyed_legacy');p['price_discount_bps']=500
        with self.assertRaises(ValueError):simulate_scale(c,1,intervention=p)

    def test_unfunded_setup_does_not_succeed(self):
        c=self.cfg();c['opening_cash_cents']=1
        a=simulate_scale(c,4,intervention=arm_policy('paid_distribution'))
        self.assertFalse(a['cash_survival'])
        self.assertEqual(a['cumulative_collected_revenue_cents'],0)

    def test_stress_choices_not_global_market_optimality(self):
        c=config_for('weak_demand',CAPITAL[0],'paid_distribution')
        a=compact(simulate_scale(c,41,intervention=arm_policy('paid_distribution')))
        self.assertIn('milestones',a)
        self.assertIn('cumulative_complete_cost_profit_cents',a)
        self.assertIsNone(a['milestones'][str(10**14)])


if __name__=='__main__': unittest.main()
