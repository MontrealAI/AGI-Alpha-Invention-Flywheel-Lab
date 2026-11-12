"""Distinct typed SQL/CSV service for prospective native qualification."""
import hashlib
from pathlib import Path
from commercial.ledger import digest,canonical
from commercial.persistence import atomic_bytes
from production060.service import safe_path,read_json
from enterprise078.service import source_paths as historical_paths
from enterprise078.transactional_admission.contract import request,accept

SCHEMA='enterprise078/sql-csv-native/v1'


def source_paths(root):
    return sorted(set(historical_paths(root)) | {p.relative_to(root).as_posix() for p in (Path(root)/'enterprise078').rglob('*.py')})


def hashes(root):
    return {p:hashlib.sha256(safe_path(root,p).read_bytes()).hexdigest() for p in source_paths(root)}


def manifest(root,ident,events):
    return {'schema':SCHEMA,'native_engine':'exact-prospective-v2','account_namespace':'adaptive012',
            'source_hashes':hashes(root),'jobs':[{'id':ident,'request':request(ident,events),'events':events,
            'delivery_path':'enterprise078/sql-deliveries/'+ident+'.json'}]}


def load_contracts(root,m):
    if (set(m)!= {'schema','native_engine','account_namespace','source_hashes','jobs'} or m['schema']!=SCHEMA
        or m['native_engine']!='exact-prospective-v2' or m['account_namespace']!='adaptive012'
        or m['source_hashes']!=hashes(root) or m['source_hashes']!=hashes(Path(__file__).resolve().parents[2])):
        raise ValueError('EXACT_SQL_NATIVE_SOURCE_MANIFEST_REQUIRED')
    jobs={};outputs=set()
    for row in m['jobs']:
        if (set(row)!={'id','request','events','delivery_path'} or row['request']!=request(row['id'],row['events'])
            or row['id'] in jobs or row['delivery_path'] in outputs
            or row['delivery_path']!='enterprise078/sql-deliveries/'+row['id']+'.json'):
            raise ValueError('DISTINCT_TYPED_SQL_REQUEST_REQUIRED')
        outputs.add(row['delivery_path']);safe_path(root,row['delivery_path'])
        job={'id':row['id'],'artifact_sha256':digest(row['request']),
             'receipt_sha256':m['source_hashes']['enterprise078/transactional_admission/contract.py']}
        jobs[row['id']]={'job':job,'artifact':{'precommitted_request':digest(row['request'])},'receipt':{}}
    if not jobs:raise ValueError('SQL_REQUEST_REQUIRED')
    return jobs


def bound(root,m,ident):
    if ident not in load_contracts(root,m):raise ValueError('UNKNOWN_SQL_REQUEST')
    return next(r for r in m['jobs'] if r['id']==ident)


def delivery(root,m,ident):
    return read_json(root,bound(root,m,ident)['delivery_path'])


def check_delivery(root,m,ident,artifact):
    row=bound(root,m,ident)
    if not isinstance(artifact,dict) or set(artifact)!={'database','csv','receipt'}:
        raise ValueError('EXACT_SQL_DELIVERY_REQUIRED')
    for key in ('database','csv'):
        if not artifact[key].startswith('enterprise078/sql-deliveries/'):
            raise ValueError('SQL_OUTPUT_NAMESPACE_REQUIRED')
    receipt=accept(row['request'],row['events'],safe_path(root,artifact['database']),safe_path(root,artifact['csv']))
    return {'accepted':receipt['accepted'] and receipt==artifact['receipt'], 'decisive':True,'scope':'SIMULATED',
            'authority':m['source_hashes']['enterprise078/transactional_admission/contract.py']}


def write_delivery(root,m,ident,db,csv):
    row=bound(root,m,ident)
    artifact={'database':db,'csv':csv,'receipt':accept(row['request'],row['events'],safe_path(root,db),safe_path(root,csv))}
    if not check_delivery(root,m,ident,artifact)['accepted']:raise ValueError('SQL_DELIVERY_REJECTED')
    path=safe_path(root,row['delivery_path']);path.parent.mkdir(parents=True,exist_ok=True)
    raw=canonical(artifact)
    if path.exists() and path.read_bytes()!=raw:raise ValueError('SQL_DELIVERY_CHANGED')
    if not path.exists():atomic_bytes(path,raw)
    return artifact


def rebind_prepared(root,m,actions,contracts=None):
    load_contracts(root,m);offers={}
    for action in actions:
        args=action['args']
        if action['op']=='offer':
            if args['id'] in offers:raise ValueError('DUPLICATE_SQL_OFFER')
            offers[args['id']]=args['job_id']
        elif action['op']=='event' and args['action']=='prepare':
            ident=offers[args['id']];artifact=delivery(root,m,ident)
            if digest(artifact)!=args['artifact_sha256'] or not check_delivery(root,m,ident,artifact)['accepted']:
                raise ValueError('SQL_PREPARED_BYTES_OR_ACCEPTANCE_CHANGED')
