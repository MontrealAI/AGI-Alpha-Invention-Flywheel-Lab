"""Qualification of the source-driven member projector and public scope."""

from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_research_site as site
import frontier_member_value as member
import frontier_member_first as editions

REVISION = 'a' * 40
OBSERVED = '2026-11-23T20:20:00Z'


def sample_ledger():
    reviewed = site.read_possibilities(ROOT / 'docs/research')
    entries = [{
        'id': 'shift-' + row['id'], 'state': site.record_state(row),
        'editorial': [{'reviewed_commit': REVISION, 'observed_at': OBSERVED, 'record': row}], 'sources': {},
    } for row in reviewed]
    primary = {'source':'arxiv', 'source_version':'2611.09822v3', 'observed_at':OBSERVED,
               'decision':'test', 'url':'https://arxiv.org/abs/2611.09822v3', 'publisher_commit':REVISION,
               'title':'Discovering Formally Verified Quantum Programs with AI', 'primary_sha256':'b'*64}
    return {'updated_at': OBSERVED, 'records': entries + [{
        'id': 'watch-arxiv-2611.09822', 'state': 'discovered',
        'editorial': [], 'sources': {'arxiv:2611.09822': [primary]},
    }]}


class MemberValueTests(unittest.TestCase):
    def test_compiles_qualified_falsified_insufficient_and_incumbent_cases(self):
        rows = {r['id']: member.context_for(r) for r in member.decision_briefs(sample_ledger())}
        self.assertEqual(rows['shift-autonomous-endpoint']['verdict'], 'ABSTAIN')
        self.assertEqual(rows['shift-alpha-1-availability']['verdict'], 'DISCARD')
        self.assertEqual(rows['shift-archive-point']['verdict'], 'USE NOW')
        self.assertEqual(rows['shift-measurement-gap']['atlas_state'], 'falsified')
        self.assertIn('Gaussian process', rows['shift-measurement-gap']['en']['missing_move'])
        self.assertIn('processus gaussien', rows['shift-measurement-gap']['fr']['missing_move'])
        new = rows['watch-arxiv-2611.09822']
        self.assertEqual(new['evidence'], 'source-identity-only')
        self.assertEqual(new['verdict'], 'PREPARE')
        self.assertEqual(new['source_version'], '2611.09822v3')
        for brief in rows.values():
            self.assertIsNone(brief['member_lead_seconds'])
            self.assertIsNone(brief['protected_release'])
            self.assertIsNone(brief['complete_cost'])
            for language in ('en', 'fr'):
                self.assertTrue(all(brief[language][field] for field in member.FIELDS))

    def test_member_output_is_staged_public_only_and_is_stable(self):
        with TemporaryDirectory() as x, TemporaryDirectory() as y:
            left, right = Path(x), Path(y)
            produced, html, seal = member.prepare(left, sample_ledger(), 'f' * 64)
            second, _, other = member.prepare(right, sample_ledger(), 'f' * 64)
            self.assertEqual(produced, second)
            self.assertEqual(seal, other)
            self.assertEqual({p.name for p in left.iterdir()}, {member.ENDPOINT_ZIP, member.ARCHIVE_ZIP, member.MEMBER_JSON})
            self.assertEqual(produced['publication'], 'public-file')
            self.assertIsNone(produced['protected_member_first'])
            self.assertIsNone(produced['real_member_trials'])
            self.assertEqual(produced['atlas_sha256'], 'f' * 64)
            for language in ('en', 'fr'):
                self.assertIn('id="mv-endpoint-run"', html[language])
                self.assertEqual(html[language].count('data-mv-record'), len(sample_ledger()['records']))
                self.assertNotIn('<!-- MV_', html[language])
                self.assertIn(produced['capabilities']['archive']['sha256'], html[language])
                self.assertIn('data-edition-run="1"', html[language])
                self.assertEqual(html[language].count('data-mv-open'), 7)
                self.assertEqual(html[language].count('href="#opportunity-capture"'), 1)
                self.assertIn('id="goal-form"', html[language])
                self.assertEqual(html[language].count('data-member-view'), 6)
                self.assertIn('id="double-flywheel" data-double-flywheel aria-labelledby="df-title" data-member-view hidden', html[language])
                self.assertIn('href="#double-flywheel"', html[language])
                self.assertNotIn('data-double-flywheel', member.home_preview(produced, language))
                self.assertEqual(html[language].count('id="mv-consent"'), 1)
                self.assertIn('id="mf-outcome" class="mf-outcome" hidden', html[language])
                for brief in produced['briefs']:
                    self.assertIn(f'data-review="{brief["review_sha256"]}"', html[language])
                self.assertEqual(member.public_feature(produced, language), '')
                preview = member.home_preview(produced, language)
                self.assertIn(f'data-preview-count="{len(produced["briefs"])}"', preview)
                self.assertIn('data-preview-version="2611.09822v3"', preview)
                self.assertIn('Endpoint Evidence Screen', preview)
                self.assertIn('NOAA Archive Point', preview)

    def test_recheck_carries_unchanged_evidence_and_flags_a_corrected_next_move(self):
        with TemporaryDirectory() as work:
            value, _, _ = member.prepare(Path(work), sample_ledger(), 'f' * 64)
        brief = next(row for row in value['briefs'] if row['id'] == 'shift-autonomous-endpoint')
        updated = deepcopy(brief)
        updated['updated_at'] = '2026-11-24T20:20:00Z'
        self.assertEqual(member.review_digest(updated, value['capabilities']), brief['review_sha256'])
        updated['fr']['next'] = 'Une correction à examiner.'
        self.assertNotEqual(member.review_digest(updated, value['capabilities']), brief['review_sha256'])

    def test_public_recaps_follow_verified_member_editions_and_quiet_runs(self):
        briefs = member.decision_briefs(sample_ledger())
        pending = editions.feed(briefs, {}, '100', Mock())
        self.assertEqual(pending['edition']['source_version'], '2611.09822v3')
        self.assertIsNone(pending['public_feature'])
        outside_schedule = Mock(return_value=OBSERVED)
        self.assertEqual(editions.feed(briefs, pending, '101', outside_schedule, promote=False), pending)
        outside_schedule.assert_not_called()
        witness = Mock(return_value=None)
        self.assertEqual(editions.feed(briefs, pending, '101', witness), pending)
        witness.assert_called_once_with('100')
        witness.return_value = OBSERVED
        featured = editions.feed(briefs, pending, '102', witness)
        self.assertEqual(featured['public_feature'], {**pending['edition'], 'public_run': '102',
                                                     'member_checked_at': OBSERVED})
        quiet = Mock()
        self.assertEqual(editions.feed(briefs, featured, '103', quiet), featured)
        quiet.assert_not_called()
        revised = {**briefs[-1], 'source_version': '2611.09822v4', 'updated_at': '2026-11-23T21:00:00Z'}
        following = editions.feed([*briefs[:-1], revised], featured, '104', Mock())
        self.assertIsNone(following['public_feature'])
        self.assertEqual(following['edition']['source_version'], revised['source_version'])

    def test_confirmation_rejects_wrong_runs_and_unverified_steps(self):
        finished = {'name': editions.CHECK_STEP, 'conclusion': 'success', 'completed_at': OBSERVED}
        jobs = [{'name': 'verify-live', 'run_id': 100, 'steps': [{**finished, 'conclusion': 'failure'}]},
                {'name': 'build', 'run_id': 100, 'steps': [finished]},
                {'name': 'verify-live', 'run_id': 101, 'steps': [finished]}]
        request = Mock(side_effect=lambda *_: json.dumps({'jobs': jobs}).encode())
        self.assertIsNone(editions.witnessed_run('100', request))
        jobs.append({'name': 'verify-live', 'run_id': 100, 'steps': [finished]})
        self.assertEqual(editions.witnessed_run('100', request), OBSERVED)
        self.assertIsNone(editions.witnessed_run('100?elsewhere', request))
