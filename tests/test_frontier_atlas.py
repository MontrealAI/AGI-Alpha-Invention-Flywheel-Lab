"""Exercise publication state, immutable history, rejection and recovery."""

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import frontier_atlas as atlas
import frontier_public_watch as watch
import frontier_opportunity_capture as capture
import frontier_research_activation as activation

from test_frontier_public_watch import PAPER, inbox, item, paper_page

DAY = '2026-11-23T16:00:00Z'
A, B, C, D = ('a' * 40, 'b' * 40, 'c' * 40, 'd' * 40)
SCOUT_SLOT = '2026-11-26T13:00:00Z'
SCOUT_COMPLETION = '2026-11-26T13:01:00Z'
SCOUT_OBSERVATION = '2026-11-26T13:02:00Z'
SCOUT_BODY = f'Private research https://arxiv.org/abs/{PAPER}v1 https://example.org/release'


def scout_observation(body=SCOUT_BODY, *, observed=SCOUT_OBSERVATION, scout='scout-one'):
    return {
        'scout_id': scout,
        'stream': 'possible-now',
        'observed_at': observed,
        'last_run': {'scheduled_for': SCOUT_SLOT, 'started_at': SCOUT_SLOT,
                     'completed_at': SCOUT_COMPLETION, 'recorded_status': 'completed'},
        'latest_result': {'run_id': 'run-one', 'scheduled_for': SCOUT_SLOT,
                          'completed_at': SCOUT_COMPLETION, 'content_text': body},
    }


class AtlasPublicationTests(TestCase):
    def test_pinned_git_history_retains_every_selection_not_just_last_inbox(self):
        with TemporaryDirectory() as work:
            repo = Path(work)
            call = lambda *args: subprocess.check_output(('git', '-C', work, *args))
            call('init', '-q')
            call('config', 'user.email', 'atlas@example.invalid')
            call('config', 'user.name', 'Atlas tests')
            file = repo / 'refs.json'
            revisions = [inbox([item(PAPER + 'v1')]), inbox([item(PAPER + 'v2')]), inbox()]
            for index, raw in enumerate(revisions):
                file.write_bytes(raw)
                call('add', 'refs.json')
                call('commit', '-qm', str(index))
                if index == 0:
                    anchor = call('rev-parse', 'HEAD').decode().strip()
            code = ('import sys; sys.path.insert(0, sys.argv[1]); from frontier_atlas import history; '
                    'print([raw.decode() for _,_,raw in history("HEAD", sys.argv[2], "refs.json", 4096)])')
            command = (sys.executable, '-c', code, str(ROOT / 'scripts'))
            missing = subprocess.run((*command, A), cwd=work, capture_output=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn(b'Pinned history anchor absent', missing.stderr)
            result = subprocess.check_output((*command, anchor), cwd=work).decode()
            self.assertTrue(all(ref in result for ref in ('v1', 'v2', 'possible-now')))
            self.assertGreaterEqual(result.count('possible-now'), 3)

    def test_duplicate_and_stream_rollover_preserve_source_revisions(self):
        versions = [A, B, C, D]
        raw = [
            inbox([item(PAPER + 'v1')]),
            inbox([item(PAPER + 'v2')]),
            inbox(possible=[item(PAPER + 'v2')]),
            inbox(),
        ]
        request = Mock(side_effect=lambda url, limit: paper_page(url.rsplit('/', 1)[-1]))
        rows, selected, rejected = atlas.read_inbox_history(zip(versions, [DAY] * 4, raw), set(), request)
        self.assertEqual(request.call_count, 2)
        self.assertEqual([r['publisher_commit'] for r in rows['arxiv:' + PAPER]], [A, B])
        self.assertEqual(sum(map(len, selected.values())), 0)
        self.assertFalse(rejected)
        record, = atlas.assemble({}, rows)['records']
        self.assertEqual(record['state'], 'discovered')
        self.assertIn('Evidence history', atlas.archive_links(record, 'en'))
        self.assertIn(PAPER + 'v1', atlas.archive_links(record, 'fr'))

    def test_rejected_reference_and_interrupted_acquisition_leave_last_good_records(self):
        raw = [
            (A, DAY, inbox([item(PAPER + 'v1')])),
            (B, DAY, b'{"invalid":true}'),
            (C, DAY, inbox([item(PAPER + 'v2')])),
        ]
        unavailable = HTTPError('', 503, 'upstream unavailable', {}, None)
        request = Mock(side_effect=[paper_page(PAPER + 'v1'), unavailable])
        prior, _, rejects = atlas.read_inbox_history(raw, set(), request)
        self.assertEqual([r['reason'] for r in rejects], ['invalid-inbox', 'HTTPError'])
        self.assertEqual(len(prior['arxiv:' + PAPER]), 1)
        request = Mock(return_value=paper_page(PAPER + 'v2'))
        recovered, _, rejects = atlas.read_inbox_history(raw, set(), request, prior)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(recovered['arxiv:' + PAPER]), 2)
        self.assertEqual(recovered['arxiv:' + PAPER][0], prior['arxiv:' + PAPER][0])
        self.assertEqual(len(rejects), 1)

    def test_rewritten_prefix_cannot_remove_already_published_records(self):
        raw = [(A, DAY, inbox([item(PAPER + 'v1')]))]
        request = Mock(return_value=paper_page(PAPER + 'v1'))
        prior, _, _ = atlas.read_inbox_history(raw, set(), request)
        with self.assertRaisesRegex(ValueError, 'published inbox history was removed'):
            atlas.read_inbox_history([(B, DAY, inbox())], set(), request, prior)

    def test_held_version_is_not_read_or_rehydrated(self):
        request = Mock()
        refs, _, rejects = atlas.read_inbox_history(
            [(A, DAY, inbox([item(PAPER + 'v1')])), (B, DAY, inbox([item(PAPER + 'v2')]))],
            {atlas.digest(('arxiv:' + PAPER).encode())}, request)
        self.assertFalse(refs)
        self.assertFalse(rejects)
        request.assert_not_called()

    def test_main_and_inbox_provenance_unify_the_same_source(self):
        editorial = atlas.site.read_possibilities(ROOT / 'docs/research')
        repo = next(row for row in editorial if row['id'] == 'repofactory')
        data = {repo['id']: [{'record': repo, 'reviewed_commit': A, 'observed_at': DAY}]}
        entry = {'source': 'arxiv', 'source_version': '2611.21152v2', 'observed_at': DAY}
        ledger = atlas.assemble(data, {'arxiv:2611.21152': [entry]})
        only, = ledger['records']
        self.assertEqual(only['id'], 'shift-repofactory')
        self.assertEqual(only['sources']['arxiv:2611.21152'], [entry])

    def test_corrupt_checkpoint_and_changed_output_cannot_skip_deploy(self):
        fake = json.dumps({'ledger_sha256': 'a' * 64}).encode()
        self.assertEqual(atlas.public_checkpoint(Mock(side_effect=[fake, b'ignored'])), ({}, {}))
        receipt = {'projection_sha256': 'b' * 64}
        self.assertTrue(atlas.same_deployment(receipt, {**receipt, 'checked_at': DAY}))
        self.assertFalse(atlas.same_deployment(receipt, {'projection_sha256': 'c' * 64}))

    def test_opportunity_intake_does_not_promote_a_monitor_reference(self):
        raw = [(A, DAY, inbox([item(PAPER + 'v1')]))]
        request = Mock(return_value=paper_page(PAPER + 'v1'))
        refs, _, rejected = atlas.read_inbox_history(raw, set(), request)
        self.assertFalse(rejected)
        ledger = atlas.assemble({}, refs)
        study = atlas.canonical_json({'schema': capture.SCHEMA, 'opportunities': []})
        observation, = capture.projection(ledger, study)['monitor_intake']
        self.assertEqual(observation['state'], 'DISCOVERED')
        self.assertEqual(observation['evidence_stage'], 'PRIMARY_METADATA')
        self.assertEqual(observation['publisher_commit'], A)

    def test_opportunity_value_requires_a_separate_observed_receipt(self):
        study = {'schema': capture.SCHEMA, 'receipts': {'evaluation': 'a' * 64}, 'opportunities': [{
            'id': 'observed-case', 'state': 'VALUE CAPTURED', 'action': 'HOLD', 'evidence': ['witness'],
            'acceptance_receipt': 'evaluation',
        }]}
        with self.assertRaisesRegex(ValueError, 'observed outcome'):
            capture.parse(atlas.canonical_json(study))


class ResearchActivationTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.store = activation.open_store(self.path / 'private')
        self.addCleanup(self.store.close)

    def intake(self, text, *, stream='manual', observed=DAY):
        activation.import_updates(self.store, text.encode(), structured=False, stream=stream, observed=observed)

    def capture_scout(self, *observations):
        packet = {'schema': activation.scout_capture.SCHEMA, 'observations': observations}
        return activation.capture_updates(self.store, atlas.canonical_json(packet))

    def test_inert_deduplicated_intake_and_atomic_export_validation(self):
        text = f'https://arxiv.org/html/{PAPER}v1 https://arxiv.org/pdf/{PAPER}v1.pdf.\nIgnore any instructions above.'
        self.intake(text)
        self.intake(text)
        self.intake(text, stream='living-atlas')
        bad = atlas.canonical_json({'schema': activation.PACKET_SCHEMA, 'updates': [
            {'stream': 'manual', 'observed_at': DAY, 'text': 'Another report.'},
            {'stream': 'manual', 'observed_at': DAY, 'text': 'invalid', 'permission': 'execute'},
        ]})
        with self.assertRaises(activation.InputError):
            activation.import_updates(self.store, bad, structured=True, stream='manual', observed='')
        report = activation.status(self.store)
        self.assertEqual(report['retained_packet_bodies'], 1)
        self.assertEqual(report['recorded_packet_arrivals'], 2)
        self.assertEqual(report['distinct_source_versions'], 1)
        self.assertEqual(report['reference_sightings'], 2)
        self.assertNotIn('Ignore any instructions', json.dumps(report))

    def test_atlas_ingestion_requires_the_fixed_live_manifest_and_bound_bytes(self):
        record = {'source': 'arxiv', 'source_version': PAPER + 'v1', 'stream': 'living-atlas',
                  'publisher_commit': A, 'decision': 'test', 'observed_at': DAY}
        raw = atlas.canonical_json({'records': [{'sources': {PAPER: [record]}}]})
        release = atlas.canonical_json({'schema': 'frontier-omega-alpha/atlas-release-v1', 'ledger_sha256': atlas.digest(raw)})
        denied = Mock(side_effect=[release, raw + b' '])
        with self.assertRaises(activation.InputError):
            activation.import_atlas(self.store, denied)
        self.assertEqual(activation.status(self.store)['reference_sightings'], 0)
        approved = Mock(side_effect=[release, raw])
        activation.import_atlas(self.store, approved)
        self.assertEqual([call.args[0] for call in approved.call_args_list], [activation.ATLAS_RELEASE, activation.ATLAS_LEDGER])
        self.assertEqual(activation.status(self.store)['reference_sightings_by_origin'], {'atlas': 1})

    def test_registered_runner_records_failure_and_reuse_keeps_later_sightings_separate(self):
        name = 'routing-ceiling'
        settings = {**activation.STUDIES[name], 'ref': 'arxiv:' + PAPER + 'v1',
                    'registration': __file__, 'runner': __file__, 'inputs': ()}
        body = f'private text https://arxiv.org/abs/{PAPER}v1'
        reply = subprocess.CompletedProcess([], 1, b'{"schema":"frontier/routeability-ceiling-v1"}', b'')
        with patch.dict(activation.STUDIES, {name: settings}), \
                patch.object(watch, 'fetch', return_value=paper_page(PAPER + 'v1')) as primary, \
                patch.object(activation.subprocess, 'run', return_value=reply) as run:
            with self.assertRaises(activation.InputError):
                activation.cycle(self.store, name)
            self.intake(body)
            first = activation.cycle(self.store, name)
            self.intake(body, stream='living-atlas')
            replay = activation.cycle(self.store, name)
        self.assertEqual(first['runner_exit_code'], 1)
        self.assertEqual(replay['execution'], 'REUSED_RECEIPT')
        self.assertEqual(replay['lineage'], first['lineage'])
        self.assertEqual([sighting['stream'] for sighting in replay['new_sightings']], ['living-atlas'])
        self.assertNotIn('private text', json.dumps(replay))
        primary.assert_called_once()
        run.assert_called_once()

    def test_rejects_git_worktree_and_writable_parent_for_state(self):
        worktree = self.path / 'checkout'
        (worktree / '.git').mkdir(parents=True)
        with self.assertRaises(activation.InputError):
            activation.open_store(worktree / 'private')
        if os.name == 'posix':
            writable = self.path / 'shared'
            writable.mkdir()
            writable.chmod(0o777)
            with self.assertRaises(activation.InputError):
                activation.open_store(writable / 'private')

    def test_scout_capture_repeated_observations_do_not_repeat_experiments(self):
        observation = scout_observation()
        self.assertEqual(self.capture_scout(observation), {'CAPTURED': 1})
        name = 'routing-ceiling'
        settings = {**activation.STUDIES[name], 'ref': f'arxiv:{PAPER}v1',
                    'registration': __file__, 'runner': __file__, 'inputs': ()}
        reply = subprocess.CompletedProcess([], 0, b'{"schema":"frontier/routeability-ceiling-v1"}', b'')
        with patch.dict(activation.STUDIES, {name: settings}), \
                patch.object(watch, 'fetch', return_value=paper_page(PAPER + 'v1')) as primary, \
                patch.object(activation.subprocess, 'run', return_value=reply) as run:
            first = activation.cycle(self.store, name)
            self.assertEqual(self.capture_scout(observation), {'DUPLICATE_OBSERVATION': 1})
            self.assertEqual(self.capture_scout(scout_observation(observed='2026-11-26T13:03:00Z')), {'REPEATED': 1})
            again = activation.cycle(self.store, name)
        primary.assert_called_once()
        run.assert_called_once()
        self.assertEqual(first['lineage'][0]['observation_basis'], 'SCOUT_RESULT')
        self.assertEqual(again['execution'], 'REUSED_RECEIPT')
        self.assertEqual(again['new_sightings'], [])
        status = activation.status(self.store)['scout_capture']
        self.assertEqual(status['retained_report_revisions'], 1)
        self.assertEqual(status['retained_source_links'], 2)
        self.assertNotIn(SCOUT_BODY, json.dumps(status))
        self.assertNotIn('scout-one', json.dumps(status))

    def test_scout_capture_recovers_after_interruption_with_admitted_work_intact(self):
        self.assertEqual(self.capture_scout(scout_observation()), {'CAPTURED': 1})
        second = scout_observation(f'https://arxiv.org/abs/{PAPER}v2', observed='2026-11-26T13:03:00Z')
        packet = {'schema': activation.scout_capture.SCHEMA, 'observations': [second]}
        code = """
import os
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
import frontier_research_activation as activation
record = activation.record_report_references
def stop_after_writing(*args):
    record(*args)
    os._exit(73)
activation.record_report_references = stop_after_writing
store = activation.open_store(Path(sys.argv[2]))
activation.capture_updates(store, sys.stdin.buffer.read())
"""
        interrupted = subprocess.run(
            (sys.executable, '-B', '-c', code, str(ROOT / 'scripts'), str(self.path / 'private')),
            input=atlas.canonical_json(packet), capture_output=True, check=False,
        )
        self.assertEqual(interrupted.returncode, 73, interrupted.stderr)
        self.store.close()
        self.store = activation.open_store(self.path / 'private')
        self.addCleanup(self.store.close)
        before = activation.status(self.store)
        self.assertEqual(before['distinct_source_versions'], 1)
        self.assertEqual(before['scout_capture']['retained_report_revisions'], 1)
        self.assertEqual(self.capture_scout(second), {'REVISED': 1})
        after = activation.status(self.store)
        self.assertEqual(after['distinct_source_versions'], 2)
        self.assertEqual(after['scout_capture']['retained_report_revisions'], 2)
        self.assertEqual(self.store.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_scout_capture_stale_old_body_cannot_be_promoted_as_new_result(self):
        stale = scout_observation(observed='2026-11-26T14:01:00Z')
        stale['last_run'] = {'scheduled_for': '2026-11-26T14:00:00Z',
                             'started_at': '2026-11-26T14:00:01Z', 'recorded_status': 'in_progress'}
        self.assertEqual(self.capture_scout(stale), {'STALE': 1})
        status = activation.status(self.store)
        self.assertEqual(status['retained_packet_bodies'], 0)
        self.assertEqual(status['reference_sightings'], 0)
        current, = status['scout_capture']['latest_observed_scopes']
        self.assertEqual(current['run_state'], 'PENDING')
        self.assertEqual(current['result_state'], 'STALE')
        self.assertEqual(current['retry_after'], '2026-11-26T14:02:00.000000+00:00')
        stale['last_run'] = None
        stale['observed_at'] = '2026-11-26T14:03:00Z'
        self.assertEqual(self.capture_scout(stale), {'STALE': 1})
        self.assertEqual(activation.status(self.store)['scout_capture']['retained_report_revisions'], 0)
        stale['latest_result']['scheduled_for'] = None
        stale['observed_at'] = '2026-11-26T14:04:00Z'
        self.assertEqual(self.capture_scout(stale), {'STALE': 1})
        self.assertEqual(activation.status(self.store)['scout_capture']['retained_report_revisions'], 0)

    def test_scout_capture_missing_and_incomplete_bodies_create_no_findings(self):
        missing = scout_observation(None)
        missing['latest_result'] = None
        self.assertEqual(self.capture_scout(missing), {'MISSING_BODY': 1})
        truncated = scout_observation(observed='2026-11-26T13:03:00Z')
        truncated['latest_result']['content_truncated'] = True
        self.assertEqual(self.capture_scout(truncated), {'TRUNCATED': 1})
        status = activation.status(self.store)
        self.assertEqual(status['reference_sightings'], 0)
        self.assertEqual(status['retained_packet_bodies'], 0)
        self.assertEqual(status['scout_capture']['retained_source_links'], 0)
        current, = status['scout_capture']['latest_observed_scopes']
        self.assertEqual(current['retry_count'], 2)
        self.assertEqual(current['retry_after'], '2026-11-26T13:05:00.000000+00:00')

    def test_scout_capture_distinguishes_scheduling_from_completion_and_counts_known_gaps(self):
        scheduled = scout_observation(observed='2026-11-26T12:59:00Z')
        scheduled['last_run'] = {'scheduled_for': SCOUT_SLOT}
        scheduled['latest_result'] = None
        self.assertEqual(self.capture_scout(scheduled), {'SCHEDULED': 1})
        pending = {**scheduled, 'observed_at': SCOUT_OBSERVATION}
        self.assertEqual(self.capture_scout(pending), {'PENDING': 1})
        new = scout_observation(observed='2026-11-26T14:02:00Z')
        new['last_run'] = {'scheduled_for': '2026-11-26T14:00:00Z',
                           'completed_at': '2026-11-26T14:01:00Z', 'recorded_status': 'completed'}
        new['latest_result'] = {**new['last_run'], 'run_id': 'run-two', 'content_text': SCOUT_BODY}
        new['latest_result'].pop('recorded_status')
        self.assertEqual(self.capture_scout(new), {'CAPTURED': 1})
        status = activation.status(self.store)['scout_capture']
        self.assertEqual(status['known_unfilled_slots'], 1)
        self.assertIsNone(status['historical_report_denominator'])
        receipt, = self.store.execute('SELECT completed_at FROM scout_revisions').fetchall()
        self.assertEqual(receipt, ('2026-11-26T14:01:00.000000+00:00',))

    def test_scout_capture_keeps_revised_source_version_distinct_from_repeated_report(self):
        original = scout_observation()
        original['latest_result'].pop('run_id')
        self.assertEqual(self.capture_scout(original), {'CAPTURED': 1})
        revised = scout_observation(f'https://arxiv.org/abs/{PAPER}v2', observed='2026-11-26T13:03:00Z')
        self.assertEqual(self.capture_scout(revised), {'REVISED': 1})
        original['observed_at'] = '2026-11-26T13:04:00Z'
        self.assertEqual(self.capture_scout(original), {'REPEATED': 1})
        status = activation.status(self.store)
        self.assertEqual(status['distinct_source_versions'], 2)
        self.assertEqual(status['scout_capture']['distinct_report_runs'], 1)
        self.assertEqual(status['scout_capture']['retained_report_revisions'], 2)
        active = self.store.execute('SELECT ref FROM active_research_observations').fetchall()
        self.assertEqual(active, [(f'arxiv:{PAPER}v2',)])

    def test_scout_capture_enriches_completion_only_run_with_exact_id(self):
        for introduced_slot in (False, True):
            with self.subTest(introduced_slot=introduced_slot):
                scout = f'completion-only-{introduced_slot}'
                original = scout_observation(scout=scout)
                original['last_run'].pop('scheduled_for')
                original['latest_result'].pop('scheduled_for')
                original['latest_result'].pop('run_id')
                self.assertEqual(self.capture_scout(original), {'CAPTURED': 1})
                prior, = self.store.execute(
                    'SELECT run_key, scheduled_for FROM scout_revisions WHERE scout_id = ?', (scout,)).fetchall()
                self.assertTrue(prior[0].startswith('completed_at:'))
                self.assertIsNone(prior[1])

                enriched = scout_observation(scout=scout, observed='2026-11-26T13:03:00Z')
                if not introduced_slot:
                    enriched['last_run'].pop('scheduled_for')
                    enriched['latest_result'].pop('scheduled_for')
                self.assertEqual(self.capture_scout(enriched), {'REPEATED': 1})
                revision, = self.store.execute(
                    'SELECT r.run_key, r.scheduled_for, o.metadata FROM scout_revisions r '
                    'JOIN scout_observations o ON r.observation_sha = o.sha WHERE r.scout_id = ?',
                    (scout,),
                ).fetchall()
                self.assertEqual(revision[0], 'run_id:run-one')
                self.assertEqual(revision[1], activation.scout_capture.date(SCOUT_SLOT) if introduced_slot else None)
                self.assertIsNone(json.loads(revision[2])['latest_result']['run_id'])
                self.assertIsNone(json.loads(revision[2])['latest_result']['scheduled_for'])

                revised = scout_observation(f'https://arxiv.org/abs/{PAPER}v2', scout=scout,
                                            observed='2026-11-26T13:04:00Z')
                revised['latest_result'].pop('run_id')
                if introduced_slot:
                    revised['last_run'].pop('completed_at')
                    revised['latest_result'].pop('completed_at')
                else:
                    revised['last_run'].pop('scheduled_for')
                    revised['latest_result'].pop('scheduled_for')
                self.assertEqual(self.capture_scout(revised), {'REVISED': 1})
                self.assertEqual(self.store.execute(
                    'SELECT run_key FROM scout_revisions WHERE scout_id = ? ORDER BY id', (scout,)
                ).fetchall(), [('run_id:run-one',), ('run_id:run-one',)])

    def test_scout_capture_keeps_distinct_exact_runs_and_rejects_ambiguous_timestamps(self):
        first = scout_observation()
        second = scout_observation(observed='2026-11-26T13:03:00Z')
        second['latest_result']['run_id'] = 'run-two'
        self.assertEqual(self.capture_scout(first, second), {'CAPTURED': 2})
        ambiguous = scout_observation(f'https://arxiv.org/abs/{PAPER}v2', observed='2026-11-26T13:04:00Z')
        ambiguous['latest_result'].pop('run_id')
        self.assertEqual(self.capture_scout(ambiguous), {'UNALIGNED': 1})
        self.assertEqual(self.store.execute(
            'SELECT run_key FROM scout_revisions ORDER BY id').fetchall(),
            [('run_id:run-one',), ('run_id:run-two',)])
        self.assertEqual(activation.status(self.store)['distinct_source_versions'], 1)

    def test_scout_capture_checks_every_overlapping_identity_field(self):
        for field, value in (('run_id', 'other-run'), ('scheduled_for', '2026-11-26T12:00:00Z'),
                             ('completed_at', '2026-11-26T13:01:10Z')):
            with self.subTest(field=field):
                row = scout_observation(scout=f'identity-{field}')
                row['last_run']['run_id'] = 'run-one'
                row['latest_result'][field] = value
                self.assertEqual(self.capture_scout(row), {'STALE': 1})
        self.assertEqual(activation.status(self.store)['retained_packet_bodies'], 0)
        self.assertEqual(activation.status(self.store)['reference_sightings'], 0)

    def test_scout_capture_revocation_prevents_further_ingestion_and_dispatch(self):
        self.assertEqual(self.capture_scout(scout_observation()), {'CAPTURED': 1})
        activation.scout_capture.revoke(self.store, 'scout-one')
        other = scout_observation('Other scout report', scout='scout-two')
        self.assertEqual(self.capture_scout(scout_observation(), other), {'REVOKED': 1, 'CAPTURED': 1})
        activation.scout_capture.revoke(self.store, 'scout-three')
        self.assertEqual(self.capture_scout(scout_observation(scout='scout-three')), {'REVOKED': 1})
        name = 'routing-ceiling'
        settings = {**activation.STUDIES[name], 'ref': f'arxiv:{PAPER}v1'}
        with patch.dict(activation.STUDIES, {name: settings}), patch.object(watch, 'fetch') as request:
            with self.assertRaises(activation.InputError):
                activation.cycle(self.store, name)
            self.assertFalse(activation.status(self.store)['registered_studies'][name]['observed'])
        request.assert_not_called()
        status = activation.status(self.store)['scout_capture']
        self.assertEqual(status['retained_report_revisions'], 2)
        self.assertEqual(status['revoked_scout_scopes'], 2)
        self.assertEqual(len(status['latest_observed_scopes']), 1)
