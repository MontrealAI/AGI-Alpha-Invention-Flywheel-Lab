"""Auditable research-only five-engine crossing inventory qualification.

No model invoices, customer commitments, real baseline model access, or live
frontier capability are asserted by a successful test or synthetic fixture.
"""
from __future__ import annotations
import copy
from datetime import date
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from frontier_omega.core import (COSTS,FRONTIER_SCHEMA,TRIAL_SCHEMA,canonical,
                                 sha,Reservoir)
from frontier_omega.crossings import (CrossingInventory,CATALOG,read_catalog,
                                      validate,expand_problem,expand_brief,render)


class FrontierCrossingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=read_catalog()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='frontier-crossing-test-')
        self.root=Path(self.temp.name)/'private'
        self.sensor=CrossingInventory(self.root)
    def tearDown(self):self.temp.cleanup()

    def bootstrap(self):
        self.sensor.seed()
        return self.sensor.view('2026-11-16')

    def test_exact_five_engine_portfolio_and_forty_new_problems(self):
        catalog=self.original
        self.assertEqual(len(catalog['engines']),5)
        self.assertEqual(len(catalog['problems']),40)
        self.assertEqual({e['rank'] for e in catalog['engines']},set(range(1,6)))
        self.assertEqual({e['id'] for e in catalog['engines']},
                         {'migrate-omega','prove-omega','trust-omega','lab-omega','workcell-omega'})

    def test_all_five_releases_follow_historical_cutoff(self):
        for e in self.original['engines']:
            self.assertLess(self.original['historical_baseline'],e['released_on'])
            self.assertLessEqual(e['released_on'],self.original['as_of'])
        self.assertEqual((date(2026,11,16)-date(2026,10,12)).days,35)

    def test_no_pretend_revenue_or_verified_customers(self):
        for c in self.original['problems']:
            self.assertIs(c['purchaser_verified'],False)
            self.assertIsNone(c['real_revenue_microUSD'])
            self.assertIsNone(c['real_complete_cost_microUSD'])
            self.assertIsNone(c['last_verified_crossing'])
        self.assertFalse(self.original['five_week_strict_impossibility_proven'])

    def test_unsupported_customer_claim_refused(self):
        c=copy.deepcopy(self.original);c['problems'][0]['purchaser_verified']=True
        with self.assertRaisesRegex(ValueError,'HYPOTHESIS'):validate(c)

    def test_assumed_cash_refused(self):
        c=copy.deepcopy(self.original);c['problems'][0]['real_revenue_microUSD']=100
        with self.assertRaisesRegex(ValueError,'HYPOTHESIS'):validate(c)

    def test_fabricated_historical_impossibility_refused(self):
        c=copy.deepcopy(self.original);c['five_week_strict_impossibility_proven']=True
        with self.assertRaisesRegex(ValueError,'IMPOSSIBILITY'):validate(c)

    def test_release_outside_five_week_window_refused(self):
        c=copy.deepcopy(self.original);c['engines'][0]['released_on']='2026-10-10'
        with self.assertRaisesRegex(ValueError,'WINDOW'):validate(c)

    def test_missing_evidence_url_refused(self):
        c=copy.deepcopy(self.original);c['problems'][0]['source_urls']=['https://example.org']
        with self.assertRaisesRegex(ValueError,'CITE'):validate(c)

    def test_duplicate_problems_refused(self):
        c=copy.deepcopy(self.original);c['problems'][1]['id']=c['problems'][0]['id']
        with self.assertRaises(ValueError):validate(c)

    def test_wrong_metric_units_refused(self):
        c=copy.deepcopy(self.original);c['problems'][0]['proposed_metrics'][0]['target']=False
        with self.assertRaisesRegex(ValueError,'THRESHOLD'):validate(c)

    def test_catalog_has_no_build_payment_authority(self):
        self.assertNotIn('payment_credentials',canonical(self.original).decode())
        self.assertNotIn('customer_signing_key',canonical(self.original).decode())

    def test_initialization_reuses_existing_reservoir(self):
        s=self.sensor.seed()
        self.assertEqual(s['new_problems'],40)
        self.assertEqual(s['new_briefs'],40)
        self.assertEqual(s['total_problems'],52)
        self.assertEqual(s['total_decision_briefs'],52)
        self.assertEqual(s['financial_effects'],0)
        self.assertEqual(self.sensor.inventory.reservoir.audit()['audit'],'PASS')

    def test_second_seed_does_not_duplicate(self):
        self.sensor.seed();s=self.sensor.seed()
        self.assertEqual(s['new_problems'],0)
        self.assertEqual(s['new_briefs'],0)
        self.assertEqual(s['total_problems'],52)

    def test_existing_twelve_problem_records_preserved(self):
        from frontier_omega.inventory import bootstrap
        base=bootstrap(self.root)
        originals={p['id']:sha(p) for p in base.reservoir.rows('problems')}
        self.sensor.seed()
        after={p['id']:sha(p) for p in self.sensor.inventory.reservoir.rows('problems')}
        self.assertEqual(len(originals),12)
        for k,v in originals.items():self.assertEqual(after[k],v)

    def test_every_problem_is_source_bound_and_has_no_purchase(self):
        self.sensor.seed()
        allp={p['id']:p for p in self.sensor.inventory.reservoir.rows('problems')}
        for engine in self.original['engines']:
            for c in (c for c in self.original['problems'] if c['engine_id']==engine['id']):
                record=allp[c['id']]
                self.assertEqual(record['demand']['status'],'PUBLIC_SIGNAL')
                self.assertIsNone(record['demand']['terms_sha256'])
                self.assertIsNone(record['demand']['ceiling_microUSD'])
                self.assertIn('No purchase',{o['name'] for o in record['alternatives']})
                self.assertIn(engine['reference'],record['source_urls'])
                self.assertEqual(len(record['alternatives']),3)

    def test_five_engine_current_frontier_signals_all_trigger_replays(self):
        v=self.bootstrap()
        self.assertEqual(v['new_problem_count'],40)
        self.assertEqual(v['canonical_problem_count'],52)
        self.assertEqual(v['historical_baseline'],'2026-10-12')
        self.assertEqual(v['status_counts']['source_signal_only'],40)
        for g in v['engines']:
            self.assertEqual(len(g['problems']),8)
            self.assertTrue(all(p['research_queue_action']=='REPLAY_CANDIDATE' for p in g['problems']))
            self.assertTrue(all(g['source_release_id'] in p['last_relevant_release_ids'] for p in g['problems']))

    def test_source_report_cannot_unlock_commercial_execution(self):
        v=self.bootstrap()
        for g in v['engines']:
            for p in g['problems']:
                self.assertFalse(p['buyer_verified'])
                self.assertFalse(p['permission_to_spend'])
                self.assertFalse(p['permission_to_contact_buyers'])
                self.assertFalse(p['independently_verified_35_day_crossing'])
                self.assertIsNone(p['real_price_microUSD'])
                self.assertIsNone(p['complete_real_cost_microUSD'])
        self.assertEqual(v['commercial_qualification'],'NONE')

    def test_as_of_moving_window_no_lookahead(self):
        v=self.bootstrap()
        later=self.sensor.view('2026-12-31')
        self.assertEqual(later['historical_baseline'],'2026-11-26')
        self.assertTrue(all(p['research_queue_action']=='MONITOR' for g in later['engines'] for p in g['problems']))

    def test_refresh_twice_leaves_no_duplicate_tasks(self):
        self.sensor.seed()
        self.sensor.inventory.refresh('2026-11-16')
        self.sensor.inventory.refresh('2026-11-16')
        with self.sensor.inventory.reservoir.tx() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM research_queue').fetchone()[0],52)

    def test_exact_blob_changes_trigger_fresh_task(self):
        self.sensor.seed();first=self.sensor.inventory.refresh('2026-11-16')
        id0=next(r['task_id'] for r in first['inventory'] if r['problem']['id']==self.original['problems'][0]['id'])
        tag=self.original['engines'][0]['tags']
        release={'schema':FRONTIER_SCHEMA,'id':'newer-observation-20261116',
                 'title':'Synthetic new technical release', 'observed_on':'2026-11-16',
                 'description':'Synthetic release injected by test; no actual model capabilities.',
                 'tags':tag,'source_urls':['https://example.org/release'],'availability':'REPORTED'}
        self.sensor.inventory.reservoir.add(release)
        nxt=self.sensor.inventory.refresh('2026-11-16')
        id1=next(r['task_id'] for r in nxt['inventory'] if r['problem']['id']==self.original['problems'][0]['id'])
        self.assertNotEqual(id0,id1)
        with self.sensor.inventory.reservoir.tx() as c:
            self.assertEqual(c.execute('SELECT state FROM research_queue WHERE id=?',(id0,)).fetchone()[0],'SUPERSEDED')

    def test_restart_retains_private_state(self):
        self.sensor.seed();self.sensor.inventory.refresh('2026-11-16')
        other=CrossingInventory(self.root)
        self.assertEqual(other.seed()['new_problems'],0)
        self.assertEqual(other.inventory.refresh('2026-11-16')['tasks_added'],0)

    def test_report_contains_source_content_identity(self):
        self.sensor.seed();v=self.sensor.view()
        self.assertEqual(v['source_catalog_sha256'],sha(self.original))
        self.assertRegex(v['canonical_snapshot_sha256'],r'^[a-f0-9]{64}$')

    def test_report_new_counts_independent_of_original_twelve(self):
        v=self.bootstrap()
        self.assertEqual(len(v['engines']),5)
        self.assertEqual(sum(len(g['problems']) for g in v['engines']),40)
        self.assertEqual(v['status_counts']['real_paid_deliveries'],0)

    def test_generated_html_escapes_customer_content(self):
        v=self.bootstrap();v['engines'][0]['problems'][0]['title']='<img src=x onerror=alert(1)>'
        html=render(v)
        self.assertNotIn('<img',html)
        self.assertIn('&lt;img',html)

    def test_generated_html_has_no_remote_dependencies(self):
        v=self.bootstrap();html=render(v)
        self.assertNotIn('<script src=',html)
        self.assertNotIn('<link rel="stylesheet"',html)
        self.assertEqual(html.count('<article'),40)
        self.assertIn('default-src &#39;none&#39;',html.replace("'",'&#39;'))

    def test_symlink_catalog_refused(self):
        file=Path(self.temp.name)/'link.json';file.symlink_to(CATALOG)
        with self.assertRaisesRegex(ValueError,'CATALOG'):read_catalog(file)

    def test_script_runs_fresh_offline_demonstration(self):
        destination=Path(self.temp.name)/'fresh'
        cmd=[sys.executable,'-m','frontier_omega.crossings','demo','--output',str(destination)]
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=25)
        self.assertEqual(p.returncode,0,p.stderr)
        d=json.loads(p.stdout)
        self.assertEqual(d['total_problems'],52)
        self.assertEqual(d['new_problems'],40)
        self.assertEqual(d['actual_customers'],0)
        self.assertTrue((destination/'FRONTIER-ECONOMIC-OPPORTUNITIES.html').exists())
        self.assertTrue((destination/'FRONTIER-ECONOMIC-OPPORTUNITIES.json').exists())

    def test_worker_does_not_poll_without_explicit_config(self):
        self.sensor.seed()
        with patch('frontier_omega.releases._fetch',side_effect=AssertionError('NETWORK_NOT_AUTHORIZED')):
            result=self.sensor.watch(.05,cycles=2)
        self.assertEqual(result['cycles'],2)
        self.assertEqual(result['payments'],0)

    def test_real_worker_receives_later_submitted_problem(self):
        self.sensor.seed()
        p=subprocess.Popen([sys.executable,'-m','frontier_omega.crossings','--root',str(self.root),
                            'watch','--interval','0.1','--cycles','7'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            import time
            time.sleep(.25)
            extra=copy.deepcopy(self.sensor.inventory.reservoir.rows('frontiers')[0]);extra['id']='test-event-in-process';extra['observed_on']='2026-11-17'
            tmp=self.root/'inbox'/'release.tmp';tmp.write_bytes(canonical(extra));tmp.rename(self.root/'inbox'/'release.json')
            out,err=p.communicate(timeout=12)
            self.assertEqual(p.returncode,0,err)
            after=CrossingInventory(self.root)
            self.assertTrue(any(e['id']=='test-event-in-process' for e in after.inventory.reservoir.rows('frontiers')))
            self.assertEqual(after.inventory.refresh('2026-11-17')['tasks_added'],0)
        finally:
            if p.poll() is None:p.kill();p.communicate(timeout=3)

    def test_watcher_requires_explicit_allowlist_to_network(self):
        self.sensor.seed()
        from frontier_omega.releases import validate_config
        config={'schema':'frontier-omega/github-release-sources/v1','repositories':[{'repository':'https://internal.svc','tags':['long-horizon-agents']}]}
        with self.assertRaises(ValueError):self.sensor.watch(.05,cycles=1,release_config=config)

    def test_watcher_rejects_negative_interval(self):
        self.sensor.seed()
        with self.assertRaises(ValueError):self.sensor.watch(float('nan'),cycles=1)

    def test_watcher_rejects_negative_cycles(self):
        self.sensor.seed()
        with self.assertRaises(ValueError):self.sensor.watch(.05,cycles=-1)

    def test_canonical_audit_of_fifty_two_problems(self):
        self.sensor.seed()
        self.assertEqual(self.sensor.audit()['audit'],'PASS')

    def test_declared_incumbent_can_defeat_synthetic_claim(self):
        self.sensor.seed()
        c=self.original['problems'][0]
        old={'schema':FRONTIER_SCHEMA,'id':'baseline-agent-20261010','title':'Historical model',
             'observed_on':'2026-10-10','description':'Synthetic test baseline, not evidence of actual availability.',
             'tags':['long-horizon-agents'],'source_urls':['https://example.org/old'],'availability':'REPORTED'}
        self.sensor.inventory.reservoir.add(old)
        e=self.original['engines'][0];newid=e['release_id']
        def arm(ident,fr,cost,alternate_cost):
            return dict(schema=TRIAL_SCHEMA,id=ident,problem_id=c['id'],frontier_id=fr,run_on='2026-11-16',
                terms_sha256=sha('terms'),acceptance_sha256=sha(c['acceptance']),protocol_sha256=sha('protocol'),
                evidence_sha256=sha(ident),scope='AUTHORED_SCENARIO',passed=True,independent_check=True,
                price_microUSD=1_000_000,acceptance_probability_bps=10000,
                costs_microUSD={k:(cost if k=='construction' else 0) for k in COSTS},
                expected_loss_microUSD=0,alternative={'name':'Strong historical specialist','qualified':True,
                'complete_cost_microUSD':alternate_cost})
        self.sensor.inventory.reservoir.add(arm('baseline-arm-20261010',old['id'],2_000_000,200_000))
        self.sensor.inventory.reservoir.add(arm('now-arm-20261116',newid,100_000,90_000))
        row=self.sensor.view()['engines'][0]['problems'][0]
        self.assertFalse(row['comparison']['reported_crossing'])
        self.assertEqual(row['status'],'COMPETENT_ALTERNATIVE_NEEDS_COMPARISON')
        self.assertFalse(row['independently_verified_35_day_crossing'])

    def test_report_is_not_a_billable_order(self):
        self.sensor.seed();r=self.sensor.view()
        self.assertNotIn('stripe',json.dumps(r))
        self.assertNotIn('customer_wallet',json.dumps(r))
        self.assertEqual(r['financial_authority'],'NONE')


if __name__=='__main__':unittest.main()
