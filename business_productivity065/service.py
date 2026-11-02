"""Two precommitted inventory requests over the canonical funded account.

No finance or producer logic. Original public demand and a named 20% demand
scenario are distinct; neither represents an observed second customer.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from production060.service import safe_path
from inventory061.independent_acceptance import SOURCE_SHA256
from .acceptance import verify, check_additional_quality95

SCHEMA = 'business-productivity065/native-services/v1'


def source_paths(root):
    root = Path(root)
    paths = ['commercial/ledger.py', 'connected_enterprise/finance.py',
             'production060/service.py', 'production060/acceptance.py',
             'inventory061/constructor.py', 'inventory061/quality_constructor.py',
             'inventory061/independent_acceptance.py', 'inventory061/QUALITY_CONTRACT_V2.json',
             'inventory061/LICENSE-OR-License.txt']
    paths += ['inventory061/inputs/' + name for name in SOURCE_SHA256]
    paths += [p.relative_to(root).as_posix() for p in (root/'business_productivity065').glob('*.py')]
    paths += [p.relative_to(root).as_posix() for p in (root/'business_productivity065').glob('*.json')]
    return sorted(set(paths))


def hashes(root):
    return {p: hashlib.sha256(safe_path(root,p).read_bytes()).hexdigest() for p in source_paths(root)}


def read(root, relative, expected=None):
    raw = safe_path(root,relative).read_bytes()
    if len(raw)>2_000_000 or (expected is not None and hashlib.sha256(raw).hexdigest()!=expected):
        raise ValueError('PRODUCTIVITY065_BOUND_BYTES_CHANGED:'+relative)
    return strict_json(raw)


def scenario_instance(root, scenario):
    original = read(root,'inventory061/inputs/01.json',SOURCE_SHA256['01.json'])
    if scenario == 'original':
        return original
    if scenario != 'demand_plus20pct_ceil':
        raise ValueError('PRODUCTIVITY065_REGISTERED_SCENARIO_REQUIRED')
    for products in original['demand'].values():
        for product, values in products.items():
            products[product] = [(6*x+4)//5 for x in values]
    return original


def prepare_manifest(root, requests):
    rows=[]
    for row in requests:
        if set(row)!={'id','instance_path','delivery_path','scenario'}:
            raise ValueError('PRODUCTIVITY065_EXACT_REQUEST_DESCRIPTION_REQUIRED')
        instance=read(root,row['instance_path'])
        if instance!=scenario_instance(root,row['scenario']):
            raise ValueError('PRODUCTIVITY065_SCENARIO_BYTES_MISMATCH')
        request={k:row[k] for k in ('id','instance_path','scenario')}
        request.update(instance_sha256=hashlib.sha256(safe_path(root,row['instance_path']).read_bytes()).hexdigest(),
                       input_canonical_sha256=digest(instance),quality='each48_joint_successes_at_least347_of365')
        rows.append({'id':row['id'],'request':request,'delivery_path':row['delivery_path']})
    manifest={'schema':SCHEMA,'native_engine':'exact-prospective-v2','account_namespace':'adaptive012',
              'source_hashes':hashes(root),'jobs':rows}
    load_contracts(root,manifest)
    return manifest


def load_contracts(root,manifest):
    if (not isinstance(manifest,dict) or set(manifest)!={'schema','native_engine','account_namespace','source_hashes','jobs'}
        or manifest['schema']!=SCHEMA or manifest['native_engine']!='exact-prospective-v2'
        or manifest['account_namespace']!='adaptive012' or not isinstance(manifest['jobs'],list) or not manifest['jobs']):
        raise ValueError('PRODUCTIVITY065_EXACT_MANIFEST_REQUIRED')
    expected=hashes(root)
    if manifest['source_hashes']!=expected or hashes(Path(__file__).resolve().parents[1])!=expected:
        raise ValueError('PRODUCTIVITY065_SOURCE_CLOSURE_CHANGED')
    jobs={}; outputs=set(); scenarios=set()
    for row in manifest['jobs']:
        if not isinstance(row,dict) or set(row)!={'id','request','delivery_path'}:
            raise ValueError('PRODUCTIVITY065_EXACT_JOB_REQUIRED')
        req=row['request']
        if (not isinstance(req,dict) or set(req)!={'id','instance_path','scenario','instance_sha256','input_canonical_sha256','quality'}
            or row['id']!=req['id'] or not isinstance(row['id'],str) or not row['id'] or len(row['id'])>160
            or req['quality']!='each48_joint_successes_at_least347_of365'):
            raise ValueError('PRODUCTIVITY065_EXACT_REQUEST_REQUIRED')
        instance=read(root,req['instance_path'],req['instance_sha256'])
        if digest(instance)!=req['input_canonical_sha256'] or instance!=scenario_instance(root,req['scenario']):
            raise ValueError('PRODUCTIVITY065_BOUND_SCENARIO_CHANGED')
        path=row['delivery_path']; safe_path(root,path)
        if not path.startswith('business_productivity065/deliveries/') or not path.endswith('.json'):
            raise ValueError('PRODUCTIVITY065_DELIVERY_NAMESPACE_REQUIRED')
        if row['id'] in jobs or path in outputs or req['scenario'] in scenarios:
            raise ValueError('PRODUCTIVITY065_UNIQUE_JOB_DELIVERY_SCENARIO_REQUIRED')
        outputs.add(path); scenarios.add(req['scenario'])
        checker=expected['business_productivity065/acceptance.py']
        job={'id':row['id'],'artifact_sha256':digest(req),'receipt_sha256':checker,
             'request':copy.deepcopy(req),'delivery_path':path}
        jobs[row['id']]={'job':job,'artifact':{'precommitted_request':digest(req)},'receipt':{'checker_sha256':checker}}
    return jobs


def has_request(root,manifest,job_id):
    if job_id not in load_contracts(root,manifest):
        raise ValueError('PRODUCTIVITY065_UNKNOWN_REQUEST')
    return True


def delivery(root,manifest,job_id):
    return read(root,load_contracts(root,manifest)[job_id]['job']['delivery_path'])


def verify_delivery(root,manifest,job_id,artifact):
    job=load_contracts(root,manifest)[job_id]['job']; req=job['request']
    instance=read(root,req['instance_path'],req['instance_sha256'])
    result=verify(instance,artifact,expected_input_sha256=req['input_canonical_sha256'])
    result['additional_quality95']=check_additional_quality95(result)
    result['accepted']=result['accepted'] and result['additional_quality95']['accepted']
    if not result['accepted'] and not result['errors']:
        result['errors'].append('PRODUCTIVITY065_QUALITY95_FAILED')
    result.update(artifact_sha256=digest(artifact),request_sha256=digest(req),checker_sha256=job['receipt_sha256'],scenario=req['scenario'])
    return result


def check_delivery(root,manifest,job_id,artifact):
    result=verify_delivery(root,manifest,job_id,artifact)
    return {'accepted':result['accepted'],'decisive':True,'scope':'SIMULATED','authority':result['checker_sha256']}


def write_delivery(root,manifest,job_id,artifact):
    result=verify_delivery(root,manifest,job_id,artifact)
    if not result['accepted']:return result
    path=safe_path(root,load_contracts(root,manifest)[job_id]['job']['delivery_path']); raw=canonical(artifact)
    if len(raw)>2_000_000:raise ValueError('PRODUCTIVITY065_BOUNDED_DELIVERY_REQUIRED')
    if path.exists() and strict_json(path.read_bytes())!=artifact:raise ValueError('PRODUCTIVITY065_EXISTING_DELIVERY_CHANGED')
    path.parent.mkdir(parents=True,exist_ok=True); atomic_bytes(path,raw)
    return result


def rebind_prepared(root,manifest,actions,contracts=None):
    jobs=load_contracts(root,manifest) if contracts is None else contracts; offers={}
    for action in actions:
        args=action['args']
        if action['op']=='offer':
            if args['id'] in offers:raise ValueError('PRODUCTIVITY065_UNIQUE_ORDER_REQUIRED')
            offers[args['id']]=args['job_id']
        elif action['op']=='event' and args['action']=='prepare':
            job_id=offers.get(args['id'])
            if job_id not in jobs:raise ValueError('PRODUCTIVITY065_PREPARED_REQUEST_MISSING')
            artifact=read(root,jobs[job_id]['job']['delivery_path'])
            if digest(artifact)!=args.get('artifact_sha256'):raise ValueError('PRODUCTIVITY065_ACTUAL_DELIVERY_HASH_CHANGED')
