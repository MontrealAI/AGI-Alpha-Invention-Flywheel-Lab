import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from adaptive_enterprise.instruments import prepare_services
from adaptive_enterprise.model import stable_projection
from adaptive_enterprise.runner import source_paths as adaptive_source_paths
from commercial.ledger import digest
from connected_enterprise.engine import default_config, run_world
from connected_enterprise.finance import SOURCE_PATHS as FINANCE_SOURCE_PATHS

ROOT = Path(__file__).resolve().parents[1]


def stable(result):
    result = copy.deepcopy(result)
    result.pop('resource_receipt', None)
    result = stable_projection(result)
    journal = result.get('owned_account', {}).get('connected_journal')
    if isinstance(journal, dict):
        for entry in journal.get('entries', []):
            attempt = entry.get('attempt')
            if isinstance(attempt, dict) and 'account_record_sha256' in attempt:
                # This full export digest commits private HMAC signatures and the
                # local filesystem label. Live/restart/public guards retain it;
                # separate owners compare every other semantic field here.
                attempt['account_record_sha256'] = 'LOCAL_ACCOUNT_AUTHORITY_WITNESS'
        result['owned_account']['connected_journal_sha256'] = digest(journal)
    return result


class ConnectedStableProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_connected_finance import ConnectedFinanceTests as Fixture
        Fixture.setUpClass()
        cls.results = []
        cls.keys_differ = False
        keys = []
        try:
            for _ in range(2):
                fixture = Fixture(); fixture.setUp()
                try:
                    keys.append(fixture.account._account._key)
                    fixture.earn(); fixture.spend()
                    fixture.account.cost('after-earned-proof', 7, 2)
                    cls.results.append({'owned_account': fixture.account.export()})
                finally:
                    fixture.tearDown()
            cls.keys_differ = keys[0] != keys[1]
        finally:
            Fixture.tearDownClass()

    def test_independent_owner_certificates_keep_same_financial_result(self):
        first, second = self.results
        self.assertTrue(self.keys_differ)
        self.assertNotEqual(first['owned_account']['connected_journal_sha256'], second['owned_account']['connected_journal_sha256'])
        self.assertEqual(first['owned_account']['ledger'], second['owned_account']['ledger'])
        self.assertEqual(stable(first), stable(second))

    def test_financial_and_native_certificate_or_obligation_changes_remain_visible(self):
        original = self.results[0]
        account = original['owned_account']
        plan_id = next(iter(account['obligation_resolutions']))
        index = len(account['connected_journal']['entries']) - 1
        mutations = [lambda a: a['ledger']['summary'].__setitem__('cash', a['ledger']['summary']['cash'] + 1),
                     lambda a: a['ledger']['actions'][-1]['args'].__setitem__('amount', 8),
                     lambda a: a['obligation_resolutions'][plan_id].__setitem__('upfront_incurred_microUSD', 1),
                     lambda a: a['connected_journal']['entries'][index]['request']['args'].__setitem__('amount', 8)]
        for field in ['native_record_sha256', 'native_state_digest', 'native_actions_sha256', 'request_sha256', 'durable_tape_sha256']:
            mutations.append(lambda a, field=field: a['connected_journal']['entries'][index]['attempt'].__setitem__(field, '0' * 64))
        for mutation in mutations:
            changed = copy.deepcopy(original); mutation(changed['owned_account'])
            with self.subTest(mutation=mutation):
                self.assertNotEqual(stable(changed), stable(original))

    def test_filesystem_label_and_its_full_account_witness_are_owner_local(self):
        changed = copy.deepcopy(self.results[0])
        changed['owned_account']['snapshot']['filesystem'] = 'authored-other-local-filesystem'
        changed['owned_account']['connected_journal']['entries'][-1]['attempt']['account_record_sha256'] = 'f' * 64
        self.assertEqual(stable(changed), stable(self.results[0]))


class ConnectedEngineRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='connected014-engine-fixture-')
        cls.root = Path(cls.fixture.name) / 'source'
        names = set(adaptive_source_paths(ROOT)) | set(FINANCE_SOURCE_PATHS)
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'connected_enterprise').glob('*.py'))
        for name in sorted(names):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.source = {'files': {name: hashlib.sha256((cls.root / name).read_bytes()).hexdigest() for name in sorted(names)}}
        cls.source['sha256'] = digest(cls.source['files'])
        cls.manifest = prepare_services(cls.root, 'service-inputs', cohort_seed=341014)
        cls.manifest_path = Path(cls.fixture.name) / 'MANIFEST.json'
        cls.manifest_path.write_text(json.dumps(cls.manifest))
        cls.config = default_config()
        cls.config.update(horizon_days=14, customer_pool=8, setup_cost=10_000_000,
                          arrival_bps=10000, retention_bps=10000, nonpayment_bps=0)
        cls.config['channels']['pilot'].update(price_microUSD=1_000_000,
                                              activation_reliability_bps=10000,
                                              realization_bps=10000, overlap_bps=0)
        cls.config_path = Path(cls.fixture.name) / 'CONFIG.json'
        cls.config_path.write_text(json.dumps(cls.config))
        cls.source_path = Path(cls.fixture.name) / 'SOURCE.json'
        cls.source_path.write_text(json.dumps(cls.source))
        cls.seed = 341014
        cls.expected = {}
        for arm in ['baseline', 'growth']:
            cls.expected[arm] = run_world(cls.root, cls.manifest, cls.config, cls.seed, arm,
                                          Path(cls.fixture.name) / ('uninterrupted-' + arm), source=cls.source)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='connected014-live-recovery-')
        self.output = Path(self.tmp.name) / 'run'

    def tearDown(self):
        self.tmp.cleanup()

    def operate(self, arm='growth', **kwargs):
        return run_world(self.root, self.manifest, self.config, self.seed, arm,
                         self.output, source=self.source, **kwargs)

    def _abrupt_event(self, kind, arm='growth', require_earned=False):
        code = """import json,os,sys
from connected_enterprise.engine import run_world
root,manifest,config,source,output,seed,arm,target,earned=sys.argv[1:]
def interrupt(name,state,account):
 if name=='after_event_before_checkpoint' and state['current']['event']['kind']==target:
  if earned=='1' and not any(o['funding_receipt']['funding']=='EARNED' for o in state['orders']):return
  os._exit(23)
run_world(root,json.loads(open(manifest).read()),json.loads(open(config).read()),int(seed),arm,output,source=json.loads(open(source).read()),failpoint=interrupt)
"""
        done = subprocess.run([sys.executable, '-c', code, str(self.root), str(self.manifest_path),
                               str(self.config_path), str(self.source_path), str(self.output),
                               str(self.seed), arm, kind, '1' if require_earned else '0'],
                              cwd=self.root, capture_output=True, text=True, timeout=90)
        self.assertEqual(done.returncode, 23, done.stderr)
        envelope = json.loads((self.output / 'STATE.json').read_text())
        self.assertEqual(set(envelope), {'body', 'signature'})
        saved = envelope['body']['state']
        self.assertIsNotNone(saved['current'])
        self.assertEqual(saved['current']['event']['kind'], kind)
        old_actions = (self.output / 'account.sqlite.actions.jsonl').read_bytes()
        key_path = self.output / 'account.sqlite.adaptive-simulation-key'
        retained_key = key_path.read_bytes()
        resumed = self.operate(arm)
        self.assertTrue(resumed['complete'])
        self.assertTrue((self.output / 'account.sqlite.actions.jsonl').read_bytes().startswith(old_actions))
        self.assertEqual(key_path.read_bytes(), retained_key)
        self.assertEqual(stable(resumed), stable(self.expected[arm]))
        return resumed

    def test_abrupt_startup_commit_replays_without_duplicate_setup_cost(self):
        result = self._abrupt_event('startup', arm='baseline')
        setup = [row for row in result['costs'] if row['category'] == 'development_integration_qualification_and_failed_search']
        self.assertEqual(len(setup), 1)

    def test_abrupt_qualified_order_plan_replays_without_duplicate_native_payment(self):
        result = self._abrupt_event('plan', require_earned=True)
        ids = [order['id'] for order in result['orders']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(result['profitable_earned_continuations'], 0)

    def test_abrupt_production_reexecutes_same_work_and_keeps_financial_identity(self):
        result = self._abrupt_event('produce', require_earned=True)
        self.assertGreater(result['accepted_jobs'], 0)

    def test_abrupt_acceptance_native_commit_replays_once(self):
        self._abrupt_event('accept', require_earned=True)

    def test_abrupt_collection_native_commit_and_tax_replay_once(self):
        self._abrupt_event('clear', require_earned=True)

    def test_bounded_quantum_then_resume_keeps_same_seed_account_and_prefix(self):
        partial = self.operate(stop_after_events=7)
        self.assertFalse(partial['complete'])
        self.assertEqual(partial['processed_events'], 7)
        prefix = copy.deepcopy(partial['owned_account']['ledger']['actions'])
        contract = partial['owned_account']['ledger']['config']['contract']
        key_path = self.output / 'account.sqlite.adaptive-simulation-key'
        retained_key = key_path.read_bytes()
        resumed = self.operate()
        self.assertEqual(resumed['seed'], self.seed)
        self.assertEqual(resumed['owned_account']['ledger']['config']['contract'], contract)
        self.assertEqual(resumed['owned_account']['ledger']['actions'][:len(prefix)], prefix)
        self.assertEqual(key_path.read_bytes(), retained_key)
        self.assertEqual(stable(resumed), stable(self.expected['growth']))
        self.assertEqual(stable(self.operate()), stable(resumed))

    def test_changed_configuration_seed_arm_or_source_cannot_resume(self):
        self.operate(stop_after_events=2)
        tape_path = self.output / 'account.sqlite.actions.jsonl'
        original_tape = tape_path.read_bytes()
        changed = copy.deepcopy(self.config)
        changed['production_cost'] += 1
        for kwargs in [dict(config=changed), dict(seed=self.seed + 1), dict(arm='channel'),
                       dict(source={'files': {}, 'sha256': digest({})})]:
            args = dict(root=self.root, manifest=self.manifest, config=self.config, seed=self.seed,
                        arm='growth', output=self.output, source=self.source)
            args.update(kwargs)
            with self.subTest(changes=list(kwargs)), self.assertRaises(ValueError):
                run_world(**args)
            self.assertEqual(tape_path.read_bytes(), original_tape)

    def test_changed_executing_source_bytes_cannot_resume(self):
        self.operate(stop_after_events=2)
        path = self.root / 'connected_enterprise/engine.py'
        original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED|SOURCE_OR_AUTHORITY_CHANGED|EXECUTING_SOURCE_CHANGED'):
                self.operate()
        finally:
            path.write_bytes(original)

    def test_operating_checkpoint_tampering_fails_and_releases_owner(self):
        self.operate(stop_after_events=2)
        path = self.output / 'STATE.json'
        original = path.read_bytes()
        envelope = json.loads(original)
        mutations = [lambda s: s.update(queue=[]), lambda s: s['buyers'][0].update(active=False),
                     lambda s: s.update(current={'event': {'kind': 'forged'}}), lambda s: s.update(last_time=9999)]
        for mutation in mutations:
            changed = copy.deepcopy(envelope)
            mutation(changed['body']['state'])
            path.write_text(json.dumps(changed))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'CHECKPOINT_SIGNATURE'):
                self.operate()
        path.write_bytes(original)
        self.assertEqual(stable(self.operate()), stable(self.expected['growth']))

    def test_growth_fixture_actually_uses_native_paid_productive_capability(self):
        baseline, growth = self.expected['baseline'], self.expected['growth']
        self.assertTrue(baseline['complete'] and growth['complete'])
        self.assertGreater(len(growth['investments']), 0)
        self.assertTrue(all(row['funding_receipt']['funding'] == 'EARNED' for row in growth['investments']))
        self.assertTrue(any(row['later_settled_order_ids'] for row in growth['productive_expansion']))
        self.assertEqual(growth['summary']['payables'], 0)


if __name__ == '__main__':
    unittest.main()
