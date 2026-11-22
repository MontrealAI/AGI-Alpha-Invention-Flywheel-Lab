import copy
import unittest

from native.production_gate import qualify


class ProductionGateTests(unittest.TestCase):
    commit = 'a' * 40
    environment = 'frontier-omega-alpha-provision'
    path = '/environments/' + environment
    responses = {
        '/branches/main': {'commit': {'sha': commit}, 'protected': True},
        '/rules/branches/main': [
            {'type': 'pull_request', 'parameters': {
                'required_approving_review_count': 1, 'require_last_push_approval': True}},
            {'type': 'required_status_checks', 'parameters': {
                'strict_required_status_checks_policy': True,
                'required_status_checks': [{'context': 'qualification'}]}},
        ],
        path: {
            'name': environment,
            'protection_rules': [
                {'type': 'required_reviewers', 'prevent_self_review': True, 'reviewers': [{'type': 'Team'}]},
            ],
            'deployment_branch_policy': {'custom_branch_policies': True},
        },
        path + '/deployment-branch-policies': {'total_count': 1, 'branch_policies': [{'name': 'main', 'type': 'branch'}]},
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
