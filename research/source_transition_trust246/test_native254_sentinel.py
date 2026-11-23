"""P0-254 fixed third witness; private ephemeral harness simulation only."""
import json
import shutil
from commercial.ledger import digest
from connected_enterprise.operations import prepare_upgrade, upgrade, operate
from tests.test_connected_operating_upgrade import OperatingUpgradeTests


class OwnerPatchNative254(OperatingUpgradeTests):
    def test_second_preparation_does_not_execute_target_codec(self):
        self.legacy()
        manifest = self.case / 'SERVICES.json'
        manifest.write_text(json.dumps(self.manifest))
        prepare_upgrade(self.new, self.old, manifest, self.world, policy=self.policy,
                        expected_checkpoint_sha256=digest(self.before), ident='operating-upgrade-1')
        upgrade(self.world)
        operate(self.world, max_events=2)
        checkpoint_path = self.world / 'STATE.json'
        checkpoint = json.loads(checkpoint_path.read_text())
        self.assertTrue(checkpoint['body']['state']['queue'])
        future = self.case / 'forward-sentinel-source'
        shutil.copytree(self.world / 'source-022', future)
        sentinel = self.case / 'target-code-executed'
        codec = future / 'connected_enterprise/transition_evidence.py'
        codec.write_bytes(codec.read_bytes() + (
            '\nfrom pathlib import Path as _P0254Path\n'
            '_P0254Path(' + repr(str(sentinel)) + ').write_text("synthetic witness")\n'
        ).encode('utf-8'))
        self.assertFalse(sentinel.exists())
        descriptor = prepare_upgrade(
            future, self.world / 'source-022', manifest, self.world, policy=self.policy,
            expected_checkpoint_sha256=digest(checkpoint), ident='operating-upgrade-2')
        self.assertFalse(sentinel.exists(), 'TARGET_CODEC_SIDE_EFFECT')
        self.assertEqual(descriptor['upgrade_request']['id'], 'operating-upgrade-2')
        self.assertEqual(descriptor['upgrade_request']['expected_checkpoint_sha256'], digest(checkpoint))
        self.assertEqual(json.loads(checkpoint_path.read_text()), checkpoint)
        self.assertEqual(self.key.stat().st_ino, self.key_inode)
