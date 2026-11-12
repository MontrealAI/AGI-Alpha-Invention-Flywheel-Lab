import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
import gateway

class PublicDemand079(unittest.TestCase):
    def setUp(self):
        self.protocol, self.sha = gateway.registered_protocol()
        self.result = gateway.build()
    def test_all_registered_routes_are_assessed_without_buyer_invention(self):
        self.assertEqual(self.result['registered_routes'], 3)
        self.assertEqual(len(self.result['assessed_routes']), 3)
        self.assertTrue(all(r['decision'] == 'NO_DEPLOY' and not r['paid_contracts_verified'] for r in self.result['assessed_routes']))
        self.assertFalse(self.result['target_3b_qualified'])
    def test_rfi_is_not_a_buyer_order(self):
        r = self.result['assessed_routes'][0]
        self.assertIn('RFI_IS_MARKET_RESEARCH_NOT_A_PURCHASE_ORDER', r['reasons'])
        self.assertEqual(r['customers_contractually_committed'], 0)
    def test_unverified_secondary_does_not_confer_eligibility(self):
        r = self.result['assessed_routes'][1]
        self.assertIn('PRIMARY_SOURCE_NOT_VERIFIED', r['reasons'])
        self.assertFalse(r['source_bytes_independently_hashed'])
    def test_closed_notice_cannot_become_a_bid(self):
        r = self.result['assessed_routes'][2]
        self.assertIn('RESPONSE_DATE_HAS_PASSED', r['reasons'])
        self.assertIn('PUBLIC_SOLICITATION_CLOSED', r['reasons'])
    def test_no_capital_forged_from_future_sale(self):
        self.assertIsNone(self.result['actual_trailing_365_complete_cost_profit_USD'])
        self.assertFalse(self.result['native_account_opened_or_modified'])
        self.assertTrue(all('FUNDED_CAPACITY_UNVERIFIED' in r['reasons'] for r in self.result['assessed_routes']))
    def test_nonzero_customer_flag_rejected(self):
        route = copy.deepcopy(self.protocol['routes'][0]); route['buyer_commitment'] = True
        with self.assertRaisesRegex(ValueError, 'REGISTERED_ROUTE_CHANGED'):
            gateway.assess(route)
    def test_hypothetical_positive_cost_claim_rejected(self):
        route = copy.deepcopy(self.protocol['routes'][1]); route['full_costs_known'] = True
        with self.assertRaisesRegex(ValueError, 'REGISTERED_ROUTE_CHANGED'):
            gateway.assess(route)
    def test_negative_prospective_cost_cannot_be_inserted_as_evidence(self):
        route = copy.deepcopy(self.protocol['routes'][1]); route['cost'] = -1
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_TRANSACTION_OR_COST'):
            gateway.assess(route)
    def test_bools_cannot_masquerade_as_verified_source_evidence(self):
        route = copy.deepcopy(self.protocol['routes'][0]); route['primary_verified'] = 1
        with self.assertRaisesRegex(ValueError, 'STRICT_REGISTERED_BOOLEAN'):
            gateway.assess(route)
    def test_changed_published_deadline_requires_new_registration(self):
        route = copy.deepcopy(self.protocol['routes'][1]); route['response_deadline'] = '2026-12-01'
        with self.assertRaisesRegex(ValueError, 'REGISTERED_ROUTE_CHANGED'):
            gateway.assess(route)
    def test_synthetic_customer_claim_cannot_be_promoted(self):
        route = copy.deepcopy(self.protocol['routes'][0]); route['synthetic_buyer'] = True
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_TRANSACTION_OR_COST'):
            gateway.assess(route)
    def test_unknown_notice_type_rejected(self):
        route = copy.deepcopy(self.protocol['routes'][0]); route['notice_type'] = 'AWARDED_CONTRACT'
        with self.assertRaisesRegex(ValueError, 'REGISTERED_ROUTE_CHANGED'):
            gateway.assess(route)
    def test_tampered_payment_receipt_refused(self):
        amended = copy.deepcopy(self.result); amended['actual_collected_revenue_USD'] = 100
        with self.assertRaisesRegex(ValueError, 'DECISION_OR_SOURCE'):
            gateway.audit(amended)
    def test_frozen_evidence_identity(self):
        raw = (gateway.ROOT/'PROTOCOL.json').read_bytes()
        self.assertEqual(gateway.git_blob(raw), gateway.PROTOCOL_GIT_BLOB)
        self.assertEqual(self.result['protocol_sha256'], self.sha)
    def test_run_and_audit_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/'out.json'
            f.write_text(json.dumps(self.result))
            gateway.audit(json.loads(f.read_text()))
            with self.assertRaisesRegex(ValueError, 'FRESH_OUTPUT'):
                import sys
                original = sys.argv
                try:
                    sys.argv = ['gateway', 'run', str(f)]
                    gateway.main()
                finally:
                    sys.argv = original
    def test_cost_completeness_and_competitors_explicit(self):
        self.assertGreaterEqual(len(self.protocol['required_cost_fields']), 14)
        self.assertIn('no purchase', self.protocol['benchmark_alternatives'])
        self.assertIn('recurring_support', self.protocol['required_cost_fields'])

if __name__ == '__main__': unittest.main()
