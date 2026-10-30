import copy
import unittest
from adaptive_enterprise.strategies import adapt_offer,adjudicate_and_adapt,offer_catalog,validate_offer
from adaptive_enterprise.instruments import produce,synthetic_raw


class AdaptiveStrategyTests(unittest.TestCase):
    def test_complete_offer_contracts_have_executable_methods(self):
        offers=offer_catalog()
        self.assertEqual(len(offers),10)
        self.assertEqual(len({offer['id'] for offer in offers}),10)
        for offer in offers:
            self.assertIs(validate_offer(offer),offer)
            self.assertTrue(offer['production_pipeline'])
            self.assertTrue(offer['later_liabilities'])
            self.assertTrue(offer['falsifiers'])

    def test_unimplemented_method_and_silent_scope_change_rejected(self):
        for key,value in [('method','free_superiority'),('scope','guaranteed_full_business'),('production_pipeline',['invented_speed_multiplier'])]:
            offer=copy.deepcopy(offer_catalog()[0]);offer[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_offer(offer)

    def test_unknown_fields_and_fabricated_capacity_costs_rejected(self):
        for key,value in [('unearned_moat',1),('capacity_units',0),('price_microUSD',True),('upfront_cost_microUSD',-1)]:
            offer=copy.deepcopy(offer_catalog()[0]);offer[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_offer(offer)

    def test_public_metadata_is_typed_and_cannot_add_hidden_state(self):
        offer=copy.deepcopy(offer_catalog()[0]);offer.update(human_anchor_microUSD=50_000_000,production_cost_microUSD=8_000_000,applicable_job_ids=['observed-job'],delivery_hours=2,evidence_level='checked')
        validate_offer(offer)
        offer['buyer_private_reservation']=999
        with self.assertRaises(ValueError):validate_offer(offer)

    def test_bundle_cannot_claim_three_outputs_with_one_unit_capacity(self):
        bundle=next(offer for offer in offer_catalog() if offer['service_id']=='operations_bundle')
        self.assertEqual(bundle['capacity_units'],3)
        bundle['capacity_units']=1
        with self.assertRaisesRegex(ValueError,'ACTUAL_COMPONENT_PRODUCTION'):validate_offer(bundle)

    def test_adaptation_changes_real_method_and_charges_construction(self):
        original=offer_catalog()[0]
        raw=synthetic_raw('reconciliation',9)
        adapted=adjudicate_and_adapt(raw,original,produce(raw,'generated_schema'))['adapted_offer']
        self.assertEqual(original['method'],'canonical')
        self.assertEqual(adapted['method'],'generated_schema')
        self.assertIn('infer_typed_mapping',adapted['production_pipeline'])
        self.assertGreater(adapted['upfront_cost_microUSD'],original['upfront_cost_microUSD'])
        self.assertNotEqual(adapted['id'],original['id'])

    def test_missing_facts_change_explicit_promised_scope(self):
        raw=synthetic_raw('reconciliation',15)
        adapted=adjudicate_and_adapt(raw,offer_catalog()[0],produce(raw,'staged_readiness'))['adapted_offer']
        self.assertEqual(adapted['scope'],'intake_readiness')
        self.assertEqual(adapted['method'],'staged_readiness')
        self.assertIn('only',adapted['outcome'])

    def test_unsupported_criticism_cannot_rewrite_the_offer(self):
        for criticism in [{'verified':False,'kind':'schema_mismatch'},{'verified':True,'kind':'schema_mismatch'},{'verified':True,'kind':'profit_looks_low'},{}]:
            with self.subTest(criticism=criticism),self.assertRaises(ValueError):adapt_offer(offer_catalog()[0],criticism)

    def test_accepted_work_and_forged_rejection_receipts_cannot_claim_criticism(self):
        original=offer_catalog()[0];canonical=synthetic_raw('reconciliation',0)
        with self.assertRaisesRegex(ValueError,'ACCEPTED_WORK'):
            adjudicate_and_adapt(canonical,original,produce(canonical,'canonical'))
        with self.assertRaisesRegex(ValueError,'ORIGINAL_OFFER_EXECUTES'):
            adjudicate_and_adapt(canonical,original,produce(canonical,'generated_schema'))
        raw=synthetic_raw('reconciliation',9);rejected=produce(raw,'generated_schema')
        chain=adjudicate_and_adapt(raw,original,rejected)
        self.assertTrue(chain['repair_acceptance']['accepted'])
        self.assertFalse(chain['adjudication']['rejection_receipt']['accepted'])
        self.assertEqual(chain['adjudication']['raw_order'],raw)
        self.assertEqual(chain['adjudication']['rejected_artifact'],rejected)
        fake=copy.deepcopy(chain['adjudication']['rejection_receipt']);fake['accepted']=True
        with self.assertRaisesRegex(ValueError,'RECEIPT_MISMATCH'):
            adjudicate_and_adapt(raw,original,rejected,fake)
        forged=copy.deepcopy(chain['adjudication']);forged['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'RECOMPUTED_SOURCE_EVIDENCE'):
            adapt_offer(original,forged)


if __name__=='__main__':unittest.main()
