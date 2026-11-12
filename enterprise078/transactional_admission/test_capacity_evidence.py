import copy
import unittest
from .capacity_evidence import inspect


class CapacityEvidenceTests(unittest.TestCase):
    def setUp(self):
        r=dict(operation='spend',kind='capacity-lease',id='lease',amount=2500,
               day=4,expected_net=2500,allow_seed=False,work={'units':1})
        self.account={'connected_journal':{'entries':[dict(request=r,status='COMPLETE',
                      receipt=dict(amount=2500,id='lease',funding='EARNED'))]}}
        c={k:v for k,v in r.items() if k not in ('operation','id')};c['ident']='lease'
        self.state={'events':[dict(commands=[dict(op='spend',args=c)]),
                     dict(commands=[],decision='CAPACITY_UNAVAILABLE_NO_CONTACT_OR_ORDER')]}
    def test_uncontacted_not_demand(self):
        r=inspect(self.account,self.state)
        self.assertEqual(r['qualified_demand_from_skipped_rows'],0)
        self.assertEqual(r['capacity_paid_microUSD'],2500)
        self.assertIsNone(r['counterfactual_profit'])
    def test_changed_cost_refused(self):
        self.state['events'][0]['commands'][0]['args']['amount']+=1
        with self.assertRaisesRegex(ValueError,'COMMAND_MISMATCH'):inspect(self.account,self.state)
    def test_duplicate_command_refused(self):
        self.state['events'].append(copy.deepcopy(self.state['events'][0]))
        with self.assertRaisesRegex(ValueError,'UNIQUE_CAPACITY'):inspect(self.account,self.state)
    def test_unpaid_lease_refused(self):
        self.account['connected_journal']['entries'][0]['status']='PENDING'
        with self.assertRaisesRegex(ValueError,'NOT_COMPLETE'):inspect(self.account,self.state)
    def test_contradictory_response_refused(self):
        self.state['events'][1]['buyer_response']={'accepted':True}
        with self.assertRaisesRegex(ValueError,'UNCONTACTED_ROW'):inspect(self.account,self.state)


if __name__=='__main__':unittest.main()
