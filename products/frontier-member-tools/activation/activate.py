"""Run the permitted bottleneck investigation, resume it, and export the lineage."""

import argparse
import json
from pathlib import Path
import signal
import sys
from time import time

from bridge.output_schema import prepare_schema, validate_output
from model_step import Constructor, object_schema, brief, step
from packets import compare, project
from pages import canonical, digest
from study import atomic, lock
from table_program import Program, Refused

FAMILIES=('learning-replay','local-runner','inventor-audit')
ARMS=('original','ordinary','augmented','withdrawn')
SCHEMA='frontier/activation-run-v1'
PROGRAM=object_schema({'hypothesis':brief(160),'program':brief(1600)})


def read(path):
    with path.open('rb') as stream:
        blob=stream.read(2_000_001)
    if len(blob)>2_000_000:
        raise ValueError('FILE_SIZE')
    return json.loads(blob)


def checked(data,name,commitments):
    value=read(data/f'{name}.json')
    if digest(value)!=commitments[name]:
        raise ValueError('DATA_COMMITMENT')
    return value


def reject_invalid(value,keys):
    if type(value) is not dict or set(value)!=set(keys):
        raise ValueError('RESPONSE_SHAPE')
    return value


def select_objective(root,source,config,model,until):
    if source.get('schema')!='frontier/bottleneck-map-v1' or len(source.get('observations',()))>16:
        raise ValueError('BOTTLENECK_MAP')
    references=[x['id'] for x in source['observations']]
    if not references or len(set(references))!=len(references):
        raise ValueError('BOTTLENECK_REFERENCES')
    options=[*FAMILIES,'abstain']
    schema=object_schema({'objective':{'enum':options},'diagnosis':brief(200),'alternatives':brief(180),'falsifier':brief(160),
                          'evidence':{'type':'array','minItems':1,'maxItems':4,'items':{'enum':references}}})
    prompt=('You are the researcher activated on FRONTIER Ω own invention limits. Interpret these actual failed and qualified results. '
            'Choose the most consequential permitted investigation for MONTREAL.AI and explain the shared bottleneck, '
            'alternative explanations, and a falsifying result. Abstain if none merit experimentation. Return only JSON.\n'
            +canonical({k:source[k] for k in ('observations','objectives','resources')}).decode())

    def validate(value):
        valid=reject_invalid(value,schema['required'])
        if valid['objective'] not in options or not valid['evidence'] or any(x not in references for x in valid['evidence']):
            raise ValueError('BINDING_OF_RESEARCH_CHOICE')
        return valid

    return step(root/'selection',config,model,schema,prompt,'bottleneck-selection',384,validate=validate,deadline=until)


def sample(case,catalog):
    full,rows=project(case,catalog)
    return {'id':case['id'],'requests':case['cap'],'need':full.bit_count(),
            'sources':[[mask.bit_count(),size,mask,int(kit)] for _,mask,size,kit in rows]}


def summarize(reports):
    valid=0
    exact=0
    rows=[]
    for report in reports:
        result=report.get('candidate',{})
        good=result.get('state')=='MATCHED'
        valid+=good
        exact+=good and result['bytes']==report['exact'].get('bytes')
        rows.append({'id':report['case'],'result':result.get('state','ABSTAIN'),
                     'reason':result.get('reason'),'planned_body_bytes':result.get('bytes'),
                     'exact_body_bytes':report['exact'].get('bytes')})
    return {'cases':len(reports),'valid':valid,'exact':exact,'rows':rows}


def assess(candidate,cases,catalog):
    if candidate is None:
        return None,{'error':'NO_PROGRAM','cases':len(cases),'valid':0,'exact':0}
    try:
        policy=Program(candidate['program'])
    except (Refused,TypeError,KeyError) as error:
        return None,{'error':str(error),'cases':len(cases),'valid':0,'exact':0}
    reports=[compare(case,catalog,policy) for case in cases]
    return policy,summarize(reports)


def cover_order(cases):
    order=[min(cases,key=lambda c:(c['cap'],c['id'])),max(cases,key=lambda c:(len(c['required']),c['id'])),
           min(cases,key=lambda c:(c['required_bytes'],c['id']))]
    return list(dict.fromkeys(c['id'] for c in [*order,*cases]))


def select_cases(cases,catalog,policy,arm):
    look={c['id']:c for c in cases}
    first=cover_order(cases)
    ranked=first.copy()
    active=arm=='augmented' and policy is not None
    error=None
    if arm=='ordinary':
        ranked=sorted(first,key=lambda k:(look[k]['required_bytes'],first.index(k)),reverse=True)
    if active:
        try:
            remaining=first.copy()
            ranked=[]
            while remaining and len(ranked)<3:
                table=[]
                for k in remaining:
                    c=look[k]
                    expected=compare(c,catalog)['exact']
                    table.append((len(c['required']),c['required_bytes'],c['cap'],expected['reads'],
                                  expected['bytes'],catalog[c['archive']]['bytes']))
                index=policy(table,3-len(ranked))
                if type(index) is not int or not 0<=index<len(remaining):
                    raise Refused('RANK_OUTPUT')
                ranked.append(remaining.pop(index))
        except Refused as exc:
            ranked,error=first,str(exc)
    chosen=ranked[:3]
    return [look[k] for k in chosen],{'coverage':first[:3],'chosen':chosen,'executed':active,
                                     'changed':set(chosen)!=set(first[:3]),'error':error}


def construct_prompt(examples,catalog,prior=None,feedback=None):
    return ('Design an evidence acquisition policy for an independent verifier. Goal: recover every required exact '
            'file within the request budget and transfer minimal bytes. Choose an available source at each step. '
            'Propose your own strategy, considering overlapping sources and scarce requests. '
            'Return JSON with hypothesis and program. Program is a bounded Python-shaped function def choose(n, r): '
            'with n rows and r requests left, returning a row index. Use integer locals, if, return, break, continue, and '
            'for i in range(n). v(i,j) reads cell j in row i. Columns: 0 newly covered count, 1 bytes, '
            '2 new coverage bitmask, 3 total still missing, 4 archive flag, 5 full missing bitmask. pop(x) counts bits. '
            'Some cases cannot finish from individual files within their request cap. Keep every necessary source kind eligible. '
            'Integer arithmetic and comparisons are supported. No imports, comprehensions, objects, or arbitrary calls. '
            'Example syntax only: def choose(n, r): followed by an indented return 0. Make the code concise.\n'
            +canonical({'development':[sample(c,catalog) for c in examples], 'prior':prior,'feedback':feedback}).decode())


def write(root,record):
    atomic(root/'activation-status.json',record)


def run(args):
    root=args.workspace
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    data=args.data
    inputs=read(data/'commitments.json')
    commitments=inputs['commitments']
    catalogue=checked(data,'catalogue',commitments)
    if bool(args.selection)==bool(args.inventory):
        raise ValueError('SELECT_ONE_SCOPE_INPUT')
    if args.inventory:
        selection=select_objective(root,read(args.inventory),args.config,args.model,args.until)
        atomic(root/'choice.json',selection)
    else:
        selection=read(args.selection)
    initial=selection.get('result') or {}
    objective=initial.get('objective')
    if objective not in FAMILIES or selection.get('status')!='SEALED':
        raise ValueError('NO_AUTHORIZED_OBJECTIVE')
    config=Constructor(args.config,args.model,PROGRAM)
    if config.provider.models[args.model].max_output_tokens<512:
        raise ValueError('MODEL_BUDGET')
    authority={'scope':'public-readonly-research','model':args.model,'config_sha256':config.config_sha256,
               'input_sha256':digest(inputs),'selection_sha256':digest(selection),'lease_until':args.until,
               'request_limit':18,'paid_budget':0,'compiler_revision':2}
    chosen=checked(data,f'{objective}-development',commitments)
    with lock(root):
        path=root/'activation-status.json'
        if path.exists():
            state=read(path)
            if state.get('authority')!=authority:
                raise ValueError('AUTHORITY_DRIFT')
            if state['state']!='COMPLETE':
                state['resumes']+=1
        else:
            state={'schema':SCHEMA,'authority':authority,'objective':objective,'state':'ACTIVE','resumes':0,
                   'journal':[],'completed':{},'next':None}
        write(root,state)
        if state['state']=='COMPLETE':
            return state

        def dispatch(label,prompt,schema=PROGRAM):
            if label in state['completed']:
                previous=state['completed'][label]
                if previous['status']=='SEALED':
                    validate_output(previous['result'],prepare_schema(schema))
                return previous
            if int(time())>=args.until:
                raise ValueError('LEASE_EXPIRED')
            state['current']=label
            write(root,state)
            actual=step(root/'calls'/label,args.config,args.model,schema,prompt,label,512,attempts=2,
                        validate=lambda value:reject_invalid(value,schema['required']),deadline=args.until,
                        expected_config=authority['config_sha256'])
            record={'status':actual['status'],'result':actual['result'],'run_sha256':digest(actual)}
            return record

        def settle(label,record,**details):
            if label in state['completed']:
                return
            state['completed'][label]={**record,**details}
            state['journal'].append({'stage':label,'state':record['status'],'time':int(time())})
            write(root,state)

        pick=select_cases(chosen,catalogue,None,'original')[0]
        start=dispatch('construct',construct_prompt(pick,catalogue))
        _,observed=assess(start['result'],chosen,catalogue)
        settle('construct',start,development=observed)
        decision_schema=object_schema({'action':{'enum':['repair','transfer','stop']},'reason':brief(180),
                                       'alternative':brief(160)})
        guide=('Review this observed development result from a genuine evidence recovery objective. '
               'Select the next authorized action: repair the program after a failure; transfer what was learned '
               'to a new task only if there is useful evidence; or stop. Include a concrete reason and discarded alternative. '
               'Return only JSON.\n'+canonical(observed).decode())
        next_=dispatch('decide',guide,decision_schema)
        settle('decide',next_)
        intention=(next_['result'] or {}).get('action','stop')
        primary=start['result']
        if intention=='repair':
            repair=dispatch('repair',construct_prompt(pick,catalogue,primary,observed))
            _,repaired=assess(repair['result'],chosen,catalogue)
            settle('repair',repair,development=repaired)
            if (repaired['exact'],repaired['valid'])>=(observed['exact'],observed['valid']) and repair['result'] is not None:
                primary=repair['result']
        state['first']=primary
        write(root,state)
        if intention in ('repair','transfer') and primary:
            rule_prompt=('Create a transferable development-case selector for the inventor. Return JSON with hypothesis and program. '
                         'Use bounded def choose(n, r): with integer locals, for i in range(n), if, return, and v(i,j). '
                         'Choose an index for each remaining slot. Columns are required count, required bytes, request cap, '
                         'exact control reads, exact control bytes, full-companion bytes. Consider failure modes that truly '
                         'inform a new implementation.\n'+canonical({'observed':observed,'first':primary}).decode())
            method=dispatch('retain-rule',rule_prompt)
            try:
                policy=Program(method['result']['program']) if method['result'] else None
            except Refused:
                policy=None
            settle('retain-rule',method,executable=policy is not None)
            next_schema=object_schema({'objective':{'enum':[x for x in FAMILIES if x!=objective]},'reason':brief(160)})
            subsequent=dispatch('choose-next','Choose the next fresh task for the same evidence-acquisition research. '
                                'Use these genuinely observed first-task findings and return only JSON.\n'+canonical(observed).decode(),next_schema)
            settle('choose-next',subsequent)
            name=(subsequent['result'] or {}).get('objective')
            if name in FAMILIES and name!=objective:
                state['next']=name
                trial=checked(data,f'{name}-development',commitments)
                for arm in ARMS if policy is not None else ('original',):
                    examples,picks=select_cases(trial,catalogue,policy,arm)
                    prior=None if arm=='original' else {'first':primary,'retained':method['result']}
                    made=dispatch(arm,construct_prompt(examples,catalogue,prior))
                    _,metrics=assess(made['result'],trial,catalogue)
                    settle(arm,made,selection=picks,development=metrics)
        state['state']='COMPLETE'
        state['current']=None
        write(root,state)
        return state


def interrupted(_signum,_frame):
    raise KeyboardInterrupt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for field in ('workspace','data','config'):
        p.add_argument('--'+field,type=Path,required=True)
    p.add_argument('--selection',type=Path)
    p.add_argument('--inventory',type=Path)
    p.add_argument('--model',required=True)
    p.add_argument('--until',type=int,required=True)
    signal.signal(signal.SIGTERM,interrupted)
    try:
        print(canonical(run(p.parse_args())).decode())
    except KeyboardInterrupt:
        print('Paused. Resume with the same lease and source commitments.',file=sys.stderr)
        sys.exit(130)
