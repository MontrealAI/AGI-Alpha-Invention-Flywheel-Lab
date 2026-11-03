import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from commercial.ledger import digest
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import SOURCE_PATHS
from outlearning073.native import BusinessAccount, audit_export
from outlearning073.service import SOURCES, load_contracts, prepare_manifest
from outlearning073.worlds import development_requests, make_session
from outlearning073.verify import verify
from outlearning073.economics import ECONOMIC_PLAN, _resume_completed, run_scenario

ROOT = Path(__file__).resolve().parents[1]
USD = 1_000_000


def development_artifact(request):
    public = make_session(request).public
    output = {row['intent']: {'content': row['content'], 'sha256': hashlib.sha256(row['content'].encode()).hexdigest()} for row in public['objects']}
    steps = []
    for intent in public['intents']:
        write = {'op': 'write', 'intent': intent, 'key': request['id'] + '-' + intent, 'value': '$output:' + intent}
        steps += [write, {'op': 'if', 'test': {'intent': intent, 'is': 'committed'}, 'then': [], 'else': [copy.deepcopy(write)]}]
    return {'steps': steps, 'output': output}


class OutlearningNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='outlearning073-native-development-')
        self.root = Path(self.temp.name) / 'source'; self.root.mkdir()
        for name in sorted(set(SOURCE_PATHS) | set(SOURCES)):
            target = self.root / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.request = development_requests()[0]
        path = self.root / 'outlearning073/requests.json'
        path.write_text(json.dumps([self.request]))
        self.manifest = prepare_manifest(self.root, [{'id': self.request['id'], 'delivery_path': 'outlearning073/deliveries/dev.json'}])
        self.account_path = Path(self.temp.name) / 'private' / 'account.sqlite'
        self.account_path.parent.mkdir(mode=0o700)
        self.account = BusinessAccount(self.root, self.manifest, self.account_path, opening=2_000 * USD)

    def tearDown(self):
        self.account.close()
        self.temp.cleanup()

    def offer(self):
        terms = prospective_terms('dev-order', 1_000 * USD, 25, 24, fee=200_000)
        self.account.begin_order(self.request['id'], 'dev-order', 'dev-buyer', 1_000 * USD,
                                 1_200 * USD, 0, 24, terms=terms)

    def test_actual_plan_native_acceptance_collection_earned_reservation_and_reopen(self):
        artifact = development_artifact(self.request)
        self.assertTrue(verify(self.request, artifact)['accepted'])
        self.assertFalse((self.root / 'outlearning073/deliveries/dev.json').exists())
        self.account.spend('dev-resources', 'complete_resources', 600 * USD, 0, {'development_only': True}, allow_seed=True)
        self.offer()
        checked = self.account.complete_order('dev-order', self.request['id'], artifact, 1)
        self.assertTrue(checked['accepted'])
        self.assertEqual(self.account.snapshot()['summary']['revenue'], 0)
        self.account.release('dev-order', 24)
        self.account.cost('dev-tax', 79_960_000, 24)
        self.account.advance(26)
        before = self.account.snapshot()['summary']
        self.assertEqual(before['profit'], 319_840_000)
        receipt = self.account.spend('dev-successor', 'next_resources', 250 * USD, 48,
                                     {'development_only': True, 'retained_content': digest(artifact)}, expected_net=950 * USD)
        self.assertEqual(receipt['funding'], 'EARNED')
        exported = self.account.export()
        self.assertTrue(audit_export(exported, root=self.root, manifest=self.manifest)['accepted'])
        self.account.close()
        self.account = BusinessAccount(self.root, self.manifest, self.account_path, opening=2_000 * USD)
        self.assertEqual(self.account.export(), exported)
        self.assertEqual(self.account.spend('dev-successor', 'next_resources', 250 * USD, 48,
            {'development_only': True, 'retained_content': digest(artifact)}, expected_net=950 * USD), receipt)
        self.assertEqual(self.account.export(), exported)

    def test_delayed_uncollected_delivery_does_not_create_earned_funds(self):
        self.account.spend('dev-resources', 'complete_resources', 600 * USD, 0, {'development_only': True}, allow_seed=True)
        self.offer()
        self.assertTrue(self.account.complete_order('dev-order', self.request['id'], development_artifact(self.request), 1)['accepted'])
        self.assertIsNone(self.account.spend('uncollected-successor', 'next_resources', 250 * USD, 2,
                                             {'development_only': True}, expected_net=950 * USD))
        summary = self.account.snapshot()['summary']
        self.assertEqual(summary['revenue'], 0)
        self.assertEqual(summary['collections'], 0)
        self.assertEqual(summary['profit'], -600 * USD - 200_000)
        self.assertTrue(self.account.audit()['accepted'])

    def test_wrong_output_refunds_and_does_not_prepare_or_collect(self):
        self.offer(); artifact = development_artifact(self.request)
        artifact['output']['archive0']['content'] = 'wrong'
        self.assertFalse(self.account.complete_order('dev-order', self.request['id'], artifact, 1)['accepted'])
        self.account.refund('dev-order', 2)
        exported = self.account.export()
        self.assertFalse(any(row['op'] == 'event' and row['args']['action'] == 'prepare' for row in exported['ledger']['actions']))
        self.assertEqual(exported['ledger']['summary']['collections'], 0)
        self.assertTrue(self.account.audit()['accepted'])

    def test_changed_delivered_plan_rejected_by_independent_financial_replay(self):
        self.offer(); artifact = development_artifact(self.request)
        self.assertTrue(self.account.complete_order('dev-order', self.request['id'], artifact, 1)['accepted'])
        exported = self.account.export()
        path = self.root / 'outlearning073/deliveries/dev.json'
        changed = copy.deepcopy(artifact); changed['steps'][0]['key'] = 'changed-key'
        path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'ACTUAL_DELIVERY_HASH_CHANGED'):
            audit_export(exported, root=self.root, manifest=self.manifest)

    def test_request_tampering_and_financial_source_drift_rejected(self):
        changed = copy.deepcopy(self.manifest); changed['jobs'][0]['request']['seed'] = 1
        with self.assertRaisesRegex(ValueError, 'FROZEN_PROFILE_CHANGED'):
            load_contracts(self.root, changed)
        path = self.root / 'outlearning073/verify.py'
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'CONNECTED_FINANCE_SOURCE_CHANGED'):
            self.account.cost('after-source-drift', USD, 0)

    def test_development_completed_queue_reopens_same_authority_and_rejects_incomplete(self):
        scenario = next(row for row in ECONOMIC_PLAN['scenarios'] if row['id'] == 'delayed-collection')
        target = Path(self.temp.name) / 'development-queue-case'
        result = run_scenario(self.root, target, self.manifest, development_artifact, scenario)
        self.assertIsNone(result['uncollected_successor_refusal']['funding_receipt'])
        self.assertTrue(result['expense_reconciliation']['equal'])
        original = (target / 'ACCOUNT_PUBLIC.json').read_bytes()
        resumed = _resume_completed(self.root, target, self.manifest, scenario, 2_000 * USD)
        self.assertEqual(resumed, result)
        self.assertEqual((target / 'ACCOUNT_PUBLIC.json').read_bytes(), original)
        (target / 'RESULT.json').unlink()
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_SCENARIO_PRESERVED'):
            _resume_completed(self.root, target, self.manifest, scenario, 2_000 * USD)
        self.assertEqual((target / 'ACCOUNT_PUBLIC.json').read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
