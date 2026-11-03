import copy,json,unittest
from pathlib import Path
from audit import audit,witness

class EvidenceTests(unittest.TestCase):
    def setUp(self):self.d=json.loads((Path(__file__).parent/'evidence/observations.json').read_text())
    def test_saved_data(self):self.assertEqual(audit(self.d)['status'],'PASS')
    def test_missing_case(self):
        self.d['r2']['cases'].pop()
        with self.assertRaises(AssertionError):audit(self.d)
    def test_lost_loss(self):
        self.d['r2']['cases'][0]['cumulative_company_profit_microUSD']=0
        with self.assertRaises(AssertionError):audit(self.d)
    def test_equity_is_not_profit(self):
        self.d['r2']['cases'][0]['final_365_day_company_profit_microUSD']=3_000_000_000_000_000
        with self.assertRaises(AssertionError):audit(self.d)
    def test_removed_obligation(self):
        case=next(x for x in self.d['r2']['cases'] if x['payables_microUSD']>0);case['payables_microUSD']=0
        with self.assertRaises(AssertionError):audit(self.d)
    def test_hidden_control_win(self):
        self.d['foundry']['summary']['all']['conventional']['arithmetic']=999999
        with self.assertRaises(AssertionError):audit(self.d)
    def test_exact_observation_witness(self):self.assertFalse(witness()['absolute_x_stress_identifiable'])
if __name__=='__main__':unittest.main()
