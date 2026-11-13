"""Independent, signer-free adversarial descriptor race probe for PR40.

This does not authenticate any real financial account. It exercises the actual
public prepare_upgrade control flow while replacing only the signer and source
copy operations with bounded synthetic fixtures. Never use its test objects as
financial receipts.
"""
import concurrent.futures
import json
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise import operations
from connected_enterprise.migration import default_policy


class PrepareUpgradeRace154(unittest.TestCase):
    def test_conflicting_writers_cannot_both_accept_same_checkpoint(self):
        """Two distinct pending target authorizations must not both succeed."""
        with tempfile.TemporaryDirectory(prefix='transition-prepare-race154-') as tmp:
            root = Path(tmp)
            output = root / 'business'
            output.mkdir()
            target = root / 'target-source'
            target.mkdir()
            manifest_path = root / 'SERVICES-ORIGINAL.json'
            manifest = {'synthetic': 'manifest-only; no real service or revenue'}
            manifest_path.write_text(json.dumps(manifest))
            prior = {'body': {'state': {
                'config': {'opening': 1000000, 'working': 500000},
                'source': {'sha256': 'a' * 64, 'files': {}},
                'seed': 154, 'arm': 'baseline', 'last_time': 0, 'current': None
            }}, 'signature': 'synthetic-not-authenticated'}
            (output / 'STATE.json').write_text(json.dumps(prior))
            checkpoint_sha = digest(prior)
            target_source = {'sha256': 'b' * 64, 'files': {}}
            authorization_barrier = threading.Barrier(2)
            entered = []
            entered_lock = threading.Lock()

            def mocked_authorizer(**kwargs):
                with entered_lock:
                    entered.append(kwargs['ident'])
                # Both callers have already passed the initial OPERATOR.json
                # existence check. A future exclusive-lock fix may serialize
                # before this point; timed barrier then simply releases one.
                try:
                    authorization_barrier.wait(timeout=1.5)
                except threading.BrokenBarrierError:
                    pass
                return {'body': {'scope': 'test-only'}, 'signature': 'not-an-HMAC'}

            def prepare(ident):
                return operations.prepare_upgrade(
                    target, target, manifest_path, output,
                    policy=default_policy(), expected_checkpoint_sha256=checkpoint_sha,
                    ident=ident)

            # Serialize only individual atomic file writes to rule out a
            # coincidental readback race. This does NOT serialize validation
            # or the source/authority decision under test.
            original_write = operations._write
            write_lock = threading.Lock()
            def serialized_file_write(path, value):
                with write_lock:
                    return original_write(path, value)

            with (patch('connected_enterprise.upgrades.authorize_upgrade', side_effect=mocked_authorizer),
                  patch('connected_enterprise.upgrades.validate_ticket', return_value=None),
                  patch('connected_enterprise.runner.identity', return_value=target_source),
                  patch.object(operations, '_copy_source', return_value=target_source),
                  patch.object(operations, '_copy_inputs', return_value=None),
                  patch.object(operations, '_write', side_effect=serialized_file_write)):
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    futures = [pool.submit(prepare, 'writer-A'), pool.submit(prepare, 'writer-B')]
                    outcomes = []
                    for future in futures:
                        try:
                            outcomes.append(('accepted', future.result(timeout=10)))
                        except Exception as exc:
                            outcomes.append(('rejected', type(exc).__name__ + ':' + str(exc)))

            accepted = [value for status, value in outcomes if status == 'accepted']
            # This is a safety contract, not a claim that mocked signatures are
            # valid. Both writers succeeding on the same prior checkpoint makes
            # the active operator descriptor depend on a write race.
            self.assertLessEqual(len(accepted), 1,
                'CONFLICTING_PREPARES_BOTH_ACCEPTED_SAME_CHECKPOINT: '
                + repr({'entered': entered, 'outcomes': outcomes}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
