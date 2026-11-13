"""Transition155 sequential pending-request authority regression (synthetic only).

Preregistered before test code at docs/transition-prepare-race154/SERIAL_REPLAY155.md.
This does not authenticate a real HMAC or prove a native financial migration.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise import operations
from connected_enterprise.engine import default_config
from connected_enterprise.migration import default_policy


class SequentialPendingUpgrade155(unittest.TestCase):
    def test_distinct_sequential_prepare_cannot_replace_pending_checkpoint(self):
        with tempfile.TemporaryDirectory(prefix='transition-serial155-') as tmp:
            root = Path(tmp)
            output = root / 'business'
            output.mkdir()
            target = root / 'target-source'
            target.mkdir()
            manifest_file = root / 'REGISTERED-SERVICES.json'
            manifest = {'synthetic': 'no actual services or revenue'}
            manifest_file.write_text(json.dumps(manifest), encoding='utf-8')
            cfg = default_config()
            prior = {'body': {'state': {
                'config': cfg, 'source': {'sha256': 'a' * 64, 'files': {}},
                'seed': 155, 'arm': 'baseline', 'last_time': 0, 'current': None
            }}, 'signature': 'SYNTHETIC_NOT_AUTHENTICATED'}
            (output / 'STATE.json').write_text(json.dumps(prior), encoding='utf-8')
            checkpoint_sha = digest(prior)
            new_source = {'sha256': 'b' * 64, 'files': {}}
            observed_signer_ids = []

            def fake_signer(**kwargs):
                observed_signer_ids.append(kwargs['ident'])
                return {'body': {'synthetic_only': True}, 'signature': 'not-an-HMAC'}

            def call(ident):
                return operations.prepare_upgrade(
                    target, target, manifest_file, output,
                    policy=default_policy(), expected_checkpoint_sha256=checkpoint_sha,
                    ident=ident)

            with (patch('connected_enterprise.upgrades.authorize_upgrade', side_effect=fake_signer),
                  patch('connected_enterprise.upgrades.validate_ticket', return_value=None),
                  patch('connected_enterprise.runner.identity', return_value=new_source),
                  patch.object(operations, '_copy_source', return_value=new_source),
                  patch.object(operations, '_copy_inputs', return_value=None)):
                first = call('writer-A')
                self.assertEqual(first['upgrade_request']['id'], 'writer-A')
                first_descriptor = (output / 'OPERATOR.json').read_bytes()
                state_bytes = (output / 'STATE.json').read_bytes()
                services_bytes = (output / 'SERVICES.json').read_bytes()
                self.assertEqual(first, call('writer-A'),
                    'IDENTICAL_PENDING_RETRY_MUST_BE_IDEMPOTENT')
                self.assertEqual(first_descriptor, (output / 'OPERATOR.json').read_bytes(),
                    'IDENTICAL_RETRY_MUST_NOT_MUTATE_DESCRIPTOR')
                history_path = output / 'OPERATOR_HISTORY'
                before_history = sorted((p.relative_to(output).as_posix(), p.read_bytes())
                                        for p in history_path.rglob('*') if p.is_file()) if history_path.exists() else []

                # The first prepare is only staged; no upgrade/commit occurs.
                # A complete exclusive-lock fix must *still* reject this
                # distinct serialized request against the unchanged checkpoint.
                rejected_error = None
                second_success = None
                try:
                    second_success = call('writer-B')
                except (ValueError, FileExistsError) as exc:
                    rejected_error = type(exc).__name__ + ':' + str(exc)
                self.assertIsNone(second_success,
                    'SERIAL_PENDING_UPGRADE_REPLACED: second distinct request succeeded')
                self.assertIsNotNone(rejected_error,
                    'PENDING_UPGRADE_REQUIRES_EXPLICIT_REJECTION')
                self.assertTrue(any(k in rejected_error.upper() for k in (
                    'PENDING', 'STALE', 'CONFLICT', 'REPLAY', 'FORK', 'REFUSED')),
                    'INCIDENTAL_IO_ERROR_NOT_A_VALID_AUTHORITY_REJECTION: ' + rejected_error)
                self.assertEqual(first_descriptor, (output / 'OPERATOR.json').read_bytes(),
                    'REJECTED_REQUEST_MUST_PRESERVE_FIRST_DESCRIPTOR')
                self.assertEqual(state_bytes, (output / 'STATE.json').read_bytes(),
                    'REJECTED_REQUEST_MUST_PRESERVE_STATE')
                self.assertEqual(services_bytes, (output / 'SERVICES.json').read_bytes(),
                    'REJECTED_REQUEST_MUST_PRESERVE_MANIFEST')
                after_history = sorted((p.relative_to(output).as_posix(), p.read_bytes())
                                       for p in history_path.rglob('*') if p.is_file()) if history_path.exists() else []
                self.assertEqual(before_history, after_history,
                    'REJECTED_REQUEST_MUST_NOT_CREATE_OPERATOR_HISTORY')
                self.assertEqual(observed_signer_ids, ['writer-A'],
                    'REJECT_CONFLICT_BEFORE_SECOND_SIGNING_ATTEMPT')


if __name__ == '__main__':
    unittest.main(verbosity=2)
