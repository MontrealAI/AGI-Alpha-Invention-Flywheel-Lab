"""Watch real release work, learn locally, and retain reviewable improvements."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from time import perf_counter_ns, process_time_ns, sleep, time

from check import read
from learning import estimate, example, examples, forecasts, train
from pages import EVENTS, HASH, REPO, WORKFLOW, canonical, current, digest, validate, witness
from study import atomic, lock

CONTROL = 'frontier/learning-authority-v1'
VIEW = 'frontier/learning-status-v1'
TRAINING_WINDOW = 512
TABLES = '''
CREATE TABLE IF NOT EXISTS experience(id INTEGER PRIMARY KEY, number INTEGER UNIQUE NOT NULL,
 row TEXT NOT NULL, prediction TEXT, observed INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS queue(key TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id INTEGER NOT NULL,
 state TEXT NOT NULL, result TEXT, wall_ns INTEGER, cpu_ns INTEGER);
CREATE TABLE IF NOT EXISTS models(sha TEXT PRIMARY KEY, run_id INTEGER NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facts(key TEXT PRIMARY KEY, value TEXT NOT NULL);
'''


def text(value):
    return canonical(value).decode()


def inventory(db, key, default=None):
    row = db.execute('SELECT value FROM facts WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else default


def fact(db,key,value):
    db.execute('INSERT OR REPLACE INTO facts VALUES (?,?)',(key,text(value)))


def event(db, kind, **payload):
    db.execute('INSERT INTO events(kind,payload) VALUES (?,?)',(kind,text(payload)))


def control(key=None):
    return {'schema':CONTROL,'repository':REPO,'workflow':WORKFLOW,'paid_budget':0,
            'rights':'public MONTREAL.AI release telemetry','read_budget':60,'retrain_every':8,
            'evaluator_key_sha256':key}


def open_state(root,policy):
    db = sqlite3.connect(root/'learning.sqlite3',timeout=10)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript(TABLES)
        seal = digest(policy)
        authority = inventory(db,'authority')
        if authority not in (None,seal):
            raise ValueError('AUTHORITY_CHANGED')
        with db:
            fact(db,'authority',seal)
        return db
    except BaseException:
        db.close()
        raise


def recover(db):
    with db:
        for key,kind in db.execute("SELECT key,kind FROM queue WHERE state='RUNNING'").fetchall():
            event(db,'INTERRUPTED',key=key,stage=kind)
            db.execute("UPDATE queue SET state='QUEUED' WHERE key=?",(key,))
        pending = inventory(db,'read_pending')
        if pending:
            event(db,'INTERRUPTED_READ',reserved=pending)
            fact(db,'read_pending',0)
        fact(db,'operating',False)


def records(db):
    return [json.loads(raw) for (raw,) in db.execute('SELECT row FROM experience ORDER BY number')]


def reserve(db, count, policy):
    with db:
        hour = int(time())//3600
        if inventory(db,'read_hour')!=hour:
            fact(db,'read_hour',hour)
            fact(db,'read_hour_reserved',0)
        consumed = inventory(db,'read_hour_reserved',0)
        if consumed+count>policy['read_budget']:
            raise ValueError('PUBLIC_READ_BUDGET')
        fact(db,'read_hour_reserved',consumed+count)
        fact(db,'read_reserved',inventory(db,'read_reserved',0)+count)
        fact(db,'read_pending',count)


def settle(db, reserved, observed):
    with db:
        if inventory(db,'read_pending')!=reserved or not 0<=observed<=reserved:
            raise ValueError('READ_ACCOUNTING')
        if observed!=reserved:
            fact(db,'read_reserved',inventory(db,'read_reserved')-reserved+observed)
            fact(db,'read_hour_reserved',inventory(db,'read_hour_reserved')-reserved+observed)
        fact(db,'read_pending',0)


def propose(db, item):
    answer = {'baseline':estimate(None,item),'admitted':None,'shadow':None}
    for label,key in (('admitted','active_model'),('shadow','latest_candidate')):
        sha = inventory(db,key)
        row = db.execute('SELECT body FROM models WHERE sha=?',(sha,)).fetchone()
        if row:
            if label=='admitted' and inventory(db,'active_expiry',0)<=int(time()):
                continue
            model=json.loads(row[0])
            if model.get('fit_events',{}).get(item['event'],0)>=8:
                answer[label] = {'sha256':sha,'seconds':estimate(model,item)}
    return answer


def revoke(db):
    current_receipt=inventory(db,'active_receipt')
    if current_receipt:
        fact(db,'revoked-'+current_receipt,True)
    fact(db,'active_receipt',None)
    fact(db,'active_model',None)
    fact(db,'active_expiry',0)


def verify_observed(db, row, prediction):
    elapsed = row['completed']-row['created']
    event(db,'PROSPECTIVE_OUTCOME',run_id=row['id'],seconds=elapsed,estimate=prediction)
    active=prediction['admitted']
    if not active or active['sha256']!=inventory(db,'active_model'):
        return
    key='admission-monitor-'+active['sha256']
    errors=inventory(db,key,[])[-4:]
    errors.append([abs(active['seconds']-elapsed),abs(prediction['baseline']-elapsed)])
    fact(db,key,errors)
    if len(errors)==5 and sum(a for a,_ in errors)*10>sum(b for _,b in errors)*11:
        revoke(db)
        event(db,'SUSPENDED_REGRESSION',candidate=active['sha256'],errors=errors)


def observe(db, rows, seed=False):
    if type(rows) is not list or len(rows)>1500:
        raise ValueError('OBSERVATION_BATCH')
    known = records(db)[-TRAINING_WINDOW:]
    with db:
        for row in sorted(rows,key=lambda x:(x['number'],x['id'])):
            validate(row)
            prior = db.execute('SELECT row,prediction FROM experience WHERE id=?',(row['id'],)).fetchone()
            old = json.loads(prior[0]) if prior else None
            if old:
                if old==row:
                    continue
                if old['completed'] is not None or any(old[k]!=row[k] for k in ('number','event','sha','created')):
                    event(db,'SOURCE_DRIFT',run_id=row['id'],record_sha256=digest(row))
                    continue
            prediction = prior[1] if prior else None
            if row['completed'] is None and not seed and prediction is None:
                item = example(row,known)
                if item:
                    prediction = text(propose(db,item))
                    event(db,'PROSPECTIVE_ESTIMATE',run_id=row['id'],**json.loads(prediction))
            if seed and row['completed'] is None:
                raise ValueError('HISTORICAL_SEED_REQUIRED')
            db.execute('INSERT INTO experience VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET row=excluded.row, '
                       'prediction=excluded.prediction, observed=excluded.observed',
                       (row['id'],row['number'],text(row),prediction,int(time())))
            if row['completed'] is not None and not seed:
                if prediction:
                    verify_observed(db,row,json.loads(prediction))
                db.execute("INSERT OR IGNORE INTO queue(key,kind,run_id,state) VALUES (?,'audit',?,'QUEUED')",
                           (f'audit-{row["id"]}',row['id']))
                trigger = inventory(db,'new_completions',0)+1
                fact(db,'new_completions',trigger)


def plan(db,policy):
    sampling = [r for r in records(db) if r['completed'] is not None]
    if len(sampling)<32 or (inventory(db,'latest_candidate') and
                            inventory(db,'new_completions',0)<policy['retrain_every']):
        return
    last = sampling[-1]['id']
    with db:
        db.execute("INSERT OR IGNORE INTO queue(key,kind,run_id,state) VALUES (?,'learn',?,'QUEUED')",
                   (f'learn-{last}',last))


def resample(db,row):
    data = [r for r in records(db) if r['completed'] is not None and r['number']<=row['number']][-TRAINING_WINDOW:]
    # Retain a chronological development slice and keep later observations out of the fit.
    cases = examples(data)
    if len(cases)<24:
        return {'state':'ABSTAIN','reason':'INSUFFICIENT_ELIGIBLE_HISTORY'}
    development = max(8,len(cases)//5)
    fitting=cases[:-development]
    model, cost = train(fitting)
    model['fit_events']={event:sum(row['event']==event for row in fitting) for event in EVENTS}
    compare = forecasts(cases[-development:],model)
    sha = digest(model)
    result = {'state':'CANDIDATE','sha256':sha,'training':cost,'development':compare,
              'training_through':cases[-development-1]['number'],'run_id':row['id'],
              'parent_candidate_sha256':inventory(db,'latest_candidate')}
    with db:
        db.execute('INSERT OR IGNORE INTO models VALUES (?,?,?)',(sha,row['id'],text(model)))
        fact(db,'latest_candidate',sha)
        fact(db,'new_completions',0)
        if compare['trained']['mae_seconds']>=compare['initial']['mae_seconds']:
            event(db,'RESEARCH_OPPORTUNITY',reason='CALIBRATION_LOSS',run_id=row['id'],candidate=sha)
    return result


def drain(db,policy,research=None,on_stage=None):
    while queued := db.execute("SELECT key,kind,run_id FROM queue WHERE state='QUEUED' ORDER BY rowid LIMIT 1").fetchone():
        key,kind,task = queued
        with db:
            db.execute("UPDATE queue SET state='RUNNING' WHERE key=?",(key,))
        if on_stage:
            on_stage()
        start,cpu = perf_counter_ns(),process_time_ns()
        row = json.loads(db.execute('SELECT row FROM experience WHERE id=?',(task,)).fetchone()[0])
        state = 'COMPLETE'
        try:
            if kind=='audit' and row['event']=='push' and row['conclusion']=='success':
                # Reserve the receipt and both asset reads before dispatch.
                reserve(db,3,policy)
                try:
                    result=witness(row)
                finally:
                    settle(db,3,3)
            elif kind=='learn':
                result=resample(db,row)
            elif kind=='invent' and research:
                result=construct(db,row,*research)
            else:
                result={'state':'ABSTAIN','reason':'NO_PRODUCTION_PUSH_TO_AUDIT'}
        except (OSError,ValueError,KeyError,TypeError) as error:
            result={'state':'REJECTED','reason':type(error).__name__}
            state='FAILED'
        with db:
            db.execute('UPDATE queue SET state=?,result=?,wall_ns=?,cpu_ns=? WHERE key=?',
                       (state,text(result),perf_counter_ns()-start,process_time_ns()-cpu,key))
            if (kind=='learn' and research and result.get('state')=='CANDIDATE' and
                    result['development']['trained']['mae_seconds']>=result['development']['initial']['mae_seconds']):
                db.execute("INSERT OR IGNORE INTO queue(key,kind,run_id,state) VALUES (?,'invent',?,'QUEUED')",
                           (f'invent-{task}',task))


def construct(db, row, root, config, choice):
    from types import SimpleNamespace
    from bridge.adapters import BridgeError
    from research import ResearchModel, ResearchRun, determine

    data = [r for r in records(db) if r['completed'] is not None and r['number']<=row['number']][-TRAINING_WINDOW:]
    cases = [c for c in examples(data) if c['event']==row['event']][-24:]
    if len(cases)<8:
        return {'state':'ABSTAIN','reason':'RESEARCH_SAMPLE'}
    location = root/'construction'/str(row['id'])
    location.mkdir(mode=0o700,parents=True,exist_ok=True)
    try:
        model = ResearchModel(SimpleNamespace(config=config,provider='localhost-inference',model=choice,representation='expression'))
    except BridgeError as error:
        return {'state':'REJECTED','reason':error.code}
    budget = min(512,model.provider.models[choice].max_output_tokens)
    if budget < 96:
        return {'state':'ABSTAIN','reason':'RESEARCH_OUTPUT_BUDGET'}
    binding = {'kind':'adaptive-construct','event':row['event'],'arm':'original',
               'attempts':1,'request_tokens':budget,'representation':'expression','cases_sha256':digest(cases),'run_id':row['id']}
    with lock(location):
        experiment = ResearchRun(location/'run.json',model,budget,binding)
        result = determine(experiment,cases,'original',None,'construct')
    return {'state':result['status'],'evidence_sha256':digest(result),'highest_authority':'DEVELOPMENT'}


def view(db):
    stale_after = inventory(db,'lease_until',0)
    stages = [dict(zip(('stage','state','result','wall_ns','cpu_ns'),(kind,state,json.loads(raw) if raw else None,wall,cpu)))
              for kind,state,raw,wall,cpu in db.execute('SELECT kind,state,result,wall_ns,cpu_ns FROM queue ORDER BY rowid DESC LIMIT 12')]
    count=db.execute('SELECT count(*) FROM experience').fetchone()[0]
    return {'schema':VIEW,'scope':'public-actions-pages','observed':count,
            'state':'ACTIVE' if inventory(db,'operating',False) and stale_after>int(time()) else 'IDLE',
            'observed_at':int(time()),'lease_until':stale_after,'reads_reserved':inventory(db,'read_reserved',0),
            'candidate_sha256':inventory(db,'latest_candidate'),
            'admitted_sha256':inventory(db,'active_model') if inventory(db,'active_expiry',0)>int(time()) else None,
            'stages':stages}


def write_view(root,db):
    summary=view(db)
    atomic(root/'learning-status.json',summary)
    return summary


def watch(db, root, policy, args):
    if not 1<=args.cycles<=24 or not 15<=args.interval<=120 or (args.run is not None and not 0<args.run<2**53):
        raise ValueError('WATCH_INTERVAL')
    if bool(args.research_config)!=bool(args.research_model):
        raise ValueError('RESEARCH_CONFIG_AND_MODEL_REQUIRED')
    research = (root,args.research_config,args.research_model) if args.research_config else None
    with db:
        fact(db,'operating',True)
    try:
        for turn in range(args.cycles):
            with db:
                fact(db,'lease_until',int(time())+args.interval+35)
            write_view(root,db)
            reserve(db,1,policy)
            started=perf_counter_ns()
            try:
                seen = current(args.run)
            except (OSError,ValueError,KeyError,TypeError) as error:
                with db:
                    event(db,'READ_FAILED',reason=type(error).__name__,run_id=args.run)
                seen=[]
            finally:
                settle(db,1,1)
            with db:
                event(db,'PUBLIC_POLL',run_id=args.run,records=len(seen),wall_ns=perf_counter_ns()-started)
            observe(db,seen)
            plan(db,policy)
            drain(db,policy,research,on_stage=lambda:write_view(root,db))
            write_view(root,db)
            if turn+1<args.cycles and not (args.run and any(row['completed'] is not None for row in seen)):
                sleep(args.interval)
            else:
                break
    finally:
        with db:
            fact(db,'operating',False)
        write_view(root,db)


def admit(db,policy,receipt_path,key_path):
    import base64
    from tempfile import TemporaryDirectory

    with key_path.open('rb') as stream:
        key=stream.read(16385)
    if len(key)>16384:
        raise ValueError('EVALUATOR_KEY')
    if not policy['evaluator_key_sha256'] or sha256(key).hexdigest()!=policy['evaluator_key_sha256']:
        raise ValueError('EVALUATOR_KEY')
    receipt=read(receipt_path)
    if set(receipt)!={'decision','signature'}:
        raise ValueError('ADMISSION_RECEIPT')
    payload=receipt['decision']
    identity=digest(payload)
    if (set(payload)!={'schema','authority','candidate','state','expires','scope'} or
            payload['schema']!='frontier/learning-admission-v1' or payload['authority']!=digest(policy) or
            payload['state']!='QUALIFIED' or payload['scope']!='public-actions-pages-forecast' or
            type(payload['expires']) is not int or payload['expires']<=int(time()) or
            inventory(db,'revoked-'+identity,False) or
            not db.execute('SELECT 1 FROM models WHERE sha=?',(payload['candidate'],)).fetchone()):
        raise ValueError('ADMISSION_REJECTED')
    with TemporaryDirectory() as scratch:
        root=Path(scratch)
        signature=base64.b64decode(receipt['signature'],validate=True)
        if not 0<len(signature)<=1024:
            raise ValueError('ADMISSION_SIGNATURE')
        (root/'key').write_bytes(key)
        (root/'signature').write_bytes(signature)
        checked=subprocess.run(('openssl','dgst','-sha256','-verify',str(root/'key'),'-signature',str(root/'signature')),
                               input=canonical(payload),capture_output=True,timeout=8)
        if checked.returncode:
            raise ValueError('ADMISSION_SIGNATURE')
    with db:
        previous=inventory(db,'active_receipt')
        if previous and previous!=identity:
            revoke(db)
        fact(db,'active_model',payload['candidate'])
        fact(db,'active_expiry',payload['expires'])
        fact(db,'active_receipt',identity)
        event(db,'ADMITTED',candidate=payload['candidate'],decision_sha256=identity)


def command(args):
    root=args.workspace
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    with lock(root):
        authority=root/'authority.json'
        if args.command=='init':
            if args.evaluator_key and not HASH.fullmatch(args.evaluator_key):
                raise ValueError('EVALUATOR_KEY')
            if not authority.exists():
                atomic(authority,control(args.evaluator_key))
            elif read(authority)!=control(args.evaluator_key):
                raise ValueError('AUTHORITY_CHANGED')
        policy=read(authority)
        if policy!=control(policy.get('evaluator_key_sha256')):
            raise ValueError('AUTHORITY_SCOPE')
        with closing(open_state(root,policy)) as db:
            recover(db)
            if args.command=='seed':
                supplied=read(args.history)
                observe(db,supplied,seed=True)
                with db:
                    event(db,'HISTORICAL_INPUT',rights=policy['rights'],sha256=digest(supplied),records=len(supplied))
            if args.command=='watch':
                watch(db,root,policy,args)
            if args.command=='advance':
                plan(db,policy)
                drain(db,policy)
            if args.command=='admit':
                admit(db,policy,args.receipt,args.public_key)
            if args.command=='rollback':
                with db:
                    event(db,'ROLLED_BACK',previous=inventory(db,'active_model'))
                    revoke(db)
            return write_view(root,db)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init').add_argument('--evaluator-key')
    sub.add_parser('seed').add_argument('history',type=Path)
    monitor=sub.add_parser('watch')
    monitor.add_argument('--run',type=int)
    monitor.add_argument('--cycles',type=int,default=4)
    monitor.add_argument('--interval',type=int,default=30)
    monitor.add_argument('--research-config',type=Path)
    monitor.add_argument('--research-model')
    promote=sub.add_parser('admit')
    promote.add_argument('receipt',type=Path)
    promote.add_argument('public_key',type=Path)
    sub.add_parser('status')
    sub.add_parser('advance')
    sub.add_parser('rollback')
    try:
        print(text(command(parser.parse_args())))
    except KeyboardInterrupt:
        print('Paused. The local queue will recover on the next invocation.',file=sys.stderr)
        sys.exit(130)
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error) as error:
        print('Local operation stopped: '+str(error),file=sys.stderr)
        sys.exit(2)
