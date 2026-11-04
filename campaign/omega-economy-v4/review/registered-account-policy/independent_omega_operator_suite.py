"""Replay 19 preregistered independent operator witnesses, retaining every result and error."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
from pathlib import Path
from subprocess import run
import argparse
import json
import os
import sys


MATRIX = {
    'successor': [('v3','skip'), ('v3','normal'), ('v1','skip'), ('v1','normal'), ('v2','skip'), ('v2','normal')],
    'config': [('v1','opening'), ('v2','contract'), ('v3','working'), ('v4','opening'), ('v4','working'), ('v4','contract')],
    'market': [('v1','ghost'), ('v2','ghost'), ('v3','ghost'), ('v1','substitution'), ('v1','budget'), ('v2','deadline'), ('v3','event')]
}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path, help='Fresh local directory for every outcome, including errors.')
    ap.add_argument('--workers', type=int, default=4)
    a=ap.parse_args()
    source=a.source.resolve()
    a.output.mkdir(exist_ok=False)
    case_scripts={suite:Path(__file__).resolve().with_name('independent_omega_'+suite+'_audit.py') for suite in MATRIX}
    cases=[(suite,v,m) for suite,coordinates in MATRIX.items() for v,m in coordinates]
    def probe(case):
        suite,version,case_name=case
        name='-'.join(case)
        output=a.output/(name+'.json')
        command=[sys.executable,'-B',str(case_scripts[suite]),str(source),version,case_name,str(output)]
        with (a.output/(name+'.log')).open('x') as log:
            p=run(command,stdout=log,stderr=log,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        row={'case':name,'exit_code':p.returncode,'observed':json.loads(output.read_bytes()) if output.exists() else None}
        if p.returncode:row['corrected_verdict_matches']=False
        elif suite=='config':
            record=row['observed']
            row['corrected_verdict_matches']=(record['generic_financial_replay'] and not record['public_operator_accepted']
                                              and not record['completed_resume_accepted'] and record['native_export_unchanged'])
        else:
            row['corrected_verdict_matches']=row['observed']['operator_accepted']==(suite=='successor' and case_name=='normal')
        return row
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures=[pool.submit(probe,c) for c in cases]
        rows=[]
        for completed in as_completed(futures):
            row=completed.result();rows.append(row)
            print(row['case'],row['exit_code'],row['corrected_verdict_matches'],flush=True)
    sha=lambda p:sha256(p.read_bytes()).hexdigest()
    owner_files=['mechanism_harness/'+p+'_native.py' for p in ('inventor','mechanism','cart')]
    receipt={'source_commit':run(['git','-C',str(source),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip(),
             'source_files_sha256':{p:sha(source/p) for p in owner_files},
             'script_sha256':{p.name:sha(p) for p in [*case_scripts.values(),Path(__file__)]},
             'scope':'Synthetic, independent, source-bound operator audit with isolated ephemeral native accounts. No stored account authority.',
             'corrected_verdicts':sum(r['corrected_verdict_matches'] for r in rows),'total':len(rows),'rows':sorted(rows,key=lambda r:r['case'])}
    with (a.output/'INDEPENDENT_OPERATOR_REPLAY.json').open('x') as out:
        json.dump(receipt,out,indent=2,sort_keys=True);out.write('\n')
    print('TOTAL',receipt['corrected_verdicts'],receipt['total'],flush=True)
    return 0 if receipt['corrected_verdicts']==len(rows) else 1

if __name__=='__main__':sys.exit(main())
