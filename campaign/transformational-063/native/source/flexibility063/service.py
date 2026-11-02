"""Precommitted synthetic requests and independently checked native deliveries."""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from commercial.ledger import canonical,digest
from commercial.persistence import atomic_bytes
from production060.service import safe_path,read_json
from .verify import validate_request,verify

SCHEMA='flexibility063/native-services/v1'
SOURCES=('flexibility063/__init__.py','flexibility063/kernel.py','flexibility063/verify.py','flexibility063/service.py','flexibility063/native.py','flexibility063/experiment.py','flexibility063/REGISTRATION.json','flexibility063/profiles.json','connected_enterprise/transformational063.py','commercial/ledger.py','connected_enterprise/finance.py','production060/service.py','production060/acceptance.py','vendor/__init__.py','vendor/alpha_claim/__init__.py','commercial/__init__.py','connected_enterprise/__init__.py','adaptive_enterprise/__init__.py')


def source_paths(root):
    for name in SOURCES:
        if not safe_path(root,name).is_file(): raise ValueError('FLEXIBILITY063_SOURCE_MISSING:'+name)
    return list(SOURCES)


def _source_hashes(root):
    return {name:hashlib.sha256(safe_path(root,name).read_bytes()).hexdigest() for name in source_paths(root)}


def _validate_manifest(root,manifest):
    if not isinstance(manifest,dict) or set(manifest)!={'schema','native_engine','account_namespace','source_hashes','jobs'} or manifest['schema']!=SCHEMA or manifest['native_engine']!='exact-prospective-v2' or manifest['account_namespace']!='adaptive012' or not isinstance(manifest['jobs'],list) or not manifest['jobs']:
        raise ValueError('EXACT_FLEXIBILITY063_MANIFEST_REQUIRED')
    expected=_source_hashes(root)
    if manifest['source_hashes']!=expected: raise ValueError('FLEXIBILITY063_SOURCE_CLOSURE_CHANGED')
    executing=Path(__file__).resolve().parents[1]
    if _source_hashes(executing)!=expected: raise ValueError('FLEXIBILITY063_EXECUTING_SOURCE_CHANGED')


def _request(root,row):
    if not isinstance(row,dict) or set(row)!={'id','request','profile_path','profile_sha256','delivery_path'}: raise ValueError('EXACT_FLEXIBILITY063_JOB_REQUIRED')
    request=validate_request(row['request'])
    if row['id']!=request['id']: raise ValueError('FLEXIBILITY063_REQUEST_ID_CHANGED')
    profiles=read_json(root,row['profile_path'],row['profile_sha256'])
    if not isinstance(profiles,list) or len([p for p in profiles if isinstance(p,dict) and p.get('id')==row['id']])!=1 or request not in profiles:
        raise ValueError('FLEXIBILITY063_FROZEN_PROFILE_CHANGED')
    if not row['profile_path'].startswith('flexibility063/') or not row['delivery_path'].startswith('flexibility063/deliveries/') or row['delivery_path']==row['profile_path']:
        raise ValueError('FLEXIBILITY063_DECLARED_NAMESPACES_REQUIRED')
    safe_path(root,row['delivery_path'])
    return request


def prepare_manifest(root,requests,*,native_engine='exact-prospective-v2'):
    rows=[]
    for row in requests:
        if not isinstance(row,dict) or set(row)-{'profile_path'}!={'id','delivery_path'}: raise ValueError('FLEXIBILITY063_REQUEST_DESCRIPTION_REQUIRED')
        path=row.get('profile_path','flexibility063/profiles.json')
        profiles=read_json(root,path)
        matches=[p for p in profiles if p['id']==row['id']]
        if len(matches)!=1: raise ValueError('FLEXIBILITY063_UNIQUE_PROFILE_REQUIRED')
        rows.append({'id':row['id'],'request':matches[0],'profile_path':path,'profile_sha256':hashlib.sha256(safe_path(root,path).read_bytes()).hexdigest(),'delivery_path':row['delivery_path']})
    manifest={'schema':SCHEMA,'native_engine':native_engine,'account_namespace':'adaptive012','source_hashes':_source_hashes(root),'jobs':rows}
    load_contracts(root,manifest)
    return manifest


def load_contracts(root,manifest):
    _validate_manifest(root,manifest)
    jobs={};outputs=set();checker=manifest['source_hashes']['flexibility063/verify.py']
    for row in manifest['jobs']:
        request=_request(root,row)
        if row['id'] in jobs or row['delivery_path'] in outputs: raise ValueError('FLEXIBILITY063_UNIQUE_REQUEST_AND_OUTPUT_REQUIRED')
        outputs.add(row['delivery_path'])
        job={'id':row['id'],'artifact_sha256':digest(request),'receipt_sha256':checker,'request':copy.deepcopy(request),'delivery_path':row['delivery_path']}
        jobs[row['id']]={'job':job,'artifact':{'precommitted_request':digest(request)},'receipt':{'checker_sha256':checker}}
    return jobs


def _bound_request(root,manifest,job_id):
    contracts=load_contracts(root,manifest)
    if job_id not in contracts: raise ValueError('FLEXIBILITY063_UNKNOWN_REQUEST')
    row=next(r for r in manifest['jobs'] if r['id']==job_id)
    return row,_request(root,row)


def has_request(root,manifest,job_id):
    _bound_request(root,manifest,job_id)
    return True


def delivery(root,manifest,job_id):
    row,_=_bound_request(root,manifest,job_id)
    return read_json(root,row['delivery_path'])


def verify_delivery(root,manifest,job_id,artifact):
    _,request=_bound_request(root,manifest,job_id)
    result=verify(request,artifact)
    result.update(request_sha256=digest(request),artifact_sha256=digest(artifact),checker_sha256=manifest['source_hashes']['flexibility063/verify.py'])
    return result


def check_delivery(root,manifest,job_id,artifact):
    result=verify_delivery(root,manifest,job_id,artifact)
    return {'accepted':result['accepted'],'decisive':True,'scope':'SIMULATED','authority':result['checker_sha256']}


def write_delivery(root,manifest,job_id,artifact,*,replace_unprepared=False):
    row,_=_bound_request(root,manifest,job_id)
    path=safe_path(root,row['delivery_path']);data=canonical(artifact)
    if len(data)>2_000_000: raise ValueError('FLEXIBILITY063_BOUNDED_DELIVERY_REQUIRED')
    if path.exists() and path.read_bytes()!=data and not replace_unprepared: raise ValueError('FLEXIBILITY063_EXISTING_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_bytes()!=data: atomic_bytes(path,data)
    return verify_delivery(root,manifest,job_id,artifact)


def rebind_prepared(root,manifest,actions,contracts=None):
    contracts=load_contracts(root,manifest) if contracts is None else contracts
    offers={}
    for action in actions:
        args=action['args']
        if action['op']=='offer':
            if args['id'] in offers: raise ValueError('FLEXIBILITY063_UNIQUE_PREPARED_ORDER_REQUIRED')
            offers[args['id']]=args['job_id']
        elif action['op']=='event' and args['action']=='prepare':
            job_id=offers.get(args['id'])
            if job_id not in contracts: raise ValueError('FLEXIBILITY063_PREPARED_REQUEST_MISSING')
            artifact=delivery(root,manifest,job_id)
            if digest(artifact)!=args.get('artifact_sha256'): raise ValueError('FLEXIBILITY063_ACTUAL_DELIVERY_HASH_CHANGED')
            if not check_delivery(root,manifest,job_id,artifact)['accepted']: raise ValueError('FLEXIBILITY063_PREPARED_ACCEPTANCE_CHANGED')
