"""Execute the registered correction; retain one primary account, publish compact evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from commercial.ledger import canonical, digest
from omega import competitive, primary_operator, successor


def save(path, value):
    path.write_bytes(canonical(value) + b'\n')


def compact_comparison(result):
    return {k:v for k,v in result.items() if k != 'comparisons'} | {
        'comparisons': [{k:v for k,v in row.items() if k not in {'outcomes','best_witness','worst_witness'}}
                        for row in result['comparisons']],
        'autonomous_low_joint_witnesses': [
            {k:row[k] for k in ('best_witness','worst_witness')}
            for row in result['comparisons']
            if (row['operation'],row['envelope'],row['mode']) == ('autonomous','low','joint')][0],
        'complete_comparison_sha256': digest(result)}


def main(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    primary = output/'primary'
    first = primary_operator.run(primary, root=ROOT, interrupt_after='first-fund')
    if first.get('complete') is not False:
        raise ValueError('REGISTERED_FUND_CRASH_NOT_EXERCISED')
    second = primary_operator.run(primary, resume=True, interrupt_after='tax')
    if second.get('complete') is not False:
        raise ValueError('REGISTERED_TAX_CRASH_NOT_EXERCISED')
    result = primary_operator.run(primary, resume=True)
    before = (primary/'public-native.json').read_bytes()
    primary_operator.run(primary, resume=True)
    if before != (primary/'public-native.json').read_bytes():
        raise ValueError('REPEATED_RESUME_CHANGED_NATIVE_HISTORY')
    check = subprocess.run([sys.executable, '-m', 'omega.primary_operator', '--output', str(primary),
                            '--frozen', '--audit'], cwd=primary/'source', capture_output=True,
                           text=True, check=True)
    independent = json.loads(check.stdout)
    if independent.get('accepted') is not True:
        raise ValueError('INDEPENDENT_PRIMARY_REPLAY_REQUIRED')
    stress = competitive.report(expanded=False, include_outcomes=False)
    expanded = competitive.report(expanded=True, include_outcomes=False)
    save(output/'stress.json', stress)
    save(output/'expanded.json', expanded)
    causal = successor.comparison(ROOT, output/'successor-comparison')
    save(output/'successor.json', causal)
    native = {k:v for k,v in result.items() if k not in {'decision_trace','successor_intent'}}
    native['decision_summary'] = [
        {'hour':t['hour'],'action':t['decision']['action'],
         'fixed_costs_cents':t['decision']['fixed_costs_cents'],
         'orders':len((t.get('row') or {}).get('orders',[])),
         'founder_minutes':(t.get('row') or {}).get('founder_minutes',0)}
        for t in result['decision_trace']]
    intent = result.get('successor_intent')
    if intent:
        native['successor'] = {
            'decision':intent['decision'], 'funding':intent['funding_receipt']['funding'],
            'artifact_sha256':intent['specification']['artifact_sha256'],
            'qualified_cases':intent.get('qualification',{}).get('accepted_case_count'),
            'task_uses':intent.get('uses'), 'failure_type':intent.get('failure_type')}
    evidence = {
        'schema':'omega/corrected-compact-evidence/v1',
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_hashes':primary_operator.source_hashes(ROOT),
        'primary':native, 'native_public_record_sha256':hashlib.sha256(before).hexdigest(),
        'process_crash_checks':{'after_fund':first,'after_tax':second,'repeat_resume_unchanged':True,
                               'independent_frozen_replay':independent},
        'expanded_comparison':compact_comparison(expanded),
        'original_stress_comparison':compact_comparison(stress),
        'successor_comparison':{k:v for k,v in causal.items() if k not in {'arms','predecessor'}},
        'successor_arms':[{k:v for k,v in row.items() if k not in {'execution','cases'}} for row in causal['arms']],
        'real_transactions':0, 'paid_model_calls':0,
        'original_account_recovered':False,'super_alpha_established':False,
        'three_billion_objective_achieved':False,
        'scope':'One native conditional counterpart; separate nonnative policy comparisons never pooled; actual complete costs unknown'}
    save(output/'EVIDENCE.json', evidence)
    print(json.dumps({'evidence':str(output/'EVIDENCE.json'),
                      'native_actions_sha256':result['native_actions_sha256'],
                      'trailing_profit_microUSD':result['trailing_profit']['trailing_365_day_profit_microUSD'],
                      'cases':expanded['total_trajectories']}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    main(parser.parse_args().output)
