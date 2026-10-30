import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commercial.ledger import audit as audit_original
from enterprise.contract012 import OwnedFiniteExchange, audit_contract012, FINAL_STATE

ROOT = Path(__file__).resolve().parents[1]


class FiniteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT/'campaign/commercial-010/service/executed-002/manifest.json').read_bytes())
        cls.job = next(j['id'] for j in cls.manifest['jobs'] if j['accepted'])

    def open(self, path, **extra):
        args = dict(root=ROOT, manifest=self.manifest, opening=500_000, working=0,
                    contract='finite012-test', liability_ticks=7, time_unit='hours', arrangement_cost=10_000)
        args.update(extra)
        return OwnedFiniteExchange(path, **args)

    def release(self, ex, ident='one', start=0):
        ex.execute('wallet', {'buyer': ident, 'amount': 400_000}, start)
        ex.execute('offer', {'id': ident, 'buyer': ident, 'price': 400_000,
                            'job_id': self.job, 'deadline': start+100}, start)
        for tick, action in [(start, 'consent'), (start, 'fund'), (start+1, 'prepare'), (start+2, 'release')]:
            ex.execute('event', {'id': ident, 'action': action, 'event_id': ident+'-'+action}, tick)

    def test_costed_finality_releases_native_eligible_cash_and_preserves_revenue(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                ex.execute('arrange', {}, 0)
                ex.execute('cost', {'id': 'production', 'amount': 20_000}, 0)
                self.release(ex)
                before = ex.snapshot()
                delivered = ex.download('one', 'one')
                self.assertEqual(before['tailReserve'], 600_000)
                ex.execute('mature', {'id': 'one', 'event_id': 'mature-one'}, 9)
                after = ex.snapshot()
                self.assertEqual(after['cash'], before['cash'])
                self.assertEqual(after['revenue'], before['revenue'])
                self.assertEqual(after['tailReserve'], 0)
                self.assertEqual(after['available']-before['available'], 600_000)
                self.assertGreater(after['unrestrictedEarned'], before['unrestrictedEarned'])
                self.assertEqual(ex.export()['invoices'][0]['state'], 'PAID')
                self.assertEqual(ex.download('one', 'one'), delivered)
                with self.assertRaises(PermissionError): ex.download('one', 'other-buyer')
                receipt = audit_contract012(ex.export(), root=ROOT, manifest=self.manifest)
                self.assertTrue(receipt['accepted'])
                self.assertEqual(receipt['orders'][0]['state'], FINAL_STATE)

    def test_no_early_release_and_no_reversal_after_finality(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                ex.execute('arrange', {}, 0)
                self.release(ex)
                before = ex.export()
                with self.assertRaisesRegex(ValueError, 'NOT_MATURE'):
                    ex.execute('mature', {'id': 'one', 'event_id': 'too-early'}, 8)
                self.assertEqual(ex.export(), before)
                ex.execute('mature', {'id': 'one', 'event_id': 'mature-one'}, 9)
                before = ex.export()
                with self.assertRaisesRegex(ValueError, 'late reversal state'):
                    ex.execute('event', {'id': 'one', 'action': 'late_reversal', 'event_id': 'late'}, 10)
                self.assertEqual(ex.export(), before)

    def test_pending_refund_cannot_mature(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                ex.execute('arrange', {}, 0)
                self.release(ex)
                ex.execute('event', {'id': 'one', 'action': 'late_reversal', 'event_id': 'reverse'}, 5)
                with self.assertRaisesRegex(ValueError, 'UNDISPUTED_ORDER_REQUIRED'):
                    ex.execute('mature', {'id': 'one', 'event_id': 'mature'}, 9)
                self.assertEqual(ex.snapshot()['tailReserve'], 0)
                self.assertEqual(ex.snapshot()['revenue'], 0)
                self.assertTrue(audit_contract012(ex.export(), root=ROOT, manifest=self.manifest)['accepted'])

    def test_arrangement_required_and_actual_cost_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                with self.assertRaisesRegex(ValueError, 'ARRANGEMENT_REQUIRED'):
                    self.release(ex)
                ex.execute('arrange', {}, 0)
                self.assertEqual(ex.snapshot()['expenses'], 10_000)
                with self.assertRaisesRegex(ValueError, 'already consumed'):
                    ex.execute('arrange', {}, 0)

    def test_tampered_maturity_terms_and_summary_fail_independent_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                ex.execute('arrange', {}, 0)
                self.release(ex)
                ex.execute('mature', {'id': 'one', 'event_id': 'mature'}, 9)
                original = ex.export()
                for change in ['terms', 'summary', 'source']:
                    tape = copy.deepcopy(original)
                    if change == 'terms': tape['config']['terms']['liability_ticks'] = 8
                    elif change == 'summary': tape['summary']['cash'] += 1
                    else: tape['config']['source_hashes']['enterprise/contract012.py'] = '0'*64
                    with self.assertRaises(ValueError):
                        audit_contract012(tape, root=ROOT, manifest=self.manifest)
                with self.assertRaisesRegex(ValueError, 'EXACT_TAPE_CONFIG_REQUIRED'):
                    audit_original(original, root=ROOT, manifest=self.manifest)

    def test_takeover_replays_finality_and_changed_contract_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'account.sqlite'
            with self.open(path) as ex:
                ex.execute('arrange', {}, 0)
                self.release(ex)
                ex.execute('mature', {'id': 'one', 'event_id': 'mature'}, 9)
                expected = ex.export()
                with self.assertRaisesRegex(ValueError, 'TAPE_ALREADY_OWNED'):
                    self.open(path)
            with self.open(path) as ex:
                self.assertEqual(ex.export(), expected)
            with self.assertRaisesRegex(ValueError, 'CONFIGURATION_MISMATCH'):
                self.open(path, liability_ticks=8)
            with self.open(path) as ex:
                self.assertEqual(ex.export(), expected)

    def test_duplicate_finality_cannot_release_same_cash_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                ex.execute('arrange', {}, 0)
                self.release(ex)
                args = {'id': 'one', 'event_id': 'mature'}
                ex.execute('mature', args, 9)
                expected = ex.snapshot()
                ex.execute('mature', args, 9)
                self.assertEqual(ex.snapshot(), expected)
                with self.assertRaisesRegex(ValueError, 'UNDISPUTED_ORDER_REQUIRED'):
                    ex.execute('mature', {'id': 'one', 'event_id': 'mature-again'}, 9)
                self.assertTrue(audit_contract012(ex.export(), root=ROOT, manifest=self.manifest)['accepted'])

    def test_acknowledged_finality_recovers_after_process_exit_without_checkpoint(self):
        code = '''
import json,os,sys
from pathlib import Path
from enterprise.contract012 import OwnedFiniteExchange
root,path=Path(sys.argv[1]),Path(sys.argv[2])
manifest=json.loads((root/'campaign/commercial-010/service/executed-002/manifest.json').read_bytes())
job=next(j['id'] for j in manifest['jobs'] if j['accepted'])
ex=OwnedFiniteExchange(path,root=root,manifest=manifest,opening=500000,working=0,contract='finite012-test',liability_ticks=7,time_unit='hours',arrangement_cost=10000)
ex.execute('arrange',{},0)
ex.execute('wallet',{'buyer':'one','amount':400000},0)
ex.execute('offer',{'id':'one','buyer':'one','price':400000,'job_id':job,'deadline':100},0)
for tick,action in [(0,'consent'),(0,'fund'),(1,'prepare'),(2,'release')]:
 ex.execute('event',{'id':'one','action':action,'event_id':'one-'+action},tick)
ex.execute('mature',{'id':'one','event_id':'mature'},9)
os._exit(0)
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'account.sqlite'
            subprocess.run([sys.executable, '-c', code, str(ROOT), str(path)], cwd=ROOT, check=True)
            self.assertFalse(path.exists())
            with self.open(path) as restored:
                self.assertEqual(restored.snapshot()['tailReserve'], 0)
                self.assertEqual(restored.snapshot()['revenue'], 400_000)
                self.assertEqual(restored.snapshot()['expenses'], 10_000)
                self.assertEqual(restored.export()['orders'][0]['state'], FINAL_STATE)
                self.assertTrue(audit_contract012(restored.export(), root=ROOT, manifest=self.manifest)['accepted'])

    def test_integer_positive_duration_and_explicit_cost_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index, extra in enumerate([{'liability_ticks': 0}, {'liability_ticks': True}, {'arrangement_cost': 0}, {'time_unit': 'months'}]):
                with self.assertRaises(ValueError): self.open(Path(tmp)/f'bad-{index}.sqlite', **extra)

    def test_finality_cash_is_reserved_through_current_native_allocation_gate(self):
        from enterprise.finance012 import AuditedAllocation
        with tempfile.TemporaryDirectory() as tmp:
            with self.open(Path(tmp)/'account.sqlite') as ex:
                ex.execute('arrange', {}, 0)
                self.release(ex)
                gate = AuditedAllocation(ex, root=ROOT, manifest=self.manifest,
                                         allocation_id='finite-test', cap=400_000)
                before = gate.observe()
                ex.execute('mature', {'id': 'one', 'event_id': 'mature'}, 9)
                observed = gate.observe()
                self.assertGreater(observed['summary']['unrestrictedEarned'], before['summary']['unrestrictedEarned'])
                plan = gate.plan('new-capacity', 300_000, 50_000,
                                 intent={'qualified': 'test-resource'}, observation=observed)
                gate.reserve(plan, 9)
                self.assertEqual(ex.snapshot()['reservedInvestment'], 300_000)
                gate.finish(plan, 300_000, '0'*64, 9)
                self.assertEqual(ex.snapshot()['reservedInvestment'], 0)
                self.assertTrue(audit_contract012(ex.export(), root=ROOT, manifest=self.manifest)['accepted'])


if __name__ == '__main__': unittest.main()
