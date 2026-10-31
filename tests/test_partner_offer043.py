"""Proof-led distribution contract: source verification, incentives, adverse cases."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from commercial.portable_offer import build as build_proof, canonical
from commercial.partner_offer import quote_terms, build, verify

def order():
    return {'scope':'SYNTHETIC_PUBLIC_WORKLOAD','currency':'USD','order_id':'DISTRIBUTION-PILOT',
            'require_complete':True,
            'invoices':[{'id':'i1','customer':'PUBLIC-SYNTHETIC','amount_cents':15000}],
            'payments':[{'id':'p1','customer':'PUBLIC-SYNTHETIC','amount_cents':15000,'invoice_refs':['i1']}]}

def costs():
    return {'distributor_cost':12000,'distributor_min_gain':5000,
            'provider_complete_cost':10000,'provider_min_gain':15000,
            'activation_cost':1000,'provider_loss_cost':6500,
            'protected_cash':30000,'opening_cash':100000}

class NativePackagingCompatibility(unittest.TestCase):
    def test_proof_and_contract_are_inside_canonical_source_closure(self):
        from connected_enterprise.runner import source_paths
        root=Path(__file__).resolve().parents[1]
        paths=set(source_paths(root))
        self.assertTrue({'commercial/portable_offer.py','commercial/partner_offer.py',
                         'examples/portable_offer/sample_order.json',
                         'docs/portable_offer/PARTNER_PILOT.md'} <= paths)


class TwoSidedTerms(unittest.TestCase):
    def test_smallest_declared_incentive_compatible_share(self):
        q=quote_terms(59900,**costs())
        self.assertEqual(q['status'],'CONDITIONALLY_FEASIBLE_QUOTE')
        self.assertEqual(q['partner_share_if_collected_cents'],17000)
        self.assertEqual(q['partner_gain_if_collected_cents'],5000)
        self.assertEqual(q['provider_gain_if_collected_cents'],31900)
        self.assertEqual(q['failed_collection_provider_loss_cents'],7500)
        self.assertEqual(q['no_sale_provider_loss_cents'],1000)
        self.assertEqual(q['required_upfront_liquidity_cents'],37500)
        self.assertTrue(q['no_demand_means_no_sales'])

    def test_no_bid_when_distributor_or_provider_cannot_participate(self):
        for changed in [{'distributor_min_gain':55000},{'provider_complete_cost':50000},
                        {'provider_min_gain':50000},{'opening_cash':20000}]:
            c={**costs(),**changed}
            with self.subTest(changed=changed):
                q=quote_terms(59900,**c)
                self.assertEqual(q['status'],'NO_BID')
                self.assertIsNone(q['partner_share_if_collected_cents'])

    def test_malformed_and_negative_costs_rejected(self):
        for changed in [{'distributor_cost':-1},{'activation_cost':True},
                        {'provider_complete_cost':1.3},{'opening_cash':10**20}]:
            with self.subTest(changed=changed),self.assertRaises(ValueError):
                quote_terms(59900,**{**costs(),**changed})

class ProofToPartnerContract(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.proof=Path(self.tmp.name)/'proof'
        self.partner=Path(self.tmp.name)/'partner'
        build_proof(order(),self.proof,price_cents=59900)

    def tearDown(self):self.tmp.cleanup()

    def test_buyer_proof_to_bilateral_contract_and_external_pin(self):
        made=build(self.proof,self.partner,**costs())
        self.assertEqual(made['proposal_status'],'CONDITIONALLY_FEASIBLE_QUOTE')
        self.assertTrue(made['rechecked'])
        self.assertEqual(made['actual_collections_cents'],0)
        self.assertIsNone(json.loads((self.partner/'PARTNER_OFFER.json').read_text())['actual_profit_cents'])
        self.assertFalse(made['partner_terms_externally_pinned'])
        pinned=verify(self.proof,self.partner,expected_sha256=made['proposal_sha256'])
        self.assertTrue(pinned['partner_terms_externally_pinned'])
        self.assertEqual(pinned['provider_gain_if_collected_cents'],31900)

    def test_changed_term_requires_new_external_agreement(self):
        made=build(self.proof,self.partner,**costs())
        p=self.partner/'PARTNER_OFFER.json'
        record=json.loads(p.read_text())
        record['proposal']['scenario']['distributor_cost']+=1
        p.write_bytes(canonical(record))
        with self.assertRaisesRegex(ValueError,'EXTERNALLY_PINNED_PARTNER_TERMS_CHANGED'):
            verify(self.proof,self.partner,expected_sha256=made['proposal_sha256'])

    def test_seller_forged_profit_and_collections_rejected(self):
        build(self.proof,self.partner,**costs())
        p=self.partner/'PARTNER_OFFER.json';record=json.loads(p.read_text())
        record['actual_collections_cents']=59900
        record['actual_profit_cents']=1000000
        p.write_bytes(canonical(record))
        with self.assertRaisesRegex(ValueError,'PARTNER_PROPOSAL_OR_SOURCE_BINDING_CHANGED'):
            verify(self.proof,self.partner)

    def test_invalid_proof_cannot_be_quoted(self):
        p=self.proof/'DELIVERY/reconciliation.json'
        p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):
            build(self.proof,self.partner,**costs())
        self.assertFalse(self.partner.exists())

    def test_no_bid_proposal_cannot_claim_sale(self):
        b=build(self.proof,self.partner,**{**costs(),'provider_min_gain':50000})
        self.assertEqual(b['proposal_status'],'NO_BID')
        self.assertIsNone(b['partner_share_if_collected_cents'])
        self.assertEqual(b['actual_collections_cents'],0)
        self.assertFalse(b['native_financial_authority'])

    def test_duplicate_json_and_symlink_guard(self):
        build(self.proof,self.partner,**costs())
        p=self.partner/'PARTNER_OFFER.json'
        p.write_text('{"schema":"a","schema":"b"}')
        with self.assertRaisesRegex(ValueError,'DUPLICATE_FIELD'):
            verify(self.proof,self.partner)
        p.unlink();p.symlink_to(self.proof/'OFFER.json')
        with self.assertRaisesRegex(ValueError,'SYMLINK'):
            verify(self.proof,self.partner)

if __name__=='__main__':unittest.main()
