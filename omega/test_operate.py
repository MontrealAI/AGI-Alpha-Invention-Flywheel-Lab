"""Native execution/replay, refusal, complete costs and report-tampering tests."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from commercial.ledger import canonical, strict_json
from omega import operate, strategy

class OperateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/'run'
        game=strategy.make_game(quarters=1,costs=replace(strategy.Costs(),packaging_hours=0))
        cls.result=operate.run(cls.path,game=game,modes=('static_all','nonentry'))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_native_acceptance_refund_nonentry_and_public_replay(self):
        rows=self.result['accounts']
        self.assertEqual(len(rows),32)
        self.assertGreater(sum(r['accepted_orders'] for r in rows),0)
        self.assertGreater(sum(r['refunded_orders'] for r in rows),0)
        self.assertTrue(all(r['native_summary_microUSD']['collections']==0 for r in rows if r['policy_mode']=='nonentry'))
        self.assertEqual(canonical(operate.replay(self.path)),canonical(self.result))
    def test_account_destination_cannot_reset(self):
        with self.assertRaises(FileExistsError):operate.run(self.path)
    def test_profit_and_trace_tampering_rejected(self):
        path=self.path/'result.json';original=path.read_bytes()
        try:
            for field in ('profit','trace'):
                data=strict_json(original)
                if field=='profit':data['accounts'][0]['economic_profit_cents']+=1
                else:data['accounts'][0]['trace']['trace'][0]['cost_cents']+=1
                path.write_bytes(canonical(data))
                with self.assertRaisesRegex(ValueError,'REPORT_CHANGED'):operate.replay(self.path)
        finally:path.write_bytes(original)
    def test_source_tampering_rejected(self):
        path=self.path/'source/omega/strategy.py';original=path.read_bytes()
        try:
            path.write_bytes(original+b'\n# altered\n')
            with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):operate.replay(self.path)
        finally:path.write_bytes(original)

if __name__=='__main__':unittest.main()
