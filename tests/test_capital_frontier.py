"""Capital identities and inverse constraints, not commerce or provider qualification."""
import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from connected_enterprise.capital_frontier import diagnose, required_tail_release, settled_cost_bound
from vendor.alpha_claim.protected_exchange import ProtectedExchange

ROOT = Path(__file__).resolve().parents[1]


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ex = ProtectedExchange(Path(self.tmp.name)/'test.sqlite', key=b'X'*32,
            contract='synthetic-capital-diagnostics-only', validate=lambda x: None,
            check=lambda t,a: {'accepted': True}, opening=100_000_000, working=1_000_000)
        self.opening = self.ex.opening

    def tearDown(self):
        self.ex.close(); self.tmp.cleanup()

    def fixture(self, paid=60_000_000, price=200_000_000):
        self.ex._entry('fixture', 'expense', paid)
        self.ex._entry('fixture', 'expense_paid', paid)
        self.ex._entry('fixture', 'revenue', price)
        self.ex._entry('fixture', 'collections', price)
        self.ex.db.execute("INSERT INTO trades(id,buyer,price,rail,task,task_hash,contract,deadline,state) VALUES(?,?,?,?,?,?,?,?,?)",
            ('fixture','fixture',str(price),'nonrecourse-simulated','{}','fixture','fixture',1,'released'))
        return self.ex.snapshot()

    def test_native_empty_account_has_no_earnings(self):
        r=diagnose(self.opening, self.ex.snapshot())
        self.assertEqual(r['available'],99_000_000); self.assertEqual(r['unrestrictedEarned'],0)

    def test_profit_and_liquidity_have_distinct_directions(self):
        s=self.fixture();r=diagnose(self.opening,s)
        self.assertEqual(s['profit'],140_000_000)
        self.assertEqual(r['available'],38_800_000)
        self.assertEqual(r['tail_minus_collections_microUSD'],200_000)

    def test_higher_price_alone_does_not_create_available_cash(self):
        low=diagnose(self.opening,self.fixture())
        self.ex._entry('higher','collections',50_000_000); self.ex._entry('higher','revenue',50_000_000)
        self.ex.db.execute("UPDATE trades SET price='250000000' WHERE id='fixture'")
        high=diagnose(self.opening,self.ex.snapshot())
        self.assertEqual(low['available'],high['available'])
        self.assertEqual(high['profit_microUSD']-low['profit_microUSD'],50_000_000)

    def test_fee_and_cost_bound_for_article_example(self):
        r=settled_cost_bound(5_000_000_000,100_000_000,80_000_000,5_030_000)
        self.assertEqual(r['maximum_paid_jobs_upper_bound'],921)
        self.assertIs(r['execution_authorized'],False)

    def test_unknown_cost_is_not_zero(self):
        r=settled_cost_bound(100,1,1,None,tail_fee=0)
        self.assertIsNone(r['maximum_paid_jobs_upper_bound'])

    def test_zero_cost_lower_bound_is_not_assumed(self):
        with self.assertRaises(ValueError): settled_cost_bound(100,1,1,0,tail_fee=0)

    def test_initial_obligations_cannot_be_ignored(self):
        self.assertEqual(settled_cost_bound(2,2,1,1)['status'],'INITIAL_OBLIGATIONS_UNFUNDED')

    def test_minimum_release_is_exact_to_one_microdollar(self):
        s=self.fixture();r=required_tail_release(self.opening,s,50_000_000)
        self.assertEqual(r['release_microUSD'],11_200_000)
        self.assertEqual(r['hypothetical_funding']['unrestrictedEarned'],50_000_000)
        self.assertEqual(s,self.ex.snapshot())

    def test_arrangement_cost_is_paid_not_ignored(self):
        s=self.fixture();r=required_tail_release(self.opening,s,50_000_000,added_cost=2_000_000)
        self.assertEqual(r['release_microUSD'],13_200_000)

    def test_unfunded_arrangement_refuses(self):
        s=self.fixture();r=required_tail_release(self.opening,s,50_000_000,added_cost=40_000_000)
        self.assertEqual(r['status'],'ARRANGEMENT_NOT_UPFRONT_FUNDED')

    def test_release_cannot_manufacture_earned_cash(self):
        s=self.fixture();r=required_tail_release(self.opening,s,150_000_000)
        self.assertEqual(r['status'],'TAIL_RELEASE_ALONE_INSUFFICIENT')

    def test_financeable_commitment_needs_no_release(self):
        self.assertEqual(required_tail_release(self.opening,self.fixture(),10_000_000)['release_microUSD'],0)

    def test_breach_stop_cannot_be_removed_by_this_instrument(self):
        self.fixture();self.ex._entry('breach','breach',1)
        r=required_tail_release(self.opening,self.ex.snapshot(),1)
        self.assertEqual(r['status'],'BREACH_STOP_REQUIRES_SEPARATE_REQUALIFICATION')

    def test_existing_reservations_remain_restricted(self):
        self.fixture();self.ex.reserve_investment('other',20_000_000,1,intent_hash='a'*64)
        s=self.ex.snapshot();r=required_tail_release(self.opening,s,30_000_000)
        self.assertEqual(r['release_microUSD'],11_200_000)
        self.assertEqual(s['reservedInvestment'],20_000_000)

    def test_working_capital_and_custody_cannot_be_released(self):
        self.ex.db.execute("INSERT INTO trades(id,buyer,price,rail,task,task_hash,contract,deadline,state,custody) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ('custody','b','99000000','nonrecourse-simulated','{}','h','t',1,'funded',1))
        self.ex._entry('fixture','collections',50_000_000);self.ex._entry('fixture','revenue',50_000_000)
        s=self.ex.snapshot();r=required_tail_release(self.opening,s,60_000_000)
        self.assertEqual(r['status'],'TAIL_RELEASE_ALONE_INSUFFICIENT')
        self.assertEqual(s,self.ex.snapshot())

    def test_native_payables_recovery_and_reservations(self):
        self.fixture();self.ex._entry('unpaid','expense',7_000_000)
        self.ex._entry('recovery','recovery_income',3_000_000)
        r=diagnose(self.opening,self.ex.snapshot())
        self.assertEqual(r['available'],34_800_000)

    def test_separate_investment_paid_must_be_supplied(self):
        self.fixture();self.ex._entry('legacy','investment_paid',1)
        with self.assertRaisesRegex(ValueError,'CASH_IDENTITY'): diagnose(self.opening,self.ex.snapshot())
        diagnose(self.opening,self.ex.snapshot(),investment_paid=1)

    def test_boolean_float_and_negative_inputs_refuse(self):
        s=self.fixture()
        for v in [True,1.5,-1]:
            with self.subTest(v=v),self.assertRaises(ValueError): diagnose(v,s)
            with self.subTest(v=v),self.assertRaises(ValueError): required_tail_release(self.opening,s,v)

    def test_forged_profit_and_available_refuse(self):
        s=self.fixture()
        for key in ['cash','profit','available','unrestrictedEarned','netEarnedAfterIncurredObligations']:
            bad=copy.deepcopy(s);bad[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError): diagnose(self.opening,bad)

    def test_missing_native_fields_refuse(self):
        s=self.fixture();del s['tailReserve']
        with self.assertRaises(ValueError): diagnose(self.opening,s)

    def test_arithmetic_is_not_authentication_or_execution(self):
        s=self.fixture();r=diagnose(self.opening,s)
        self.assertFalse(r['native_authentication_performed']);self.assertFalse(r['execution_authorized'])

    def test_120_random_native_snapshots_and_inverse_closed_form(self):
        for seed in range(120):
            rng=random.Random(seed)
            self.ex.db.execute('DELETE FROM journal');self.ex.db.execute('DELETE FROM trades')
            self.ex.db.execute('DELETE FROM investments')
            price=rng.randrange(1,400)*1_000_000; paid=rng.randrange(0,90)*1_000_000
            s=self.fixture(paid,price)
            if seed%3==0:self.ex._entry('unpaid','expense',3_000_000)
            if seed%5==0:self.ex._entry('recovery','recovery_income',2_000_000)
            s=self.ex.snapshot();diagnose(self.opening,s)
            cost=rng.randrange(0,3)*1_000_000; target=rng.randrange(1,200)*1_000_000
            actual=required_tail_release(self.opening,s,target,added_cost=cost)
            if cost>s['available']:
                self.assertEqual(actual['status'],'ARRANGEMENT_NOT_UPFRONT_FUNDED');continue
            net=s['collections']-s['expensePaid']-s['payables']-cost
            equity=max(0,self.opening+s['recoveryIncome']+min(0,net))
            protection=s['tailReserve']+s['custodyReserve']+s['workingCapital']
            threshold=min(s['cash']-cost-s['payables']-target,equity+max(0,net)-target)
            expected=max(0,protection-threshold)
            if net<target or expected>s['tailReserve']:
                self.assertIsNone(actual['release_microUSD'])
            else:self.assertEqual(actual['release_microUSD'],expected)

    def test_cli_exclusive_output_and_no_simulation_scope_upgrade(self):
        s=self.fixture();p=Path(self.tmp.name);f=p/'input.json';o=p/'result.json'
        data=dict(scope='SIMULATED',currency='simulated-microUSD',opening=self.opening,investment_paid=0,summary=s)
        f.write_text(json.dumps(data));cmd=[sys.executable,'-m','connected_enterprise.capital_frontier','--input',str(f),'--output',str(o),'--commitment-microUSD','50000000']
        first=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(first.returncode,0,first.stderr);raw=o.read_bytes()
        again=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(again.returncode,2);self.assertEqual(o.read_bytes(),raw)
        data['scope']='OBSERVED';f.write_text(json.dumps(data));o.unlink()
        third=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(third.returncode,2);self.assertFalse(o.exists())


if __name__ == '__main__':unittest.main()
