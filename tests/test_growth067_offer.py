"""Independent complete-offer controls; no economic accounts or real records."""
import copy
import unittest
from growth066.quality import HOLDOUT_SEEDS, make_case, digest
from growth067.offer import produce
from growth067.acceptance import verify


class OfficeAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.packet, self.truth = make_case(HOLDOUT_SEEDS[0])
        self.output = produce(self.packet)
    def test_all_six_same_grammar_heldout_packets(self):
        for seed in HOLDOUT_SEEDS:
            packet, truth = make_case(seed)
            with self.subTest(seed=seed):
                self.assertTrue(verify(packet, produce(packet), truth)['accepted'])
    def test_false_posting_even_when_balanced_is_rejected(self):
        out = copy.deepcopy(self.output)
        out['draft_postings'][0]['debits'][0]['cents'] += 1
        out['draft_postings'][0]['credits'][0]['cents'] += 1
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
    def test_unbalanced_posting_and_false_invoice_link_rejected(self):
        out = copy.deepcopy(self.output)
        out['draft_postings'][0]['debits'][0]['cents'] += 1
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
        out = copy.deepcopy(self.output)
        out['receivables_open_items'][0]['payment_ids'] = ['NONEXISTENT_PAYMENT']
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
        out = copy.deepcopy(self.output)
        out['receivables_open_items'][0]['open_balance_cents'] += 1
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
        out = copy.deepcopy(self.output)
        out['support_response']['duplicate_record_ids'] = []
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
    def test_omitted_invoice_and_handoff_rejected(self):
        for field in ('receivables_open_items', 'exception_handoff', 'draft_postings'):
            out = copy.deepcopy(self.output); out[field].pop()
            with self.subTest(field=field):
                self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
    def test_unapproved_resolution_or_posting_rejected(self):
        out = copy.deepcopy(self.output)
        out['exception_handoff'][0]['disposition'] = 'RESOLVED_AUTOMATICALLY'
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
        out = copy.deepcopy(self.output); out['draft_postings'][0]['status'] = 'POSTED'
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
    def test_wrong_human_report_and_support_rejected(self):
        for field in ('management_summary', 'support_response'):
            out = copy.deepcopy(self.output)
            if field == 'management_summary': out[field]['totals']['open_balance_cents'] += 100
            else: out[field]['answer'] = 'Duplicates were deleted and all invoices are bank-cleared.'
            with self.subTest(field=field):
                self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
    def test_bool_money_and_false_intake_rejected(self):
        out = copy.deepcopy(self.output); out['receivables_open_items'][0]['open_balance_cents'] = False
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
        out = copy.deepcopy(self.output); out['intake']['source_rows'] += 1
        self.assertFalse(verify(self.packet, out, self.truth)['accepted'])
    def test_authorized_source_amendment_requires_current_output_and_truth(self):
        amended = copy.deepcopy(self.packet)
        amended['invoices'][0]['amount_cents'] += 123
        truth = copy.deepcopy(self.truth)
        # Invoice face-value amendment does not change the independently known
        # settlement matching or cash bridge, but it changes receivables balances.
        truth['input_sha256'] = digest(amended)
        revised = produce(amended)
        self.assertFalse(verify(amended, self.output, truth)['accepted'])
        self.assertFalse(verify(amended, revised, self.truth)['accepted'])
        self.assertTrue(verify(amended, revised, truth)['accepted'])
        self.assertEqual(revised['management_summary']['totals']['open_balance_cents'] - self.output['management_summary']['totals']['open_balance_cents'], 123)


if __name__ == '__main__':
    unittest.main()
