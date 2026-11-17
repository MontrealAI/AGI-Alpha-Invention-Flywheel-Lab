"""Decision-ready living inventory over the canonical FRONTIER Omega reservoir.

Research prioritization only. No new account, spending, model call or buyer consent.
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta, datetime, timezone
import hashlib
import html
import os
from pathlib import Path
import signal
import threading
import time
import uuid
from .core import Reservoir, canonical, parse, sha, load_file, day, exact, title, identifier

SCHEMA = 'frontier-omega/decision-brief/v1'
FIELDS = {'schema','id','problem_id','problem_sha256','assessed_on','value_driver',
          'delivery_unit','buyer_question','successor_asset','access','criteria','source_urls'}
ACTIONS = ('REVIEW_DEMAND','REPLAY_CANDIDATE','COMPARE_INCUMBENT','MEASURE_ECONOMICS',
           'MONITOR','EXPIRED_DEMAND','DEFINE_TEST')


def validate_brief(b):
    from .core import SHA, sources
    exact(b,FIELDS)
    if b['schema'] != SCHEMA: raise ValueError('BRIEF_SCHEMA')
    for k in ('id','problem_id'): identifier(b[k])
    if not isinstance(b['problem_sha256'],str) or not SHA.fullmatch(b['problem_sha256']):
        raise ValueError('BOUND_PROBLEM_HASH_REQUIRED')
    day(b['assessed_on'])
    for k in ('value_driver','delivery_unit','buyer_question','successor_asset'): title(b[k])
    if b['access'] not in ('LOCAL_RESEARCH','AUTHORIZED_COMPUTE_REQUIRED','EXTERNAL_VALIDATION_REQUIRED'):
        raise ValueError('EXPLICIT_RESOURCE_ACCESS_REQUIRED')
    sources(b['source_urls'])
    if type(b['criteria']) is not list or not 1 <= len(b['criteria']) <= 12:
        raise ValueError('FINITE_MEASURABLE_CRITERIA_REQUIRED')
    seen=set()
    for c in b['criteria']:
        exact(c,{'metric','operator','target','unit','test'})
        identifier(c['metric'])
        if c['metric'] in seen: raise ValueError('DUPLICATE_METRIC')
        seen.add(c['metric'])
        if c['operator'] not in ('>=','<=','=') or type(c['target']) is not int or c['target'] < 0:
            raise ValueError('EXACT_THRESHOLD_REQUIRED')
        title(c['unit']);title(c['test'])
    canonical(b)
    return b


def atomic(path,data):
    """Owner-private output, no symlink destinations, atomic replacement."""
    path=Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path,*path.parents)): raise ValueError('SYMLINK_OUTPUT_REFUSED')
    temp=path.with_name('.'+uuid.uuid4().hex+'.tmp')
    try:
        with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:temp.unlink(missing_ok=True)


class Inventory:
    def __init__(self,root):
        root=Path(os.path.abspath(root))
        for p in (root/'frontier.sqlite',root/'frontier.lock'):
            if p.is_symlink():raise ValueError('SYMLINK_STATE_REFUSED')
        self.reservoir=Reservoir(root)
        self.root=self.reservoir.root
        with self.reservoir.tx() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS decision_briefs(id TEXT PRIMARY KEY,
              problem_id TEXT NOT NULL,body TEXT NOT NULL,hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS inventory_clock(id INTEGER PRIMARY KEY CHECK(id=1),as_of TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_queue(id TEXT PRIMARY KEY,
              problem_id TEXT NOT NULL,body TEXT NOT NULL,hash TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('OPEN','ACKNOWLEDGED','SUPERSEDED')),
              note TEXT);
            ''')

    def add_brief(self,b):
        validate_brief(b)
        with self.reservoir.tx() as c:
            p=c.execute('SELECT body,hash FROM problems WHERE id=?',(b['problem_id'],)).fetchone()
            if not p or p['hash'] != b['problem_sha256'] or sha(parse(p['body'])) != p['hash']:
                raise ValueError('BRIEF_PROBLEM_BINDING_MISMATCH')
            old=c.execute('SELECT body,hash FROM decision_briefs WHERE id=?',(b['id'],)).fetchone()
            if old and (old['hash'] != sha(b) or parse(old['body']) != b):
                raise ValueError('IMMUTABLE_BRIEF_CONFLICT')
            c.execute('INSERT OR IGNORE INTO decision_briefs VALUES(?,?,?,?)',
                      (b['id'],b['problem_id'],canonical(b).decode(),sha(b)))
            return not bool(old)

    def snapshot(self):
        # One read transaction avoids mixed-state reports while inbox writers commit.
        with self.reservoir.tx() as c:
            c.execute('BEGIN')
            snapshot={}
            for table in ('problems','frontiers','trials','triggers','decision_briefs'):
                values=[]
                for r in c.execute('SELECT * FROM '+table+' ORDER BY id'):
                    v=parse(r['body'])
                    if v['id'] != r['id'] or sha(v) != r['hash']:
                        raise ValueError('INVENTORY_SOURCE_INTEGRITY_FAILED')
                    values.append(v)
                snapshot[table]=values
        problems={p['id']:p for p in snapshot['problems']}
        for b in snapshot['decision_briefs']:
            validate_brief(b)
            if b['problem_id'] not in problems or b['problem_sha256'] != sha(problems[b['problem_id']]):
                raise ValueError('BRIEF_PROBLEM_BINDING_MISMATCH')
        return snapshot

    @staticmethod
    def _comparison(p,frontiers,trials,as_of,cutoff):
        """Best eligible historical arm versus latest matched current arm; reported only."""
        scoped=[t for t in trials if t['problem_id']==p['id'] and t['run_on']<=as_of
                and t['frontier_id'] in frontiers and frontiers[t['frontier_id']]['observed_on']<=as_of
                and t['acceptance_sha256']==sha(p['acceptance'])]
        pairs=[]
        for old in scoped:
            if frontiers[old['frontier_id']]['observed_on']>cutoff:continue
            for new in scoped:
                if frontiers[new['frontier_id']]['observed_on']<=cutoff:continue
                if any(old[k]!=new[k] for k in ('terms_sha256','acceptance_sha256','protocol_sha256','price_microUSD','scope')):continue
                if p['demand']['terms_sha256'] is not None and new['terms_sha256']!=p['demand']['terms_sha256']:continue
                if p['demand']['ceiling_microUSD'] is not None and new['price_microUSD']>p['demand']['ceiling_microUSD']:continue
                pairs.append((old,new))
        if not pairs:return None
        # Do not cherry-pick a weak old arm; current ties are broken deterministically.
        latest=max((frontiers[n['frontier_id']]['observed_on'],n['run_on'],n['id']) for _,n in pairs)
        eligible=[(o,n) for o,n in pairs if (frontiers[n['frontier_id']]['observed_on'],n['run_on'],n['id'])==latest]
        def historical_value(t):
            v=Reservoir._value(t);a=t['alternative']
            if a['qualified'] and a['complete_cost_microUSD'] is not None:
                v=max(v,t['price_microUSD']*t['acceptance_probability_bps']-10000*a['complete_cost_microUSD'])
            return v
        old,new=max(eligible,key=lambda pair:(historical_value(pair[0]),pair[0]['id']))
        a,b=historical_value(old),Reservoir._value(new)
        alternative=new['alternative']
        ordinary_wins=(alternative['qualified'] and alternative['complete_cost_microUSD'] is not None
                       and alternative['complete_cost_microUSD']<=sum(new['costs_microUSD'].values()))
        crossing=a<=0<b and new['passed'] and new['independent_check']
        return {'before_trial':old['id'],'after_trial':new['id'],
                'before_margin_numerator':a,'after_margin_numerator':b,
                'denominator':10000,'unit':'modeled-microUSD','reported_crossing':crossing,
                'ordinary_cost_competitive':ordinary_wins,'evidence_scope':new['scope'],
                'historical_availability_independently_verified':False,
                'actual_profit_established':False}

    def plan(self,as_of):
        day(as_of);cutoff=(date.fromisoformat(as_of)-timedelta(days=35)).isoformat()
        s=self.snapshot();frontiers={f['id']:f for f in s['frontiers']}
        rows=[]
        for p in s['problems']:
            briefs=[b for b in s['decision_briefs'] if b['problem_id']==p['id'] and b['assessed_on']<=as_of]
            brief=max(briefs,key=lambda b:(b['assessed_on'],b['id'])) if briefs else None
            recent=[f for f in s['frontiers'] if cutoff<f['observed_on']<=as_of and set(f['tags'])&set(p['tags'])]
            recent.sort(key=lambda f:(f['observed_on'],f['id']),reverse=True)
            comp=self._comparison(p,frontiers,s['trials'],as_of,cutoff)
            d=p['demand'];expired=d['deadline'] is not None and d['deadline']<as_of
            if expired:action='EXPIRED_DEMAND';reason='Reconfirm buyer deadline before new commercial consideration.'
            elif brief is None:action='DEFINE_TEST';reason='Missing a source-bound decision brief and measurable acceptance targets.'
            elif comp and comp['ordinary_cost_competitive']:
                action='COMPARE_INCUMBENT';reason='Reported conventional alternative ties or beats production cost; investigate complete delivery advantage, not novelty.'
            elif comp and comp['reported_crossing']:
                action='REVIEW_DEMAND';reason='A modeled crossing is reported; independently verify historical access, buyer terms, full costs and current alternatives.'
            elif comp:
                action='MEASURE_ECONOMICS';reason='Matched records do not establish a positive crossing; retain negative evidence and inspect the limiting cost or capability.'
            elif recent:action='REPLAY_CANDIDATE';reason='Relevant recent capability report; execute a matched old/new/strong-alternative test before claiming progress.'
            else:action='MONITOR';reason='No relevant capability report in the 35-day window; retain the problem and its blocker.'
            # Explicit lexicographic research triage, not an estimate of dollar value or global optimality.
            demand_rank=int(d['status']=='CUSTOMER_REPORTED_UNVERIFIED')
            action_rank={'REVIEW_DEMAND':5,'REPLAY_CANDIDATE':4,'COMPARE_INCUMBENT':3,
                         'MEASURE_ECONOMICS':2,'DEFINE_TEST':1,'MONITOR':0,'EXPIRED_DEMAND':-1}[action]
            latest=recent[0]['observed_on'] if recent else ''
            evidence={'problem':sha(p),'brief':sha(brief) if brief else None,
                      'frontiers':[sha(f) for f in recent],
                      'trials':[sha(t) for t in s['trials'] if comp and t['id'] in (comp['before_trial'],comp['after_trial'])]}
            packet={'problem_id':p['id'],'action':action,'reason':reason,'evidence':evidence,
                    'proposed_test':p['next_test'],'criteria':brief['criteria'] if brief else [],
                    'criteria_status':'PROPOSED_NOT_MEASURED','execution_authorized':False,
                    'financial_authority':'NONE','buyer_consent_verified':False}
            task_id=sha(packet)
            rows.append({'problem':p,'brief':brief,'action':action,'reason':reason,
                         'recent_frontier_ids':[f['id'] for f in recent],
                         'comparison':comp,'priority_key':[int(not expired),demand_rank,action_rank,latest],
                         'task_id':task_id,'packet':packet})
        rows.sort(key=lambda r:r['problem']['id'])
        rows.sort(key=lambda r:r['priority_key'],reverse=True)
        return {'schema':'frontier-omega/living-inventory/v1','as_of':as_of,'historical_cutoff':cutoff,
                'inventory':rows,'problem_count':len(rows),'rank_policy':'LEXICOGRAPHIC_RESEARCH_TRIAGE_NOT_DOLLAR_VALUE',
                'source_snapshot_sha256':sha(s),'actual_customers':'NOT_ESTABLISHED',
                'verified_economic_crossings':0,'financial_authority':'NONE'}

    def refresh(self,as_of):
        with self.reservoir.lock():
            return self._refresh(as_of)

    def _refresh(self,as_of):
        plan=self.plan(as_of);added=0;reopened=0
        with self.reservoir.tx() as c:
            clock=c.execute('SELECT as_of FROM inventory_clock WHERE id=1').fetchone()
            if clock and as_of<clock[0]:raise ValueError('REFRESH_CLOCK_REGRESSION_USE_READ_ONLY_PLAN')
            c.execute('INSERT OR REPLACE INTO inventory_clock VALUES(1,?)',(as_of,))
            for r in plan['inventory']:
                p=r['packet'];ident=r['task_id']
                c.execute("UPDATE research_queue SET state='SUPERSEDED' WHERE problem_id=? AND id!=? AND state='OPEN'",(p['problem_id'],ident))
                exists=c.execute('SELECT body,hash,state FROM research_queue WHERE id=?',(ident,)).fetchone()
                if exists and (parse(exists['body'])!=p or exists['hash']!=sha(p)):
                    raise ValueError('RESEARCH_QUEUE_INTEGRITY_FAILED')
                c.execute("INSERT OR IGNORE INTO research_queue VALUES(?,?,?,?, 'OPEN',NULL)",
                          (ident,p['problem_id'],canonical(p).decode(),sha(p)))
                added+=int(not exists)
                if exists and exists['state']=='SUPERSEDED':
                    c.execute("UPDATE research_queue SET state='OPEN',note=NULL WHERE id=?",(ident,))
                    reopened+=1
            statuses={r['id']:r['state'] for r in c.execute('SELECT id,state FROM research_queue')}
        for r in plan['inventory']:r['task_state']=statuses[r['task_id']]
        plan['tasks_added']=added;plan['tasks_reopened']=reopened
        atomic(self.root/'INVENTORY.json',canonical(plan))
        atomic(self.root/'INVENTORY.html',render(plan).encode())
        return plan

    def acknowledge(self,ident,note):
        title(note)
        with self.reservoir.tx() as c:
            row=c.execute('SELECT * FROM research_queue WHERE id=?',(ident,)).fetchone()
            if not row or sha(parse(row['body']))!=ident or row['hash']!=ident:raise ValueError('UNKNOWN_OR_CHANGED_RESEARCH_TASK')
            if row['state']=='ACKNOWLEDGED':
                if row['note']!=note:raise ValueError('ACKNOWLEDGMENT_CONFLICT')
                return False
            if row['state']!='OPEN':raise ValueError('SUPERSEDED_RESEARCH_TASK')
            c.execute("UPDATE research_queue SET state='ACKNOWLEDGED',note=? WHERE id=?",(note,ident))
        return True

    def watch(self,interval,cycles=None,stop=None,release_config=None,release_every=3600,release_fetch=None):
        import math
        if type(interval) not in (int,float) or not math.isfinite(interval) or interval<.05:raise ValueError('FINITE_POLL_INTERVAL_REQUIRED')
        if cycles is not None and (type(cycles) is not int or cycles<1):raise ValueError('POSITIVE_CYCLES_REQUIRED')
        if type(release_every) not in (int,float) or not math.isfinite(release_every) or release_every<300:
            raise ValueError('RELEASE_POLL_MUST_BE_AT_LEAST_300_SECONDS')
        if release_config is not None:
            from .releases import validate_config,poll
            validate_config(release_config)
        stop=stop or threading.Event();count=0;last_poll=None
        with self.reservoir.lock():
            while not stop.is_set():
                self.reservoir.ingest_inbox()
                if release_config is not None and (last_poll is None or time.monotonic()-last_poll>=release_every):
                    observation=poll(self.reservoir,release_config,fetch=release_fetch)
                    atomic(self.root/'RADAR.json',canonical(observation));last_poll=time.monotonic()
                self._refresh(datetime.now(timezone.utc).date().isoformat());count+=1
                if cycles is not None and count>=cycles:break
                stop.wait(interval)
        return {'polls_completed':count,'worker_stopped':True,'financial_authority':'NONE'}


def render(plan):
    esc=lambda x:html.escape(str(x),quote=True)
    cards=[]
    for r in plan['inventory']:
        p,b=r['problem'],r['brief'];b=b or {}
        criteria=''.join('<li>'+esc(c['metric']+' '+c['operator']+' '+str(c['target'])+' '+c['unit'])+'</li>' for c in b.get('criteria',[]))
        sources=''.join('<a target="_blank" rel="noopener noreferrer" href="'+esc(u)+'">'+esc(u)+'</a>' for u in p['source_urls'])
        cards.append('<article data-search="'+esc(' '.join([p['title'],p['beneficiary'],*p['tags'],r['action']]).lower())+'"><small>'+esc(r['action'].replace('_',' '))+'</small><h2>'+esc(p['title'])+'</h2><p>'+esc(p['outcome'])+'</p><dl><dt>Who benefits</dt><dd>'+esc(p['beneficiary'])+'</dd><dt>Economic value hypothesis</dt><dd>'+esc(b.get('value_driver','Not yet specified'))+'</dd><dt>What still blocks delivery</dt><dd>'+esc(p['blocker'])+'</dd><dt>Next decisive test</dt><dd>'+esc(p['next_test'])+'</dd><dt>Buyer question</dt><dd>'+esc(b.get('buyer_question','Request actual acceptance terms and budget.'))+'</dd><dt>Reusable asset</dt><dd>'+esc(b.get('successor_asset','Not yet specified'))+'</dd></dl><details><summary>Acceptance targets, alternatives and evidence</summary><p>Proposed targets, not measured performance.</p><ul>'+criteria+'</ul><p>'+esc(' / '.join(a['name']+': '+a['route'] for a in p['alternatives']))+'</p><div class="links">'+sources+'</div><p>Recent signals: '+esc(', '.join(r['recent_frontier_ids']) or 'None')+'</p><p>Task: '+esc(r['task_id'])+'</p></details><footer>'+esc(r['reason'])+'</footer></article>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>FRONTIER Ω · Living opportunity inventory</title><style>body{margin:0;background:#0c1420;color:#ecf1f6;font:16px/1.6 system-ui}main{max-width:1160px;margin:auto;padding:48px 24px}header{padding:32px 0 40px;border-bottom:1px solid #304151}small{color:#bba77c;letter-spacing:.12em;font-size:12px}h1{font-size:clamp(38px,7vw,72px);line-height:1.05;margin:18px 0}h2{font-size:23px;line-height:1.3}p{max-width:80ch}input{width:100%;box-sizing:border-box;padding:16px;background:#132230;color:#fff;border:1px solid #527082;border-radius:8px;font:inherit;margin:30px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(450px,100%),1fr));gap:20px}article{background:#111e2c;border:1px solid #2d4255;border-radius:12px;padding:26px}dt{font-size:12px;color:#9bb5c8;margin-top:16px;text-transform:uppercase;letter-spacing:.04em}dd{margin:4px 0}footer{border-top:1px solid #304151;margin-top:20px;padding-top:16px;font-size:14px;color:#b6c6d3}details{margin-top:18px}summary{cursor:pointer;color:#decda6}.links a{display:block;overflow-wrap:anywhere;color:#a8d0de;font-size:12px}li{overflow-wrap:anywhere}.note{color:#b8c8d8}article[hidden]{display:none}.stat{font-size:28px;color:#decda6}</style></head><body><main><header><small>MONTREAL.AI / ALPHA ECONOMIC ENGINE / SENSOR & TIMING</small><h1>FRONTIER Ω</h1><p>Know which valuable problem to test when the frontier moves.</p><div class="stat">'''+str(plan['problem_count'])+''' problems · 35-day watch window</div><p class="note">As of '''+esc(plan['as_of'])+'''. Research hypotheses—not customers, profits or proven frontier breakthroughs. Private, offline inventory. Nothing on this page authorizes spending.</p></header><label for="search">Search outcomes, buyers, capabilities or actions</label><input id="search" type="search" placeholder="Search the inventory…"><div class="grid">'''+''.join(cards)+'''</div><footer>One canonical reservoir. Source-bound research tasks. No external assets, telemetry, or network calls. Acknowledging a task does not certify commercial value.</footer></main><script>document.getElementById('search').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('article').forEach(a=>{a.hidden=!a.dataset.search.includes(q)})});</script></body></html>'''


def bootstrap(root):
    from .catalog import additions,briefs_for
    inv=Inventory(root)
    seed=Path(__file__).resolve().parents[1]/'examples/frontier-omega/public-opportunities-20261116.json'
    inv.reservoir.seed(load_file(seed))
    for p in additions():inv.reservoir.add(p)
    for b in briefs_for(inv.reservoir.rows('problems')):inv.add_brief(b)
    return inv


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=Path('./frontier-private'))
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('init','refresh','list'):
        s=sub.add_parser(name);s.add_argument('--as-of',default=datetime.now(timezone.utc).date().isoformat())
        if name=='list':s.add_argument('--limit',type=int,default=5)
    b=sub.add_parser('brief');b.add_argument('--file',type=Path,required=True)
    a=sub.add_parser('ack');a.add_argument('--task-id',required=True);a.add_argument('--note',required=True)
    w=sub.add_parser('watch');w.add_argument('--interval',type=float,default=30);w.add_argument('--cycles',type=int);w.add_argument('--release-config',type=Path);w.add_argument('--release-every',type=float,default=3600)
    d=sub.add_parser('demo');d.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='demo':
        if args.output.exists():p.error('demo requires a fresh output directory')
        inv=bootstrap(args.output);r=inv.refresh('2026-11-16')
        again=inv.refresh('2026-11-16')
        result={'problem_count':r['problem_count'],'first_tasks':r['tasks_added'],'repeat_tasks':again['tasks_added'],
                'canonical_audit':inv.reservoir.audit(),'customer_count':0,'economic_crossings_verified':0,
                'public_research_only':True,'source_sha256':{x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in (Path(__file__),Path(__file__).with_name('catalog.py'),Path(__file__).with_name('core.py'),Path(__file__).with_name('releases.py'))}}
        atomic(args.output/'RESULTS.json',canonical(result))
    else:
        inv=bootstrap(args.root) if args.command=='init' else Inventory(args.root)
        if args.command in ('init','refresh'):
            full=inv.refresh(args.as_of)
            result={k:full[k] for k in ('problem_count','tasks_added','tasks_reopened','as_of','source_snapshot_sha256')}
            result.update(dashboard=str(inv.root/'INVENTORY.html'),inventory=str(inv.root/'INVENTORY.json'),financial_authority='NONE')
        elif args.command=='list':
            if args.limit<1:p.error('limit must be positive')
            result=inv.plan(args.as_of);result['inventory']=result['inventory'][:args.limit]
        elif args.command=='brief':result={'brief_added':inv.add_brief(load_file(args.file))}
        elif args.command=='ack':result={'acknowledged':inv.acknowledge(args.task_id,args.note)}
        else:
            stop=threading.Event()
            signal.signal(signal.SIGINT,lambda *_:stop.set());signal.signal(signal.SIGTERM,lambda *_:stop.set())
            result=inv.watch(args.interval,args.cycles,stop,load_file(args.release_config) if args.release_config else None,args.release_every)
    print(canonical(result).decode())

if __name__=='__main__':main()
