"""A repeated historical audit must recheck its transitive content-addressed evidence."""
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from commercial.ledger import canonical
from connected_enterprise import upgrades
from connected_enterprise.transition_evidence import evidence_directory


class HistoricalAuditCacheIntegrityTests(unittest.TestCase):
    def test_missing_nested_cas_blob_cannot_reuse_earlier_acceptance(self):
        upgrades._HISTORICAL_AUDITS.clear()
        with tempfile.TemporaryDirectory(prefix='historical-cas-replay-') as temporary:
            base = Path(temporary)
            root = base / 'historical'
            (root / 'connected_enterprise').mkdir(parents=True)
            (root / 'connected_enterprise/finance.py').write_text('SYNTHETIC = True\n')
            inventory = upgrades.source_inventory(root)
            evidence = base / 'evidence'
            evidence.mkdir()
            raw = canonical({'schema': 'synthetic-prior-record/v1', 'prior_cash': 42})
            name = hashlib.sha256(raw).hexdigest()
            (evidence / name).write_bytes(raw)
            reference = {'sha256': name, 'bytes': len(raw)}
            nested = {'body': {'schema': 'agi-alpha/native-source-transition/v2-cas',
                               'id': 'older-transition', 'account_path': str(base / 'account.sqlite'),
                               'from_source': {'files': {}, 'sha256': 'a' * 64},
                               'to_source': {'files': {}, 'sha256': 'b' * 64},
                               'counter': 1, 'expected_state_digest': 'c' * 64, 'day': 1,
                               'historical_root': str(root), 'verifier_files': inventory,
                               'evidence': {'prior_record': reference, 'prior_envelope': reference}},
                      'signature': '0' * 64}
            body = {'schema': 'agi-alpha/native-source-transition/v1',
                    'historical_root': str(root), 'verifier_files': inventory,
                    'from_source': {'sha256': 'd' * 64},
                    'prior_record': {'connected_journal': {'source_history': [nested]}}}
            key = os.urandom(32)
            ticket = {'body': body, 'signature': hmac.new(key, upgrades.DOMAIN + canonical(body), hashlib.sha256).hexdigest()}
            invocations = []

            def replay(_root, _code, payload, _inventory):
                invocations.append(payload['evidence_dir'])
                if not (evidence / name).is_file():
                    return SimpleNamespace(returncode=1, stdout='', stderr='TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
                return SimpleNamespace(returncode=0, stdout=json.dumps({'accepted': True}), stderr='')

            with patch('commercial.ledger.load_jobs'), patch.object(upgrades, '_run_pinned_historical_python', side_effect=replay):
                with evidence_directory(evidence), upgrades._owner_authenticated_history([ticket], key):
                    self.assertTrue(upgrades.verify_historical(ticket, {}, root=root)['accepted'])
                    (evidence / name).unlink()
                    with self.assertRaisesRegex(ValueError, 'PINNED_HISTORICAL_AUDIT_FAILED'):
                        upgrades.verify_historical(ticket, {}, root=root)
            self.assertEqual(invocations, [str(evidence), str(evidence)])


if __name__ == '__main__':
    unittest.main()
