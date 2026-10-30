"""Report-only conversion counts from archived, immutable confirmation decisions."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def ratio(n,d):return n/d if d else None

def summarize(runs):
    totals={k:sum(r[k] for r in runs) for k in ['scheduled_slots','arrivals','participation_wins','technical_acceptances','settled_collections','quality_accepted_production_slots']}
    n,a,w,q,c=(totals[k] for k in ['scheduled_slots','arrivals','participation_wins','technical_acceptances','settled_collections'])
    return {'runs':len(runs),**totals,'opportunity_arrival':ratio(a,n),'conditional_wins_per_arrival':ratio(w,a),'technical_acceptances_per_win':ratio(q,w),'collections_per_technical_acceptance':ratio(c,q),'collections_per_win':ratio(c,w),'settled_per_slot':ratio(c,n),'zero_denominator_policy':'null means undefined, never inferred zero'}


def run(source_root,output):
    source_root=Path(source_root);policy=json.loads((ROOT/'campaign/commercial-010/POLICY.json').read_text());result=json.loads((ROOT/'campaign/commercial-010/RESULT.json').read_text())
    index_path=ROOT/'evidence/commercial010/raw-parts/INDEX.json';index=json.loads(index_path.read_text());members={x['path']:x for x in index['entries'] if x['kind']=='file'}
    files=sorted((source_root/'artifacts/confirmation').glob('*/*/*/RESULT.json'))
    expected={(a['id'],w['id'],seed) for a in policy['arms'] for w in policy['worlds'] for seed in policy['confirmation_seeds']}
    rows=[];seen=set()
    for path in files:
        raw=path.read_bytes();r=json.loads(raw);key=(r['arm']['id'],r['world'],r['seed'])
        if key not in expected or key in seen:raise ValueError('CONFIRMATION_IDENTITY_OR_DUPLICATE')
        seen.add(key);member='resumed/'+path.relative_to(source_root).as_posix();digest=hashlib.sha256(raw).hexdigest()
        if member not in members or members[member]['sha256']!=digest:raise ValueError('ARCHIVED_RAW_RESULT_IDENTITY')
        decisions=[d for cycle in r['cycles'] for d in cycle['decisions']]
        n=sum(len(cycle['jobs']) for cycle in r['cycles'])
        if len(decisions)!=n or any(type(d['arrival']) is not bool or type(d['participates']) is not bool or (d['participates'] and not d['arrival']) for d in decisions):raise ValueError('DECISION_PARTITION')
        wins=sum(d['participates'] for d in decisions);arrivals=sum(d['arrival'] for d in decisions)
        quality=sum(receipt['fresh_checker_receipt']['accepted'] is True for cycle in r['cycles'] for receipt in cycle['actual_post_commitment_work'])
        native_prepares=sum(e['op']=='event' and e['args']['action']=='prepare' for e in r['ledger']['actions'])
        paid=sum(o['state']=='released' for o in r['ledger']['orders'])
        outcome_paid=sum(d.get('outcome')=='SIMULATED_COLLECTED' for d in decisions)
        if wins!=len(r['ledger']['orders']) or native_prepares!=wins or paid!=outcome_paid or paid!=r['paid_jobs'] or quality!=n or not 0<=paid<=native_prepares<=wins<=arrivals<=n:raise ValueError('NATIVE_AND_DECISION_COUNTS_DISAGREE')
        rows.append({'arm':key[0],'world':key[1],'seed':key[2],'archive_member':member,'raw_result_sha256':digest,'scheduled_slots':n,'arrivals':arrivals,'participation_wins':wins,'technical_acceptances':native_prepares,'settled_collections':paid,'quality_accepted_production_slots':quality})
    if seen!=expected:raise ValueError('ALL_168_FROZEN_CONFIRMATION_RUNS_REQUIRED')
    region={w['id'] for w in policy['worlds'] if w['qualification_region']};arms={}
    for arm in policy['arms']:
        matching=[x for x in rows if x['arm']==arm['id']]
        worlds={w['id']:summarize([x for x in matching if x['world']==w['id']]) for w in policy['worlds']}
        regional=summarize([x for x in matching if x['world'] in region])
        for name,value in [(None,regional),*worlds.items()]:
            old=result['arms'][arm['id']]['qualification_region' if name is None else 'worlds']
            if name is not None:old=old[name]
            if abs((value['settled_per_slot'] or 0)-old['win_probability'])>1e-12:raise ValueError('LEGACY_SETTLED_CONVERSION_MISMATCH')
        arms[arm['id']]={'all_worlds':summarize(matching),'qualification_region':regional,'worlds':worlds}
    report={'schema':'agi-alpha/commercial010-conversion-report/v1','scope':'REPORTING_ONLY_OVER_SIMULATED_IMMUTABLE_CONFIRMATION','financial_results_unchanged':True,'legacy_field':'win_probability','legacy_definition':'settled_collections / scheduled_slots over actually executed cycles; not conditional on arrival and not the participation-win probability','source_index_sha256':hashlib.sha256(index_path.read_bytes()).hexdigest(),'source_result_sha256':hashlib.sha256((ROOT/'campaign/commercial-010/RESULT.json').read_bytes()).hexdigest(),'arms':arms,'runs':rows,'actual_customer_measurement':False}
    Path(output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v['qualification_region'] for k,v in arms.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.source_root,a.output)
