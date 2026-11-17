"""FRONTIER Ω — economic-crossing inventory, connected to its canonical reservoir.

This is a SENSOR, not an order intake, payment processor, model gateway, or
invention engine. All candidate price, real cost, demand and 35-day feasibility
crossing assertions remain unverified until appropriate external evidence exists.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import signal
import threading
import time

from .core import (PROBLEM_SCHEMA, canonical, sha, parse, title, day,
                   validate_problem, identifier)
from .inventory import Inventory, bootstrap, atomic

SCHEMA='frontier-omega/economic-crossing-catalog/v1'
REPORT='frontier-omega/economic-crossing-report/v1'
ALLOWED_STATES=('SOURCE_SIGNAL_ONLY', 'REPLAY_REPORTED_UNVERIFIED',
                'REPORTED_CROSSING_REQUIRES_BUYER_AND_INDEPENDENT_REPLAY',
                'COMPETENT_ALTERNATIVE_NEEDS_COMPARISON')
ENGINES=('migrate-omega','prove-omega','trust-omega','lab-omega','workcell-omega')
FIELDS={'id','engine_id','title','beneficiary','outcome','blocker','acceptance',
        'strong_incumbent','buyer_validation','delivery_unit','successor_asset','downside',
        'current_hypothesis','next_experiment','proposed_metrics','purchaser_verified',
        'real_revenue_microUSD','real_complete_cost_microUSD','last_verified_crossing','source_urls'}
METRIC_FIELDS={'metric','operator','target','unit','test'}
CATALOG=Path(__file__).resolve().parents[1]/'examples/frontier-omega/economic-crossings-20261116.json'


def _exact(x,fields):
    if type(x) is not dict or set(x)!=fields:raise ValueError('EXACT_FRONTIER_WINDOW_SCHEMA_REQUIRED')


def validate(data):
    _exact(data,{'schema','as_of','historical_baseline','scope',
                 'five_week_strict_impossibility_proven','engines','problems','note'})
    if data['schema']!=SCHEMA or data['scope']!='DATED_CAPABILITY_SIGNALS_PLUS_RESEARCH_HYPOTHESES_NOT_VALIDATED_COMMERCIAL_CROSSINGS':
        raise ValueError('UNSUPPORTED_CATALOG_SCOPE')
    day(data['as_of']);day(data['historical_baseline'])
    if (date.fromisoformat(data['as_of'])-date.fromisoformat(data['historical_baseline'])).days!=35:
        raise ValueError('EXACT_35_DAY_MATCHED_WINDOW_REQUIRED')
    if data['five_week_strict_impossibility_proven'] is not False:
        raise ValueError('IMPOSSIBILITY_CANNOT_BE_DECLARED_FROM_RELEASE_NEWS')
    if type(data['engines']) is not list or len(data['engines'])!=5 or type(data['problems']) is not list or not (20<=len(data['problems'])<=120):
        raise ValueError('FIVE_ENGINE_BOUNDED_CANDIDATE_CATALOG_REQUIRED')
    title(data['note'])
    from .core import sources,tags
    engines={}
    for e in data['engines']:
        _exact(e,{'id','rank','name','label','release_id','released_on','reference',
                  'source_mechanism','tags','product','why_now','competitive_risk',
                  'moat','scalability','threshold','first_sale'})
        identifier(e['id']);identifier(e['release_id']);day(e['released_on'])
        if e['id'] in engines or type(e['rank']) is not int or not 1<=e['rank']<=5:
            raise ValueError('UNIQUE_RANKED_ENGINE_REQUIRED')
        if not data['historical_baseline']<e['released_on']<=data['as_of']:
            raise ValueError('RELEASE_OUTSIDE_35_DAY_WINDOW')
        sources([e['reference']]);tags(e['tags'])
        for k in ('name','label','source_mechanism','product','why_now','competitive_risk',
                  'moat','scalability','threshold','first_sale'): title(e[k])
        engines[e['id']]=e
    if set(engines)!=set(ENGINES) or {e['rank'] for e in engines.values()}!=set(range(1,6)):
        raise ValueError('EXACT_FIVE_FLAGSHIP_ENGINES_REQUIRED')
    seen=set();per_engine={e:0 for e in engines}
    for p in data['problems']:
        _exact(p,FIELDS)
        identifier(p['id'])
        if p['id'] in seen or p['engine_id'] not in engines:raise ValueError('UNKNOWN_ENGINE_OR_DUPLICATE_PROBLEM')
        seen.add(p['id']);per_engine[p['engine_id']]+=1
        for k in ('title','beneficiary','outcome','blocker','acceptance','strong_incumbent',
                  'buyer_validation','delivery_unit','successor_asset','downside','current_hypothesis','next_experiment'):
            title(p[k])
        sources(p['source_urls'])
        if engines[p['engine_id']]['reference'] not in p['source_urls']:
            raise ValueError('PROBLEM_MUST_CITE_EXACT_FRONTIER_CATALYST')
        if (p['purchaser_verified'] is not False or p['real_revenue_microUSD'] is not None or
            p['real_complete_cost_microUSD'] is not None or p['last_verified_crossing'] is not None):
            raise ValueError('HYPOTHESIS_CANNOT_CLAIM_REAL_CUSTOMER_CASH_OR_CROSSING')
        if type(p['proposed_metrics']) is not list or not 2<=len(p['proposed_metrics'])<=8:
            raise ValueError('MEASURABLE_ACCEPTANCE_REQUIRED')
        metrics=set()
        for m in p['proposed_metrics']:
            _exact(m,METRIC_FIELDS);identifier(m['metric'])
            if m['metric'] in metrics:raise ValueError('DUPLICATE_ACCEPTANCE_METRIC')
            metrics.add(m['metric'])
            if m['operator'] not in ('=','>=','<=') or type(m['target']) is not int or m['target']<0:
                raise ValueError('EXACT_PROPOSED_THRESHOLD_REQUIRED')
            title(m['unit']);title(m['test'])
    if set(per_engine.values())!={8}:raise ValueError('EIGHT_CUSTOMER_OUTCOMES_PER_ENGINE_REQUIRED')
    canonical(data)
    return data


def read_catalog(path=CATALOG):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>350_000:
        raise ValueError('BOUNDED_REGULAR_CATALOG_REQUIRED')
    return validate(parse(path.read_bytes()))


def expand_problem(c,e):
    p={'schema':PROBLEM_SCHEMA,'id':c['id'],'title':c['title'],'beneficiary':c['beneficiary'],
       'outcome':c['outcome'],'acceptance':c['acceptance'],'blocker':c['blocker'],
       'tags':e['tags'],'demand':{'status':'PUBLIC_SIGNAL',
         'basis':'Engineering hypothesis arising from a dated technical report; no buyer, budget, independent capability crossing or revenue established.',
         'ceiling_microUSD':None,'deadline':None,'terms_sha256':None,'consent_verification':'NOT_VERIFIED'},
       'alternatives':[
         {'name':'Competent specialist','route':c['strong_incumbent'],
          'unknowns':'Obtain independent complete-cost quote including failures, risk, verification, delivery and obligations.'},
         {'name':'Human-plus-AI provider','route':'A competent authorized specialist using frontier AI plus established tools and independent quality checks.',
          'unknowns':'May already satisfy the same acceptance; must be tested on equal access, time and full costs.'},
         {'name':'No purchase','route':'Buyer defers, keeps present process or substitutes existing product.',
          'unknowns':'Cost of inaction and actual purchasing intent are unmeasured.'}],
       'source_urls':c['source_urls'],'next_test':c['next_experiment']}
    return validate_problem(p)


def expand_brief(c,problem,as_of):
    from .inventory import SCHEMA as BRIEF_SCHEMA,validate_brief
    data={'schema':BRIEF_SCHEMA,'id':'brief-'+c['id']+'-v1',
          'problem_id':problem['id'],'problem_sha256':sha(problem),'assessed_on':as_of,
          'value_driver':'Hypothesized buyer value: '+c['outcome']+' '+c['current_hypothesis'],
          'delivery_unit':c['delivery_unit'],'buyer_question':c['buyer_validation'],
          'successor_asset':c['successor_asset'],'access':'EXTERNAL_VALIDATION_REQUIRED',
          'source_urls':c['source_urls'],'criteria':c['proposed_metrics']}
    return validate_brief(data)


class CrossingInventory:
    """One canonical SQLite reservoir; this layer adds public research evidence only."""
    def __init__(self,root,catalog=CATALOG):
        self.root=Path(os.path.abspath(root))
        self.catalog=read_catalog(catalog)
        self.inventory=Inventory(self.root)

    def seed(self):
        # Reuse the original 12-dossier published reservoir, in the same DB.
        bootstrap(self.root)
        engines={e['id']:e for e in self.catalog['engines']}
        observed={e['id']:e for e in self.inventory.reservoir.rows('frontiers')}
        for e in engines.values():
            f=observed.get(e['release_id'])
            if f is None or f['observed_on']!=e['released_on'] or not set(f['tags'])&set(e['tags']):
                raise ValueError('FLAGSHIP_FRONTIER_RELEASE_NOT_BOUND_TO_CANONICAL_OBSERVATION')
        new=0;briefs=0
        for c in self.catalog['problems']:
            p=expand_problem(c,engines[c['engine_id']])
            new+=int(self.inventory.reservoir.add(p)['added'])
            briefs+=int(self.inventory.add_brief(expand_brief(c,p,self.catalog['as_of'])))
        return {'new_problems':new,'new_briefs':briefs,
                'total_problems':len(self.inventory.reservoir.rows('problems')),
                'total_decision_briefs':len(self.inventory.snapshot()['decision_briefs']),
                'scope':'UNVERIFIED_DEMAND_RESEARCH_ONLY','financial_effects':0}

    def view(self,as_of='2026-11-16'):
        day(as_of)
        planned=self.inventory.plan(as_of)
        keyed={r['problem']['id']:r for r in planned['inventory']}
        groups=[];counts={'source_signal_only':0,'replay_reported':0,'real_paid_deliveries':0}
        for e in sorted(self.catalog['engines'],key=lambda x:x['rank']):
            problems=[]
            for c in (c for c in self.catalog['problems'] if c['engine_id']==e['id']):
                if c['id'] not in keyed:raise ValueError('CANONICAL_PROBLEM_NOT_SEEDED')
                r=keyed[c['id']]
                comparison=r['comparison']
                if comparison is None:
                    status='SOURCE_SIGNAL_ONLY';counts['source_signal_only']+=1
                else:
                    counts['replay_reported']+=1
                    if comparison['ordinary_cost_competitive']:
                        status='COMPETENT_ALTERNATIVE_NEEDS_COMPARISON'
                    elif comparison['reported_crossing']:
                        status='REPORTED_CROSSING_REQUIRES_BUYER_AND_INDEPENDENT_REPLAY'
                    else:status='REPLAY_REPORTED_UNVERIFIED'
                problems.append({'id':c['id'],'title':c['title'],'beneficiary':c['beneficiary'],
                  'outcome':c['outcome'],'blocker':c['blocker'],'acceptance':c['acceptance'],
                  'strong_incumbent':c['strong_incumbent'],'buyer_question':c['buyer_validation'],
                  'source_urls':c['source_urls'],'next_experiment':c['next_experiment'],
                  'risk':c['downside'],'delivery_unit':c['delivery_unit'],
                  'future_asset':c['successor_asset'],'proposed_metrics':c['proposed_metrics'],
                  'last_relevant_release_ids':r['recent_frontier_ids'],
                  'research_queue_action':r['action'],'research_task_id':r['task_id'],
                  'comparison':comparison,'status':status,
                  'buyer_verified':False,'real_price_microUSD':None,'complete_real_cost_microUSD':None,
                  'independently_verified_35_day_crossing':False,
                  'permission_to_spend':False,'permission_to_contact_buyers':False})
            groups.append({'id':e['id'],'rank':e['rank'],'name':e['name'],'label':e['label'],
                           'source_release_id':e['release_id'],'release_date':e['released_on'],
                           'source_url':e['reference'],'source_claim_scope':e['source_mechanism'],
                           'commercial_product':e['product'],'why_now':e['why_now'],
                           'competitor_risk':e['competitive_risk'],'potential_moat':e['moat'],
                           'autonomous_scalability':e['scalability'],'gate_to_first_sale':e['first_sale'],
                           'gate_to_economic_viability':e['threshold'],'problems':problems})
        return {'schema':REPORT,'as_of':as_of,'historical_baseline':(date.fromisoformat(as_of)-timedelta(days=35)).isoformat(),
                'research_window_days':35,'engines':groups,
                'new_problem_count':sum(map(lambda g:len(g['problems']),groups)),
                'canonical_problem_count':planned['problem_count'],
                'source_catalog_sha256':sha(self.catalog),
                'canonical_snapshot_sha256':planned['source_snapshot_sha256'],
                'status_counts':counts,'economic_priority':'RESEARCH_JUDGMENT_NOT_PROVEN_GLOBAL_OPTIMUM',
                'commercial_qualification':'NONE','strictly_new_since_baseline':'NOT_INDEPENDENTLY_PROVEN',
                'financial_authority':'NONE','source_release_availability':'REPORTED_NOT_INDEPENDENTLY_REPRODUCED',
                'full_cost_and_customer_demand':'UNKNOWN_NOT_ZERO'}

    def export(self,as_of='2026-11-16'):
        view=self.view(as_of)
        atomic(self.root/'FRONTIER-ECONOMIC-OPPORTUNITIES.json',canonical(view))
        atomic(self.root/'FRONTIER-ECONOMIC-OPPORTUNITIES.html',render(view).encode())
        return view

    def refresh(self,as_of='2026-11-16'):
        self.inventory.refresh(as_of)
        return self.export(as_of)

    def watch(self,interval=30,cycles=None,stop=None,release_config=None,release_every=3600,fetch=None):
        from .releases import poll,validate_config
        if not isinstance(interval,(int,float)) or not math.isfinite(interval) or interval<.05:
            raise ValueError('FINITE_POSITIVE_WATCH_INTERVAL_REQUIRED')
        if cycles is not None and (type(cycles) is not int or cycles<1):raise ValueError('POSITIVE_WATCH_CYCLES_REQUIRED')
        if not isinstance(release_every,(int,float)) or not math.isfinite(release_every) or release_every<300:
            raise ValueError('RELEASE_POLL_AT_LEAST_300_SECONDS')
        if release_config is not None:validate_config(release_config)
        stop=stop or threading.Event();n=0;last=None
        with self.inventory.reservoir.lock():
            while not stop.is_set():
                self.inventory.reservoir.ingest_inbox()
                if release_config is not None and (last is None or time.monotonic()-last>=release_every):
                    outcome=poll(self.inventory.reservoir,release_config,fetch=fetch)
                    atomic(self.root/'FRONTIER-RELEASE-RADAR.json',canonical(outcome));last=time.monotonic()
                as_of=datetime.now(timezone.utc).date().isoformat()
                self.inventory._refresh(as_of)
                self.export(as_of)
                n+=1
                if cycles is not None and n>=cycles:break
                stop.wait(interval)
        return {'cycles':n,'stopped':True,'payments':0,'financial_authority':'NONE'}

    def audit(self):
        base=self.inventory.reservoir.audit()
        v=self.view()
        if base['audit']!='PASS' or v['new_problem_count']!=40:raise ValueError('CROSSING_INVENTORY_REPLAY_FAILED')
        return {'audit':'PASS','original_reservoir':base,'40_new_problem_records':40,
                'real_revenue_known':False,'economic_crossings_independently_verified':0}


def render(v):
    escape=lambda x:html.escape(str(x),quote=True)
    cards=[]
    for group in v['engines']:
        block=[]
        for c in group['problems']:
            criteria=''.join('<li>'+escape(m['metric'])+' '+escape(m['operator'])+' '+escape(m['target'])+' '+escape(m['unit'])+'</li>' for m in c['proposed_metrics'])
            block.append('''<article data-search="'''+escape((c['title']+' '+c['beneficiary']+' '+c['blocker']+' '+c['status']).lower())+'''"><div class="line"><small>'''+escape(c['status'].replace('_',' '))+'''</small><span class="tag">'''+escape(c['research_queue_action'])+'''</span></div><h3>'''+escape(c['title'])+'''</h3><p>'''+escape(c['outcome'])+'''</p><div class="detail"><b>Economic buyer</b><span>'''+escape(c['beneficiary'])+'''</span><b>Blocking constraint</b><span>'''+escape(c['blocker'])+'''</span><b>Best known alternative</b><span>'''+escape(c['strong_incumbent'])+'''</span></div><details><summary>Decisive test, acceptance and buyer question</summary><p>'''+escape(c['next_experiment'])+'''</p><ul>'''+criteria+'''</ul><p><b>Ask the buyer:</b> '''+escape(c['buyer_question'])+'''</p><p><b>Reusable asset:</b> '''+escape(c['future_asset'])+'''</p><p><b>Downside:</b> '''+escape(c['risk'])+'''</p><p><b>Source:</b> <a href="'''+escape(c['source_urls'][0])+'''" target="_blank" rel="noopener noreferrer">'''+escape(c['source_urls'][0])+'''</a></p></details></article>''')
        cards.append('''<section class="engine" data-engine="'''+escape(group['id'])+'''"><div class="engine-title"><div><small>ENGINE '''+str(group['rank'])+''' / PUBLIC-SOURCE CATALYST '''+escape(group['release_date'])+'''</small><h2>'''+escape(group['name'])+'''</h2><p>'''+escape(group['label'])+''' — '''+escape(group['commercial_product'])+'''</p></div><div class="num">8<span>Problems</span></div></div><p class="scope"><b>Why now:</b> '''+escape(group['why_now'])+'''</p><p class="scope"><b>First paid pilot:</b> '''+escape(group['gate_to_first_sale'])+'''</p><div class="cards">'''+''.join(block)+'''</div></section>''')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; object-src 'none'"><title>FRONTIER Ω / Capture the Exponential</title><style>:root{color-scheme:dark}*{box-sizing:border-box}body{background:radial-gradient(ellipse at 50% -24%,#213955 0,#0a131f 58%);color:#e9f0f6;margin:0;font:15px/1.6 system-ui,-apple-system,sans-serif}main{max-width:1250px;margin:auto;padding:62px 32px 90px}header{padding-bottom:45px;border-bottom:1px solid #314456}.eyebrow{color:#dbbd7e;text-transform:uppercase;letter-spacing:.18em;font-size:11px;font-weight:700}h1{font-size:clamp(45px,8vw,90px);line-height:1.04;letter-spacing:-.055em;margin:17px 0}h1 span{color:#c5ac7d}h2{font-size:36px;line-height:1.15;letter-spacing:-.03em;margin:8px 0}h3{font-size:19px;line-height:1.25;margin:12px 0;color:#fff}.lead{font-size:19px;max-width:840px;color:#cfdae6}.disclaimer{max-width:910px;border-left:3px solid #b89b6b;padding:7px 17px;background:#132434;color:#c2cedb}.stats{display:flex;gap:34px;flex-wrap:wrap;margin-top:30px}.stats div{font-weight:700;font-size:30px}.stats span{font-size:12px;color:#a6bac9;display:block;font-weight:400}.controls{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:40px 0 24px}input,select{font:inherit;background:#162638;color:#f7fbff;border:1px solid #475e71;padding:14px 16px;border-radius:9px;min-height:50px}input{flex:1;min-width:230px}.engine{border-top:1px solid #344757;padding:35px 0 50px}.engine-title{display:flex;justify-content:space-between;align-items:center;gap:18px}.engine-title p{color:#b8c9d8;max-width:860px}.num{font-size:42px;color:#c9ad78;text-align:right}.num span{display:block;font-size:12px;color:#94afbe}.scope{color:#b6c6d4}.scope b{color:#ecdebf}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:24px}article{background:#122131;border:1px solid #34495b;border-radius:12px;padding:23px;min-width:0}article p{color:#c2d1dd}article .line{display:flex;gap:10px;justify-content:space-between;flex-wrap:wrap;align-items:center}small{color:#d5be8f;letter-spacing:.08em;text-transform:uppercase;font-size:10px}.tag{color:#b0c9db;background:#22394d;padding:3px 8px;border-radius:5px;font-size:10px}.detail{display:grid;grid-template-columns:1fr;gap:4px}.detail b{font-size:11px;text-transform:uppercase;color:#ddc995;margin-top:10px}.detail span{color:#b7cad8}details{padding-top:17px;margin-top:18px;border-top:1px solid #30495b}summary{color:#efd6a7;cursor:pointer}li{color:#bdd0dc;margin-top:6px}a{color:#bce7ef;overflow-wrap:anywhere}article[hidden],section[hidden]{display:none}footer{border-top:1px solid #344757;padding-top:28px;margin-top:30px;color:#93abbc}@media(max-width:800px){main{padding:32px 17px 70px}.cards{grid-template-columns:1fr}h2{font-size:30px}.num{font-size:30px}}</style></head><body><main><header><div class="eyebrow">MONTREAL.AI / ALPHA ECONOMIC ENGINE / SENSOR & IGNITION TIMING</div><h1>FRONTIER <span>Ω</span></h1><p class="lead">Capture the exponential. A living inventory of economically valuable problems that emerging intelligence may make attainable.</p><div class="disclaimer">As of '''+escape(v['as_of'])+'''. Dated source reports and candidate business hypotheses. No independently verified five-week economic crossing, customer payment or proven market demand. Every investment remains subject to separate authorization and full-cost accounting.</div><div class="stats"><div>5<span>Candidate autonomous engines</span></div><div>40<span>New scoped customer outcomes</span></div><div>12<span>Previously retained problems</span></div><div>35d<span>Matched historical window</span></div></div></header><div class="controls"><label for="q">Search</label><input id="q" type="search" placeholder="Buyer, problem, constraint or method…"><label for="group">Engine</label><select id="group"><option value="all">All five engines</option>'''+''.join('<option value="'+escape(g['id'])+'">'+escape(g['name'])+'</option>' for g in v['engines'])+'''</select></div><div id="portfolio">'''+''.join(cards)+'''</div><footer>Existing FRONTIER Ω research account and records remain unchanged. Problems are technical-commercial hypotheses; actual revenue, real complete costs, signed demand and model task-performance vintage comparisons are unmeasured. No analytics or external resources.</footer></main><script>const q=document.getElementById('q'),g=document.getElementById('group');function apply(){const term=q.value.toLowerCase();for(const section of document.querySelectorAll('.engine')){const selected=g.value==='all'||section.dataset.engine===g.value;let visible=0;for(const card of section.querySelectorAll('article')){card.hidden=!card.dataset.search.includes(term);if(!card.hidden)visible++}section.hidden=!selected||!visible}}q.addEventListener('input',apply);g.addEventListener('change',apply)</script></body></html>'''


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('./frontier-private'))
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('seed');sub.add_parser('audit')
    for name in ('refresh','list'):
        x=sub.add_parser(name);x.add_argument('--as-of',default=datetime.now(timezone.utc).date().isoformat())
        if name=='list':x.add_argument('--limit',type=int,default=8)
    demo=sub.add_parser('demo');demo.add_argument('--output',required=True,type=Path)
    watch=sub.add_parser('watch');watch.add_argument('--interval',type=float,default=30)
    watch.add_argument('--cycles',type=int);watch.add_argument('--release-config',type=Path)
    args=parser.parse_args(argv)
    if args.command=='demo':
        if args.output.exists():parser.error('Choose a new demo output directory')
        obj=CrossingInventory(args.output)
        result=obj.seed();obj.inventory.refresh('2026-11-16');v=obj.export('2026-11-16')
        result['research_tasks']=v['new_problem_count'];result['audit']=obj.audit()['audit']
        result['offline']=True;result['actual_customers']=0;result['verified_economic_crossings']=0
        atomic(obj.root/'RESULTS.json',canonical(result))
    else:
        obj=CrossingInventory(args.root)
        if args.command=='seed':result=obj.seed()
        elif args.command=='audit':result=obj.audit()
        elif args.command in ('refresh','list'):
            v=obj.refresh(args.as_of) if args.command=='refresh' else obj.view(args.as_of)
            result={'total_problems':v['canonical_problem_count'],'new_problems':v['new_problem_count'],
                    'five_engines':len(v['engines']), 'status':v['status_counts'],
                    'financial_authority':'NONE','output':str(obj.root/'FRONTIER-ECONOMIC-OPPORTUNITIES.html')}
            if args.command=='list':
                if args.limit<1:parser.error('limit must be positive')
                result['priorities']=[{'engine':g['name'],'problem':c['title'],'action':c['research_queue_action']}
                       for g in v['engines'] for c in g['problems']][:args.limit]
        else:
            from .core import load_file
            stop=threading.Event()
            signal.signal(signal.SIGINT,lambda *_:stop.set())
            signal.signal(signal.SIGTERM,lambda *_:stop.set())
            config=load_file(args.release_config) if args.release_config else None
            result=obj.watch(args.interval,args.cycles,stop,config)
    print(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
