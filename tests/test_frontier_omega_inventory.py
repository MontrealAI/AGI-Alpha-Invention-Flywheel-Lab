import copy
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from frontier_omega.core import COSTS,TRIAL_SCHEMA,FRONTIER_SCHEMA,canonical,sha
from frontier_omega.catalog import additions,briefs_for
from frontier_omega.inventory import Inventory,validate_brief,render,atomic

NOW='2026-11-16'

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'private'
        self.inv=Inventory(self.root);self.p=additions()[0]
        self.inv.reservoir.add(self.p)
        self.brief=briefs_for([self.p])[0];self.inv.add_brief(self.brief)
    def tearDown(self):self.tmp.cleanup()
    def event(self,ident='new-release',when='2026-11-10',tags=None):
        f=dict(schema=FRONTIER_SCHEMA,id=ident,title='Reported capability update',observed_on=when,
               description='Synthetic observation; not actual model evaluation.',tags=tags or self.p['tags'],
               source_urls=['https://example.org/release'],availability='REPORTED')
        self.inv.reservoir.add(f);return f
    def trial(self,frontier,ident,cost,**changes):
        t=dict(schema=TRIAL_SCHEMA,id=ident,problem_id=self.p['id'],frontier_id=frontier,
               run_on=NOW,terms_sha256=sha('terms'),acceptance_sha256=sha(self.p['acceptance']),
               protocol_sha256=sha('protocol'),evidence_sha256=sha(ident),scope='AUTHORED_SCENARIO',
               passed=True,independent_check=True,price_microUSD=10_000_000,
               acceptance_probability_bps=10000,costs_microUSD={k:cost if k=='construction' else 0 for k in COSTS},
               expected_loss_microUSD=0,alternative=dict(name='Ordinary implementation',qualified=False,complete_cost_microUSD=None))
        t.update(changes);self.inv.reservoir.add(t);return t
    def pair(self,**changes):
        self.event('old-release','2026-10-12');self.event()
        self.trial('old-release','old-trial',12_000_000)
        self.trial('new-release','new-trial',5_000_000,**changes)
    def row(self):return self.inv.plan(NOW)['inventory'][0]
    def test_catalog_validates_and_has_no_invented_prices(self):
        for p in additions():
            self.inv.reservoir.add(p)
            for b in briefs_for([p]):self.inv.add_brief(b)
            self.assertIsNone(p['demand']['ceiling_microUSD'])
        self.assertEqual(len(self.inv.plan(NOW)['inventory']),6)
    def test_unknown_value_stays_unknown(self):
        r=self.row();self.assertIsNone(r['comparison']);self.assertEqual(r['action'],'MONITOR')
    def test_recent_event_requeues_targeted_replay(self):
        self.event();r=self.row();self.assertEqual(r['action'],'REPLAY_CANDIDATE')
        self.assertFalse(r['packet']['execution_authorized'])
    def test_future_observation_does_not_trigger(self):
        self.event(when='2026-11-17');self.assertEqual(self.row()['action'],'MONITOR')
    def test_old_observation_does_not_trigger(self):
        self.event(when='2026-10-12');self.assertEqual(self.row()['action'],'MONITOR')
    def test_irrelevant_observation_does_not_trigger(self):
        self.event(tags=['unrelated-domain']);self.assertEqual(self.row()['action'],'MONITOR')
    def test_reported_crossing_never_authorizes_money(self):
        self.pair();r=self.row();self.assertEqual(r['action'],'REVIEW_DEMAND')
        self.assertTrue(r['comparison']['reported_crossing']);self.assertFalse(r['comparison']['actual_profit_established'])
    def test_strong_current_competitor_wins(self):
        self.pair(alternative=dict(name='Ordinary route',qualified=True,complete_cost_microUSD=4_000_000))
        self.assertEqual(self.row()['action'],'COMPARE_INCUMBENT')
    def test_strong_historical_alternative_blocks_false_crossing(self):
        self.event('old-release','2026-10-01');self.event()
        self.trial('old-release','old-trial',12_000_000,alternative=dict(name='Strong prior route',qualified=True,complete_cost_microUSD=4_000_000))
        self.trial('new-release','new-trial',5_000_000)
        self.assertFalse(self.row()['comparison']['reported_crossing'])
    def test_strongest_historical_arm_used(self):
        self.pair();self.event('better-old','2026-10-02');self.trial('better-old','strong-old',1_000_000)
        r=self.row();self.assertEqual(r['comparison']['before_trial'],'strong-old');self.assertFalse(r['comparison']['reported_crossing'])
    def test_price_changes_do_not_fake_frontier_uplift(self):
        self.pair(price_microUSD=20_000_000);self.assertIsNone(self.row()['comparison'])
    def test_wrong_acceptance_not_matched(self):
        self.pair(acceptance_sha256=sha('other contract'));self.assertIsNone(self.row()['comparison'])
    def test_future_trial_not_selected(self):
        self.pair(run_on='2026-11-17');self.assertIsNone(self.row()['comparison'])
    def test_failed_current_arm_not_positive(self):
        self.pair(passed=False);self.assertFalse(self.row()['comparison']['reported_crossing'])
    def test_missing_independent_check_not_crossing(self):
        self.pair(independent_check=False);self.assertFalse(self.row()['comparison']['reported_crossing'])
    def test_expired_buyer_request_deprioritized(self):
        p=copy.deepcopy(self.p);p['id']='expired-buyer-request'
        p['demand'].update(status='CUSTOMER_REPORTED_UNVERIFIED',deadline='2026-11-15')
        self.inv.reservoir.add(p)
        r=next(r for r in self.inv.plan(NOW)['inventory'] if r['problem']['id']==p['id'])
        self.assertEqual(r['action'],'EXPIRED_DEMAND')
    def test_unknown_brief_requests_explicit_test(self):
        p=additions()[1];self.inv.reservoir.add(p)
        r=next(r for r in self.inv.plan(NOW)['inventory'] if r['problem']['id']==p['id'])
        self.assertEqual(r['action'],'DEFINE_TEST')
    def test_brief_must_bind_exact_problem(self):
        b=copy.deepcopy(self.brief);b['problem_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'BINDING'):self.inv.add_brief(b)
    def test_future_brief_not_used(self):
        b=copy.deepcopy(self.brief);b['id']='future-brief';b['assessed_on']='2026-12-01'
        self.inv.add_brief(b);self.assertEqual(self.row()['brief']['id'],self.brief['id'])
    def test_brief_immutable(self):
        b=copy.deepcopy(self.brief);b['value_driver']='Changed value hypothesis'
        with self.assertRaisesRegex(ValueError,'IMMUTABLE'):self.inv.add_brief(b)
    def test_brief_idempotent(self):self.assertFalse(self.inv.add_brief(self.brief))
    def test_threshold_rejects_boolean(self):
        b=copy.deepcopy(self.brief);b['criteria'][0]['target']=True
        with self.assertRaisesRegex(ValueError,'THRESHOLD'):validate_brief(b)
    def test_duplicate_metrics_rejected(self):
        b=copy.deepcopy(self.brief);b['criteria'].append(b['criteria'][0])
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):validate_brief(b)
    def test_repeat_refresh_is_idempotent(self):
        self.assertEqual(self.inv.refresh(NOW)['tasks_added'],1)
        self.assertEqual(self.inv.refresh(NOW)['tasks_added'],0)
    def test_restart_retains_queue(self):
        self.inv.refresh(NOW);new=Inventory(self.root)
        self.assertEqual(new.refresh(NOW)['tasks_added'],0)
    def test_daily_refresh_no_duplicate_alerts(self):
        self.inv.refresh(NOW);self.assertEqual(self.inv.refresh('2026-11-17')['tasks_added'],0)
    def test_changed_evidence_supersedes_pending_task(self):
        old=self.inv.refresh(NOW)['inventory'][0]['task_id'];self.event()
        r=self.inv.refresh(NOW);self.assertEqual(r['tasks_added'],1)
        with self.inv.reservoir.tx() as c:self.assertEqual(c.execute('SELECT state FROM research_queue WHERE id=?',(old,)).fetchone()[0],'SUPERSEDED')
    def test_acknowledged_task_not_reopened(self):
        ident=self.inv.refresh(NOW)['inventory'][0]['task_id']
        self.assertTrue(self.inv.acknowledge(ident,'Reviewed, more evidence needed.'))
        r=self.inv.refresh(NOW);self.assertEqual(r['inventory'][0]['task_state'],'ACKNOWLEDGED')
    def test_ack_conflict_rejected(self):
        ident=self.inv.refresh(NOW)['inventory'][0]['task_id'];self.inv.acknowledge(ident,'Reviewed once.')
        with self.assertRaisesRegex(ValueError,'CONFLICT'):self.inv.acknowledge(ident,'Changed note.')
    def test_refresh_does_not_rewind_live_queue(self):
        self.inv.refresh(NOW)
        with self.assertRaisesRegex(ValueError,'CLOCK'):self.inv.refresh('2026-11-15')
        self.assertEqual(self.inv.plan('2026-11-15')['as_of'],'2026-11-15')
    def test_tampered_source_rejected(self):
        with self.inv.reservoir.tx() as c:c.execute("UPDATE problems SET body='{}'")
        with self.assertRaises((ValueError,KeyError)):self.inv.plan(NOW)
    def test_tampered_queue_rejected(self):
        self.inv.refresh(NOW)
        with self.inv.reservoir.tx() as c:c.execute("UPDATE research_queue SET hash='bad'")
        with self.assertRaisesRegex(ValueError,'INTEGRITY'):self.inv.refresh(NOW)
    def test_html_escapes_untrusted_content(self):
        plan=self.inv.plan(NOW);plan['inventory'][0]['problem']['title']='<img src=x onerror=alert(1)>'
        text=render(plan);self.assertNotIn('<img',text);self.assertIn('&lt;img',text)
    def test_output_symlink_refused(self):
        target=Path(self.tmp.name)/'outside';target.write_text('preserve')
        (self.root/'INVENTORY.json').symlink_to(target)
        with self.assertRaisesRegex(ValueError,'SYMLINK'):self.inv.refresh(NOW)
        self.assertEqual(target.read_text(),'preserve')
    def test_state_symlink_refused(self):
        other=Path(self.tmp.name)/'other';other.mkdir(mode=0o700)
        (other/'frontier.sqlite').symlink_to(self.root/'frontier.sqlite')
        with self.assertRaisesRegex(ValueError,'SYMLINK'):Inventory(other)
    def test_process_lock_enforced(self):
        with self.inv.reservoir.lock():
            with self.assertRaisesRegex(RuntimeError,'WORKER'):self.inv.refresh(NOW)
    def test_watch_ingests_and_stops(self):
        f=self.event();f['id']='incoming-release'
        (self.root/'inbox'/'incoming.json').write_bytes(canonical(f))
        result=self.inv.watch(.05,cycles=2)
        self.assertEqual(result['polls_completed'],2)
        self.assertTrue((self.root/'INVENTORY.html').is_file())
    def test_watch_interrupt(self):
        stop=threading.Event();stop.set();self.assertEqual(self.inv.watch(.05,stop=stop)['polls_completed'],0)
    def test_bad_watch_interval(self):
        with self.assertRaises(ValueError):self.inv.watch(float('nan'),cycles=1)
    def test_negative_economics_stay_negative(self):
        self.pair(costs_microUSD={k:30_000_000 if k=='construction' else 0 for k in COSTS})
        r=self.row();self.assertEqual(r['action'],'MEASURE_ECONOMICS');self.assertFalse(r['comparison']['reported_crossing'])

    def release_config(self):
        return {'schema':'frontier-omega/github-release-sources/v1','repositories':[
            {'repository':'example/research','tags':self.p['tags']}]}
    def test_combined_watch_polls_once_with_single_writer(self):
        calls=[]
        def fetch(url):
            calls.append(url)
            return {'tag_name':'v1','html_url':'https://github.com/example/research/releases/tag/v1',
                    'name':'New release','body':'Reported capability, not measured outcome.'}
        result=self.inv.watch(.05,cycles=2,release_config=self.release_config(),release_fetch=fetch)
        self.assertEqual(result['polls_completed'],2);self.assertEqual(len(calls),1)
        self.assertEqual(len(self.inv.reservoir.rows('frontiers')),1)
        self.assertTrue((self.root/'RADAR.json').exists())
        from frontier_omega.core import load_file
        self.assertEqual(load_file(self.root/'INVENTORY.json')['inventory'][0]['action'],'REPLAY_CANDIDATE')
    def test_watch_network_disabled_without_source_config(self):
        with patch('frontier_omega.releases._fetch',side_effect=AssertionError('No network allowed')):
            self.inv.watch(.05,cycles=1)
    def test_failed_public_source_is_not_a_capability(self):
        def fail(_):raise OSError('offline')
        self.inv.watch(.05,cycles=1,release_config=self.release_config(),release_fetch=fail)
        self.assertEqual(self.inv.reservoir.rows('frontiers'),[])
    def test_restarted_release_watch_preserves_first_observation(self):
        def fetch(_):return {'tag_name':'v1','html_url':'https://github.com/example/research/releases/tag/v1'}
        self.inv.watch(.05,cycles=1,release_config=self.release_config(),release_fetch=fetch)
        before=self.inv.reservoir.rows('frontiers')
        restarted=Inventory(self.root)
        restarted.watch(.05,cycles=1,release_config=self.release_config(),release_fetch=fetch)
        self.assertEqual(before,restarted.reservoir.rows('frontiers'))
    def test_invalid_release_poll_refused(self):
        with self.assertRaises(ValueError):self.inv.watch(.05,cycles=1,release_every=0)
    def test_negative_cycle_count_refused(self):
        with self.assertRaises(ValueError):self.inv.watch(.05,cycles=-1)
    def test_source_config_cannot_supply_arbitrary_url(self):
        c=self.release_config();c['repositories'][0]['repository']='https://private.example/path'
        with self.assertRaises(ValueError):self.inv.watch(.05,cycles=1,release_config=c)
    def test_old_monitor_task_reopens_when_signal_expires(self):
        old=self.inv.refresh(NOW)['inventory'][0]['task_id'];self.event()
        self.inv.refresh(NOW);new=self.inv.refresh('2026-12-20')
        self.assertEqual(new['inventory'][0]['task_id'],old)
        self.assertEqual(new['inventory'][0]['task_state'],'OPEN')
        self.assertEqual(new['tasks_reopened'],1)
    def test_cli_brief_import_is_bound_and_idempotent(self):
        path=Path(self.tmp.name)/'brief.json';path.write_bytes(canonical(self.brief))
        result=subprocess.run([sys.executable,'-m','frontier_omega.inventory','--root',str(self.root),
                               'brief','--file',str(path)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('"brief_added":false',result.stdout)
    def test_mismatched_trial_scope_refused(self):
        self.pair(scope='OPERATOR_REPORTED_UNVERIFIED')
        self.assertIsNone(self.row()['comparison'])
    def test_buyer_ceiling_blocks_reported_crossing(self):
        # A separate source-bound problem; do not mutate a frozen record.
        p=copy.deepcopy(self.p);p['id']='buyer-priced-demand'
        p['demand'].update(status='CUSTOMER_REPORTED_UNVERIFIED',ceiling_microUSD=1_000_000)
        self.inv.reservoir.add(p);self.p=p
        self.inv.add_brief(briefs_for([additions()[0]])[0])
        self.pair()
        r=next(r for r in self.inv.plan(NOW)['inventory'] if r['problem']['id']==p['id'])
        self.assertIsNone(r['comparison'])


    def test_frozen_inventory_pre_observation_current_trial_excluded(self):
        self.event('old-release', '2026-10-12')
        self.event()
        self.trial('old-release', 'old-observed', 12_000_000)
        self.trial('new-release', 'new-before-observed', 5_000_000,
                   run_on='2026-11-09')
        self.assertIsNone(self.row()['comparison'])

    def test_frozen_inventory_pre_observation_historical_trial_excluded(self):
        self.event('old-release', '2026-10-12')
        self.event()
        self.trial('old-release', 'old-before-observed', 12_000_000,
                   run_on='2026-10-11')
        self.trial('new-release', 'new-observed', 5_000_000)
        self.assertIsNone(self.row()['comparison'])

if __name__=='__main__':unittest.main()
