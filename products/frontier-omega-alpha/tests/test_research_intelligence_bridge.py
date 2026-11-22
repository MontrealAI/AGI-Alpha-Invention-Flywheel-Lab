from base64 import b64encode
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha1
import json
import unittest

from research.economic_alpha import study
from research.intelligence_bridge import github_intake, intake, member

NOW = datetime(2026, 11, 22, 21, tzinfo=timezone.utc)
WALL = '2026-11-22T20:01:00Z'
EMPTY = {'schema': intake.LEDGER, 'entries': []}
LOCAL = {'submitted_at': WALL, 'submitter': None, 'github_pr': None, 'commit_sha': None, 'authenticated_by': 'local-only'}
REST = {'submitted_at': WALL, 'submitter': 'ApprovedOwner', 'github_pr': 3, 'commit_sha': 'a' * 40,
        'authenticated_by': 'github-rest'}


def finding(profile='prusa-retrofit', **changes):
    if profile == 'prusa-retrofit':
        source, version, baseline = 'prusa', 'ht-400-2026-10-21', 'stock-290'
    else:
        source, version, baseline = 'formal_verification', 'v4.36.0', 'v4.35.0'
    return {'schema': intake.CAPSULE, 'source_task_id': intake.TASK, 'classification': 'public-evidence',
            'profile': profile, 'source': source, 'version': version, 'baseline': baseline,
            'created_at': '2026-11-22T20:00:00Z', 'observed_at': '2026-11-22T19:00:00Z',
            'method': 'manual-export', **changes}


def oem_evidence(value):
    observed = study.named('source_observation.json')
    return intake.fetch_evidence(value, oem=lambda item: (item[0], observed['sources'][item[0]]))


class FindingsTests(unittest.TestCase):
    def test_no_finding_has_no_effect_or_network(self):
        def fail(_):
            self.fail('A no-finding cycle must not acquire sources')
        result = intake.receive(b'null', EMPTY, LOCAL, NOW, evidence=fail)
        self.assertEqual(result, {'disposition': 'no-finding', 'record': None, 'ledger': EMPTY})

    def test_closed_schema_rejects_privacy_scope_and_forged_provenance(self):
        cases = [finding(source_task_id='another-task'), finding(classification='internal'), finding(raw_chat='private text'),
                 finding(url='http://127.0.0.1/'), finding(method='scheduled-writer'), finding(profile='unregistered'),
                 finding(source='unrelated'), finding(created_at='2099-01-01T12:00:00Z')]
        for value in cases:
            with self.assertRaises(ValueError):
                intake.capsule(intake.canonical(value), NOW)
        with self.assertRaises(ValueError):
            intake.capsule(b'{"schema":"x","schema":"y"}', NOW)
        with self.assertRaises(ValueError):
            intake.receive(intake.canonical(finding()), EMPTY, {**LOCAL, 'submitter': 'Bogus'}, NOW, evidence=oem_evidence)

    def test_prepared_approved_verified_encrypted_inputs_and_duplicate(self):
        raw = intake.canonical(finding())
        first = intake.receive(raw, EMPTY, REST, NOW, evidence=oem_evidence)
        self.assertEqual(first['disposition'], 'experiment-prepared')
        self.assertFalse(first['record']['reopened'])
        self.assertEqual(first['record']['evaluation']['independence']['distinct_groups'], 1)
        verified = intake.receive(raw, first['ledger'], REST, NOW, evidence=oem_evidence, run_registered=True)
        self.assertEqual(verified['disposition'], 'technically-verified')
        self.assertEqual(verified['record']['change']['independently_measured']['new_catalog_routes'], 7)
        self.assertTrue(all(value is None for value in verified['record']['economics'].values()))
        self.assertFalse(verified['record']['production_authority'])
        stages = member.packet(verified['record'], verified['ledger'])
        self.assertEqual(set(stages), {'radar', 'opportunity', 'experiment', 'verification', 'compounding', 'archive'})
        self.assertTrue(all(item['en']['paragraphs'] and item['fr']['paragraphs'] for item in stages.values()))
        invalidated = intake.observe_again(verified['ledger'], verified['record']['finding_id'], 'contradicted', NOW)
        with self.assertRaises(ValueError):
            member.packet(verified['record'], invalidated)
        duplicate = intake.receive(intake.canonical(finding(method='interactive-connector')), verified['ledger'], REST, NOW,
                                  evidence=lambda _: self.fail('Duplicate should not fetch'))
        self.assertEqual(duplicate['disposition'], 'duplicate')

    def test_insufficient_evidence_is_recorded_without_repeated_output(self):
        raw = intake.canonical(finding())

        def offline(_):
            raise ValueError('primary evidence missing')

        first = intake.receive(raw, EMPTY, LOCAL, NOW, evidence=offline)
        retry = intake.receive(raw, first['ledger'], LOCAL, NOW, evidence=offline)
        self.assertEqual(first['disposition'], 'source-insufficient')
        self.assertEqual(retry['ledger'], first['ledger'])
        self.assertIsNone(retry['record'])
        self.assertEqual(intake.receive(raw, first['ledger'], LOCAL, NOW, evidence=oem_evidence)['disposition'],
                         'experiment-prepared')

    def test_reopen_requires_material_event_and_matching_historical_condition(self):
        old = {'id': '1' * 64, 'scope': 'formal_verification', 'version': 'v4.35.0', 'phase': 'waiting',
               'effective_on': '2026-10-12', 'at': WALL, 'digest': '2' * 64}
        ledger = {'schema': intake.LEDGER, 'entries': [old]}

        def release_evidence(value):
            return ([{'publisher': 'leanprover/lean4'}], None, '2026-11-16', value['profile'] == 'lean-bitvector')

        generic = intake.receive(intake.canonical(finding('upstream-release')), ledger, LOCAL, NOW, release_evidence)
        self.assertFalse(generic['record']['reopened'])
        material = intake.receive(intake.canonical(finding('lean-bitvector')), generic['ledger'], LOCAL, NOW, release_evidence)
        self.assertTrue(material['record']['reopened'])
        self.assertFalse(material['record']['evaluation']['bounded_runner'])


class GitHubReceiptTests(unittest.TestCase):
    def test_reads_one_immutable_capsule_with_actual_pr_metadata_contract(self):
        value = finding()
        raw = intake.exported_capsule(value)
        sha = sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        identifier = intake.event_id(value)
        repo = {'full_name': github_intake.REPO}
        meta = {'number': 3, 'state': 'open', 'user': {'login': 'ApprovedOwner'}, 'created_at': WALL,
                'base': {'ref': 'main', 'repo': repo}, 'changed_files': 1,
                'head': {'ref': 'bridge-intake/' + identifier, 'sha': 'a' * 40, 'repo': repo}}
        routes = {
            '/pulls/3': meta,
            '/pulls/3/files?per_page=2': [{'filename': intake.INBOX + identifier + '.json', 'status': 'added', 'sha': sha}],
            '/git/blobs/' + sha: {'sha': sha, 'encoding': 'base64', 'size': len(raw), 'content': b64encode(raw).decode()},
        }

        def get(path):
            return deepcopy(routes[path.removeprefix('repos/' + github_intake.REPO)])

        self.assertEqual(github_intake.intake_pr(3, {'ApprovedOwner'}, get), (raw, REST))
        with self.assertRaises(ValueError):
            github_intake.intake_pr(3, {'Other'}, get)
        meta['changed_files'] = 2
        with self.assertRaises(ValueError):
            github_intake.intake_pr(3, {'ApprovedOwner'}, get)
        meta['changed_files'] = 1
        routes['/git/blobs/' + sha]['content'] = b64encode(raw[:-1] + b' ').decode()
        with self.assertRaises(ValueError):
            github_intake.intake_pr(3, {'ApprovedOwner'}, get)


if __name__ == '__main__':
    unittest.main()
