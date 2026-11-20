"""Content-addressed dynamic contracts for the canonical SIMULATED native account.

Appending a request does not change the immutable manifest or grant spending.
Each order binds its request hash and host checker; actual deliveries bind late.
"""
from collections.abc import Mapping
from pathlib import Path
from .core import canonical, child, contract, digest, filehash, identifier, immutable, read
from .checker import verify

SCHEMA='alpha-economic/native-services/v1'
ROOT=Path(__file__).resolve().parents[2]


def source_paths(root):
    root=Path(root)
    paths=[str(p.relative_to(root)) for p in (root/'connected_enterprise/alpha_economic').glob('*.py')]
    paths += [str(p.relative_to(root)) for p in (root/'products/alpha-genesis-harness/bridge').glob('*.py')]
    return sorted(set(paths+['commercial/ledger.py','connected_enterprise/finance.py']))


def source_hashes(root): return {p:filehash(child(root,p)) for p in source_paths(root)}


def prepare_manifest(root):
    return {'schema':SCHEMA,'native_engine':'exact-prospective-v2','account_namespace':'adaptive012',
            'source_hashes':source_hashes(root),'store':'alpha-economic-data'}


def validate_manifest(root,m):
    if not isinstance(m,dict) or set(m)!={'schema','native_engine','account_namespace','source_hashes','store'} or m['schema']!=SCHEMA or m['native_engine']!='exact-prospective-v2' or m['account_namespace']!='adaptive012' or m['store']!='alpha-economic-data':
        raise ValueError('EXACT_DYNAMIC_ECONOMIC_MANIFEST_REQUIRED')
    if source_hashes(root)!=m['source_hashes'] or source_hashes(ROOT)!=m['source_hashes']:
        raise ValueError('ECONOMIC_EXECUTION_SOURCE_CHANGED')


def request_path(root,m,job):
    if not isinstance(job,str) or len(job)!=66 or not job.startswith('a-') or any(x not in '0123456789abcdef' for x in job[2:]):
        raise ValueError('CONTENT_ADDRESSED_JOB_ID_REQUIRED')
    return child(root,m['store']+'/requests/'+job+'.json')


def request(root,m,job):
    c=contract(read(request_path(root,m,job)))
    if identifier(c)!=job: raise ValueError('REQUEST_CONTENT_ADDRESS_CHANGED')
    return c


class BoundJobs(Mapping):
    def __init__(self,root,m): self.root,self.manifest=Path(root),m
    def __iter__(self):
        folder=child(self.root,self.manifest['store']+'/requests')
        return iter(sorted(p.stem for p in folder.glob('a-*.json')))
    def __len__(self): return sum(1 for _ in self)
    def __getitem__(self,job):
        try: c=request(self.root,self.manifest,job)
        except FileNotFoundError: raise KeyError(job) from None
        check_hash=self.manifest['source_hashes']['connected_enterprise/alpha_economic/checker.py']
        row={'id':job,'artifact_sha256':digest(c),'receipt_sha256':check_hash,'request':c}
        return {'job':row,'artifact':{'precommitted_request':digest(c)},'receipt':{'checker_sha256':check_hash}}


def load_contracts(root,m):
    validate_manifest(root,m)
    return BoundJobs(root,m)


def admit(root,m,c):
    validate_manifest(root,m); job=identifier(c)
    immutable(request_path(root,m,job),c)
    return job


def delivery(root,m,job):
    request(root,m,job)
    return read(child(root,m['store']+'/deliveries/'+job+'.json'))


def check_delivery(root,m,job,artifact):
    c=request(root,m,job); checked=verify(c,artifact)
    return {'accepted':checked['accepted'],'decisive':True,'scope':'SIMULATED',
            'authority':m['source_hashes']['connected_enterprise/alpha_economic/checker.py']}


def write_delivery(root,m,job,artifact):
    result=verify(request(root,m,job),artifact)
    if not result['accepted']: return result
    immutable(child(root,m['store']+'/deliveries/'+job+'.json'),artifact)
    return result


def rebind_prepared(root,m,actions,contracts=None):
    jobs=load_contracts(root,m); offers={}
    for event in actions:
        args=event['args']
        if event['op']=='offer':
            if args['id'] in offers: raise ValueError('DUPLICATE_ORDER')
            if args['job_id'] not in jobs: raise ValueError('MISSING_BOUND_REQUEST')
            offers[args['id']]=args['job_id']
        elif event['op']=='event' and args['action']=='prepare':
            job=offers[args['id']]; artifact=delivery(root,m,job)
            if digest(artifact)!=args.get('artifact_sha256') or not check_delivery(root,m,job,artifact)['accepted']:
                raise ValueError('HISTORICAL_ACCEPTED_DELIVERY_CHANGED')
