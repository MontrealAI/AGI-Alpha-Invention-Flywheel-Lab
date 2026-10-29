"""One bounded, exclusive-output replay of the constructed ideal component.

This reproduces exposed engineering evidence. It creates no new confirmation,
buyer consent, transaction, hardware measurement or commercial success.
"""
from __future__ import annotations
import argparse, datetime, gzip, hashlib, json, os, pathlib, resource, shutil, subprocess, sys, time

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FIELDS=['n','physical_weights','global_phase_exponent','logical_order','codewords']

def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write(p,x):
    with pathlib.Path(p).open('x') as h: json.dump(x,h,indent=2); h.write('\n')
def bounded():
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(600,600))

def run(output):
    manifest=json.loads((HERE/'DISTRIBUTION_SHA256.json').read_text())
    actual={str(p.relative_to(HERE)) for p in HERE.rglob('*.py')}
    expected={p for p in manifest if p.endswith('.py')}
    if actual!=expected: raise ValueError('DISTRIBUTION_PYTHON_SOURCE_SET_MISMATCH')
    for name,digest in manifest.items():
        p=HERE/name
        if p.is_symlink() or sha(p)!=digest: raise ValueError('DISTRIBUTION_HASH_MISMATCH:'+name)
    freeze=json.loads((ROOT/'campaign/cycle-004/CANDIDATE_FREEZE.json').read_text())
    for name,digest in freeze['source_sha256'].items():
        if sha(ROOT/name)!=digest: raise ValueError('FROZEN_CORE_CHANGED:'+name)
    out=pathlib.Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();steps=[]
    def call(label,args,cwd=ROOT):
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
        t=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
        r=subprocess.run([sys.executable,*map(str,args)],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180,preexec_fn=bounded)
        (out/(label+'.log')).write_bytes(r.stdout);after=resource.getrusage(resource.RUSAGE_CHILDREN)
        steps.append({'step':label,'returncode':r.returncode,'wall_seconds':time.monotonic()-t,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime})
        write(out/(label+'.receipt.json'),steps[-1])
        if r.returncode: raise ValueError('STEP_FAILED:'+label)
    try:
        write(out/'STARTED.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'mode':'REPRODUCTION_OF_EXPOSED_EVIDENCE','distribution_sha256':sha(HERE/'DISTRIBUTION_SHA256.json')})
        call('independent-verifier-self-tests',['-m','unittest','discover','-s',HERE/'verification','-p','test_*.py','-v'])
        call('construct',[HERE/'construct.py','--n','15','--seed','42017','--output',out/'construction'])
        call('exactify',[HERE/'exactify.py','--source',out/'construction/NUMERIC.json','--output',out/'reconstructed.json'])
        original=ROOT/freeze['candidate'];d=json.loads(original.read_text());rebuilt=json.loads((out/'reconstructed.json').read_text())
        if {k:d[k] for k in FIELDS}!={k:rebuilt[k] for k in FIELDS}: raise ValueError('RECONSTRUCTED_MATHEMATICS_DIFFER')
        projection=out/'exact-input.json';write(projection,{k:d[k] for k in FIELDS})
        call('exact-certificate',[HERE/'verification/certify.py',projection,'--expected-sha256',sha(projection),'--output',out/'CERTIFICATE.json'])
        # The original baseline script writes beside itself. Reproduce in a copy.
        baseline=out/'baseline';shutil.copytree(HERE/'verification',baseline,ignore=shutil.ignore_patterns('__pycache__'))
        call('known-full-alternatives',[baseline/'baseline_audit.py'])
        call('encoder',[HERE/'encoder.py','--candidate',original,'--numeric',HERE/'artifacts/controlled_s15_numeric.json','--output',out/'encoder'])
        call('resource-audit',[HERE/'resource_audit.py','--candidate',original,'--numeric',HERE/'artifacts/controlled_s15_numeric.json','--output',out/'RESOURCE_AUDIT.json'])
        call('ideal-runtime',[HERE/'runtime.py','--candidate',original,'--sha256',sha(original),'--output',out/'runtime'])
        call('independent-process',[HERE/'verification/finish_confirmation.py','--lab-root',ROOT,'--output',out/'independent-process'])
        call('fresh-reuse',[HERE/'transfer.py','--output',out/'fresh-reuse'])
        call('commercial-boundary',[HERE/'commercial.py','--candidate',original,'--certificate',out/'CERTIFICATE.json','--output',out/'commercial'])
        process=json.loads((out/'independent-process/SUMMARY.json').read_text())
        reuse=json.loads((out/'fresh-reuse/TRANSFER_REPORT.json').read_text())
        commercial=json.loads((out/'commercial/COMMERCIAL.json').read_text())
        if not json.loads((out/'encoder/ENCODER_REPORT.json').read_text())['passed'] or not json.loads((out/'runtime/REPORT.json').read_text())['all_development_checks_passed']: raise ValueError('BUILDER_IMPLEMENTATION_CHECK_FAILED')
        if process['status']!='PASS' or not reuse['all_certified'] or not reuse['ordinary_reuse_parity']: raise ValueError('REPRODUCED_OUTCOME_FAILED')
        for row in json.loads((ROOT/'evidence/cycle-004/confirmation/LOSSLESS_ARCHIVES.json').read_text()):
            raw=gzip.decompress((ROOT/'evidence/cycle-004/confirmation'/row['gzip_path']).read_bytes())
            if hashlib.sha256(raw).hexdigest()!=row['raw_sha256']: raise ValueError('PRESERVED_EVIDENCE_ARCHIVE_CORRUPT')
        report={'status':'PASS_SCOPED_IDEAL_COMPONENT_REPRODUCTION','candidate_sha256':sha(original),'mathematical_reconstruction_equal':True,'process_cases':process['process_cases'],'ordinary_reuse_parity':True,'commercial_success':False,'real_revenue_USD':0,'simulated_receipts_microUSD':commercial['simulated_receipts_microUSD'],'earned_funded_successor':False,'wall_seconds':time.monotonic()-start,'steps':steps,'scope':'Exact mathematics and ideal process only. No physical fault-tolerant system, discovery-policy advantage, new statistical confirmation, paid delivery or profit.'}
        write(out/'REPORT.json',report);write(out/'COMPLETE.json',{'report_sha256':sha(out/'REPORT.json')})
        print(json.dumps({k:report[k] for k in ['status','mathematical_reconstruction_equal','process_cases','commercial_success','wall_seconds']}))
        return report
    except BaseException as exc:
        write(out/'FAILED.json',{'exception':type(exc).__name__,'reason':str(exc),'steps':steps,'wall_seconds':time.monotonic()-start})
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
