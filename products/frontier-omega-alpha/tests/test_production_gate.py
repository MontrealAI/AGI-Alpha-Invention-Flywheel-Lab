import copy
from pathlib import Path
import subprocess
import unittest

from native.production_gate import CHECKPOINT, REQUIRED_CHECKS, qualify


class ProductionGateTests(unittest.TestCase):
    commit = 'a' * 40
    environment = 'frontier-omega-alpha-provision'
    path = '/environments/' + environment
    responses = {
        '/branches/main': {'commit': {'sha': commit}, 'protected': True},
        '/rules/branches/main': [
            {'type': 'pull_request', 'parameters': {
                'required_approving_review_count': 1, 'require_last_push_approval': True,
                'dismiss_stale_reviews_on_push': True}},
            {'type': 'required_status_checks', 'parameters': {
                'strict_required_status_checks_policy': True,
                'required_status_checks': [{'context': context, 'integration_id': provider}
                                           for context, provider in sorted(REQUIRED_CHECKS)]}},
            {'type': 'deletion'},
            {'type': 'non_fast_forward'},
        ],
        path: {
            'name': environment,
            'protection_rules': [
                {'type': 'required_reviewers', 'prevent_self_review': True, 'reviewers': [{'type': 'Team'}]},
            ],
            'deployment_branch_policy': {'custom_branch_policies': True},
        },
        path + '/deployment-branch-policies': {'total_count': 1, 'branch_policies': [{'name': 'main', 'type': 'branch'}]},
        CHECKPOINT: [{'type': 'creation', 'ruleset_id': 1}, {'type': 'update', 'ruleset_id': 1},
                     {'type': 'deletion', 'ruleset_id': 2}, {'type': 'non_fast_forward', 'ruleset_id': 2}],
    }

    def test_accepts_main_only_with_github_enforced_reviews_and_checks(self):
        observed = []

        def read(endpoint):
            observed.append(endpoint)
            return self.responses[endpoint]

        qualify(self.environment, self.commit, read)
        self.assertEqual(observed, list(self.responses))
        with self.assertRaisesRegex(ValueError, 'current main'):
            qualify(self.environment, 'b' * 40, read)
        with self.assertRaisesRegex(ValueError, 'approved environment'):
            qualify('github-pages', self.commit, read)

    def test_rejects_unprotected_main_and_ruleset_missing_required_settings(self):
        for branch, rules, message in [
                (False, self.responses['/rules/branches/main'], 'main as protected'),
                (True, [], 'independent review'),
                (True, self.responses['/rules/branches/main'][:1], 'status checks')]:
            with self.subTest(message=message):
                responses = copy.deepcopy(self.responses)
                responses['/branches/main']['protected'] = branch
                responses['/rules/branches/main'] = rules
                with self.assertRaisesRegex(ValueError, message):
                    qualify(self.environment, self.commit, responses.__getitem__)

    def test_requires_stale_review_dismissal_check_origin_and_immutable_main(self):
        for missing, message in [('stale_review_dismissal', 'dismiss stale'), ('check_origin', 'GitHub Actions'),
                                 ('deletion', 'prohibit deletion')]:
            with self.subTest(missing=missing):
                responses = copy.deepcopy(self.responses)
                rules = responses['/rules/branches/main']
                if missing == 'stale_review_dismissal':
                    rules[0]['parameters']['dismiss_stale_reviews_on_push'] = False
                elif missing == 'check_origin':
                    rules[1]['parameters']['required_status_checks'][0].pop('integration_id')
                else:
                    rules.remove({'type': 'deletion'})
                with self.assertRaisesRegex(ValueError, message):
                    qualify(self.environment, self.commit, responses.__getitem__)

    def test_requires_separate_checkpoint_writer_and_immutability_rules(self):
        for edit, message in [('missing_creation', 'both creation and forward updates'),
                              ('shared_bypass_scope', 'separate writer exceptions'),
                              ('allows_upstream_update', 'restrict every update'),
                              ('missing_rule_identity', 'both creation and forward updates')]:
            with self.subTest(edit=edit):
                responses = copy.deepcopy(self.responses)
                checkpoint = responses[CHECKPOINT]
                if edit == 'missing_creation':
                    checkpoint.pop(0)
                elif edit == 'shared_bypass_scope':
                    checkpoint[2]['ruleset_id'] = checkpoint[0]['ruleset_id']
                elif edit == 'allows_upstream_update':
                    checkpoint[1]['parameters'] = {'update_allows_fetch_and_merge': True}
                else:
                    checkpoint[0].pop('ruleset_id')
                with self.assertRaisesRegex(ValueError, message):
                    qualify(self.environment, self.commit, responses.__getitem__)

    def test_checkpoint_write_refuses_missing_or_shared_dispatch_credentials(self):
        script = Path(__file__).resolve().parents[1] / 'native' / 'github-provision.sh'
        for credentials, message in [({'GH_TOKEN': 'test-token'}, 'Missing approved checkpoint writer token'),
                                     ({'GH_TOKEN': 'test-token', 'FRONTIER_ALPHA_CHECKPOINT_TOKEN': 'test-token'},
                                      'Checkpoint writes and Pages dispatch require separate credentials')]:
            with self.subTest(message=message):
                result = subprocess.run(['/bin/bash', str(script)], env=credentials, capture_output=True,
                                        text=True, timeout=10, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertNotIn('test-token', result.stderr)

    def test_rejects_self_approval_and_all_non_main_deployment_policies(self):
        responses = copy.deepcopy(self.responses)
        responses[self.path]['protection_rules'][0]['prevent_self_review'] = False
        with self.assertRaisesRegex(ValueError, 'separate reviewer'):
            qualify(self.environment, self.commit, responses.__getitem__)
        for policies in [[{'name': '*', 'type': 'branch'}], [{'name': 'main', 'type': 'tag'}],
                         [{'name': 'main', 'type': 'branch'}, {'name': 'release', 'type': 'branch'}]]:
            with self.subTest(policies=policies):
                responses = copy.deepcopy(self.responses)
                responses[self.path + '/deployment-branch-policies'] = {
                    'total_count': len(policies), 'branch_policies': policies}
                with self.assertRaisesRegex(ValueError, 'deployment policy'):
                    qualify(self.environment, self.commit, responses.__getitem__)
