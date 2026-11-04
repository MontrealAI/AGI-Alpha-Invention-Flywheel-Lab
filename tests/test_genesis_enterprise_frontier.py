from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from genesis_enterprise.frontier import observe, changes, validate_hypotheses, proposal_schema
from genesis_enterprise.codex import command, propose


def sample():
    fields = ('beneficiary', 'outcome', 'missing_means', 'best_complete_alternative', 'decisive_experiment', 'commercial_test', 'successor')
    return {'hypotheses': [dict({k: 'Needs empirical investigation ' + str(i) for k in fields},
        id=str(i), frontier_source='https://example.org/primary', status='UNQUALIFIED_HYPOTHESIS') for i in range(3)]}


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.release = {'id': 123, 'tag_name': 'v1', 'draft': False, 'prerelease': False,
                        'html_url': 'https://github.com/openai/codex/releases/tag/v1', 'published_at': '2025-01-01T00:00:00Z'}

    def obs(self): return observe('openai/codex', fetch=lambda _: self.release)

    def test_no_access_inferred(self):
        r = self.obs()
        self.assertEqual(r['access'], 'UNVERIFIED'); self.assertFalse(r['can_activate'])

    def test_observation_timestamp_not_new_release(self):
        old, new = self.obs(), self.obs()
        self.assertEqual(changes([old], [new]), [])

    def test_changed_release_replayed(self):
        old = self.obs(); self.release['tag_name'] = 'v2'
        self.assertEqual(len(changes([old], [self.obs()])), 1)

    def test_arbitrary_url_refused(self):
        with self.assertRaises(ValueError): observe('https://localhost/key', fetch=lambda _: self.release)

    def test_redirect_refused(self):
        from genesis_enterprise.frontier import NoRedirect
        with self.assertRaises(ValueError): NoRedirect().redirect_request(None, None, None, None, None, None)

    def test_draft_prerelease_refused(self):
        for k in ('draft', 'prerelease'):
            self.release[k] = True
            with self.assertRaises(ValueError): self.obs()
            self.release[k] = False

    def test_future_claim_refused(self):
        self.release['published_at'] = '2999-01-01T00:00:00Z'
        with self.assertRaises(ValueError): self.obs()

    def test_wrong_repository_refused(self):
        self.release['html_url'] = 'https://evil.test/openai/codex/releases/v1'
        with self.assertRaises(ValueError): self.obs()

    def test_three_proposals_accepted_as_hypotheses_only(self):
        self.assertEqual(validate_hypotheses(sample()), sample())

    def test_model_cannot_grant_approval(self):
        r = sample(); r['hypotheses'][0]['status'] = 'APPROVED'
        with self.assertRaises(ValueError): validate_hypotheses(r)

    def test_model_cannot_supply_execution_command(self):
        r = sample(); r['hypotheses'][0]['exec'] = 'do anything'
        with self.assertRaises(ValueError): validate_hypotheses(r)

    def test_duplicate_hypothesis_rejected(self):
        r = sample(); r['hypotheses'][2] = r['hypotheses'][0]
        with self.assertRaises(ValueError): validate_hypotheses(r)

    def test_too_few_proposals_rejected(self):
        r = sample(); r['hypotheses'].pop()
        with self.assertRaises(ValueError): validate_hypotheses(r)

    def test_codex_missing_no_api_fallback(self):
        with patch('shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'NO_PROVIDER_FALLBACK'):
                propose('new measurement', [], '/tmp/unused-genesis-output', 'account-model')

    def test_codex_chatgpt_only_readonly(self):
        c = command('/usr/bin/codex', Path('/tmp/x'), 'account-model')
        self.assertIn('forced_login_method="chatgpt"', c)
        self.assertIn('read-only', c); self.assertIn('--ignore-user-config', c)
        self.assertIn('features.shell_tool=false', c)
        self.assertNotIn('danger-full-access', c)

    def test_model_argument_injection_refused(self):
        with self.assertRaises(ValueError): command('codex', Path('/tmp'), '--bad model')

    def test_transport_schema_and_environment(self):
        def fake(cmd, **kw):
            self.assertNotIn('OPENAI_API_KEY', kw['env'])
            self.assertNotIn('OPENAI_BASE_URL', kw['env'])
            self.assertNotIn('SECRET', kw['env'])
            (kw['cwd'] / 'answer.json').write_text(json.dumps(sample()))
            return SimpleNamespace(returncode=0, stdout='{"type":"turn.completed","usage":{"input_tokens":1}}')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'OPENAI_API_KEY': 'not-a-key-test', 'OPENAI_BASE_URL': 'https://invalid', 'SECRET': 'fixture'}):
            r = propose('new observation', [], Path(tmp) / 'result.json', 'account-model', runner=fake, executable='codex')
            self.assertFalse(r['access_or_commercial_qualification_granted'])
            self.assertEqual(r['reported_usage']['input_tokens'], 1)

    def test_failed_transport_does_not_retry(self):
        called = []
        def fake(cmd, **kw):
            called.append(cmd)
            return SimpleNamespace(returncode=1, stdout='')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'NO_API_FALLBACK'):
                propose('new observation', [], Path(tmp) / 'result', 'model', runner=fake, executable='codex')
        self.assertEqual(len(called), 1)


if __name__ == '__main__': unittest.main()
