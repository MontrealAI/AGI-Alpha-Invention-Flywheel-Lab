"""Optimization parity only: these arithmetic tapes are not business qualification."""
import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from commercial.ledger import digest
from connected_enterprise import scale

class SlowObservedFlows:
    """The previous prefix-scan equations, independent of the incremental state."""
    def __init__(self):
        self.actions=[]; self.collections=[]; self.receivables=0; self.trailing_collections=0
    def advance(self, action, collection_delta):
        self.actions.append(action)
        self.receivables=scale._receivables(self.actions)
        if collection_delta:self.collections.append((action['day'],collection_delta))
        self.trailing_collections=sum(amount for hour,amount in self.collections
                                      if action['day']-scale.YEAR_HOURS < hour <= action['day'])

def fixture():
    s={'collections':0,'recoveryIncome':0,'revenue':0,'expenses':0,'expensePaid':0,
       'cash':100000,'profit':0,'payables':0,'tailReserve':0,'custodyReserve':0,
       'workingCapital':0,'unrestrictedEarned':0,'available':100000,
       'equityProtectionBacking':0,'investmentStopped':False}
    actions=[]
    def add(t,op,args,**flows):
        before=copy.deepcopy(s)
        for k,v in flows.items():s[k]+=v
        s['cash']=100000+s['collections']+s['recoveryIncome']-s['expensePaid']
        s['profit']=s['revenue']+s['recoveryIncome']-s['expenses']
        s['available']=s['cash'];s['unrestrictedEarned']=max(0,s['profit'])
        actions.append(dict(seq=len(actions),day=t,op=op,args=args,before=before,after=copy.deepcopy(s)))
    add(0,'cost',{'id':'setup'},expenses=13,expensePaid=13)
    add(0,'offer',{'id':'a','price':101})
    add(0,'event',{'id':'a','action':'prepare'})
    add(1,'event',{'id':'a','action':'release'},collections=101,revenue=101)
    add(1,'offer',{'id':'b','price':207})
    add(1,'event',{'id':'b','action':'prepare'})
    add(2,'event',{'id':'b','action':'commit'})
    add(2,'event',{'id':'b','action':'prepare'})
    add(3,'event',{'id':'b','action':'refund'})
    add(4,'cost',{'id':'negative-correction'},collections=-7,revenue=-7)
    add(8759,'cost',{'id':'incurred-unpaid'},expenses=11,payables=11)
    add(8760,'cost',{'id':'pay'},expensePaid=11,payables=-11)
    add(8761,'cost',{'id':'boundary'},collections=19,revenue=19)
    add(8761,'cost',{'id':'same-time-negative'},collections=-2,revenue=-2)
    add(8764,'cost',{'id':'negative-expired'})
    return dict(config={'opening':100000},actions=actions,actions_sha256=digest(actions),summary=copy.deepcopy(s),receivables=0)

class StreamingObserverTests(unittest.TestCase):
    def test_every_prefix_matches_old_scans_and_year_observer(self):
        original=fixture()
        for n in range(1,len(original['actions'])+1):
            tape=copy.deepcopy(original);tape['actions']=tape['actions'][:n]
            tape['actions_sha256']=digest(tape['actions']);tape['summary']=tape['actions'][-1]['after']
            tape['receivables']=scale._receivables(tape['actions'])
            actual=scale.aggregate_native(tape,checkpoints=(1,2))
            annual=scale.trailing_profit(tape,operating_end_hour=8765,operating_complete=True)
            with patch.object(scale,'_ObservedFlows',SlowObservedFlows):
                self.assertEqual(actual,scale.aggregate_native(tape,checkpoints=(1,2)))
                self.assertEqual(annual,scale.trailing_profit(tape,operating_end_hour=8765,operating_complete=True))
    def test_negative_and_exact_window_boundary(self):
        tape=fixture();result=scale.aggregate_native(tape)
        byday={r['day']:r for r in result['days']}
        self.assertEqual(byday[365]['trailing_365_day_collections_microUSD'],17)
        self.assertEqual(result['collections'][1]['amount'],-7)
    def test_no_prefix_receivable_rescan(self):
        with patch.object(scale,'_receivables',side_effect=AssertionError('quadratic rescan')):
            scale.aggregate_native(fixture())
    def test_nonmonotonic_rejected(self):
        tape=fixture();tape['actions'][5]['day']=0;tape['actions_sha256']=digest(tape['actions'])
        with self.assertRaisesRegex(ValueError,'NONCAUSAL'):scale.aggregate_native(tape)
    def test_unknown_event_rejected(self):
        tape=fixture();tape['actions'][2]['args']['id']='missing';tape['actions_sha256']=digest(tape['actions'])
        with self.assertRaisesRegex(ValueError,'EVENT_WITHOUT'):scale.aggregate_native(tape)
    def test_replaced_offer_and_duplicate_prepare_preserve_scan_semantics(self):
        # Such tapes still require the separate native auditor. Observer parity
        # must not accidentally change its existing arithmetic interpretation.
        fast=scale._ObservedFlows();slow=SlowObservedFlows()
        for op,args in [('offer',{'id':'x','price':9}),('event',{'id':'x','action':'prepare'}),
                        ('event',{'id':'x','action':'prepare'}),('offer',{'id':'x','price':15}),
                        ('event',{'id':'x','action':'prepare'})]:
            action={'op':op,'args':args,'day':0};fast.advance(action,0);slow.advance(action,0)
            self.assertEqual(fast.receivables,slow.receivables)

if __name__=='__main__':unittest.main()
