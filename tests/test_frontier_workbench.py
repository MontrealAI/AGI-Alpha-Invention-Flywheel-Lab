"""Actual private-store/HTTP tests; network radar uses named fixtures, not live inference."""
from __future__ import annotations
import copy
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from frontier_omega.core import canonical, load_file, sha
from frontier_omega.workbench import Workbench, make_server, blank_profile, economics, money, COSTS

ROOT = Path(__file__).resolve().parents[1]
SEEDS = [ROOT / 'examples/frontier-omega' / name for name in
         ('public-opportunities-20261116.json', 'expanded-opportunities-20261116.json')]
CONFIG = {'schema': 'frontier-omega/github-release-sources/v1',
          'repositories': [{'repository': 'example/research', 'tags': ['gpu-kernels']}]}
TOKEN = 'local-test-token-not-a-real-customer-secret-0123456789'


def scenario():
    return {'price': ['100', '200'], 'costs': {k: ['1', '2'] for k in COSTS},
            'loss': ['3', '4'], 'probability_bps': [5000, 9000],
            'basis': 'Authored unit-test scenario; no buyer or actual costs.'}


def release(tag='v1'):
    return {'tag_name': tag, 'html_url': 'https://github.com/example/research/releases/tag/' + tag,
            'name': 'Fixture ' + tag, 'body': 'Authored public release-metadata fixture.'}


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'private'
        self.w = Workbench(self.root)
        for path in SEEDS: self.w.import_snapshot(load_file(path))
        self.problem = 'gpu-kernels-verified-savings'

    def test_twelve_original_and_added_dossiers_use_existing_reservoir(self):
        s = self.w.state()
        self.assertEqual(s['counts']['problems'], 12)
        self.assertEqual(s['counts']['capability_observations'], 5)
        self.assertEqual(s['counts']['retest_signals'], 26)
        self.assertEqual(s['counts']['reported_trials'], 0)
        self.assertTrue(all(p['scenario']['status'] == 'UNKNOWN' for p in s['inventory']))
        self.assertEqual(s['claims']['financial_authority'], 'NONE')

    def test_stage_filter_has_all_selectable_research_options(self):
        from html.parser import HTMLParser
        class Options(HTMLParser):
            def __init__(self):
                super().__init__(); self.in_filter = False; self.in_option = False; self.options = []
            def handle_starttag(self, tag, attrs):
                if tag == 'select' and dict(attrs).get('id') == 'stage': self.in_filter = True
                if self.in_filter and tag == 'option': self.in_option = True
            def handle_endtag(self, tag):
                if tag == 'option': self.in_option = False
                if tag == 'select': self.in_filter = False
            def handle_data(self, data):
                if self.in_filter and self.in_option: self.options.append(data)
        parser = Options(); parser.feed((ROOT / 'frontier_omega/workbench.html').read_text())
        self.assertEqual(parser.options, ['All research stages', 'BLOCKED', 'RETEST', 'TESTING', 'PILOT_REVIEW', 'ARCHIVED'])

    def test_original_problem_bytes_preserved(self):
        old = {p['id']: p for p in load_file(SEEDS[0])['problems']}
        rows = {p['id']: p for p in self.w.reservoir.rows('problems')}
        for k in old: self.assertEqual(sha(old[k]), sha(rows[k]))

    def test_profile_and_scenario_survive_restart(self):
        b = blank_profile(); b.update(stage='TESTING', priority=1, note='A test is scheduled, not passed.', economics=scenario())
        first = self.w.save('profile', self.problem, b, 0)
        self.assertEqual(first['revision'], 1)
        fresh = Workbench(self.root)
        p = next(p for p in fresh.state()['inventory'] if p['id'] == self.problem)
        self.assertEqual(p['profile']['body'], b)
        self.assertIsNone(p['scenario']['actual_profit'])
        self.assertEqual(p['scenario']['low_microUSD_x10000'], 260000000000)
        self.assertEqual(p['scenario']['high_microUSD_x10000'], 1670000000000)

    def test_optimistic_edits_reject_stale_revision(self):
        b = blank_profile(); b['note'] = 'First evidence.'
        self.w.save('profile', self.problem, b, 0)
        b['note'] = 'Stale edit.'
        with self.assertRaisesRegex(ValueError, 'REVISION_CONFLICT'):
            self.w.save('profile', self.problem, b, 0)

    def test_same_edit_is_idempotent(self):
        b = blank_profile(); b['note'] = 'Persistent evidence.'
        a = self.w.save('profile', self.problem, b, 0)
        z = self.w.save('profile', self.problem, b, 1)
        self.assertEqual(a, z)
        self.assertEqual(self.w.audit()['profile_history_records'], 1)

    def test_two_competing_editors_do_not_silently_overwrite(self):
        results = []
        def write(note):
            b = blank_profile(); b['note'] = note
            try: self.w.save('profile', self.problem, b, 0); results.append('saved')
            except ValueError: results.append('conflict')
        ts = [threading.Thread(target=write, args=(s,)) for s in ('First change', 'Second change')]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertCountEqual(results, ['saved', 'conflict'])

    def test_completion_of_retest_requires_a_result_note(self):
        t = self.w.reservoir.rows('triggers')[0]
        with self.assertRaisesRegex(ValueError, 'NEEDS_EVIDENCE'):
            self.w.save('task', t['id'], {'status': 'DONE', 'note': ''}, 0)
        self.w.save('task', t['id'], {'status': 'DONE', 'note': 'Test failed; keep blocker.'}, 0)
        row = next(x for x in self.w.state()['retest_signals'] if x['id'] == t['id'])
        self.assertEqual(row['triage']['body']['status'], 'DONE')
        self.assertFalse(row['execution_authorized'])

    def test_unknown_target_cannot_create_free_floating_claim(self):
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_NOTE_TARGET'):
            self.w.save('profile', 'unknown-problem', blank_profile(), 0)

    def test_paid_or_verified_research_stage_cannot_be_forged(self):
        b = blank_profile()
        for stage in ('PAID', 'VERIFIED', 'PROFITABLE'):
            b['stage'] = stage
            with self.assertRaises(ValueError): self.w.save('profile', self.problem, b, 0)

    def test_economic_unknowns_are_not_assumed_zero(self):
        s = scenario(); s['costs']['support'] = [None, None]
        self.assertEqual(economics(s)['status'], 'UNKNOWN')
        self.assertIsNone(economics(s)['low_microUSD_x10000'])

    def test_every_cost_category_must_exist(self):
        s = scenario(); del s['costs']['maintenance']
        with self.assertRaisesRegex(ValueError, 'TEN_COMPLETE'): economics(s)

    def test_negative_nonfinite_and_float_money_are_rejected(self):
        for value in ('-1', 'NaN', 'Infinity', 1.1, True, '0.0000001', '1e999999999'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError): money(value)

    def test_exact_large_decimal_not_rounded_by_decimal_context(self):
        self.assertEqual(money('1234567890123456789012345678.123456'),
                         1234567890123456789012345678123456)
        self.assertEqual(money('0.000001'), 1)

    def test_probability_boolean_and_reversed_range_rejected(self):
        for v in ([True, 10000], [9000, 1000], [0, 10001]):
            s = scenario(); s['probability_bps'] = v
            with self.assertRaises(ValueError): economics(s)

    def test_complete_scenario_requires_basis(self):
        s = scenario(); s['basis'] = ''
        with self.assertRaisesRegex(ValueError, 'BASIS_REQUIRED'): economics(s)

    def test_reversed_costs_are_rejected(self):
        s = scenario(); s['costs']['research'] = ['3', '2']
        with self.assertRaisesRegex(ValueError, 'LOW_EXCEEDS_HIGH'): economics(s)

    def test_export_reimport_idempotent_snapshot_and_profiles(self):
        b = blank_profile(); b['value_hypothesis'] = 'Potential reusable verification asset.'
        self.w.save('profile', self.problem, b, 0)
        t = self.w.reservoir.rows('triggers')[0]
        self.w.save('task', t['id'], {'status': 'RUNNING', 'note': 'Under evaluation.'}, 0)
        data = self.w.export()
        other = Workbench(Path(self.temp.name) / 'restored')
        other.import_snapshot(data)
        self.assertEqual(other.export(), data)
        self.assertEqual(other.import_snapshot(data)['added_records'], 0)
        self.assertEqual(other.audit()['audit'], 'PASS')

    def test_conflicting_import_rolls_back_prior_insertions(self):
        data = copy.deepcopy(load_file(SEEDS[1]))
        new = copy.deepcopy(data['problems'][0]); new['id'] = 'new-before-conflict'
        changed = copy.deepcopy(data['problems'][1]); changed['title'] += ' changed'
        data['problems'] = [new, changed]
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE_RECORD'):
            self.w.import_snapshot(data)
        self.assertNotIn('new-before-conflict', [p['id'] for p in self.w.reservoir.rows('problems')])

    def test_imported_note_conflict_rolls_back_new_problem(self):
        b = blank_profile(); b['note'] = 'Existing note.'
        self.w.save('profile', self.problem, b, 0)
        data = self.w.export()
        new = copy.deepcopy(data['seed']['problems'][0]); new['id'] = 'new-conflicting-import'
        data['seed']['problems'].append(new)
        data['notes'][0]['body']['note'] = 'Different imported note.'
        with self.assertRaisesRegex(ValueError, 'IMPORT_CONFLICT'):
            self.w.import_snapshot(data)
        self.assertNotIn(new['id'], [p['id'] for p in self.w.reservoir.rows('problems')])

    def test_import_rejects_unknown_seed_fields(self):
        data = load_file(SEEDS[1]); data['spend'] = True
        with self.assertRaises(ValueError): self.w.import_snapshot(data)

    def test_local_history_mutation_is_detected(self):
        b = blank_profile(); b['note'] = 'Original note.'
        self.w.save('profile', self.problem, b, 0)
        with self.w.reservoir.tx() as c: c.execute("UPDATE workbench_history SET body='{}'")
        with self.assertRaisesRegex(ValueError, 'HISTORY_INTEGRITY'): self.w.audit()

    def test_symlink_database_refused(self):
        folder = Path(self.temp.name) / 'linked'; folder.mkdir(mode=0o700)
        (folder / 'frontier.sqlite').symlink_to(self.root / 'frontier.sqlite')
        with self.assertRaisesRegex(ValueError, 'LINKED_STORAGE'): Workbench(folder)

    def test_network_disabled_does_not_invoke_transport(self):
        with patch('frontier_omega.releases._fetch') as fetch:
            with self.assertRaises(PermissionError): self.w.check_sources()
            fetch.assert_not_called()

    def test_configured_radar_creates_retests_without_payment_authority(self):
        seen = []
        def fetch(url): seen.append(url); return release()
        w = Workbench(self.root, CONFIG, network=True, fetch=fetch)
        first = w.check_sources(); second = w.check_sources()
        self.assertEqual(first['sources_checked'], 1)
        self.assertEqual(first['receipts'][0]['retests_queued'], 1)
        self.assertTrue(first['receipts'][0]['added'])
        self.assertFalse(second['receipts'][0]['added'])
        self.assertEqual(len(seen), 2)
        self.assertEqual(first['financial_effects'], 0)
        self.assertEqual(w.audit()['audit'], 'PASS')

    def test_changed_release_generates_a_new_targeted_retest(self):
        values = iter([release('v1'), release('v2')])
        w = Workbench(self.root, CONFIG, network=True, fetch=lambda _: next(values))
        w.check_sources(); w.check_sources()
        tasks = [t for t in w.state()['retest_signals'] if t['problem_id'] == self.problem]
        self.assertEqual(len(tasks), 4)  # Two seeded matches and two release signals.

    def test_unavailable_source_cannot_become_successful_capability_claim(self):
        def failed(_): raise OSError('unavailable')
        w = Workbench(self.root, CONFIG, network=True, fetch=failed)
        before = w.state()['counts']
        out = w.check_sources()
        self.assertEqual(out['receipts'][0]['status'], 'NO_CLAIM_NO_TRIGGER')
        self.assertEqual(w.state()['counts'], before)

    def test_priority_order_is_explicit_not_fake_market_value(self):
        b = blank_profile(); b['priority'] = 1
        self.w.save('profile', self.problem, b, 0)
        self.assertEqual(self.w.state()['inventory'][0]['id'], self.problem)
        self.assertIn('not validated', self.w.state()['ranking_basis'])

    def test_bad_source_configuration_refused(self):
        config = copy.deepcopy(CONFIG); config['repositories'][0]['repository'] = 'evil/../../private'
        with self.assertRaises(ValueError): Workbench(self.root, config)

    def test_old_interface_still_returns_advisory_signals(self):
        self.assertEqual(self.w.reservoir.audit()['audit'], 'PASS')
        self.assertTrue(all(t['execution_authorized'] is False for t in self.w.reservoir.rows('triggers')))


class LauncherTests(unittest.TestCase):
    def test_real_launcher_seeds_twelve_dossiers_and_stops_cleanly(self):
        import subprocess
        import sys
        import re
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.Popen([sys.executable, str(ROOT / 'start_frontier.py'),
                '--root', str(Path(tmp) / 'state'), '--port', '0', '--no-browser'],
                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertIn('FRONTIER', proc.stdout.readline())
                url = proc.stdout.readline().strip()
                match = re.fullmatch(r'http://127\.0\.0\.1:(\d+)/#(.+)', url)
                self.assertIsNotNone(match, url)
                conn = http.client.HTTPConnection('127.0.0.1', int(match.group(1)), timeout=5)
                conn.request('GET', '/api/state', headers={'Authorization': 'Bearer '+match.group(2)})
                res = conn.getresponse(); data = json.loads(res.read()); conn.close()
                self.assertEqual(res.status, 200)
                self.assertEqual(data['counts']['problems'], 12)
                self.assertFalse(data['radar']['network_enabled'])
                self.assertEqual(len(data['radar']['sources']['repositories']), 5)
            finally:
                proc.terminate()
                out, err = proc.communicate(timeout=15)
            self.assertEqual(proc.returncode, 0, err)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.w = Workbench(Path(self.temp.name) / 'private')
        for p in SEEDS: self.w.import_snapshot(load_file(p))
        self.server = make_server(self.w, TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever); self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self, path, data=None, headers=None, raw=False):
        h = {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'}
        if headers: h.update(headers)
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('GET' if data is None else 'POST', path,
                     data if raw else canonical(data) if data is not None else None, h)
        r = conn.getresponse(); body = r.read(); status, hs = r.status, dict(r.getheaders()); conn.close()
        return status, body, hs

    def test_public_shell_never_contains_secret_or_customer_records(self):
        code, body, headers = self.request('/', headers={'Authorization': 'Bearer wrong'})
        self.assertEqual(code, 200); self.assertIn(b'FRONTIER', body)
        self.assertNotIn(TOKEN.encode(), body)
        self.assertNotIn(b'gpu-kernels-verified-savings', body)
        self.assertIn('sha256-', headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')

    def test_private_api_needs_session_token(self):
        self.assertEqual(self.request('/api/state', headers={'Authorization': 'wrong'})[0], 401)
        self.assertEqual(self.request('/api/export', headers={'Authorization': 'wrong'})[0], 401)

    def test_host_and_cross_origin_requests_are_refused(self):
        self.assertEqual(self.request('/api/state', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.request('/api/profile', {}, headers={'Origin': 'https://evil.example'})[0], 401)

    def test_exact_same_origin_is_allowed(self):
        origin = 'http://127.0.0.1:' + str(self.server.server_port)
        self.assertEqual(self.request('/api/state', headers={'Origin': origin})[0], 200)

    def test_real_http_add_profile_and_readback(self):
        p = copy.deepcopy(load_file(SEEDS[1])['problems'][0]); p['id'] = 'browser-added-problem'
        self.assertEqual(self.request('/api/problem', p)[0], 200)
        b = blank_profile(); b.update(note='Written through HTTP.', stage='RETEST')
        self.assertEqual(self.request('/api/profile', {'target': p['id'], 'body': b, 'expected_revision': 0})[0], 200)
        code, raw, _ = self.request('/api/state'); self.assertEqual(code, 200)
        found = next(x for x in json.loads(raw)['inventory'] if x['id'] == p['id'])
        self.assertEqual(found['profile']['body']['note'], b['note'])

    def test_duplicate_json_key_rejected_before_mutation(self):
        self.assertEqual(self.request('/api/import', b'{"schema":1,"schema":2}', raw=True)[0], 400)
        self.assertEqual(self.w.state()['counts']['problems'], 12)

    def test_incorrect_content_type_rejected(self):
        self.assertEqual(self.request('/api/import', {}, headers={'Content-Type': 'text/plain'})[0], 400)

    def test_network_off_endpoint_cannot_trigger_http(self):
        self.assertEqual(self.request('/api/poll', {})[0], 403)

    def test_export_contains_current_state_and_no_session_key(self):
        code, raw, _ = self.request('/api/export')
        self.assertEqual(code, 200); self.assertNotIn(TOKEN.encode(), raw)
        self.assertEqual(len(json.loads(raw)['seed']['problems']), 12)

    def test_http_snapshot_roundtrip(self):
        snap = json.loads(self.request('/api/export')[1])
        code, raw, _ = self.request('/api/import', snap)
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(raw)['added_records'], 0)

    def test_body_size_limit_and_bad_routes(self):
        self.assertEqual(self.request('/api/import', b'{}', {'Content-Length': '2000001'}, raw=True)[0], 400)
        self.assertEqual(self.request('/api/unknown')[0], 404)

    def test_audit_over_http_runs_real_reservoir_audit(self):
        code, raw, _ = self.request('/api/audit', {})
        self.assertEqual(code, 200); self.assertEqual(json.loads(raw)['audit'], 'PASS')

    def test_http_stale_revision_is_rejected(self):
        b = blank_profile(); b['note'] = 'First'
        data = {'target': 'gpu-kernels-verified-savings', 'body': b, 'expected_revision': 0}
        self.assertEqual(self.request('/api/profile', data)[0], 200)
        data['body']['note'] = 'Stale'
        self.assertEqual(self.request('/api/profile', data)[0], 400)

    def test_bad_trial_comparison_does_not_claim_qualified_crossing(self):
        code, raw, _ = self.request('/api/compare', {'problem': 'compiled-crypto-assurance',
            'before': 'flashprove-prototype-20261102', 'after': 'alphaproof-code-20261110'})
        self.assertEqual(code, 200)
        self.assertFalse(json.loads(raw)['economic_crossing_established'])


if __name__ == '__main__': unittest.main()
