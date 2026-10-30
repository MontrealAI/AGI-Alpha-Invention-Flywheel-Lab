import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from commercial.ledger import TapeExchange, amount, audit, digest, load_jobs
from commercial.verdicts import verdicts

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path('campaign/commercial-010/service/executed-002/manifest.json')


class Commercial010AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='commercial010-adversarial-')
        self.work = Path(self.tmp.name)
        self.manifest = json.loads((ROOT / MANIFEST).read_text())
        self.ex = TapeExchange(self.work / 'native.sqlite', root=ROOT, manifest=self.manifest,
                               opening=1_000_000_000, working=0, contract='independent-audit-010')
        self.job = next(x['id'] for x in self.manifest['jobs'] if x['accepted'])

    def tearDown(self):
        self.ex.close()
        self.tmp.cleanup()

    def settle(self):
        self.ex.execute('cost', {'id': 'all-cost', 'amount': 20_000_000}, 0)
        self.ex.execute('wallet', {'buyer': 'simulated-buyer', 'amount': 500_000_000}, 0)
        self.ex.execute('offer', {'id': 'order', 'buyer': 'simulated-buyer', 'price': 200_000_000,
                                 'job_id': self.job, 'deadline': 100}, 1)
        for day, action in enumerate(['consent', 'fund', 'prepare', 'release'], 2):
            self.ex.execute('event', {'id': 'order', 'action': action, 'event_id': action}, day)

    def test_seed_is_never_earned(self):
        s = self.ex.ex.snapshot()
        self.assertGreater(s['cash'], 0)
        self.assertEqual(s['unrestrictedEarned'], 0)
        with self.assertRaises(ValueError):
            self.ex.execute('reserve', {'id': 'seed-claim', 'amount': 1, 'expected_net_value': 1,
                                       'intent_sha256': '0' * 64}, 0)

    def test_nonfinite_negative_boolean_and_overflow_costs_rejected(self):
        for value in [-1, True, float('nan'), float('inf'), 10**12 + 1, '0', None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                amount(value)

    def test_duplicate_payment_cannot_increase_collections(self):
        self.settle()
        before = self.ex.ex.snapshot()
        self.ex.execute('event', {'id': 'order', 'action': 'release', 'event_id': 'release'}, 5)
        self.assertEqual(self.ex.ex.snapshot(), before)
        with self.assertRaises(ValueError):
            self.ex.execute('event', {'id': 'order', 'action': 'release', 'event_id': 'new-release'}, 5)
        self.assertEqual(self.ex.ex.snapshot(), before)

    def test_cost_identifier_reuse_rejected(self):
        self.ex.execute('cost', {'id': 'charge', 'amount': 100}, 0)
        before = self.ex.ex.snapshot()
        with self.assertRaises(ValueError):
            self.ex.execute('cost', {'id': 'charge', 'amount': 100}, 0)
        self.assertEqual(self.ex.ex.snapshot(), before)

    def test_cancellation_restores_reserved_earnings_without_topup(self):
        self.settle()
        before = self.ex.ex.snapshot()
        self.ex.execute('reserve', {'id': 'repeat', 'amount': 40_000_000, 'expected_net_value': 100_000_000,
                                   'intent_sha256': '0' * 64}, 6)
        self.assertEqual(self.ex.ex.snapshot()['unrestrictedEarned'], before['unrestrictedEarned'] - 40_000_000)
        self.ex.execute('cancel_investment', {'id': 'repeat'}, 6)
        self.assertEqual(self.ex.ex.snapshot(), before)

    def test_earned_spend_is_expensed_once_and_tail_stays_restricted(self):
        self.settle()
        self.ex.execute('reserve', {'id': 'repeat', 'amount': 40_000_000, 'expected_net_value': 100_000_000,
                                   'intent_sha256': '0' * 64}, 6)
        self.ex.execute('finish', {'id': 'repeat', 'amount': 40_000_000,
                                  'artifact_sha256': '1' * 64}, 6)
        s = self.ex.ex.snapshot()
        self.assertEqual(s['expenses'], 60_000_000)
        self.assertEqual(s['collections'], 200_000_000)
        self.assertEqual(s['cash'], 1_140_000_000)
        self.assertEqual(s['tailReserve'], 200_200_000)
        self.assertLessEqual(s['unrestrictedEarned'], s['collections'] - s['expenses'])

    def test_replay_rejects_derived_summary_mutations(self):
        self.settle()
        tape = self.ex.export()
        for key in ['cash', 'collections', 'expenses', 'profit', 'unrestrictedEarned', 'tailReserve']:
            mutated = copy.deepcopy(tape)
            mutated['summary'][key] += 1
            with self.subTest(key=key), self.assertRaises(ValueError):
                audit(mutated, root=ROOT, manifest=self.manifest)

    def test_replay_rejects_repriced_cost_event_and_external_rehash(self):
        self.settle()
        tape = self.ex.export()
        mutated = copy.deepcopy(tape)
        mutated['actions'][0]['args']['amount'] = 0
        mutated['actions_sha256'] = digest(mutated['actions'])
        with self.assertRaises(ValueError):
            audit(mutated, root=ROOT, manifest=self.manifest)
        with self.assertRaises(ValueError):
            audit(mutated, root=ROOT, manifest=self.manifest,
                  expected_actions_sha256=tape['actions_sha256'])

    def test_event_reordering_and_scope_upgrade_rejected(self):
        self.settle()
        tape = self.ex.export()
        reordered = copy.deepcopy(tape)
        reordered['actions'][0], reordered['actions'][1] = reordered['actions'][1], reordered['actions'][0]
        reordered['actions_sha256'] = digest(reordered['actions'])
        with self.assertRaises(ValueError):
            audit(reordered, root=ROOT, manifest=self.manifest)
        tape['config']['scope'] = 'OBSERVED'
        with self.assertRaises(ValueError):
            audit(tape, root=ROOT, manifest=self.manifest)
        task = self.ex.task(self.job)
        task['scope'] = 'OBSERVED'
        with self.assertRaises(ValueError):
            self.ex.validate(task)

    def test_source_and_cohort_mutation_rejected(self):
        mutated = copy.deepcopy(self.manifest)
        mutated['jobs'][0]['artifact_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            load_jobs(ROOT, mutated)
        mutated = copy.deepcopy(self.manifest)
        mutated['accepted_count'] += 1
        with self.assertRaises(ValueError):
            load_jobs(ROOT, mutated)

    def test_forged_acceptance_cannot_admit_nonservice_artifact(self):
        isolated = self.work / 'forged'
        shutil.copytree(ROOT / MANIFEST.parent, isolated / MANIFEST.parent)
        protocol = json.loads((ROOT / self.manifest['source_freeze']).read_text())
        for source in protocol['source_hashes']:
            target = isolated / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, target)
        mutated = copy.deepcopy(self.manifest)
        job = mutated['jobs'][0]
        raw = b'{"invented":"not a reconciliation"}'
        (isolated / job['artifact']).write_bytes(raw)
        job['artifact_sha256'] = hashlib.sha256(raw).hexdigest()
        receipt_path = isolated / job['receipt']
        receipt = json.loads(receipt_path.read_text())
        receipt['accepted'] = True
        receipt['artifact_sha256'] = job['artifact_sha256']
        raw = json.dumps(receipt).encode()
        receipt_path.write_bytes(raw)
        job['receipt_sha256'] = hashlib.sha256(raw).hexdigest()
        with self.assertRaises(ValueError):
            load_jobs(isolated, mutated)

    def test_whole_tape_clean_replay(self):
        self.settle()
        result = audit(self.ex.export(), root=ROOT, manifest=self.manifest)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['scope'], 'SIMULATED')
        self.assertEqual(result['summary'], self.ex.ex.snapshot())

    def test_commercial_go_requires_actual_accepted_service_and_positive_economics(self):
        for accepted, positive in [(0, False), (0, True), (16, False)]:
            with self.subTest(accepted=accepted, positive=positive), self.assertRaises(ValueError):
                verdicts(simulated_go=True, accepted_jobs=accepted, positive_service=positive)

    def test_fixed_capability_service_can_qualify_without_invention_or_live_claim(self):
        result = verdicts(simulated_go=True, accepted_jobs=16, positive_service=True)
        self.assertEqual(result['simulated_commercial_flywheel']['verdict'], 'CONDITIONAL_SIMULATED_GO')
        for key in ['observed_commercial_flywheel', 'capability_compounding_flywheel', 'blue_sky_enablement']:
            self.assertEqual(result[key]['verdict'], 'NOT_ESTABLISHED')
        with self.assertRaises(ValueError):
            verdicts(simulated_go=True, accepted_jobs=16, positive_service=True, observed_evidence={'scope': 'OBSERVED'})


if __name__ == '__main__':
    unittest.main()
