"""Source-bound admission for the optional material054 service, using native finance."""
from pathlib import Path
import hashlib
from commercial.ledger import canonical, strict_json, digest
from .material_verify054 import audit_plan, audit_transfer

SCHEMA='agi-alpha/material054-services/v1'
SOURCES=('connected_enterprise/material054.py','connected_enterprise/material_verify054.py',
         'connected_enterprise/material_service054.py','connected_enterprise/material_cycle054.py',
         'connected_enterprise/finance.py','commercial/ledger.py')


def bound(root,path,expected):
    relative=Path(path)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('RELATIVE_MATERIAL_EVIDENCE_REQUIRED')
    full=Path(root)/relative
    if full.is_symlink() or any(p.is_symlink() for p in full.parents):
        raise ValueError('MATERIAL_SYMLINK_REFUSED')
    raw=full.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('MATERIAL_EVIDENCE_CHANGED')
    return raw


def validate_manifest(root, manifest):
    if set(manifest)!={'schema','scope','currency','account_namespace','native_engine','source_hashes','jobs'} or manifest['schema']!=SCHEMA or manifest['scope']!='SYNTHETIC_PUBLIC_WORKLOAD' or manifest['currency']!='USD' or manifest['account_namespace']!='adaptive012' or manifest['native_engine']!='exact-prospective-v2':
        raise ValueError('EXACT_MATERIAL_MANIFEST_REQUIRED')
    if set(manifest['source_hashes'])!=set(SOURCES):raise ValueError('MATERIAL_SOURCE_CLOSURE_REQUIRED')
    for p,h in manifest['source_hashes'].items():
        bound(root,p,h)
        if hashlib.sha256((Path(__file__).resolve().parents[1]/p).read_bytes()).hexdigest()!=h:
            raise ValueError('EXECUTING_MATERIAL_SOURCE_CHANGED')
    if not isinstance(manifest['jobs'],list) or not manifest['jobs']:raise ValueError('MATERIAL_JOBS_REQUIRED')


def check_job(root, manifest, job, artifact=None):
    validate_manifest(root,manifest)
    if set(job)!={'id','service_id','accepted','input','input_sha256','artifact','artifact_sha256','receipt','receipt_sha256','parent_job_id'} or job['service_id']!='material054' or job['accepted'] is not True:
        raise ValueError('EXACT_MATERIAL_JOB_REQUIRED')
    raw=strict_json(bound(root,job['input'],job['input_sha256']))
    saved=strict_json(bound(root,job['artifact'],job['artifact_sha256']))
    receipt=strict_json(bound(root,job['receipt'],job['receipt_sha256']))
    checked=audit_plan(raw,saved if artifact is None else artifact)
    if job['id']!=raw['order_id'] or receipt!=checked or not checked['accepted'] or (artifact is not None and canonical(artifact)!=canonical(saved)):
        raise ValueError('INDEPENDENT_MATERIAL_ACCEPTANCE_MISMATCH')
    parent_id=job['parent_job_id']
    if parent_id is not None:
        prior=[j for j in manifest['jobs'] if j['id']==parent_id]
        if len(prior)!=1 or parent_id==job['id']:raise ValueError('UNIQUE_PARENT_JOB_REQUIRED')
        p=prior[0]
        parent_raw=strict_json(bound(root,p['input'],p['input_sha256']))
        parent_art=strict_json(bound(root,p['artifact'],p['artifact_sha256']))
        if not audit_transfer(parent_raw,parent_art,raw)['accepted']:raise ValueError('MATERIAL_TRANSFER_REJECTED')
    return {'job':job,'artifact':saved,'receipt':receipt}


def load_jobs(root,manifest):
    validate_manifest(root,manifest)
    result={}
    consumed=set()
    for job in manifest['jobs']:
        if job.get('id') in result:raise ValueError('UNIQUE_MATERIAL_JOB_REQUIRED')
        result[job['id']]=check_job(root,manifest,job)
        current={r['stock_id'] for r in result[job['id']]['artifact']['patterns']}
        if current & consumed:raise ValueError('MATERIAL_STOCK_DOUBLE_CONSUMPTION')
        consumed.update(current)
    return result


def freeze_jobs(root, relative, triples):
    """Freeze production/check inputs; this admission is not a sale or physical proof."""
    root=Path(root); target=root/relative
    target.mkdir(parents=True,exist_ok=False)
    jobs=[]
    for raw,artifact,parent in triples:
        checked=audit_plan(raw,artifact)
        if not checked['accepted']:raise ValueError(str(checked))
        job={'id':raw['order_id'],'service_id':'material054','accepted':True,'parent_job_id':parent}
        for name,value in [('input',raw),('artifact',artifact),('receipt',checked)]:
            p=Path(relative)/(raw['order_id']+'-'+name+'.json')
            data=canonical(value);(root/p).write_bytes(data)
            job[name]=str(p);job[name+'_sha256']=hashlib.sha256(data).hexdigest()
        jobs.append(job)
    manifest={'schema':SCHEMA,'scope':'SYNTHETIC_PUBLIC_WORKLOAD','currency':'USD','account_namespace':'adaptive012',
        'native_engine':'exact-prospective-v2','source_hashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SOURCES},'jobs':jobs}
    load_jobs(root,manifest)
    (target/'MANIFEST.json').write_bytes(canonical(manifest))
    return manifest
