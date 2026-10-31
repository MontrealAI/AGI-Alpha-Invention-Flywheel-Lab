"""Four already-exposed native worlds: unchanged incumbent vs finite follower game.

This uses the connected enterprise and its original JournalAccount, not a second
business simulator or a fabricated market. No real spending or customers.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from commercial.ledger import canonical,digest,strict_json
from connected_enterprise.registration import validate


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    dest=args.output.expanduser().absolute()
    if dest.exists() or dest.is_symlink() or not dest.parent.is_dir() or any(x.is_symlink() for x in dest.parents):
        raise ValueError('NEW_NORMAL_OUTPUT_REQUIRED')
    registration=ROOT/'campaign/strategic-game-042/REGISTRATION.json'
    spec=strict_json(registration.read_bytes())
    validate(spec)
    if (spec['seeds']!=[341014] or set(spec['configs'])!={'central','game'}
            or spec['arms']!=['baseline','growth'] or spec['configs']['central']['opening']!=100_000_000_000
            or spec['configs']['game']['opening']!=100_000_000_000
            or spec['configs']['central']['horizon_days']!=28 or spec['configs']['game']['horizon_days']!=28
            or 'game' in spec['configs']['central']['opportunity_policy']
            or 'game' not in spec['configs']['game']['opportunity_policy']):
        raise ValueError('EXACT_EXPOSED_100K_NATIVE_GAME_PROTOCOL_REQUIRED')
    if {k:v for k,v in spec['configs']['central'].items() if k!='opportunity_policy'}!={k:v for k,v in spec['configs']['game'].items() if k!='opportunity_policy'}:
        raise ValueError('MARKET_MUST_BE_IDENTICAL_ACROSS_GAME_ARMS')
    if {k:v for k,v in spec['configs']['central']['opportunity_policy'].items()}!={k:v for k,v in spec['configs']['game']['opportunity_policy'].items() if k!='game'}:
        raise ValueError('SAME_NATIVE_POLICY_EXCEPT_FINITE_GAME_REQUIRED')
    dest.mkdir(mode=0o700)
    private=dest/'native-private'
    public=dest/'public';public.mkdir(mode=0o755)
    deadline=time.monotonic()+1500
    started=resource.getrusage(resource.RUSAGE_CHILDREN)
    command_log=[]

    def run(command,*params):
        remaining=deadline-time.monotonic()
        if remaining<10:raise TimeoutError('REGISTERED_GAME042_OPERATION_RESOURCE_WINDOW_EXHAUSTED')
        proc=subprocess.Popen([sys.executable,'-m','connected_enterprise',command,*params],
                              cwd=ROOT if command=='register' else private/'source',
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        begin=time.monotonic()
        try:
            stdout,stderr=proc.communicate(timeout=min(remaining,1400))
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM)
            try:proc.communicate(timeout=4)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate()
            raise TimeoutError('NATIVE_OPERATION_INTERRUPTED_WITH_ORIGINAL_ACCOUNTS_LEFT_IN_PLACE')
        command_log.append({'action':command,'returncode':proc.returncode,'wall_seconds':round(time.monotonic()-begin,4)})
        if proc.returncode:raise RuntimeError('NATIVE_'+command+'_REFUSED:'+stderr.decode(errors='replace')[-900:])
        try:return json.loads(stdout)
        except ValueError:raise ValueError('NATIVE_COMMAND_RECEIPT_NOT_JSON')

    try:
        reg=run('register','--config',str(registration),'--output',str(private))
        report=run('operate','--output',str(private))
        if report.get('scope')!='CONDITIONAL_SIMULATION' or report.get('all_independent_audits_passed') is not True:
            raise ValueError('ALL_FOUR_FINISHED_NATIVE_WORLDS_REQUIRED')
        receipt=run('audit','--output',str(private))
        if receipt.get('accepted') is not True or receipt.get('worlds')!=4:
            raise ValueError('FOUR_CANONICAL_INDEPENDENT_WORLD_AUDITS_REQUIRED')
        summary={}
        for case in ('central','game'):
            for arm in ('baseline','growth'):
                folder=private/'worlds'/f'341014-{case}-{arm}'
                output=strict_json((folder/'RESULT.json').read_bytes())
                proof=strict_json((folder/'AUDIT.json').read_bytes())
                if not output['complete'] or proof.get('accepted') is not True:
                    raise ValueError('INCOMPLETE_OR_UNQUALIFIED_WORLD')
                if output['config']['opening']!=100_000_000_000:
                    raise ValueError('NO_CAPITAL_REPLACEMENT_ALLOWED')
                s=output['summary']
                game_decisions=[d for d in output['decisions'] if d.get('kind')=='opportunity_search']
                summary[case+'_'+arm]={
                    'native_profit_microUSD':s['profit'],
                    'native_collections_microUSD':s['collections'],
                    'native_expenses_microUSD':s['expenses'],
                    'available_microUSD':s['available'],'unrestricted_earned_microUSD':s['unrestrictedEarned'],
                    'payables_microUSD':s['payables'], 'investment_stopped':s['investmentStopped'],
                    'settled_jobs':output['paid_jobs'],'paying_customers':output['customers'],
                    'repeat_customers':output['repeat_customers'],
                    'earned_native_investments':[{'kind':i['kind'],'cost_microUSD':i['cost'],'time':i['purchased_time'],
                        'plan_id':i['plan_id']} for i in output['investments'] if i['funding_receipt']['funding']=='EARNED'],
                    'opportunity_search_decisions':len(game_decisions),
                    'finite_game_decisions':sum('game_certificate' in d for d in game_decisions),
                    'finite_game_choices':{mode:sum(d['selected']==mode for d in game_decisions) for mode in ('continue_direct','partner_access','add_capacity')},
                    'native_ledger_actions_sha256':output['owned_account']['ledger']['actions_sha256']}
        differences={case:summary[case+'_growth']['native_profit_microUSD']-summary[case+'_baseline']['native_profit_microUSD'] for case in ('central','game')}
        differences['game_vs_heuristic_growth_microUSD']=summary['game_growth']['native_profit_microUSD']-summary['central_growth']['native_profit_microUSD']
        usage=resource.getrusage(resource.RUSAGE_CHILDREN)
        result={'schema':'agi-alpha/strategic-game042-native-proof/v1','scope':'EXPOSED_DEVELOPMENT_FINITE_NATIVE_SIMULATION',
                'game_claim':'EXACT_FINITE_RIVAL_BEST_RESPONSE_WITH_DECLARED_UNCALIBRATED_SCENARIOS_ONLY',
                'registration_sha256':digest(spec),'frozen_source_sha256':reg['source_sha256'],
                'frozen_sha256':reg['frozen_sha256'],'starting_capital_per_independent_world_microUSD':100_000_000_000,
                'external_capital_injected_microUSD':0,'registered_days':28,'native_full_audit_accepted':True,
                'worlds':summary,'paired_comparisons':differences,'command_receipts':command_log,
                'child_cpu_seconds':round(usage.ru_utime+usage.ru_stime-started.ru_utime-started.ru_stime,3),
                'actual_customers':0,'actual_collected_microUSD':0,'actual_profit_microUSD':None,
                'model_host_engineering_bill_usd':None,
                'broader_business_success':'NOT_ESTABLISHED','inventor_policy_advantage':'NOT_ESTABLISHED',
                'limits':['The game solves a tiny authored rival-response subgame, not all markets or hidden buyer values.',
                          'All buyer acceptance/payment/delivery are independently replayed by the native connected enterprise.',
                          'The 28-day exposed development cohort does not establish a fresh confirmation or complete 365-day profit.',
                          'No release/deployment or paid external activity is performed.']}
        with (public/'SUMMARY.json').open('xb') as f:
            f.write(canonical(result)+b'\n');f.flush();os.fsync(f.fileno())
        print(json.dumps({'status':'COMPLETE_AUDITED_SYNTHETIC','summary':str(public/'SUMMARY.json'),
                          'worlds':4,'game_profit':summary['game_growth']['native_profit_microUSD'],
                          'heuristic_profit':summary['central_growth']['native_profit_microUSD']},sort_keys=True))
        return 0
    except Exception as exc:
        error={'schema':'agi-alpha/strategic-game042-incomplete/v1','status':'NOT_QUALIFIED',
               'stage':command_log[-1]['action'] if command_log else 'registration',
               'reason':type(exc).__name__+':'+str(exc)[:500],
               'original_native_accounts_preserved':True,'profit_target_claim':False,
               'fixed_registration_sha256':digest(spec),'command_receipts':command_log}
        with (public/'INCOMPLETE.json').open('xb') as f:f.write(canonical(error)+b'\n')
        print(json.dumps(error,sort_keys=True),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
