"""Run the predeclared fresh reuse experiment with content-equivalent controls."""
from __future__ import annotations
import argparse, hashlib, json, os, pathlib, resource, subprocess, sys, time

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FIELDS=['n','physical_weights','global_phase_exponent','logical_order','codewords']

def bounded():
    resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(240,240))

def call(args, log):
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    start=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    r=subprocess.run([sys.executable,*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env,timeout=180,preexec_fn=bounded)
    log.write_bytes(r.stdout);after=resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'returncode':r.returncode,'wall_seconds':time.monotonic()-start,'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'log':log.name}

def run(output, verifier=None):
    out=pathlib.Path(output);out.mkdir(parents=True,exist_ok=False)
    protocol=ROOT/'campaign/cycle-004/TRANSFER_PROTOCOL.json'
    spec=json.loads(protocol.read_text());verifier=pathlib.Path(verifier) if verifier else HERE/'verification/certify.py'
    reports=[]; results={}
    for task in spec['fresh_tasks']:
        applicability=__import__('applicability').analyze(task['n'])
        for arm in ('retained','ordinary_reuse_equal_content'):
            d=out/f"n{task['n']}-seed{task['seed']}-{arm}";d.mkdir()
            record={'task':task,'arm':arm,'applicability':applicability,'source_sha256':hashlib.sha256((HERE/'construct.py').read_bytes()).hexdigest()}
            steps=[]
            steps.append(call([HERE/'construct.py','--n',task['n'],'--seed',task['seed'],'--output',d/'construction'],d/'construct.log'))
            numeric=d/'construction/NUMERIC.json'
            if steps[-1]['returncode']==0 and json.loads(numeric.read_text())['all_numeric_feasible']:
                # Invoke the public function under the parent's stricter240s cap.
                # The frozen standalone CLI tries to set its own600s hard cap.
                steps.append(call(['-c','import sys;sys.path.insert(0,sys.argv[1]);from exactify import exactify;exactify(sys.argv[2],sys.argv[3])',HERE,numeric,d/'CANDIDATE.json'],d/'exactify.log'))
                if steps[-1]['returncode']==0:
                    candidate=json.loads((d/'CANDIDATE.json').read_text());projection={k:candidate[k] for k in FIELDS}
                    p=d/'projection.json';p.write_text(json.dumps(projection,indent=2)+'\n')
                    digest=hashlib.sha256(p.read_bytes()).hexdigest()
                    steps.append(call([verifier,p,'--expected-sha256',digest,'--output',d/'CERTIFICATE.json'],d/'certify.log'))
                    record['certified']=steps[-1]['returncode']==0
                    results[(task['n'],task['seed'],arm)]=projection
            record['steps']=steps;record.setdefault('certified',False);reports.append(record)
    comparisons=[]
    for task in spec['fresh_tasks']:
        key=(task['n'],task['seed'])
        same=results.get((*key,'retained'))==results.get((*key,'ordinary_reuse_equal_content')) and (*key,'retained') in results
        comparisons.append({'task':task,'equal_mathematical_artifacts':same})
    report={'schema':'phase-code-fresh-reuse/v1','protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),'runs':reports,'comparisons':comparisons,'all_certified':all(x['certified'] for x in reports),'ordinary_reuse_parity':all(x['equal_mathematical_artifacts'] for x in comparisons),'new_discovery_policy_advantage':'NOT_ESTABLISHED','earned_funded':False,'funding':'Existing research allocation; no commercial receipt or earned investment','scope':'Fresh exact construction tasks, not a representative workload sample or evidence of superior discovery strategy.'}
    (out/'TRANSFER_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['all_certified','ordinary_reuse_parity','earned_funded']}))
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--verifier');a=p.parse_args();run(a.output,a.verifier)
