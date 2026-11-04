"""Independently check saved public account exports against registered starting terms."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ORIGINAL = 'f1074b1e128069d5a4754b10955a73a3d95db7c5'
CORRECTED = 'c6ddb25f77c984a5be89196776dbaad1c5b79ce6'
PAID = '9187e8f0b57d4b11124a14ed89582914f33b30b6'
PINNED = {
    ORIGINAL: (60,'eb3b32b0cce20353b61516bb848ae4327e780ef1f658a6d331cc0eaacc2887dc'),
    CORRECTED: (62,'1c862f979deba90ce302f1aa8dcf781e75fc84fbac4be48236ca3d143cb1956e'),
    PAID: (71,'72ce9400200c8201a5c60bb7a299b9206cf00d0ae70fa2baf36433ff5ac49010'),
}
OPENING = 100_000_000_000
CART_ID = 'omega-private-mechanisms-v4-fresh-synthetic'
CART_CASES = {('generated',k) for k in ('central','copycat','failed_acceptance','no_demand','payment_failure')} | {('standard','central'),('full_control','central')}
TARIFF = {'setup_cents':2000,'discovery_per_market_cents':500,'quote_cents':10,'maintenance_cents':1200,'successor_cents':500,'tax_bps':2000}
WORLDS = ('central','weak','copycat','no_demand','failed_activation')
SCOPES = {
    'record': {'schema':'agi-alpha/adaptive012-owned-account/v1','scope':'SIMULATED'},
    'tape': {'schema':'agi-alpha/commercial010-tape/v1','currency':'simulated-microUSD','scope':'SIMULATED'},
    'resource_journal': {'schema':'agi-alpha/connected014-resource-journal/v1','scope':'SIMULATED_LOCAL_POSIX'},
    'snapshot': {'scope':'SIMULATED','ownership':'MANDATORY_SINGLE_LOCAL_POSIX_WRITER'},
}
def sha(raw): return hashlib.sha256(raw).hexdigest()
def enc(obj): return json.dumps(obj,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
def dg(obj): return sha(enc(obj))
def strict(raw):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ValueError('DUPLICATE_JSON_MEMBER')
            d[k]=v
        return d
    def reject(x): raise ValueError('NONFINITE_JSON_NUMBER')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=reject)
def read(p): return strict(p.read_bytes())
def eq(got,want,reason):
    # Canonical bytes also distinguish booleans or floats masquerading as integers.
    if enc(got)!=enc(want): raise ValueError(reason)
def sha_public_source(repo,commit,source):
    eq([len(source),dg(source)],list(PINNED[commit]),'REGISTERED_RUNTIME_IDENTITY_CHANGED')
    for n,h in source.items():
        raw=subprocess.check_output(['git','-C',str(repo),'show',commit+':'+n])
        eq(sha(raw),h,'REGISTERED_SOURCE_FILE_CHANGED:'+n)
def case(folder,arm,world,cohort,commit,public):
    payload={n:(folder/n).read_bytes() for n in ('CONTRACT.json','MANIFEST.json','REPORT.json','SOURCE.json','NATIVE_EXPORT.json')}
    fi={n:sha(v) for n,v in payload.items()}
    c,m,r,source,e=(strict(payload[n]) for n in payload)
    cfg,j,snap=e['ledger']['config'],e['connected_journal'],e['snapshot']
    if cohort=='paid':
        eq({k:fi[k] for k in fi},{k:public['artifact_file_sha256'][k] for k in fi},'PAID_PUBLIC_ARTIFACT_HASH_CHANGED')
        eq([c['arm'],c['scenario'],c['opening_microUSD'],c['working_microUSD'],c['source_sha256'],c['clock']],
           [arm,world,OPENING,0,dg(source),{'start_day':0,'end_day_exclusive':365}],'WRONG_REGISTERED_PAID_TERMS')
        eq([r['arm'],r['scenario'],r['source_sha256']],[arm,world,dg(source)],'WRONG_PAID_REPORT_ID')
        contract='omega-earned-paid-reach-v1-'+dg(c)
    else:
        eq([fi['NATIVE_EXPORT.json'],dg(r)],[public['native_export_sha256'],public['report_sha256']],'ARCHIVED_CART_EVIDENCE_CHANGED')
        eq(c,{'arm':arm,'stress':world,'tariff':TARIFF},'WRONG_CART_OPERATING_CONTRACT')
        eq([r['arm'],r['stress'],r['tariff'],r['clock'],r['source']],
           [arm,world,TARIFF,{'start_day':0,'end_day':364,'days':365},source],'WRONG_CART_REPORT_TERMS')
        contract=CART_ID
    eq([r['opening_microUSD'],r['actual_revenue_usd']],[OPENING,0],'WRONG_REPORT_CLAIM')
    cfg_want={**SCOPES['tape'],'opening':OPENING,'working':0,'contract':contract,'manifest_sha256':dg(m)}
    eq(cfg,cfg_want,'WRONG_COMPLETE_TAPE_CONFIGURATION')
    native_source=j['source']
    eq(dg(native_source['files']),native_source['sha256'],'WRONG_JOURNAL_SOURCE_DIGEST')
    for n,h in native_source['files'].items():
        eq([h,sha((folder/'runtime'/n).read_bytes())],[source[n],source[n]],'WRONG_PRIVATE_RUNTIME_PUBLIC_CODE')
    head={k:v for k,v in j.items() if k!='entries'}
    j_want={**SCOPES['resource_journal'],'opening':OPENING,'working':0,'contract':contract,'manifest_sha256':dg(m),'source':native_source}
    eq(head,j_want,'WRONG_COMPLETE_RESOURCE_JOURNAL_HEADER')
    eq(dg(j),e['connected_journal_sha256'],'BROKEN_RESOURCE_JOURNAL_COMMITMENT')
    eq({k:e[k] for k in SCOPES['record']},SCOPES['record'],'WRONG_RECORD_ENVELOPE')
    eq({k:snap[k] for k in SCOPES['snapshot']},SCOPES['snapshot'],'WRONG_SNAPSHOT_ENVELOPE')
    ledger=e['ledger'];a=ledger['actions'];before=a[0]['before']
    eq(a[0]['seq'],0,'FIRST_SEQUENCE_MISSING')
    eq([before[k] for k in ('cash','available','workingCapital','collections','expenses','profit','revenue','payables','tailReserve','reservedInvestment','unrestrictedEarned')],
       [OPENING,OPENING,0,0,0,0,0,0,0,0,0],'OPENING_NOT_ACTUALLY_APPLIED')
    eq([ledger['actions_sha256'],snap['actions_sha256'],snap['sequence']],[dg(a),dg(a),len(a)],'WRONG_NATIVE_ACTION_BINDINGS')
    eq(snap['state_digest'],dg({'config':cfg_want,'actions_sha256':dg(a),'summary':ledger['summary']}),'WRONG_CONFIG_BOUND_SNAPSHOT')
    eq(snap['summary'],ledger['summary'],'WRONG_SNAPSHOT_SUMMARY')
    eq(r['native_summary'],ledger['summary'],'WRONG_REPORT_SUMMARY')
    return source, {'arm':arm,'environment':world,'accepted':True,'native_contract':contract,'opening_microUSD':cfg['opening'],
        'working_microUSD':cfg['working'],'native_config_sha256':dg(cfg),'journal_header_sha256':dg(head),
        'source_sha256':dg(source),'operating_contract_sha256':dg(c),'production_manifest_sha256':dg(m),
        'native_export_file_sha256':fi['NATIVE_EXPORT.json'],'report_file_sha256':fi['REPORT.json'],'canonical_report_sha256':dg(r),'native_actions':len(a)}
def main():
    ap=argparse.ArgumentParser()
    for k in ('repo','evidence','original','original-diagnostics','corrected','corrected-diagnostics','paid','paid-evidence','out'):
        ap.add_argument('--'+k,required=True,type=Path)
    o=ap.parse_args()
    original=read(o.evidence/'NATIVE_EVIDENCE.json');corrected=read(o.evidence/'CORRECTED_NATIVE_EVIDENCE.json');paid=read(o.paid_evidence)
    orig_rows=original['comparisons']['cases']+original['failure_diagnostics']['cases']
    assert original['runtime_commit']==ORIGINAL
    data={}
    for label,commit,rows,want in [('original',ORIGINAL,orig_rows,CART_CASES),('corrected',CORRECTED,corrected['cases'],CART_CASES|{('adaptive','central')})]:
        eq(sorted((v['arm'],v['stress']) for v in rows),sorted(want),'WRONG_CART_COHORT')
        verified=[];declared=None
        for item in rows:
            arm,world=item['arm'],item['stress']
            d=getattr(o,label+'_diagnostics' if world in ('failed_acceptance','payment_failure') else label)/(arm+'-'+world)
            source,rec=case(d,arm,world,label,commit,item)
            if declared is None: sha_public_source(o.repo,commit,source);declared=source
            else:eq(source,declared,'HYBRID_OPERATING_SOURCE')
            verified.append(rec)
        data[label]={'runtime_commit':commit,'source_files':len(declared),'source_sha256':dg(declared),'accounts':verified}
    eq(sorted(paid['pairs']),sorted(WORLDS),'WRONG_PAID_COHORT')
    cells=[];declared=None
    for w in WORLDS:
        for a in ('organic','pilot'):
            source,rec=case(o.paid/w/a,a,w,'paid',PAID,paid['pairs'][w][a])
            if declared is None:sha_public_source(o.repo,PAID,source);declared=source
            else:eq(source,declared,'HYBRID_OPERATING_SOURCE')
            cells.append(rec)
    data['paid']={'runtime_commit':PAID,'source_files':len(declared),'source_sha256':dg(declared),'accounts':cells}
    receipt={'schema':'omega/archived-export-initialization-replay/v1','accepted':True,'account_count':25,
             'comparison_script_sha256':sha(Path(__file__).read_bytes()),'expected_record_envelopes':SCOPES,
             'expected_opening_microUSD_each':OPENING,'expected_initial_working_microUSD_each':0,
             'comparisons':data,'rejections':[],'scope':'Read-only comparison of historical exported records against pinned research rules, registered cases, public evidence, actual runtime code hashes and first pre-action native state. The original V4 audit omitted an independent initialization binding. This retrospective check found every inspected archived account correct. No live authority, private signing key, or commercial writer accessed; no claim about subsequent live state or independent cryptographic authentication.'}
    with o.out.open('x') as f:json.dump(receipt,f,sort_keys=True,indent=2);f.write('\n')
    print(sha(o.out.read_bytes()),{k:len(v['accounts']) for k,v in data.items()})
if __name__=='__main__':main()
