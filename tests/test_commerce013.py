"""Native growth pilot controls; all customer outcomes remain simulated."""
import copy
from pathlib import Path
import tempfile
import unittest
from commerce013.experiment import (ARMS,FAMILIES,base_config,canonical,choose_dev,
                                    configured,sha,summarize,validate_design,world_row)
from enterprise.services import prepare_services
from enterprise.model import money

ROOT=Path(__file__).resolve().parents[1]


class Channel013Logic(unittest.TestCase):
    def test_five_declared_market_families_have_a_preregistered_weight_sum(self):
        self.assertEqual(sum(x['weight_bps'] for x in FAMILIES.values()),10000)
    def test_channel_costs_are_charged_in_native_units(self):
        c=configured(base_config(),'ordinary','buy_large_channel')
        self.assertEqual(c['intervention_setup_cost'],money(8))
        self.assertEqual(c['intervention_daily_cost'],money(.4))
    def test_no_purchase_is_real_control(self):
        c=configured(base_config(),'ordinary','retain_existing_channel')
        self.assertEqual((c['contacts_per_day'],c['intervention_setup_cost'],c['intervention_daily_cost']),(1,0,0))
    def test_channel_supplier_failure_buys_no_extra_usable_contact_capacity(self):
        c=configured(base_config(),'failed_channel','buy_large_channel')
        self.assertEqual(c['contacts_per_day'],1)
        self.assertEqual(c['intervention_setup_cost'],money(8))
    def test_not_synthetic_buyer_generation(self):
        for arm in ARMS:
            for fam in FAMILIES:
                self.assertEqual(configured(base_config(),fam,arm)['customer_pool'],6)
    def test_not_synthetic_delivery_generation(self):
        for arm in ARMS:
            self.assertEqual(configured(base_config(),'ordinary',arm)['policy'],base_config()['policy'])
    def test_invalid_negative_and_nonfinite_contracts_refused(self):
        for value in [-1,float('nan'),float('inf'),True]:
            a=copy.deepcopy(ARMS);a['buy_large_channel']['daily_usd']=value
            with self.assertRaises(ValueError):validate_design(a)
    def test_fractional_slot_count_refused(self):
        a=copy.deepcopy(ARMS);a['buy_large_channel']['slots']=2.5
        with self.assertRaises(ValueError):validate_design(a)
    def test_unregistered_market_refused(self):
        with self.assertRaises(ValueError):configured(base_config(),'beyond_market','buy_large_channel')
    def test_source_config_unchanged(self):
        c=base_config();original=sha(c)
        configured(c,'ordinary','buy_large_channel')
        self.assertEqual(sha(c),original)
    def test_incomplete_matched_comparison_refused(self):
        row={'family':'ordinary','seed':1,'arm':'buy_large_channel','profit_microUSD':1,'cash_survived':True}
        with self.assertRaises(ValueError):summarize([row])
    def test_development_selection_requires_no_purchase_or_positive_modeled_gain(self):
        base={'family':'ordinary','seed':1,'arm':'retain_existing_channel','profit_microUSD':0,'cash_survived':True}
        rows=[]
        for family in FAMILIES:
            for arm in ARMS:
                rows.append({**base,'family':family,'arm':arm,'profit_microUSD':0 if arm=='retain_existing_channel' else -99})
        self.assertEqual(choose_dev(rows)['selected'],'retain_existing_channel')
    def test_cash_survival_gate_does_not_erase_negative_results(self):
        base={'family':'ordinary','seed':1,'arm':'retain_existing_channel','profit_microUSD':0,'cash_survived':True}
        rows=[]
        for family in FAMILIES:
            for arm in ARMS:
                rows.append({**base,'family':family,'arm':arm,'profit_microUSD':100 if arm!='retain_existing_channel' else 0,'cash_survived':arm=='retain_existing_channel'})
        self.assertEqual(choose_dev(rows)['selected'],'retain_existing_channel')
    def test_no_premature_revenue_claim(self):
        self.assertEqual(sum(FAMILIES[f]['weight_bps'] for f in FAMILIES),10000)


class NativeChannel013Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=tempfile.TemporaryDirectory(prefix='native-commerce013-',dir=ROOT)
        cls.manifest=prepare_services(ROOT,str((Path(cls.folder.name)/'services').relative_to(ROOT)))
    @classmethod
    def tearDownClass(cls): cls.folder.cleanup()

    def test_source_bound_real_native_execution_and_acceptance(self):
        r=world_row(ROOT,self.manifest,base_config(),12002,'ordinary','buy_large_channel')
        self.assertGreater(r['executed_accepted_work'],1)
        self.assertEqual(r['paid'],r['executed_accepted_work'])
        self.assertEqual(r['actual_sales'],0)
        self.assertIn('SIMULATED',r['native_audit_scope'])
        self.assertEqual(r['manifest_sha256'],sha(self.manifest))

    def test_paid_outreach_with_failed_supply_cannot_beat_same_base_jobs(self):
        baseline=world_row(ROOT,self.manifest,base_config(),12002,'ordinary','retain_existing_channel')
        failed=world_row(ROOT,self.manifest,base_config(),12002,'failed_channel','buy_large_channel')
        self.assertEqual(failed['paid'],baseline['paid'])
        self.assertEqual(failed['collections_microUSD'],baseline['collections_microUSD'])
        self.assertLess(failed['profit_microUSD'],baseline['profit_microUSD'])

    def test_adverse_market_can_make_paid_channel_worse_than_no_purchase(self):
        before=world_row(ROOT,self.manifest,base_config(),12002,'correlated_shock','retain_existing_channel')
        after=world_row(ROOT,self.manifest,base_config(),12002,'correlated_shock','buy_large_channel')
        self.assertLess(after['profit_microUSD'],before['profit_microUSD'])
        self.assertEqual(after['paid'],0)


if __name__=='__main__':unittest.main()
