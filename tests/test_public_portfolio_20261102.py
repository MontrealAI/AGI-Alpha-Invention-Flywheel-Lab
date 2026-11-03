import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from commercial.ledger import canonical
from connected_enterprise.finance import audit_journal
from experiments.public_portfolio_20261102 import service
from experiments.public_portfolio_20261102.native import BusinessAccount

ROOT = Path(__file__).resolve().parents[1]
USD = 1_000_000

class PublicPortfolioNativeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'source'
        self.root.mkdir()
        self.products = json.loads((ROOT / service.PREFIX / 'PRODUCTS.json').read_text())
        for name in service.source_paths(ROOT):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        from connected_enterprise.finance import source_paths_for_manifest
        for name in source_paths_for_manifest({'schema': service.SCHEMA}):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        self.product = next(p for p in self.products if p['id'] == 'interface-k1')
        self.manifest = service.prepare_manifest(self.root, [self.product], 'unittest')

    def test_canonical_verifier_cannot_be_chosen_by_producer(self):
        altered = copy.deepcopy(self.manifest)
        altered['jobs'][0]['approval_path'] = service.PREFIX + 'forged-approval.json'
        (self.root / altered['jobs'][0]['approval_path']).write_bytes((self.root / service.APPROVAL).read_bytes())
        with self.assertRaisesRegex(ValueError, 'CANONICAL_VERIFIER'):
            service.load_contracts(self.root, altered)

    def test_approval_evidence_and_source_changes_fail_closed(self):
        approval = self.root / service.APPROVAL
        original = approval.read_bytes()
        data = json.loads(original)
        data['products'][0]['accepted'] = not data['products'][0]['accepted']
        approval.write_bytes(canonical(data))
        with self.assertRaisesRegex(ValueError, 'SOURCE_CLOSURE_CHANGED'):
            service.load_contracts(self.root, self.manifest)
        approval.write_bytes(original)
        source = self.root / service.VERIFIER
        source.write_bytes(source.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'SOURCE_CLOSURE_CHANGED'):
            service.load_contracts(self.root, self.manifest)

    def test_unapproved_failed_successor_cannot_be_sold(self):
        approval_path = self.root / service.APPROVAL
        approval = json.loads(approval_path.read_text())
        rejected = next(p for p in approval['products'] if p['id'] == 'arrangement-k2')
        self.assertFalse(rejected['accepted'])
        row = {key: rejected[key] for key in ('id', 'route', 'stage', 'product_path', 'product_sha256')}
        row.update(approval_path=service.APPROVAL, approval_sha256=hashlib.sha256(approval_path.read_bytes()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'APPROVED_BYTES_REQUIRED'):
            service.prepare_manifest(self.root, [row], 'rejected')

    def test_exact_funded_delivery_public_replay_resume_and_tamper(self):
        path = Path(self.tmp.name) / 'private' / 'account'
        path.parent.mkdir()
        artifact = json.loads((self.root / self.product['product_path']).read_text())
        with BusinessAccount(self.root, self.manifest, path, opening=100 * USD, contract='portfolio-unit') as account:
            account.cost('research', 2 * USD, 0)
            account.begin('interface-k1', 'order', 'buyer', 10 * USD, 50 * USD, 1, 3, 8, USD)
            before = account.snapshot()['summary']
            self.assertEqual(before['revenue'], 0)
            receipt = account.spend('production', 'prepaid-checking-support', USD, 1, {'scope': 'UNIT_TEST'}, USD, allow_seed=True)
            self.assertEqual(receipt['funding'], 'SEED')
            self.assertTrue(account.deliver('order', 'interface-k1', artifact, 2)['accepted'])
            account.event('order', 'release', 3)
            account.advance(9)
            exported = account.export()
            self.assertTrue(account.audit()['accepted'])
        with BusinessAccount(self.root, self.manifest, path, opening=100 * USD, contract='portfolio-unit') as resumed:
            self.assertEqual(resumed.export(), exported)
        self.assertTrue(audit_journal(exported, root=self.root, manifest=self.manifest)['accepted'])
        delivery = self.root / self.manifest['jobs'][0]['delivery_path']
        changed = dict(artifact, function='tampered')
        delivery.write_bytes(canonical(changed))
        with self.assertRaises(ValueError):
            audit_journal(exported, root=self.root, manifest=self.manifest)

    def test_empty_research_account_has_costs_and_no_trade_authority(self):
        manifest = service.prepare_manifest(self.root, [], 'research-only')
        path = Path(self.tmp.name) / 'research-account'
        with BusinessAccount(self.root, manifest, path, opening=10 * USD, contract='research-only') as account:
            account.cost('failed-research', 3 * USD, 0)
            self.assertEqual(account.snapshot()['summary']['profit'], -3 * USD)
            with self.assertRaisesRegex(ValueError, 'REGISTERED_LICENSE_REQUIRED'):
                account.begin('interface-k1', 'o', 'b', USD, USD, 1, 2, 3, 0)
            self.assertTrue(account.audit()['accepted'])

    def test_buyer_budget_cannot_be_refilled_on_renewal(self):
        path = Path(self.tmp.name) / 'budget-account'
        with BusinessAccount(self.root, self.manifest, path, opening=100 * USD, contract='budget-test') as account:
            account.begin('interface-k1', 'o1', 'same-buyer', USD, 20 * USD, 0, 2, 4, 0)
            with self.assertRaisesRegex(ValueError, 'TOPUP_REFUSED'):
                account.begin('interface-k1', 'o2', 'same-buyer', USD, 30 * USD, 1, 3, 5, 0)

if __name__ == '__main__': unittest.main()
