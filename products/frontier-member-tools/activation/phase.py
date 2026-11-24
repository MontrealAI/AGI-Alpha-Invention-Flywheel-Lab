"""Observe released workflow phases and compare forecasts without future data."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter_ns, sleep, time

from pages import API, canonical, current, digest, get, timestamp
from study import atomic, lock

NAMES=('build','deploy','verify-live')


def clock(value):
    return timestamp(value) if value else None


def jobs(body,run_id):
    raw=json.loads(body)
    if raw['total_count']>30 or len(raw['jobs'])>30:
        raise ValueError('JOB_SCOPE')
    result={}
    for job in raw['jobs']:
        if job['run_id']!=run_id:
            raise ValueError('JOB_RUN_BINDING')
        name=job['name']
        if name not in NAMES:
            continue
        if name in result:
            raise ValueError('AMBIGUOUS_JOB')
        result[name]={'state':job['status'],'start':clock(job['started_at']),'finish':clock(job['completed_at']),
                      'conclusion':job['conclusion']}
    return result


def prepare(source):
    index=json.loads((source/'sources.json').read_bytes())
    output=[]
    for key,reference in sorted(index['results'].items()):
        blob=(source/f'{int(key)}.json').read_bytes()
        sha=sha256(blob).hexdigest()
        if sha!=reference['sha256']:
            raise ValueError('PHASE_DATA_DRIFT')
        row=reference['run']
        output.append({'run':row,'jobs':jobs(blob,row['id']),'origin':reference['url'],'sha256':sha})
    return {'history':output,'errors':index['errors']}


def visible(now,run,phases):
    if run['event']=='pull_request':
        scope=NAMES[:1]
    else:
        scope=NAMES
    for name in scope:
        job=phases.get(name)
        if job is None or job['state']!='completed':
            started=job['start'] if job else None
            if started is not None and started<=now and job['state']=='in_progress':
                return name,started
            previous=[row['finish'] for idx,row in phases.items() if idx in scope[:scope.index(name)]
                      and row['finish'] is not None and row['finish']<=now]
            return 'before-'+name,max(previous,default=run['created'])
    finishes=[job['finish'] for job in phases.values() if job['finish'] is not None and job['finish']<=now]
    return 'finalizing',max(finishes,default=run['created'])


def basis(entry,phase):
    refs=entry['jobs']
    created=entry['run']['created']
    if phase in NAMES:
        return refs.get(phase,{}).get('start')
    if phase=='finalizing':
        return max((job['finish'] for job in refs.values() if job['finish']),default=created)
    if phase.startswith('before-') and phase.removeprefix('before-') in NAMES:
        name=phase.removeprefix('before-')
        prior=NAMES[:NAMES.index(name)]
        return max((refs[k]['finish'] for k in prior if k in refs and refs[k]['finish']),default=created)
    raise ValueError('PHASE')


def predict(now,run,phases,history,events):
    phase,anchor=visible(now,run,phases)
    elapsed=max(0,now-run['created'])
    qualified=sorted((row for row in events if row['event']==run['event'] and row['completed'] is not None
                      and row['completed']<run['created']),key=lambda row:row['number'])[-60:]
    if len(qualified)<8:
        return None
    whole=[row['completed']-row['created'] for row in qualified]
    late=[seconds-elapsed for seconds in whole if seconds>=elapsed]
    phase_delays=[]
    for item in history:
        old=item['run']
        if old['event']!=run['event'] or old['completed']>=run['created']:
            continue
        past=basis(item,phase)
        if past is not None and old['completed']-past>=now-anchor>=0:
            phase_delays.append(old['completed']-past-(now-anchor))
    return {'phase':phase,'observed_at':now,'phase_age':now-anchor,'phase_support':len(phase_delays),
            'elapsed':elapsed,'trailing_60':max(0,round(median(whole))-elapsed),
            'elapsed_survival':round(median(late)) if len(late)>=4 else None,
            'phase_remaining':round(median(phase_delays)) if len(phase_delays)>=4 else None}


def close(state,run):
    state['terminal']=run
    for row in state['predictions']:
        actual=run['completed']-row['observed_at']
        row['actual']=actual if actual>0 else None
        row['admissible']=actual>0
    state['state']='COMPLETE'


def watch(args):
    if not 1<=args.cycles<=14 or not 15<=args.interval<=120 or not 0<args.run<2**53:
        raise ValueError('PHASE_LEASE')
    history=json.loads(args.history.read_bytes())['history']
    observed=json.loads(args.events.read_bytes())
    binding={'run':args.run,'history':digest(history),'events':digest(observed),'expires':args.until}
    args.workspace.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=args.workspace/'phase-status.json'
    with lock(args.workspace):
        state=json.loads(path.read_bytes()) if path.exists() else {'schema':'frontier/phase-study-v1','binding':binding,
                    'state':'IDLE','reads':0,'polls':[],'predictions':[],'terminal':None}
        if binding!=state['binding']:
            raise ValueError('PHASE_SCOPE_DRIFT')
        if state['state']=='COMPLETE':
            return state
        for attempt in range(args.cycles):
            if time()>=args.until or state['reads']+2>30:
                break
            start=perf_counter_ns()
            state['state']='ACTIVE'
            state['reads']+=2
            atomic(path,state)
            try:
                records=current(args.run)
                if len(records)!=1:
                    raise ValueError('PHASE_RUN_SCOPE')
                run=records[0]
                if run['completed'] is not None:
                    close(state,run)
                    atomic(path,state)
                    return state
                if time()>=args.until:
                    break
                raw=get(f'{API}/runs/{args.run}/jobs?filter=latest&per_page=30',450000)
                seen=jobs(raw,args.run)
                now=int(time())
                if any(t is not None and t>now for job in seen.values() for t in (job['start'],job['finish'])):
                    raise ValueError('JOB_CLOCK_AHEAD_OF_OBSERVATION')
                label=predict(now,run,seen,history,observed)
                state['polls'].append({'seen':now,'jobs':seen,'created':run['created'],'started':run['started'],
                                       'response_sha256':sha256(raw).hexdigest(),
                                       'wall_ns':perf_counter_ns()-start})
                if label and label['phase'] not in {r['phase'] for r in state['predictions']}:
                    state['predictions'].append(label)
            except (OSError,ValueError,KeyError,TypeError) as error:
                state['polls'].append({'seen':int(time()),'error':type(error).__name__,'wall_ns':perf_counter_ns()-start})
            atomic(path,state)
            if attempt+1<args.cycles and time()+args.interval<args.until:
                sleep(args.interval)
        state['state']='IDLE'
        atomic(path,state)
        return state


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    sub=cli.add_subparsers(dest='command',required=True)
    sub.add_parser('prepare').add_argument('source',type=Path)
    observer=sub.add_parser('watch')
    for key in ('history','events','workspace'):
        observer.add_argument('--'+key,type=Path,required=True)
    observer.add_argument('--run',type=int,required=True)
    observer.add_argument('--until',type=int,required=True)
    observer.add_argument('--interval',type=int,default=20)
    observer.add_argument('--cycles',type=int,default=12)
    args=cli.parse_args()
    value=prepare(args.source) if args.command=='prepare' else watch(args)
    print(canonical(value).decode())
