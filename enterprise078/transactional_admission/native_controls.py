"""Run only in an exact staged historical runtime, on a NEW test account."""
import copy
import importlib.util
import json
import tempfile
from pathlib import Path

from commercial.ledger import digest
from enterprise078.native import BusinessAccount
from enterprise078.service import prepare_manifest


def run():
    spec = importlib.util.spec_from_file_location('admission_authority', Path(__file__).with_name('authority.py'))
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    root = Path.cwd()
    manifest = prepare_manifest(root, [{'id': 'dev-K1', 'delivery_path': 'enterprise078/deliveries/admission-fixture.json'}])
    checks = []
    with tempfile.TemporaryDirectory(prefix='fresh-admission-test-only-') as tmp:
        path = Path(tmp)/'account'
        try:
            guard.open_existing(root, manifest, path, opening=25000000000, working=0, contract='TEST_ONLY_NOT_CONTINUATION')
        except ValueError as e:
            assert str(e) == 'ORIGINAL_ACCOUNT_AUTHORITY_REQUIRED_NO_RESEED'
        else: raise AssertionError('MISSING_ACCOUNT_RESEEDED')
        assert list(Path(tmp).iterdir()) == []
        checks.append('missing_account_no_reseed')
        with BusinessAccount(root, manifest, path, opening=25000000000, working=0, contract='TEST_ONLY_NOT_CONTINUATION') as account:
            account.cost('test-incurred-failure', 100000000, 0)
            before = digest(account.export())
            for expected in (0, -1000000):
                assert account.spend('rejected-'+str(expected), 'test-admission', 1000000, 1, {'test': True}, expected_net=expected) is None
                assert digest(account.export()) == before
            checks.append('nonpositive_expected_net_no_actions')
            try:
                guard.open_existing(root, manifest, path, opening=25000000000, working=0, contract='TEST_ONLY_NOT_CONTINUATION')
            except (ValueError, BlockingIOError): pass
            else: raise AssertionError('OVERLAPPING_NATIVE_WRITER_ACCEPTED')
            checks.append('native_writer_exclusion')
            assert account.audit()['accepted']
            assert account.snapshot()['summary']['profit'] == -100000000
        changed = copy.deepcopy(manifest)
        changed['unregistered_transactional_catalog'] = 'not-authorized'
        try:
            guard.open_existing(root, changed, path, opening=25000000000, working=0, contract='TEST_ONLY_NOT_CONTINUATION')
        except ValueError: pass
        else: raise AssertionError('OLD_MANIFEST_CHANGED')
        checks.append('changed_manifest_refused')
        key = path.with_name(path.name+'.adaptive-simulation-key')
        held = path.with_name('held-test-authority')
        key.rename(held)
        try:
            try:
                guard.open_existing(root, manifest, path, opening=25000000000, working=0, contract='TEST_ONLY_NOT_CONTINUATION')
            except ValueError as e:
                assert str(e) == 'ORIGINAL_ACCOUNT_AUTHORITY_REQUIRED_NO_RESEED'
            else: raise AssertionError('MISSING_KEY_RESEEDED')
            assert not key.exists()
        finally: held.rename(key)
        checks.append('missing_key_no_reseed')
        with guard.open_existing(root, manifest, path, opening=25000000000, working=0, contract='TEST_ONLY_NOT_CONTINUATION') as account:
            assert digest(account.export()) == before
            assert account.audit()['accepted']
            assert account.snapshot()['summary']['profit'] == -100000000
        checks.append('same_history_reopen_preserves_loss')
    return {'accepted': True, 'checks': checks, 'fixture_incurred_loss_microUSD': 100000000,
            'fixture_scope': 'new disposable test account; never original continuation or pooled business'}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
