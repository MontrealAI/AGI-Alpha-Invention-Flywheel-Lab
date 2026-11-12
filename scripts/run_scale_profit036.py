"""Exact-head hosted $100k native pilot + scoped 60-month conditional study.

No paid APIs, marketing, real customers, real transactions or keys leave runner.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from connected_enterprise.engine import default_config, MICRO
from connected_enterprise.scale_profit036 import validate_protocol,strict_read,canonical_bytes


def run_experiment(destination,protocol_file):
    dest=Path(destination).expanduser().absolute()
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir() or any(q.is_symlink() for q in dest.parents):
        raise ValueError('FRESH_NORMAL_DESTINATION_REQUIRED')
    protocol=validate_protocol(strict_read(protocol_file))
    dest.mkdir(mode=0o700)
    native=dest/'private-native'
    public=dest/'public'
    native_config=default_config()
    native_config.update(opening=100_000*MICRO,horizon_days=14,customer_pool=36,initial_slots=1,maximum_slots=3)
    registered={'schema':'agi-alpha/connected014-registration/v1','label':'billion-036-native-anchor',
      'evidence_role':'development','seeds':[2610313601],'configs':{'central':native_config},
      'arms':['baseline','growth'],'control_arm':'baseline','candidate_arm':'growth',
      'service_cohort_seed':2610313600,'workers':2}
    registration=dest/'REGISTRATION.json'
    registration.write_bytes(canonical_bytes(registered)+b'\n')
    deadline=time.monotonic()+600
    child_before=resource.getrusage(resource.RUSAGE_CHILDREN)
    logs=[]
    def call(command,stage):
        remaining=int(deadline-time.monotonic())
        if remaining<1:raise TimeoutError('CUMULATIVE_RUN_BUDGET_EXHAUSTED')
        r=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                         timeout=min(180,remaining),check=False)
        logs.append({'stage':stage,'return_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr)})
        if r.returncode:
            raise RuntimeError('NATIVE_STAGE_FAILED:'+stage+':'+r.stderr.decode('utf8',errors='replace')[-300:])
        return r
    call([sys.executable,'-m','connected_enterprise','register','--config',str(registration),'--output',str(native)],'register')
    call([sys.executable,'-m','connected_enterprise','operate','--output',str(native)],'operate')
    call([sys.executable,'-m','connected_enterprise','audit','--output',str(native)],'audit')
    call([sys.executable,'-m','connected_enterprise.scale_profit036','--native-output',str(native),
          '--protocol',str(protocol_file),'--trust-frozen-source','--output',str(public)],'profit-study')
    summary=strict_read(public/'SUMMARY.json')
    anchor=strict_read(public/'ANCHOR.json')
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={'schema':'agi-alpha/scale-profit036-run-receipt/v1','source_sha256':anchor['source_sha256'],
      'scope':'NATIVE_14_DAY_EXECUTED_THEN_CONDITIONAL_60_MONTH_AGGREGATION',
      'native_worlds':len(anchor['worlds']),'native_cash_microUSD':{
        x['id']:x['available_microUSD'] for x in anchor['worlds']},
      'months_projected':60,'seed_count':len(protocol['seeds']),'case_count':len(protocol['cases']),
      'cases':summary,'wall_seconds':600-(deadline-time.monotonic()),
      'child_cpu_seconds':usage.ru_utime+usage.ru_stime-child_before.ru_utime-child_before.ru_stime,
      'real_customers':0,'real_collections_cents':0,'funding_authority':False,
      'commands':logs,'limits':['Actual Python/host/model/engineering billing unknown.','Sources are simulated; $1B is reached only under unverified high-value partner assumptions.',
        'Only the public/ files are eligible for a public Actions upload. Native private output is not an artifact.']}
    with (public/'RUN_RECEIPT.json').open('xb') as f:
        f.write(canonical_bytes(receipt)+b'\n');f.flush();os.fsync(f.fileno())
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--protocol',default=str(ROOT/'campaign/scale-profit-036/PROTOCOL.json'))
    args=p.parse_args(argv)
    receipt=run_experiment(args.output,args.protocol)
    print(json.dumps({'source_sha256':receipt['source_sha256'],'cases':receipt['cases'],'scope':receipt['scope']},sort_keys=True))

if __name__=='__main__':main()
