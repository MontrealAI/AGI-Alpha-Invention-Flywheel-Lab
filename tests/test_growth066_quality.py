import copy
import unittest
from growth066.quality import make_case, verify, DEVELOPMENT_SEEDS, HOLDOUT_SEEDS


class QualityTests(unittest.TestCase):
    def test_constructed_truth_for_all_fixed_seeds(self):
        self.assertFalse(set(DEVELOPMENT_SEEDS)&set(HOLDOUT_SEEDS))
        for seed in DEVELOPMENT_SEEDS+HOLDOUT_SEEDS:
            packet,truth=make_case(seed)
            result=verify(packet,truth['expected'],truth)
            self.assertTrue(result['accepted'],result)
            self.assertEqual(result['matched_groups'],24)
            self.assertEqual(result['reported_exceptions'],14)
    def test_order_is_not_evidence(self):
        packet,truth=make_case(DEVELOPMENT_SEEDS[0]);output=copy.deepcopy(truth['expected'])
        output['matches'].reverse();output['exceptions'].reverse()
        for match in output['matches']:
            match['bank_ids'].reverse();match['payment_ids'].reverse()
        self.assertTrue(verify(packet,output,truth)['accepted'])
    def test_reject_false_match_omission_corruption_reuse_and_boolean_money(self):
        packet,truth=make_case(DEVELOPMENT_SEEDS[0])
        variants=[]
        a=copy.deepcopy(truth['expected']);a['matches'][0]['bank_ids']=['bogus'];variants.append(a)
        a=copy.deepcopy(truth['expected']);a['exceptions'].pop();variants.append(a)
        a=copy.deepcopy(truth['expected']);a['bridge']['closing_balance_cents']+=1;variants.append(a)
        a=copy.deepcopy(truth['expected']);a['matches'].append(copy.deepcopy(a['matches'][0]));variants.append(a)
        a=copy.deepcopy(truth['expected']);a['matches'][0]['fee_cents']=False;variants.append(a)
        a=copy.deepcopy(truth['expected']);a['exceptions'].append(copy.deepcopy(a['exceptions'][0]));variants.append(a)
        a=copy.deepcopy(truth['expected']);a['bridge']['bank_activity_cents']=float('nan');variants.append(a)
        for output in variants:self.assertFalse(verify(packet,output,truth)['accepted'])
    def test_changed_input_requires_new_bound_truth(self):
        packet,truth=make_case(DEVELOPMENT_SEEDS[0]);packet['opening_balance_cents']+=1
        self.assertFalse(verify(packet,truth['expected'],truth)['accepted'])
    def test_balance_bridge_and_coverage(self):
        packet,truth=make_case(DEVELOPMENT_SEEDS[0]);out=truth['expected'];b=out['bridge']
        self.assertEqual(b['opening_balance_cents']+b['bank_activity_cents'],b['closing_balance_cents'])
        self.assertEqual(b['matched_bank_cents']+b['unmatched_bank_cents'],b['bank_activity_cents'])
        self.assertEqual(b['matched_bank_cents']+b['matched_fee_cents']+b['unmatched_payment_gross_cents'],b['payment_gross_cents'])
        codes={e['code'] for e in out['exceptions']}
        self.assertEqual(codes,{'INVALID_CURRENCY','INVALID_DATE','INVALID_INVOICE_REFERENCE','DUPLICATE_BANK_REFERENCE','MISSING_REFERENCE','AMBIGUOUS_AMOUNT','UNMATCHED_BANK','UNMATCHED_PAYMENT','AMOUNT_MISMATCH','UNPAID_INVOICE'})

if __name__=='__main__':unittest.main()
