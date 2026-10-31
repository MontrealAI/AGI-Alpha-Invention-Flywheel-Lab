"""Execute a fixed matched opportunity+means search in the canonical native enterprise.

This is an EXPOSED synthetic development comparison, not a calibrated buyer
population, a proof of invention-policy superiority, or real collections.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commercial.ledger import canonical,digest
from connected_enterprise.opportunity_search040 import connected_sequence


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='new parent directory for separate private/native and public evidence')
    parser.add_argument('--registration',type=Path,default=ROOT/'campaign/opportunity-040/REGISTRATION.json')
    args=parser.parse_args(argv)
    output=args.output.absolute();registration=args.registration.resolve()
    if output.exists() or output.is_symlink() or not output.parent.is_dir() or any(x.is_symlink() for x in output.parents):
        raise ValueError('NEW_SECURE_OPPORTUNITY_OUTPUT_REQUIRED')
    from connected_enterprise.registration import validate
    config=json.loads(registration.read_bytes(),parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_REGISTRATION')))
    if validate(config)!=config or config['evidence_role']!='reproduction' or config['seeds']!=[341014] or config['arms']!=['baseline','growth'] or config['configs']['central']['opening']!=100_000_000_000 or config['configs']['central']['horizon_days']!=28:
        raise ValueError('EXACT_FROZEN_100K_OPPORTUNITY_PROTOCOL_REQUIRED')
    deadline=time.monotonic()+1100
    start_usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    output.mkdir(mode=0o700)
    original=output/'original-native-private'
    commands=[]
    def native(*cmd):
        remaining=deadline-time.monotonic()
        if remaining<5:raise TimeoutError('CUMULATIVE_1100_SECOND_NATIVE_LIMIT')
        start=time.monotonic()
        run=subprocess.run([sys.executable,'-m','connected_enterprise',*cmd],cwd=ROOT,
                 capture_output=True,timeout=min(1050,remaining))
        commands.append({'command':cmd[0],'exit':run.returncode,'wall_seconds':round(time.monotonic()-start,3)})
        if run.returncode:
            raise RuntimeError('NATIVE_'+cmd[0]+'_FAILED:'+run.stderr.decode(errors='replace')[-1200:])
        return json.loads(run.stdout.decode())
    native('register','--config',str(registration),'--output',str(original))
    native('operate','--output',str(original))
    checked=native('audit','--output',str(original))
    if checked.get('accepted') is not True or checked.get('worlds')!=2:raise ValueError('TWO_CANONICAL_NATIVE_AUDITS_REQUIRED')
    compared=native('comparison','--output',str(original),'--control','baseline','--candidate','growth')
    manifest=json.loads((original/'SERVICES.json').read_bytes())
    worlds={}
    for arm in ('baseline','growth'):
        result=json.loads((original/'worlds'/f'341014-central-{arm}'/'RESULT.json').read_bytes())
        if not result['complete'] or result['seed']!=341014 or result['arm']!=arm or result['config']['opening']!=100_000_000_000:
            raise ValueError('ONLY_MATCHED_COMPLETED_NATIVE_WORLDS_ALLOWED')
        native_proof=json.loads((original/'worlds'/f'341014-central-{arm}'/'AUDIT.json').read_bytes())
        if native_proof['accepted'] is not True:raise ValueError('NATIVE_OPERATING_AUDIT_REQUIRED')
        s=result['summary']
        worlds[arm]={'paid_jobs':result['paid_jobs'],'paying_customers':result['customers'],
             'repeat_customers':result['repeat_customers'],'collections_microUSD':s['collections'],
             'expenses_microUSD':s['expenses'],'profit_microUSD':s['profit'],
             'available_microUSD':s['available'],'unrestricted_earned_microUSD':s['unrestrictedEarned'],
             'payables_microUSD':s['payables'],'investment_stopped':s['investmentStopped'],
             'earned_funded_investments':[{'id':i['id'],'kind':i['kind'],'time':i['purchased_time'],
                   'cost_microUSD':i['cost'],'source_plan_id':i['plan_id']} for i in result['investments'] if i['funding_receipt']['funding']=='EARNED'],
             'native_actions_sha256':result['owned_account']['ledger']['actions_sha256'],
             'opportunity':connected_sequence(result,manifest) if arm=='growth' else None}
    if worlds['growth']['collections_microUSD'] != worlds['growth']['profit_microUSD']+worlds['growth']['expenses_microUSD']:
        raise ValueError('SIMULATED_CASH_PROFIT_COST_IDENTITY_FAILED')
    # This is an engineering fitness contract for a fixed exposed case, not a
    # requirement to find a winning seed or claim all future markets succeed.
    growth=worlds['growth'];baseline=worlds['baseline']
    status=('CONNECTED_POSITIVE_EXPOSED_NATIVE_CASE' if growth['opportunity']['status']=='CONNECTED_PROFITABLE_OPPORTUNITY_SEQUENCE'
             and growth['profit_microUSD']>0 and growth['paid_jobs']>baseline['paid_jobs'] else 'NOT_ESTABLISHED')
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    summary={'schema':'agi-alpha/native-opportunity-search040-result/v1','scope':'EXPOSED_DEVELOPMENT_SYNTHETIC_NOT_REAL_COMMERCE',
             'registration_sha256':hashlib.sha256(registration.read_bytes()).hexdigest(),
             'frozen_source_sha256':json.loads((original/'FROZEN.json').read_bytes())['source']['sha256'],
             'source_identity':digest({k:v for k,v in json.loads((original/'FROZEN.json').read_bytes())['source']['files'].items()}),
             'native_audit_accepted':True,'native_comparison_id':digest(compared),
             'starting_capital_per_independent_arm_microUSD':100_000_000_000,'external_funding_microUSD':0,
             'registered_days':28,'observed_status':status,'worlds':worlds,'commands':commands,
             'child_cpu_seconds':round(usage.ru_utime+usage.ru_stime-start_usage.ru_utime-start_usage.ru_stime,3),
             'actual_customers':0,'actual_collections_microUSD':0,'actual_profit_microUSD':None,
             'host_model_and_engineering_billing':'UNMEASURED_IN_THIS_DEVELOPMENT_RUN',
             'causal_replicated_profit_advantage':'NOT_ESTABLISHED_WITH_ONE_EXPOSED_SEED',
             'fresh_inventor_improvement':'NOT_ESTABLISHED',
             'limits':['Opportunity target is a public-catalog service hypothesis; acquired channel does not guarantee buyers in that service.',
                       'A native buyer chooses voluntarily between seller, human and rival and may decline.',
                       'No live customer data or real payments; all conversion, competitor and channel terms are synthetic.',
                       'One positive exposed 28-day case cannot validate a 60-month billion-dollar enterprise or market behavior.']}
    public=output/'public';public.mkdir()
    target=public/'SUMMARY.json'
    with target.open('xb') as f:
        f.write(canonical(summary)+b'\n');f.flush();os.fsync(f.fileno())
    print(json.dumps({'status':status,'public_summary':str(target),'private_accounts_retained':True,
                      'native_audits':True,'registered_worlds':2},sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
