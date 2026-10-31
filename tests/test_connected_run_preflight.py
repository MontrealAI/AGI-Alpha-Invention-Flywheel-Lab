import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from connected_enterprise.engine import default_config, run_world, validate_config
from enterprise.runner import RunLock


class ConnectedRunPreflightTests(unittest.TestCase):
    def test_invalid_config_never_acquires_lease_or_enters_engine(self):
        config = default_config()
        config['channels']['pilot']['lead_days'] = 0
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'nested' / 'output'
            with patch('enterprise.runner.RunLock') as lock, patch('connected_enterprise.engine._run_world') as engine:
                with self.assertRaisesRegex(ValueError, 'CONNECTED_CHANNEL_ADVANCE_LEAD_REQUIRED'):
                    run_world(temporary, {}, config, 13, 'growth', output)
                lock.assert_not_called()
                engine.assert_not_called()
            self.assertFalse(output.parent.exists())

    def test_normalized_detached_config_and_options_reach_locked_engine(self):
        config = default_config()
        config['channels']['pilot'].pop('failure_credit_bps')
        original = copy.deepcopy(config)
        source = {'engineering': 'source-sentinel'}
        manifest = {'engineering': 'manifest-sentinel'}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'output'

            def inside(root, received_manifest, received_config, seed, arm, received_output, **options):
                self.assertTrue(output.is_dir())
                self.assertEqual(received_config, validate_config(original))
                self.assertIsNot(received_config, config)
                self.assertIs(received_manifest, manifest)
                self.assertEqual((seed, arm, received_output), (13, 'growth', output.resolve()))
                self.assertEqual(options, {'source': source, 'stop_after_events': 3, 'failpoint': 'engineering-sentinel'})
                with self.assertRaisesRegex(ValueError, 'ANOTHER_CURRENT_RUN_OWNS_OUTPUT'):
                    with RunLock(output):
                        self.fail('lease was not held')
                received_config['channels']['pilot']['lead_days'] = 999
                return 'engineering-result'

            with patch('connected_enterprise.engine._run_world', side_effect=inside):
                self.assertEqual(run_world(temporary, manifest, config, 13, 'growth', output,
                                          source=source, stop_after_events=3, failpoint='engineering-sentinel'),
                                 'engineering-result')
            self.assertEqual(config, original)
            with RunLock(output):
                pass

    def test_existing_output_lease_still_blocks_valid_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with RunLock(output), patch('connected_enterprise.engine._run_world') as engine:
                with self.assertRaisesRegex(ValueError, 'ANOTHER_CURRENT_RUN_OWNS_OUTPUT'):
                    run_world(temporary, {}, default_config(), 13, 'growth', output)
                engine.assert_not_called()


if __name__ == '__main__':
    unittest.main()
