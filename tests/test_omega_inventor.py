"""Scope, construction, economics, provenance and adversarial integration checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mechanism_harness import inventor as i
from mechanism_harness import inventor_native as n
from mechanism_harness import game_maker as game
from mechanism_harness.game_input import decode, read_input, MAX_BYTES
from adaptive_enterprise.checkers import audit_delivery

ROOT=Path(__file__).resolve().parents[1]


class StrictGameInput(unittest.TestCase):
    def test_duplicate_root_money(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):decode(b'{"opening_cash":100,"opening_cash":0}')
    def test_duplicate_nested_budget(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):decode(b'{"buyer":[{"budget":100,"budget":0}]}')
    def test_duplicate_nested_weight(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):decode(b'{"scenario":{"weight_bps":1,"weight_bps":2}}')
    def test_nonfinite_and_encoding(self):
        for data in (b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1e999}',b'\xff'):
            with self.subTest(data=data), self.assertRaises(ValueError):decode(data)
    def test_depth_and_size(self):
        for data in (b'['*34+b'0'+b']'*34,b' '* (MAX_BYTES+1)):
            with self.assertRaises(ValueError):decode(data)
    def test_file_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a';p.write_bytes(b'{}');q=Path(d)/'b';q.symlink_to(p)
            with self.assertRaises(ValueError):read_input(q)
    def test_legacy_exact_outcome_preserved(self):
        s=json.loads((ROOT/'mechanism_harness/game_maker_fixture.json').read_text())
        r=game.invent(s)
        self.assertEqual(r['winner']['expected_profit'],'41/10')
        self.assertTrue(game.rederive(s,r)['accepted'])
    def test_raw_and_executable_identity(self):
        path=ROOT/'mechanism_harness/game_maker_fixture.json';raw,s=read_input(path)
        r=game.invent(s);r['input_binding']=game.binding(raw,s);r['replay']=game.rederive(s,r,raw)
        self.assertTrue(game.audit_file(path,r)['accepted'])
        with self.assertRaisesRegex(ValueError,'RAW_INPUT_BYTES'):game.rederive(s,r)
        changed=json.dumps(s,sort_keys=True).encode()
        self.assertEqual(decode(changed),s)
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):game.rederive(s,r,changed)
        with patch.object(game,'source_hashes',return_value={'changed':'0'*64}):
            with self.assertRaises(ValueError):game.rederive(s,r,raw)
    def test_raw_audit_cannot_be_downgraded(self):
        path=ROOT/'mechanism_harness/game_maker_fixture.json';raw,s=read_input(path)
        with self.assertRaisesRegex(ValueError,'RAW_FILE_BINDING_REQUIRED'):game.audit_file(path,game.invent(s))
    def test_output_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.json';p.write_bytes(b'existing')
            with self.assertRaises(FileExistsError):game.main([str(ROOT/'mechanism_harness/game_maker_fixture.json'),'--output',str(p)])
            self.assertEqual(p.read_bytes(),b'existing')


class Discovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen=i.learn(i.inputs(i.TRAIN_SEEDS,i.TRAIN_INDICES))
        cls.confirmed=i.confirm(cls.frozen,i.inputs(i.TEST_SEEDS,i.TEST_INDICES))
    def test_entire_grammar_executed(self):
        self.assertEqual(len(self.frozen['development_candidates']),32)
        self.assertTrue(all(s['accepted'] for s in self.frozen['development_candidates']))
    def test_fresh_comparison_is_complete(self):
        c=self.confirmed
        self.assertEqual(c['case_count'],72)
        self.assertEqual(c['old_work'],50304);self.assertEqual(c['new_work'],7008)
        self.assertTrue(c['promoted_in_scope']);self.assertTrue(c['same_content_reuse_ties'])
    def test_acquisition_not_erased(self):
        self.assertEqual(self.frozen['acquisition_work'],200912)
        self.assertEqual(self.confirmed['metered_reuse_break_even_cases'],335)
        self.assertGreater(self.frozen['acquisition_work']+self.confirmed['new_work'],self.confirmed['old_work'])
    def test_confirm_cannot_leak(self):
        with self.assertRaisesRegex(ValueError,'LEAKAGE'):i.confirm(self.frozen,i.inputs(i.TRAIN_SEEDS,i.TRAIN_INDICES))
    def test_frozen_policy_cannot_change(self):
        f=copy.deepcopy(self.frozen);f['policy']['cache_columns']=False
        with self.assertRaisesRegex(ValueError,'FROZEN'):i.confirm(f,i.inputs((88888,),(8,)))
    def test_empty_samples_not_evidence(self):
        with self.assertRaises(ValueError):i.learn([])
        with self.assertRaises(ValueError):i.confirm(self.frozen,[])
    def test_no_generated_code_execution(self):
        for p in (i.policy(['eval']),i.policy(['unit','unit']),{**i.policy(),'command':'touch /tmp/x'}):
            with self.assertRaises(ValueError):i.validate_policy(p)
    def test_missing_information_not_complete(self):
        a=i.execute(i.substrate.synthetic_raw('reconciliation',15,88888),self.frozen['policy'])
        self.assertEqual(a['outcome_scope'],'intake_readiness')
        self.assertFalse(a['useful_outcome']['production_ready'])
    def test_artifact_corruption_rejected_independently(self):
        raw=i.substrate.synthetic_raw('reconciliation',8,88888);a=i.execute(raw,self.frozen['policy'])
        a['normalized_input']['invoices'][0]['amount_cents']+=1
        self.assertFalse(audit_delivery('reconciliation',raw,a)['accepted'])
    def test_output_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            q=Path(d)/'q';q.symlink_to(Path(d),target_is_directory=True)
            with self.assertRaises(ValueError):i.checked_output(q)


class StrategicChoices(unittest.TestCase):
    def test_profit_not_maximum_quote(self):
        d=n.choose(17*n.MICRO,1000*n.MICRO)
        self.assertEqual(d['selected']['quote'],99*n.MICRO)
        self.assertEqual(d['selected']['response']['buyer'],'seller')
    def test_rival_can_erase_advantage(self):
        self.assertIsNone(n.choose(17*n.MICRO,1000*n.MICRO,copycat=True)['selected'])
    def test_no_money_no_order(self):
        self.assertIsNone(n.choose(17*n.MICRO,0)['selected'])
    def test_order_principal_reserve_is_not_spendable(self):
        self.assertIsNone(n.choose(17*n.MICRO,21*n.MICRO)['selected'])
    def test_no_value_no_order(self):
        self.assertIsNone(n.choose(17*n.MICRO,1000*n.MICRO,value=0)['selected'])
    def test_budget_remains_binding(self):
        self.assertIsNone(n.choose(17*n.MICRO,1000*n.MICRO,budget=1)['selected'])
    def test_invalid_money_rejected(self):
        for val in (-1,True,1.5):
            with self.assertRaises(ValueError):n.choose(val,1000)
    def test_expensive_production_may_not_be_sold(self):
        self.assertIsNone(n.choose(500*n.MICRO,1000*n.MICRO)['selected'])


class NativeBridge(unittest.TestCase):
    """A one-order ENGINEERING fixture, not the registered 16-opportunity campaign."""
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='omega-native-unit-');cls.path=Path(cls.tmp.name)
        cls.source=i.source_identity();cls.p=i.policy(('unit','unique','text'),True)
        with patch.object(n,'INDEXES',(8,)):
            cls.result=n.operate(cls.path,cls.p,cls.source,200912)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_native_finance_and_acceptance(self):
        with patch.object(n,'INDEXES',(8,)):
            self.assertTrue(n.audit_operation(self.path,self.result,self.source,self.p)['accepted'])
        self.assertEqual(self.result['settled'],1)
        self.assertLess(self.result['native_summary']['profit'],0) # no false profitable early milestone
    def test_summary_tamper_rejected(self):
        altered=copy.deepcopy(self.result);altered['native_summary']['profit']+=1
        with patch.object(n,'INDEXES',(8,)),self.assertRaisesRegex(ValueError,'SUMMARY_CHANGED'):
            n.audit_operation(self.path,altered,self.source,self.p)
    def test_controller_policy_cannot_be_substituted(self):
        with patch.object(n,'INDEXES',(8,)),self.assertRaisesRegex(ValueError,'UNBOUND'):
            n.audit_operation(self.path,self.result,self.source,i.policy())
    def test_report_count_cannot_inflate(self):
        altered=copy.deepcopy(self.result);altered['settled']+=1
        with patch.object(n,'INDEXES',(8,)),self.assertRaisesRegex(ValueError,'DENOMINATORS'):
            n.audit_operation(self.path,altered,self.source,self.p)
    def test_repeat_operation_does_not_reseed_or_resettle(self):
        before=n.read(self.path/'NATIVE_EXPORT.json')
        with patch.object(n,'INDEXES',(8,)):
            again=n.operate(self.path,self.p,self.source,200912)
        self.assertEqual(again,self.result)
        self.assertEqual(n.read(self.path/'NATIVE_EXPORT.json'),before)


if __name__=='__main__':unittest.main()
