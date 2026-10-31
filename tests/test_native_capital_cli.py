import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeCapitalCLITests(unittest.TestCase):
    def test_existing_matched_comparison_resumes_frozen_accounts(self):
        with tempfile.TemporaryDirectory(prefix='native-capital-compare-resume-') as tmp:
            root = Path(tmp); output = root / 'comparison'
            from connected_enterprise.capital import freeze, register, operate
            frozen = freeze(ROOT, {'arrivals': 3}, output, comparison=True)
            register(output)
            prior = operate(output, max_events=3, business=output / 'arms/recycling_enabled', enabled=True)
            self.assertFalse(prior['complete'])
            keys = list((output / 'arms/recycling_enabled').glob('*simulation-key'))
            inode = keys[0].stat().st_ino
            result = self.command('comparison', '--output', output)
            self.assertEqual(result['schema'], 'agi-alpha/native-capital-comparison/v1')
            final = json.loads((output / 'arms/recycling_enabled/RESULT.json').read_text())
            self.assertEqual(final['source_sha256'], frozen['source']['sha256'])
            self.assertEqual(final['owned_account']['ledger']['actions'][:len(prior['owned_account']['ledger']['actions'])], prior['owned_account']['ledger']['actions'])
            self.assertEqual(keys[0].stat().st_ino, inode)
            self.assertTrue(final['complete'])
            self.assertEqual(result, self.command('comparison', '--output', output))
            self.assertEqual(final['owned_account']['ledger'], json.loads((output / 'arms/recycling_enabled/RESULT.json').read_text())['owned_account']['ledger'])
            self.assertTrue(self.command('audit', '--output', output)['accepted'])

    def command(self, *args):
        result = subprocess.run([sys.executable, '-m', 'connected_enterprise', *map(str, args)],
                                cwd=ROOT, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-3000:])
        return json.loads(result.stdout)

    def frozen_python(self, output, code, *args):
        result = subprocess.run([sys.executable, '-c', code, str(output), *args], cwd=output / 'source',
                                capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout[-3000:])
        return json.loads(result.stdout)

    def test_register_pause_resume_audit_and_scoreboard_keep_one_account(self):
        with tempfile.TemporaryDirectory(prefix='native-capital-cli-') as tmp:
            root = Path(tmp); config = root / 'config.json'; output = root / 'operation'
            config.write_text(json.dumps({'arrivals': 3}))
            self.command('register', '--config', config, '--output', output)
            self.command('operate', '--output', output, '--max-events', 3)
            first = json.loads((output / 'business/RESULT.json').read_text())
            self.assertFalse(first['complete'])
            key = (output / 'business/account.sqlite.adaptive-simulation-key').read_bytes()
            self.command('resume', '--output', output)
            result = json.loads((output / 'business/RESULT.json').read_text())
            self.assertTrue(result['complete'])
            self.assertEqual((output / 'business/account.sqlite.adaptive-simulation-key').read_bytes(), key)
            prefix = first['owned_account']['ledger']['actions']
            self.assertEqual(result['owned_account']['ledger']['actions'][:len(prefix)], prefix)
            self.assertEqual(first['owned_account']['ledger']['config'], result['owned_account']['ledger']['config'])
            checked = self.command('audit', '--output', output)
            self.assertTrue(checked['accepted'])
            score = self.command('scoreboard', '--output', output)
            self.assertEqual(score['settled_orders'], 3)
            self.assertEqual(score['matured_orders'], 3)
            self.assertEqual(score['profitable_earned_continuations'], 2)
            self.assertTrue(score['repeated_earned_financed_expansion'])
            self.assertEqual(score['native_summary']['tailReserve'], 0)
            self.assertIsNone(score['actual_profit'])
            self.assertEqual(score['tax_provisioned_microUSD'], score['tax_cash_paid_microUSD'])
            tampered = '''import json,sys
from pathlib import Path
from connected_enterprise.capital import audit_business
output=Path(sys.argv[1]);path=output/'business/RESULT.json';raw=path.read_bytes();result=json.loads(raw)
result['state']['orders'][0]['accepted_hour']+=1
path.write_text(json.dumps(result))
try:audit_business(output)
except ValueError as error:
 assert 'ACCEPTANCE_TIME' in str(error)
 print(json.dumps({'forged_acceptance_time_rejected':True}))
else:raise AssertionError('forged acceptance hour accepted')
finally:path.write_bytes(raw)
'''
            self.assertTrue(self.frozen_python(output, tampered)['forged_acceptance_time_rejected'])

    def test_after_commit_production_and_tax_interruptions_resume_exact_intents(self):
        code = '''import json,sys
from unittest.mock import patch
from connected_enterprise.capital import operate
from connected_enterprise.finance import JournalAccount
output,boundary=sys.argv[1:]
name='spend' if boundary=='production' else 'cost'
original=getattr(JournalAccount,name)
def interrupted(self,ident,*args,**kwargs):
 result=original(self,ident,*args,**kwargs)
 if (boundary=='production' and ident=='production-capital-order-001') or (boundary=='tax' and ident.startswith('tax-')):
  raise RuntimeError('INJECTED_AFTER_NATIVE_COMMIT')
 return result
try:
 with patch.object(JournalAccount,name,interrupted):operate(output)
except RuntimeError as error:
 assert str(error)=='INJECTED_AFTER_NATIVE_COMMIT'
 print(json.dumps({'injected_after_commit':boundary}))
else:raise AssertionError('fault did not execute')
'''
        for boundary, arrivals in [('production', 2), ('tax', 1)]:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory(prefix='native-capital-interrupt-') as tmp:
                root = Path(tmp); config = root / 'config.json'; output = root / 'operation'
                config.write_text(json.dumps({'arrivals': arrivals}))
                self.command('register', '--config', config, '--output', output)
                self.command('operate', '--output', output, '--max-events', 1)
                self.assertEqual(self.frozen_python(output, code, boundary)['injected_after_commit'], boundary)
                envelope = json.loads((output / 'business/STATE.json').read_text())
                current = envelope['body']['state']['current']
                self.assertIn('decision' if boundary == 'production' else 'tax_intent', current)
                original_intent = current.get('decision', current.get('tax_intent'))
                self.command('resume', '--output', output)
                checked = self.command('audit', '--output', output)
                self.assertTrue(checked['accepted'])
                result = json.loads((output / 'business/RESULT.json').read_text())
                if boundary == 'production':
                    decision = next(d for d in result['state']['decisions'] if d['index'] == 1)
                    self.assertEqual(decision, original_intent)
                    order = next(o for o in result['state']['orders'] if o['index'] == 1)
                    self.assertEqual(order['funding_receipt']['funding'], 'EARNED')
                    entries = result['owned_account']['connected_journal']['entries']
                    production = next(e for e in entries if e['key'] == 'spend:production-' + order['id'])
                    self.assertEqual(production['request']['work']['terms_sha256'], order['terms_sha256'])
                else:
                    self.assertEqual(result['state']['orders'][0]['tax'], original_intent)
                    tax_events = [e for e in result['owned_account']['ledger']['actions'] if e['op'] == 'cost' and e['args']['id'].startswith('tax-')]
                    self.assertEqual(len(tax_events), 1)

    def test_decline_and_registered_claim_omission_are_not_success(self):
        omission = '''import json,sys
from unittest.mock import patch
from connected_enterprise.capital import operate,audit_business
from connected_enterprise.finance import JournalAccount,audit_journal
from commercial.ledger import strict_json
from pathlib import Path
output=Path(sys.argv[1]);original=JournalAccount.execute
def dropped(self,op,args,day):
 return self.snapshot() if op=='claim' else original(self,op,args,day)
with patch.object(JournalAccount,'execute',dropped):result=operate(output)
manifest=strict_json((output/'SERVICES.json').read_bytes())
assert audit_journal(result['owned_account'],root=output/'source',manifest=manifest)['accepted']
try:audit_business(output)
except ValueError as error:
 assert 'REGISTERED_CLAIM_OMITTED' in str(error)
 print(json.dumps({'financial_audit':True,'operating_audit_rejected':str(error)}))
else:raise AssertionError('omitted adverse claim was accepted')
'''
        with tempfile.TemporaryDirectory(prefix='native-capital-failure-') as tmp:
            root = Path(tmp); config = root / 'config.json'; output = root / 'decline'
            config.write_text(json.dumps({'arrivals': 2, 'decline_every': 1}))
            self.command('register', '--config', config, '--output', output)
            self.command('operate', '--output', output)
            score = self.command('scoreboard', '--output', output)
            self.assertEqual(score['settled_orders'], 0)
            self.assertFalse(score['repeated_earned_financed_expansion'])
            config.write_text(json.dumps({'arrivals': 1, 'claims': [{'hour': 3, 'order_index': 0, 'amount': 250_000_000, 'kind': 'provider_default'}]}))
            output = root / 'claim-omission'
            self.command('register', '--config', config, '--output', output)
            verdict = self.frozen_python(output, omission)
            self.assertTrue(verdict['financial_audit'])
            config.write_text(json.dumps({'arrivals': 2, 'claims': [{'hour': 7, 'order_index': 1, 'amount': 250_000_000, 'kind': 'provider_default'}]}))
            output = root / 'claimed-earned-order'
            self.command('register', '--config', config, '--output', output)
            self.command('operate', '--output', output)
            score = self.command('scoreboard', '--output', output)
            self.assertEqual(score['profitable_earned_continuations'], 0)
            self.assertLess(score['funding_lineage'][0]['later_modeled_profit_microUSD'], 0)
            self.assertFalse(score['repeated_earned_financed_expansion'])

    def test_matched_comparison_changes_financing_only(self):
        with tempfile.TemporaryDirectory(prefix='native-capital-comparison-') as tmp:
            root = Path(tmp); config = root / 'config.json'; output = root / 'comparison'
            config.write_text(json.dumps({'arrivals': 5}))
            result = self.command('comparison', '--config', config, '--output', output)
            enabled, disabled = result['arms']['recycling_enabled'], result['arms']['recycling_disabled']
            self.assertEqual(enabled['settled_orders'], 5)
            self.assertEqual(disabled['settled_orders'], 4)
            self.assertGreater(result['profit_delta_microUSD'], 0)
            self.assertEqual(disabled['profitable_earned_continuations'], 0)
            self.assertFalse(result['terms_effect_tested'])
            self.assertFalse(result['capability_effect_tested'])
            checked = self.command('audit', '--output', output)
            self.assertTrue(checked['accepted'])


if __name__ == '__main__':
    unittest.main()
