"""Native failure boundaries on explicit development fixtures, never the registered prospective cohort."""
from __future__ import annotations

import copy
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from connected_enterprise.channels import ChannelBook
from connected_enterprise.finance import audit_journal
from mechanism_harness import reach_native as native


class ReachNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        prep = cls.root / 'development-inputs'
        prep.mkdir()
        with (patch.object(native.policy, 'JOBS_PER_SERVICE', 32),
              patch.object(native.policy, 'JOB_SEED', 71422)):
            cls.runtime, cls.manifest = native._prepare(prep)
        cls.inventory = {}
        for job in cls.manifest['jobs']:
            cls.inventory.setdefault(job['service_id'], []).append(job)
        cls.services = ['kpi_variance', 'evidence_matrix']
        cls.market = {'payment_bps': 200, 'outcomes':
                      [{'id': 'k', 'services': cls.services[:1], 'cost_cents': 100},
                       {'id': 'e', 'services': cls.services[1:], 'cost_cents': 100},
                       {'id': 'both', 'services': cls.services, 'cost_cents': 200}]}
        cls.program = {'fixture': 'developer-provided union order'}
        cls.terms = native.contract('pilot', 'central', {'fixture': 'independent-dev-ledger'})
        cls.initial = 10_000

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def open_account(self, name):
        path = self.root / name
        path.mkdir(exist_ok=True)
        return native.JournalAccount(self.runtime, self.manifest, path / 'account.sqlite',
                                     opening=native.OPENING, working=0, contract='dev-' + name)

    def trade(self, account, *, prior=(), ordinal=1, day=5, slot=8):
        choice = {'outcome_id': 'both', 'price_cents': 3000, 'seller_contribution_cents': 2700}
        row = {'day': day, 'buyer': 'dev-purchaser', 'source': 'warm', 'ordinal': ordinal,
               'source_plan_id': None, 'choice': choice, 'remaining_after_cents': self.initial -
               sum(r['collections_microUSD'] // native.CENT for r in prior),
               'quote_microUSD': 0, 'fee_microUSD': 0, 'production_microUSD': 0, 'collections_microUSD': 0}
        jobs = native._components(self.runtime, self.inventory, self.market,
                                  self.market['outcomes'][-1], 3000, slot, ordinal)
        row['status'] = native._checkout(account, self.runtime, self.terms, self.market, self.program,
                                         jobs, row, prior, self.initial, native.OPENING)
        return row

    def test_post_invoice_pre_right_reopens_exact_earned_debit(self):
        account = self.open_account('pre-right')
        book = ChannelBook(811, self.terms['supplier_contracts'])
        try:
            warm = self.trade(account)
            self.assertEqual(warm['status'], 'SETTLED')
            with patch.object(book, 'purchase', side_effect=RuntimeError('before supplier acknowledgment')):
                with self.assertRaisesRegex(RuntimeError, 'before supplier'):
                    native._decision(account, book, self.terms, 90, [], [warm])
            self.assertFalse(book.export()['purchase_receipts'])
            after_debit = account.export()
            self.assertEqual(after_debit['connected_journal']['entries'][-1]['funding'], 'EARNED')
            authority = (account.path.parent / 'account.sqlite.adaptive-simulation-key').read_bytes()
        finally:
            account.close()
        account = self.open_account('pre-right')
        try:
            recovered = native._decision(account, book, self.terms, 90, [], [warm])
            self.assertEqual(recovered['purchase']['invoice_microUSD'], 6_250_000)
            self.assertEqual(recovered['funding']['plan_id'], recovered['purchase']['source_plan_id'])
            self.assertEqual(after_debit, account.export())
            self.assertEqual(authority, (account.path.parent / 'account.sqlite.adaptive-simulation-key').read_bytes())
            self.assertTrue(account.audit()['accepted'])
        finally:
            account.close()

    def test_partial_union_release_then_repeat_preserves_one_wallet(self):
        account = self.open_account('partial-union')
        original = account.execute
        def interrupt(op, args, day):
            receipt = original(op, args, day)
            if op == 'event' and args['action'] == 'release':
                raise RuntimeError('after first release')
            return receipt
        try:
            with patch.object(account, 'execute', interrupt):
                with self.assertRaisesRegex(RuntimeError, 'first release'):
                    self.trade(account)
            partial = account.export()['ledger']['summary']
            self.assertEqual(partial['collections'], 15_000_000)
        finally:
            account.close()
        account = self.open_account('partial-union')
        try:
            first = self.trade(account)
            again = self.trade(account, prior=[first], ordinal=2, day=8, slot=9)
            self.assertEqual((first['status'], again['status']), ('SETTLED', 'SETTLED'))
            self.assertEqual(again['remaining_after_cents'], 4000)
            tape = account.export()['ledger']
            self.assertEqual(sum(a['op'] == 'wallet' for a in tape['actions']), 1)
            self.assertEqual(tape['summary']['collections'], 60_000_000)
            self.assertEqual(tape['summary']['expenses'], 5_200_000)
            self.assertTrue(account.audit()['accepted'])
        finally:
            account.close()

    def test_whole_union_capacity_and_full_refund(self):
        account = self.open_account('limits')
        try:
            first = self.trade(account)
            partial_day = [dict(first, components=first['components'][:1])]
            before = account.export()
            denied = self.trade(account, prior=partial_day, ordinal=2, slot=9)
            self.assertEqual(denied['status'], 'CAPACITY')
            self.assertEqual(account.export(), before)
            produce = native.instruments.produce
            def corrupt_one(raw, *args, **kwargs):
                artifact = produce(raw, *args, **kwargs)
                if raw['service_id'] == self.services[-1]:
                    artifact['outcome_scope'] = 'intake_readiness'
                return artifact
            with patch.object(native.instruments, 'produce', corrupt_one):
                failed = self.trade(account, prior=[first], ordinal=2, day=8, slot=9)
            self.assertEqual(failed['status'], 'REFUNDED')
            self.assertEqual(failed['remaining_after_cents'], 7000)
            self.assertEqual(failed['collections_microUSD'], 0)
            self.assertGreater(failed['production_microUSD'], 0)
            tape = account.export()['ledger']
            self.assertEqual(tape['summary']['collections'], 30_000_000)
            self.assertEqual(sum(a['op'] == 'event' and a['args']['action'] == 'refund' for a in tape['actions']), 2)
        finally:
            account.close()

    def test_completed_resume_requires_unchanged_live_custody(self):
        # Isolate local-authority reconciliation from portable public-evidence
        # verification, independently exercised by the full verifier fixture.
        out = self.root / 'completed'
        out.mkdir()
        shutil.copytree(self.runtime, out / 'runtime')
        source = native.source_identity()
        terms = native.contract('organic', 'central', source)
        for name, value in [('MANIFEST', self.manifest), ('SOURCE', source), ('CONTRACT', terms)]:
            native.save(out / (name + '.json'), value)
        def reopen():
            return native.JournalAccount(out / 'runtime', self.manifest, out / 'account.sqlite', opening=native.OPENING,
                                         working=0, contract=native.native_contract(terms))
        account = reopen()
        try:
            account.cost('development-completed-cost', 100_000, 4)
            exported = account.export()
            native.save(out / 'NATIVE_EXPORT.json', exported)
            native.save(out / 'REPORT.json', {'scope': 'development ledger completion fixture',
                                             'native_export_sha256': native.digest(exported),
                                             'summary': exported['ledger']['summary']})
        finally:
            account.close()
        def verify_development_ledger(path):
            # This test exercises local custody only. Validate the actual ledger and
            # the exact fixture report rather than claiming a registered reach audit.
            exported = native.read(path / 'NATIVE_EXPORT.json')
            checked = audit_journal(exported, root=path / 'runtime', manifest=self.manifest)
            report = native.read(path / 'REPORT.json')
            self.assertEqual(report, {'scope': 'development ledger completion fixture',
                                     'native_export_sha256': native.digest(exported),
                                     'summary': exported['ledger']['summary']})
            return {'accepted': checked['accepted'], 'report_sha256': native.digest(report)}
        before = (out / 'NATIVE_EXPORT.json').read_bytes()
        with patch.object(native, 'audit', side_effect=verify_development_ledger):
            self.assertEqual(native.run(out, resume=True), native.read(out / 'REPORT.json'))
            account = reopen()
            try:
                with (patch.object(account, '_attempt', side_effect=RuntimeError('durable intent')),
                      self.assertRaisesRegex(RuntimeError, 'durable intent')):
                    account.cost('development-divergent-cost', 7, 5)
                self.assertEqual(account.export()['connected_journal']['entries'][-1]['status'], 'PENDING')
            finally:
                account.close()
            tape_path = out / 'account.sqlite.actions.jsonl'
            journal_path = out / 'account.sqlite.connected-journal.json'
            before_tape, pending_journal = tape_path.read_bytes(), journal_path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'COMPLETED_NATIVE_ACCOUNT_DIFFERS'):
                native.run(out, resume=True)
            self.assertTrue(tape_path.read_bytes() == before_tape, 'completed resume executed the signed intent')
            self.assertTrue(journal_path.read_bytes() == pending_journal, 'completed resume consumed the signed intent')
            # The ordinary writer still recovers this legitimate request exactly once.
            account = reopen()
            try:
                self.assertEqual(account.export()['connected_journal']['entries'][-1]['status'], 'COMPLETE')
                self.assertEqual(account.snapshot()['summary']['expenses'], 100_007)
            finally:
                account.close()
            tape = (out / 'account.sqlite.actions.jsonl').read_bytes()
            with self.assertRaisesRegex(ValueError, 'COMPLETED_NATIVE_ACCOUNT_DIFFERS'):
                native.run(out, resume=True)
            self.assertEqual((out / 'account.sqlite.actions.jsonl').read_bytes(), tape)
            self.assertEqual((out / 'NATIVE_EXPORT.json').read_bytes(), before)
            key = out / 'account.sqlite.adaptive-simulation-key'
            key.rename(out / 'dev-removed-authority')
            with self.assertRaisesRegex(ValueError, 'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                native.run(out, resume=True)
            (out / 'REPORT.json').unlink()
            with self.assertRaisesRegex(ValueError, 'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                native.run(out, resume=True)
            self.assertFalse(key.exists())

    def test_null_menu_and_unqualified_quote_do_not_observe_wallet(self):
        market = {'types': []}
        study = {'study': {'cases': [{'market': market}]}, 'selection': {'decisions': [{'action': 'NONENTRY'}]}}
        route = {'customer_id':'reach-000','source':'organic','source_plan_id':None,
                 'exposure_id':'dev-contact','paid_exclusive':False}
        account = self.open_account('no-lookahead')
        try:
            with (patch.object(native.policy, 'lifetime_budget', side_effect=AssertionError('private wallet read')),
                  patch.object(native.policy, 'qualification', side_effect=AssertionError('qualification read'))):
                skipped = native._contact(account, self.runtime, {}, self.terms, study, [{}], route, 5, [])
            self.assertEqual(skipped['status'], 'NONENTRY')
            self.assertEqual(skipped['quote_microUSD'], 0)
            operable = copy.deepcopy(study)
            operable['selection']['decisions'][0]['action'] = 'OPERATE'
            with (patch.object(native.policy, 'lifetime_budget', side_effect=AssertionError('private wallet read')),
                  patch.object(native.policy, 'qualification', return_value=False)):
                declined = native._contact(account, self.runtime, {}, self.terms, operable, [{}], route, 5, [])
            self.assertEqual(declined['status'], 'UNQUALIFIED')
            self.assertIsNone(declined['remaining_before_cents'])
            self.assertEqual(account.export()['ledger']['summary']['expenses'], 100_000)
        finally:
            account.close()


if __name__ == '__main__':
    unittest.main()
