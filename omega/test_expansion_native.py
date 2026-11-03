import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from omega.expansion_native import NativeBridge,default_config,audit_output,CENT,validate_config
ROOT=Path(__file__).resolve().parents[1]

def order(ident='one',hour=1,**changes):
    return dict({'id':ident,'buyer':ident+'-buyer','budget_cents':50000,'price_cents':29900,'hour':hour,
                 'choice':True,'acquired':True,'pay':True,'accept':True,'delivery_ok':True,'collection_delay_hours':0},**changes)

class NativeExpansionTests(unittest.TestCase):
    def test_individual_orders_costs_acceptance_budget_and_full_year(self):
        with tempfile.TemporaryDirectory() as tmp:
            with NativeBridge(Path(tmp)/'account') as b:
                before=b.snapshot()
                for ident,change,status in [('decline',{'choice':False},'declined'),('poor',{'budget_cents':200},'declined'),
                                           ('unpaid',{'pay':False},'nonpayment'),('bad',{'accept':False},'refunded'),
                                           ('missing',{'delivery_ok':False},'refunded'),('okay',{},'released')]:
                    result=b.deliver(order(ident,**change));self.assertEqual(result['status'],status)
                    snap=b.snapshot();self.assertEqual(b.deliver(order(ident,**change)),result);self.assertEqual(snap,b.snapshot())
                result=b.finish()
                self.assertTrue(result['accepted']);self.assertTrue(result['rolling_year']['complete_365_day_operating_history'])
                self.assertEqual(result['summary']['collections'],29900*CENT)
                self.assertEqual(result['summary']['payables'],0)
                self.assertGreater(result['tax']['paid_microUSD'],0)
                self.assertEqual(result['tax']['incurred_microUSD'],result['tax']['paid_microUSD'])
            self.assertTrue(audit_output(Path(tmp)/'account')['accepted'])

    def test_delayed_collection_profit_is_not_spendable_cash(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=default_config();cfg.update(opening_cents=32000,engineering_fixture=True,income_tax_bps=0)
            with NativeBridge(Path(tmp)/'account',config=cfg) as b:
                b.deliver(order('settled'))
                r=b.deliver(order('one',hour=2,collection_delay_hours=48));self.assertEqual(r['status'],'accepted_uncollected')
                self.assertGreater(b.snapshot()['profit_cents'],0)
                self.assertFalse(b.spend('too-large',30000,3,'research',allow_seed=False))
                b.advance(50);self.assertTrue(b.order_receipt('one')['collected'])
                self.assertEqual(b.order_receipt('one')['status'],'released')

    def test_seed_remains_available_after_earning(self):
        with tempfile.TemporaryDirectory() as tmp:
            with NativeBridge(Path(tmp)/'account') as b:
                b.deliver(order());s=b.snapshot()
                amount=s['unrestricted_earned_cents']+1000
                self.assertLess(amount,s['available_cents'])
                self.assertTrue(b.spend('seed-and-earnings',amount,2,'capacity',allow_seed=True))
                self.assertEqual(b.state['spends']['seed-and-earnings']['receipt']['funding'],'SEED')

    def test_interrupted_fund_restarts_same_account_without_intervening_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);request=p/'order.json';request.write_text(json.dumps(order()))
            account=p/'account'
            crashed=subprocess.run([sys.executable,'-m','omega.expansion_native','--output',str(account),'--order-json',str(request),'--interrupt-after','fund'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(crashed.returncode,75,crashed.stderr)
            tape=(account/'account.sqlite.actions.jsonl').read_bytes()
            completed=subprocess.run([sys.executable,'-m','omega.expansion_native','--output',str(account),'--resume'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertTrue((account/'account.sqlite.actions.jsonl').read_bytes().startswith(tape))
            result=json.loads((account/'RESULT.json').read_text());self.assertEqual(result['summary']['collections'],29900*CENT)
            with NativeBridge(account,resume=True) as b:
                before=b.account.export()['ledger']['actions_sha256'];b.finish();self.assertEqual(before,b.account.export()['ledger']['actions_sha256'])

    def test_sequential_cash_feasible_pair_is_not_whole_cohort_prefunded(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=default_config();cfg.update(opening_cents=32000,engineering_fixture=True,claim_hours=1,income_tax_bps=0)
            with NativeBridge(Path(tmp)/'account',config=cfg) as b:
                # Both full order commitments exceed the opening capital together.
                self.assertGreater(2*(29900+998+20),32000)
                self.assertEqual(b.deliver(order('first',hour=1))['status'],'released')
                # Qualified maturity releases protection; it is not income.
                before=b.snapshot()['profit_cents'];b.advance(3)
                self.assertEqual(b.snapshot()['profit_cents'],before)
                self.assertEqual(b.deliver(order('second',hour=3))['status'],'released')
                self.assertEqual(b.account.snapshot()['summary']['collections'],59800*CENT)

    def test_chunked_restart_and_sequential_native_execution_are_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);orders=[order('first'),order('second',hour=2)]
            with NativeBridge(p/'batch') as b:
                for r in orders:b.deliver(r)
                batch=b.finish()
            with NativeBridge(p/'chunks') as b:b.deliver(orders[0])
            with NativeBridge(p/'chunks',resume=True) as b:
                b.deliver(orders[1]);chunk=b.finish()
            self.assertEqual(batch['summary'],chunk['summary'])
            left=json.loads((p/'batch'/'PUBLIC_ACCOUNT.json').read_text())['ledger']['actions']
            right=json.loads((p/'chunks'/'PUBLIC_ACCOUNT.json').read_text())['ledger']['actions']
            self.assertEqual([(a['op'],a['day'],a['before'],a['after']) for a in left],[(a['op'],a['day'],a['before'],a['after']) for a in right])

    def test_crash_after_tax_keeps_native_contribution_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);request=p/'order.json';request.write_text(json.dumps(order()))
            with NativeBridge(p/'baseline') as b:
                expected=b.deliver(order())['contribution_cents'];b.finish()
            interrupted=subprocess.run([sys.executable,'-m','omega.expansion_native','--output',str(p/'crash'),'--order-json',str(request),'--interrupt-after','tax'],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(interrupted.returncode,75,interrupted.stderr)
            with NativeBridge(p/'crash',resume=True) as b:
                self.assertEqual(b.order_receipt('one')['contribution_cents'],expected)
                b.finish()

    def test_grouped_invoice_and_individual_components_preserve_financial_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            results=[]
            for grouped in (False,True):
                c=default_config();c['cost_batching']=grouped
                with NativeBridge(Path(tmp)/str(grouped),config=c) as b:
                    for r in (order('a'),order('b',hour=2,accept=False),order('c',hour=3,pay=False)):
                        b.deliver(r)
                    results.append(b.finish())
            self.assertEqual(results[0]['summary'],results[1]['summary'])
            self.assertEqual(results[0]['rolling_year']['trailing_365_day_profit_microUSD'],results[1]['rolling_year']['trailing_365_day_profit_microUSD'])
            self.assertEqual([r['status'] for r in results[0]['orders'].values()],[r['status'] for r in results[1]['orders'].values()])

    def test_configuration_rejects_invalid_probabilities_and_silent_new_seed(self):
        for changes in ({'income_tax_bps':10001},{'payment_bps':-1},{'opening_cents':1},{'residual_bps':True}):
            c=default_config();c.update(changes)
            with self.assertRaises(ValueError):validate_config(c)

if __name__=='__main__':unittest.main()
