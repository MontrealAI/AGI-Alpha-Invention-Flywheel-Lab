"""Independent executable and adversarial qualification of market creation 045."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from commercial import possibility_exchange as x, possibility_audit as audit
from scripts import run_possibility_exchange045 as cli

ROOT=Path(__file__).resolve().parents[1]


def fixture(adverse=False):
    name='ADVERSE.json' if adverse else 'INPUT.json'
    return json.loads((ROOT/'campaign/possibility-exchange-045'/name).read_text())


class CoalitionMarketCreationTests(unittest.TestCase):
    def test_nonviable_individuals_become_viable_only_by_constructing_shared_means(self):
        spec=fixture()
        self.assertFalse(any(q['method_kind']=='direct_specialist' for q in x.candidates(spec)))
        result=x.build(spec)
        chosen=result['chosen']
        self.assertEqual(result['status'],'CONDITIONALLY_FEASIBLE_NEW_BUSINESS')
        self.assertEqual(chosen['method_kind'],'shared_proof')
        self.assertEqual(chosen['buyer_ids'],['buyer0','buyer1','buyer2'])
        self.assertEqual(chosen['complete_model_cost_cents'],7_240_000)
        self.assertEqual(chosen['conditional_revenue_cents'],8_280_000)
        self.assertEqual(chosen['conditional_provider_gain_cents'],1_040_000)
        self.assertEqual(chosen['partner_distributed_gain_cents'],240_000)
        self.assertEqual(chosen['buyer_incremental_gains_cents'],{f'buyer{i}':240_000 for i in range(3)})
        self.assertLess(chosen['required_protected_cash_cents'],spec['capital_cents'])
        self.assertEqual(audit.verify(spec,result)['actual_verified_deliveries'],3)
        self.assertEqual(result['actual_customer_collections_cents'],0)
        self.assertIsNone(result['actual_profit_cents'])

    def test_adverse_and_insufficient_liquidity_produce_no_bid(self):
        for spec in (fixture(True),fixture()):
            if spec==fixture():spec['capital_cents']=8_000_000
            with self.subTest(spec=spec['capital_cents']):
                result=x.build(spec)
                self.assertEqual(result['status'],'NO_BID_OR_RETAIN_CASH')
                self.assertIsNone(result['chosen'])
                self.assertEqual(result['produced_checked_outcomes'],[])
                self.assertTrue(audit.verify(spec,result)['accepted'])

    def test_outside_alternative_budget_and_reserves_remain_binding(self):
        for change in ('outside','budget','reserves'):
            spec=fixture()
            if change=='outside':spec['buyers'][0]['outside_utility_cents']=2_950_000
            elif change=='budget':spec['buyers'][0]['budget_cents']=1
            else:spec['risk_reserve_cents']=3_000_000
            with self.subTest(change=change):
                self.assertIsNone(x.build(spec)['chosen'])

    def test_heterogeneous_raw_formats_are_actually_normalized_and_checked(self):
        spec=fixture();result=x.build(spec)
        source=spec['buyers'][1]['source']
        receipt=next(q for q in result['produced_checked_outcomes'] if q['buyer_id']=='buyer1')
        self.assertEqual(receipt['normalized_order']['order_id'],source['id'])
        self.assertEqual(receipt['normalized_order']['payments'][0]['invoice_refs'],['I-C01'])
        self.assertTrue(audit.verify(spec,result)['accepted'])

    def test_false_completed_service_is_not_sold(self):
        spec=fixture()
        spec['buyers'][1]['source']['settlement_rows'][0]['amount_minor']+=1
        with self.assertRaisesRegex(ValueError,'UNQUALIFIED_COMPLETED_WORK'):
            x.build(spec)

    def test_selected_gain_price_and_forged_collections_rejected(self):
        spec=fixture();original=x.build(spec)
        for alteration in ('gain','price','method','source','output','checker','consent','revenue'):
            row=copy.deepcopy(original)
            if alteration=='gain':row['chosen']['conditional_provider_gain_cents']+=1
            if alteration=='price':row['chosen']['prices_cents']['buyer0']+=1
            if alteration=='method':row['chosen']['method_id']='invented-by-evaluator'
            if alteration=='source':row['source_sha256']='0'*64
            if alteration=='output':row['produced_checked_outcomes'][0]['verified_report']['totals']['invoice_cents']+=1
            if alteration=='checker':row['produced_checked_outcomes'][0]['independent_checker_receipt']['accepted']=False
            if alteration=='consent':row['partner_consent_observed']=True
            if alteration=='revenue':row['actual_customer_collections_cents']=50_000_000
            with self.subTest(alteration=alteration),self.assertRaises(ValueError):
                audit.verify(spec,row)

    def test_duplicate_buyers_or_work_refused(self):
        spec=fixture();spec['buyers'][1]['id']='buyer0'
        with self.assertRaises(ValueError):x.validate(spec)
        spec=fixture();spec['buyers'][1]['source']['id']='O-C00'
        with self.assertRaises(ValueError):x.validate(spec)

    def test_unregistered_contract_terms_refused(self):
        spec=fixture();spec['methods'][0]['free_money']=50_000
        with self.assertRaises(ValueError):x.validate(spec)
        spec=fixture();spec['buyers'][1]['fictitious_income']=10_000
        with self.assertRaises(ValueError):x.validate(spec)

    def test_external_proposal_pin_and_repeated_verification(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'proof'
            outcome=cli.build(ROOT/'campaign/possibility-exchange-045/INPUT.json',p)
            self.assertEqual(outcome['conditional_provider_gain_cents'],1_040_000)
            self.assertTrue(cli.verify(p,expected_manifest_sha256=outcome['manifest_sha256'])['verified'])
            with self.assertRaises(FileExistsError):cli.build(ROOT/'campaign/possibility-exchange-045/INPUT.json',p)
            manifest=p/'MANIFEST.json';manifest.write_bytes(manifest.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'EXTERNAL_PROPOSAL_MANIFEST_PIN_CHANGED'):
                cli.verify(p,expected_manifest_sha256=outcome['manifest_sha256'])

    def test_rehashed_forgery_fails_even_without_external_pin(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'proof'
            original=cli.build(ROOT/'campaign/possibility-exchange-045/INPUT.json',p)
            q=p/'PROPOSAL.json';a=json.loads(q.read_text())
            a['chosen']['conditional_provider_gain_cents']+=1000
            q.write_bytes(x.canonical(a))
            manifest=p/'MANIFEST.json';m=json.loads(manifest.read_text())
            m['file_sha256']['PROPOSAL.json']=hashlib.sha256(q.read_bytes()).hexdigest()
            manifest.write_bytes(x.canonical(m))
            with self.assertRaisesRegex(ValueError,'UNTRUTHFUL_FEASIBLE_COALITION_OR_SELECTION'):
                cli.verify(p)
            with self.assertRaisesRegex(ValueError,'EXTERNAL_PROPOSAL_MANIFEST_PIN_CHANGED'):
                cli.verify(p,expected_manifest_sha256=original['manifest_sha256'])

    def test_optimality_claim_is_finite_and_no_actual_money_is_booked(self):
        spec=fixture();record=x.build(spec);verdict=audit.verify(spec,record)
        self.assertEqual(verdict['feasible_options'],1)
        self.assertEqual(verdict['game_claim'],'EXACT_FINITE_AUTHORED_PRICE_PARTICIPATION_OPTIMUM_NOT_TRUTHFUL_REVELATION_OR_REAL_DEMAND')
        self.assertIsNone(verdict['maximum_possible_native_collections_cents'])
        self.assertFalse(record['buyer_consent_observed'])
        self.assertFalse(record['partner_consent_observed'])
        self.assertEqual(record['native_cash_committed_cents'],0)

    def test_native_frozen_source_contains_required_business_instrument(self):
        from connected_enterprise.runner import source_paths
        paths=set(source_paths(ROOT))
        required={'commercial/possibility_exchange.py','commercial/possibility_audit.py',
                  'scripts/run_possibility_exchange045.py',
                  'tests/test_possibility_exchange045.py',
                  'campaign/possibility-exchange-045/INPUT.json'}
        self.assertTrue(required<=paths)


if __name__=='__main__':unittest.main()
