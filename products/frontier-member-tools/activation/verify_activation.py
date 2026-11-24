"""Independently score frozen packet policies and reproduce a live public replay."""

import argparse
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns,process_time_ns

from activate import ARMS, checked, read, select_cases
from packets import collect, compare, optimal, PACKS, result
from pages import canonical, digest
from table_program import Program, Refused

LIVE_CASE='b5df48ae7f936c34a5e9f791259e0d92b4bafc95e667c89ae66bbd1448975908'
LIVE_CATALOGUE='abd222f672967e54f9fc7353f9c32d30b64694471110d77b8e4f9dacb9e96b5b'


def score(candidate,cases,catalogue,revision):
    policy=None
    reason=None
    if candidate:
        try:
            policy=Program(candidate['program'],revision)
        except (Refused,TypeError,KeyError) as error:
            reason=str(error)
    else:
        reason='NO_PROGRAM'
    rows=[compare(case,catalogue,policy,independent=True) for case in cases]
    valid=sum(x.get('candidate',{}).get('state')=='MATCHED' for x in rows)
    exact=sum(x.get('candidate',{}).get('bytes')==x['exact']['bytes'] for x in rows)
    return {'cases':len(cases),'valid':valid,'exact':exact,'error':reason,
            'verdict':'MATCHED_EXACT' if exact==len(cases) else 'REJECTED','results':rows}


def verify(data,observed):
    inputs=read(data/'commitments.json')
    commitments=inputs['commitments']
    catalogue=checked(data,'catalogue',commitments)
    state=observed['state']
    if state['authority']['input_sha256']!=digest(inputs) or state['state']!='COMPLETE':
        raise ValueError('EXPERIMENT_BINDING')
    calls=observed['calls']
    for label,event in state['completed'].items():
        call=calls[label]
        if (digest(call)!=event['run_sha256'] or call['model']!=state['authority']['model']
                or call['config_sha256']!=state['authority']['config_sha256']
                or call['result']!=event['result']):
            raise ValueError('CONSTRUCTOR_BINDING')
    objective=state['objective']
    selection=observed['selection']
    if digest(selection)!=state['authority']['selection_sha256'] or selection['result']['objective']!=objective:
        raise ValueError('OBJECTIVE_BINDING')
    first=state['completed']['construct']
    repaired=state['completed'].get('repair')
    expected=first['result']
    if repaired and repaired['result']:
        original=first['development']
        trial=repaired['development']
        if (trial['exact'],trial['valid'])>=(original['exact'],original['valid']):
            expected=repaired['result']
    if state['first']!=expected:
        raise ValueError('PRIMARY_LINEAGE')
    revision=state['authority'].get('compiler_revision',1)
    primary=score(state['first'],checked(data,f'{objective}-confirmation',commitments),catalogue,revision)
    scores={}
    next_=state['next']
    if next_:
        if state['completed']['choose-next']['result']['objective']!=next_ or next_==objective:
            raise ValueError('FRESH_OBJECTIVE_BINDING')
        new=checked(data,f'{next_}-confirmation',commitments)
        dev=checked(data,f'{next_}-development',commitments)
        retained=state['completed'].get('retain-rule',{}).get('result')
        try:
            learned=Program(retained['program'],revision) if retained else None
        except Refused:
            learned=None
        for label in ARMS:
            arm=state['completed'].get(label)
            if not arm:
                continue
            _,witness=select_cases(dev,catalogue,learned,label)
            if witness!=arm['selection']:
                raise ValueError('TRANSFER_SELECTION_BINDING')
            scores[label]={**score(arm['result'],new,catalogue,revision),'selection':witness}
    return {'schema':'frontier/activation-verification-v1','objective':objective,'primary':primary,
            'next':next_,'fresh':scores,'cohort_sha256':digest(inputs),'evidence_sha256':digest(observed)}


def qualified_replay(case,catalogue,which,path,parallel=1):
    # This command executes trusted, exact-source public software. Arbitrary
    # downloaded material, caller-supplied maps and model output do not qualify.
    if digest(case)!=LIVE_CASE or digest(catalogue)!=LIVE_CATALOGUE:
        raise ValueError('UNAUTHORIZED_REPLAY_CODE')
    begin,cpu=perf_counter_ns(),process_time_ns()
    chosen=optimal(case,catalogue) if which=='exact' else [case['archive']]
    receipt=collect(case,catalogue,chosen,path,parallel=parallel)
    with TemporaryDirectory() as temporary:
        root=Path(temporary)
        for name,sha in case['files'].items():
            target=root/name
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError('REPLAY_PATH')
            body=(path/sha).read_bytes()
            if sha256(body).hexdigest()!=sha:
                raise ValueError('RESTORED_BYTES')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(body)
        completed=subprocess.run((sys.executable,'check.py','verify','study/cohort','--training','study/training.json'),
                                 cwd=root,timeout=30,capture_output=True,check=True)
        import json
        reproduced=json.loads(completed.stdout)
        verdict=reproduced['forecast']
        control={'cases':reproduced['public_cases'],'model_sha256':reproduced['model_sha256'],
                 'verdict':verdict['verdict'],'reference':verdict['reference'],
                 'mae':verdict['comparisons']['trained']['mae_seconds']}
        if control!={'cases':56,'model_sha256':'7ba496e4a8d796a2633f227db931cb364982608aeb2407a16946560c9e20737f',
                     'verdict':'REJECTED','reference':'trailing-21','mae':89.0}:
            raise ValueError('REPLAY_RESULT_DRIFT')
    return {'method':which,'retrieval':receipt,'accepted_replay':control,
            'complete_wall_ns':perf_counter_ns()-begin,'coordinator_cpu_ns':process_time_ns()-cpu}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    verification=sub.add_parser('verify')
    verification.add_argument('data',type=Path)
    verification.add_argument('observed',type=Path)
    live=sub.add_parser('live')
    live.add_argument('data',type=Path)
    live.add_argument('case',type=Path)
    live.add_argument('workspace',type=Path)
    live.add_argument('--parallel',type=int,choices=(1,4,8),default=1)
    live.add_argument('--method',choices=('both','exact','full'),default='both')
    live.add_argument('--full-first',action='store_true')
    args=p.parse_args()
    if args.command=='verify':
        value=verify(args.data,read(args.observed))
    else:
        bindings=read(args.data/'commitments.json')['commitments']
        cat=checked(args.data,'catalogue',bindings)
        case=read(args.case)
        if case['archive']!='a:'+PACKS[3] or result(case,cat,[case['archive']])['state']!='MATCHED':
            raise ValueError('LIVE_SCOPE')
        order=('full','exact') if args.full_first else ('exact','full')
        methods=order if args.method=='both' else (args.method,)
        value=[qualified_replay(case,cat,way,args.workspace/way,args.parallel) for way in methods]
    print(canonical(value).decode())
