import argparse
import gzip
import hashlib
import importlib
import json
from pathlib import Path
import resource
import sys
import time
import types

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from enterprise.profit_horizon import reconcile, cost_sensitivity, identity

SOURCE='2503b8823028200565e31933c521bac2cd82e080'
PINS={'enterprise/scale.py':'0d0b22b5e47e6f220040176df0818ff5ffc91c8ce125134fc1dcf515f97b66ba',
      'enterprise/growth_frontier.py':'d7579693f3b4e766ab50f9497abad54ca305cfc9973f0b553ee4961e37ba9777',
      'campaign/growth-frontier-012/RESULT.json':'b2ab5abe02db084368b7f60fa961feb7c28ba3c9c2fd7a84b8df7988a392a94e'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--historical-source',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    source=a.historical_source.resolve()
    if a.output.exists() or any(x.is_symlink() for x in [a.output,*a.output.parents]):
        raise ValueError('NEW_UNSYMLINKED_OUTPUT_REQUIRED')
    for path,expected in PINS.items():
        if hashlib.sha256((source/path).read_bytes()).hexdigest()!=expected:
            raise ValueError('HISTORICAL_SOURCE_CHANGED:'+path)
    package=types.ModuleType('_profit018_historical')
    package.__path__=[str(source/'enterprise')]
    sys.modules[package.__name__]=package
    frontier=importlib.import_module(package.__name__+'.growth_frontier')
    scale=importlib.import_module(package.__name__+'.scale')
    old=json.loads((source/'campaign/growth-frontier-012/RESULT.json').read_text())
    selected=old['candidate_selected_on_development_only']
    if selected!='paid_distribution' or tuple(frontier.CONFIRMATION_SEEDS)!=tuple(range(10001,10009)):
        raise ValueError('HISTORICAL_SELECTION_OR_SEEDS_CHANGED')
    started=time.process_time()
    original,rows,raw_runs={},[],[]
    a.output.mkdir(parents=True)
    for capital in frontier.CAPITAL:
        for family in frontier.REGIMES:
            key=f'{capital}:{family}'
            original[key]={}
            for policy in frontier.ARMS:
                original[key][policy]=[]
                for seed in frontier.CONFIRMATION_SEEDS:
                    cfg=frontier.config_for(family,capital,policy)
                    before=time.process_time()
                    run=scale.simulate_scale(cfg,seed,intervention=frontier.arm_policy(policy,family))
                    cpu=time.process_time()-before
                    original[key][policy].append(frontier.compact(run))
                    audit=reconcile(run,cfg)
                    final=next((x for x in audit['profit_periods'] if x['end_month']==60),None)
                    row={'family':family,'policy':policy,'seed':seed,'starting_capital_cents':capital,
                        'horizon_months':60,'cpu_seconds_replay':cpu,'quality_evidence':'AGGREGATE_AUTHORED_ACCEPTANCE_PROBABILITY_NOT_EXECUTED_ARTIFACTS',
                        **audit,'month60_period':final,'run_sha256':identity(run)}
                    row['cost_sensitivities']=[cost_sensitivity(final,extra,tax) for extra in [0,2500,10000] for tax in [0,2000,3500]] if final else []
                    rows.append(row)
                    raw_runs.append({'family':family,'policy':policy,'capital_cents':capital,'config':cfg,'run':run})
            regenerated=frontier.aggregate_phase({key:original[key]})[key]
            if regenerated!=old['confirmation'][key]:
                (a.output/'FAILED_AGGREGATE.json').write_text(json.dumps({'key':key,'actual':regenerated,'expected':old['confirmation'][key]},indent=2)+'\n')
                raise ValueError('HISTORICAL_AGGREGATE_REPLAY_MISMATCH:'+key)
    with (a.output/'trajectories.json.gz').open('xb') as stream:
        with gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0) as zipped:
            zipped.write(json.dumps(raw_runs,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    summary=[]
    for capital in frontier.CAPITAL:
        for family in frontier.REGIMES:
            rs=[r for r in rows if r['starting_capital_cents']==capital and r['family']==family and r['policy']==selected]
            observed=[r['month60_period']['accrual_profit_cents'] for r in rs if r['month60_period'] is not None]
            summary.append({'capital_cents':capital,'family':family,'policy':selected,'worlds':len(rs),
                'completed_month60':len(observed),'survivors':sum(r['cash_survival'] for r in rs),
                'mean_month60_annual_profit_cents':sum(observed)/len(observed) if observed else None,
                'min_month60_annual_profit_cents':min(observed) if observed else None,
                'max_month60_annual_profit_cents':max(observed) if observed else None,
                'first_3b_annual_profit_crossings':[r['first_trailing_12_profit_crossing_month'] for r in rs],
                'failures':[{'seed':r['seed'],'reason':r['terminal_reason'],'last_month':r['months_completed'],
                             'partial_month':r['terminal_partial_month_residual']} for r in rs if not r['cash_survival']]})
    result={'schema':'agi-alpha/profit-horizon018-replay/v1','source_sha':SOURCE,'source_sha256':PINS,
        'evidence_kind':'HISTORICAL_EXPOSED_PROJECTION_REPLAY_NOT_FRESH_CONFIRMATION',
        'selected_policy':selected,'policy_selection':'UNCHANGED_HISTORICAL_DEVELOPMENT_SELECTION',
        'matched_published_strata':len(original),'matched_published_policy_aggregates':len(original)*len(frontier.ARMS),
        'worlds':len(rows),'profit_target_cents':300_000_000_000,
        'first_crossing_count':sum(r['first_trailing_12_profit_crossing_month'] is not None for r in rows),
        'summary':summary,'matrix':rows,
        'replay_cpu_seconds':time.process_time()-started,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'cost_sources':'Unchanged authored PR23 configs; no measured model bills, human trial, market demand or native liabilities',
        'adoption':'Historical accounting correction only; no operating policy or reserve terms authorized by these projections',
        'native_aggregation_validation':'NOT_PERFORMED; this model is not the native financial ledger',
        'real_customers':0,'real_collections':0,
        'limits':['Income taxes and complete frontier-model billing are not measured. Model expense totals are not certified complete economic costs.',
                  'Capacity and setup are immediately expensed; no residual value, amortization or profit tax is implemented.',
                  'Finite three-month percentage reserves differ from permanent native obligations; do not use projections to release native cash.',
                  'Projected net paid jobs are recognized at invoice time; settled-job count uses modeled delay and excludes terminal receivables.',
                  'Failure-month unrecorded financial mutations are disclosed; no missing months are filled or annualized.',
                  'Sensitivity changes accounting only; changed growth paths, funding feasibility and tax applicability remain unevaluated.',
                  'No fresh frontier-agent/human benchmark, recycling treatment, joint C/K treatment, insurer or legal finality was established.']}
    (a.output/'RESULT.json').write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'worlds':len(rows),'matched_policy_aggregates':result['matched_published_policy_aggregates'],
                      'profit_crossings':result['first_crossing_count'],'summary':summary},indent=2))


if __name__=='__main__':main()
