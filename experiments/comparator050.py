"""Source-bound native comparison with explicit unavailable comparator slots."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
from commercial.ledger import digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.composed_window049 import configuration as composed_configuration
from connected_enterprise.cooperation044 import _inventory_identity
from connected_enterprise.runner import source_paths

ROOT = Path(__file__).resolve().parents[1]
ARMS = ('strong_conventional', 'commerce_only', 'capability_only', 'composed_joint', 'tuned_fixed_split')
AVAILABLE = ARMS
SHARES = (0, 5000, 10000)
PROTOCOL = {
    'schema': 'agi-alpha/comparator050/v1', 'native_category_policy_dependency': 'e37f78193e0aaf7644b76727676ea8d3c1b825cc', 'evidence_role': 'BUILDER_VISIBLE_FINITE_ENGINEERING_COMPARISON',
    'seed': 2611010501, 'cohort_seed': 2611010502, 'development_seed': 2611010503, 'development_cohort_seed': 2611010504, 'cases': ['central', 'no_demand'],
    'horizon_days': 21, 'opening_microUSD_per_account': 100000000000, 'customer_pool': 8,
    'jobs_per_service': 32, 'packet_jobs': 24, 'packet_rows': 12,
    'arms': list(ARMS), 'available_arms': list(AVAILABLE),
    'primary_metric': 'Whole-account recognized revenue plus recovery minus all incurred modeled expenses; no annualization.',
    'strong_control': 'Same public complete-offer atoms, outside options, exact quotes, composed one-window forecasts, channel/capacity contracts and candidate options as composed_joint; ordinary native exact risk-adjusted allocation replaces only the follower-game objective.',
    'commerce_ablation': 'Same composed public channel/quote path with declared capacity quantity zero; physical supplier contracts remain unchanged.',
    'capability_ablation': 'Existing baseline engine arm suppresses channel acquisition; explicit quantity recourse remains active. No sequence/channel-menu policy, same physical contracts, admitted work and public complete-offer pricing.',
    'costs': 'Common existing complete-cost native envelopes. Strong/conventional, commerce and joint pay the same composed USD5 setup and USD0.05 daily planning additions; capability-only does not pay unused sequence additions. Actual host/model/engineering billing is unknown.',
    'fixed_split': {
        'status': 'REGISTERED_NOT_EVALUATED', 'development_acquisition_bps': list(SHARES),
        'scope': 'Fixed per-decision category upfront-invoice caps on current eligible earned funds after operating deduction; not persistent buckets or cumulative/lifetime spend proportions. All chosen acquisition/capacity invoices count, including typed seed-eligible startup if present; future contingent invoices must replan under future caps.',
        'selection_rule': 'Maximize minimum case complete modeled profit, then sum profit, then nearest5000bps acquisition, then lower acquisitionbps.',
        'tuning_cost': 'Sum incurred native expenses of all six development worlds; attribute exactly once across two fixed-split evaluation setup envelopes, central receives integer residual. Do not add development expense again to the already-attributed evaluation lifecycle score. Independent simulation histories are not pooled.',
        'requires': 'Qualified category_budgets_bps native policy; reject unavailable interface, never substitute quantity caps or changed provider terms.'
    },
    'stop': 'Exactly six development accounts before ten evaluation accounts: three fixed shares crossed with central/no-demand, then five frozen policies crossed with central/no-demand.21 operating days plus normal drain each. No evaluation outcome may select the fixed share. No seed search, favorable retries, arm extension, top-up or balance pooling.',
    'limits': ['Five-policy completion requires all six tuning and ten evaluation accounts to complete and independently audit',
               'No improved discovery, actual commerce, annual-profit or global-optimality claim',
               'Human staffing/task-hours and frontier AI bills remain unmeasured; outside quotes are authored scenarios'],
    'authority': []
}
EXTRA_SOURCE = ('experiments/comparator050.py', 'tests/test_connected_comparator050.py', 'campaign/comparator-050/PROTOCOL.json')


def read(path):
    return strict_json(Path(path).read_bytes())


def write(path, value):
    atomic_bytes(Path(path), json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n')


def identity(root):
    root = Path(root)
    files = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sorted(set(source_paths(root)) | set(EXTRA_SOURCE))}
    return {'files': files, 'sha256': digest(files)}


def configuration(manifest, case, arm, root=ROOT, *, split_bps=None, tuning_charge=0):
    if case not in PROTOCOL['cases'] or arm not in ARMS:
        raise ValueError('REGISTERED_COMPARATOR_CASE_ARM_REQUIRED')
    cfg, manifest = composed_configuration(manifest, case, 'composed', root=root)
    cfg.update(horizon_days=PROTOCOL['horizon_days'], opening=PROTOCOL['opening_microUSD_per_account'], customer_pool=PROTOCOL['customer_pool'])
    engine_arm = 'competitive_growth'
    if arm in {'strong_conventional','tuned_fixed_split'}:
        cfg['strategic_allocation_policy'].pop('strategic_game')
    elif arm == 'commerce_only':
        cfg['strategic_allocation_policy']['capacity_menu']['max_quantity'] = 0
    elif arm == 'capability_only':
        cfg['strategic_allocation_policy'].pop('sequence')
        cfg.pop('channel_menu_policy')
        cfg['setup_cost'] -= 5000000
        cfg['maintenance_daily'] -= 50000
        engine_arm = 'baseline'
    if arm=='tuned_fixed_split':
        if type(split_bps) is not int or split_bps not in SHARES or type(tuning_charge) is not int or tuning_charge<0:raise ValueError('REGISTERED_DEVELOPMENT_SHARE_AND_EXPLICIT_TUNING_CHARGE_REQUIRED')
        cfg['strategic_allocation_policy']['category_budgets_bps']={'acquisition':split_bps,'capacity':10000-split_bps}
        cfg['setup_cost']+=tuning_charge
    from connected_enterprise.engine import validate_config
    return validate_config(cfg), manifest, engine_arm


def make_manifest(root, relative, cohort):
    from adaptive_enterprise.instruments import prepare_complete_offer_services
    manifest=prepare_complete_offer_services(root,relative,cohort_seed=cohort,jobs_per_service=PROTOCOL['jobs_per_service'],packet_jobs=PROTOCOL['packet_jobs'],packet_rows=PROTOCOL['packet_rows'])
    manifest['native_engine']='exact-permanent-v2'
    return manifest


def prepare(output):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    source=output/'source'
    for name in identity(ROOT)['files']:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
    if identity(source)!=identity(ROOT):raise ValueError('SOURCE_FREEZE_CHANGED')
    development=make_manifest(source,'workloads/comparator050-development',PROTOCOL['development_cohort_seed'])
    evaluation=make_manifest(source,'workloads/comparator050-evaluation',PROTOCOL['cohort_seed'])
    configs={'development':{},'evaluation':{}}
    for case in PROTOCOL['cases']:
        configs['development'][case]={}
        configs['evaluation'][case]={}
        for share in SHARES:
            cfg,m,engine_arm=configuration(development,case,'tuned_fixed_split',source,split_bps=share)
            configs['development'][case][str(share)]={'config':cfg,'engine_arm':engine_arm}
            if m!=development:raise ValueError('MATCHED_MANIFEST_CHANGED')
        for arm in ARMS[:-1]:
            cfg,m,engine_arm=configuration(evaluation,case,arm,source)
            configs['evaluation'][case][arm]={'config':cfg,'engine_arm':engine_arm}
            if m!=evaluation:raise ValueError('MATCHED_MANIFEST_CHANGED')
    value={'protocol':PROTOCOL,'source':identity(source),'manifests':{'development':development,'evaluation':evaluation},'configs':configs}
    write(output/'REGISTERED.json',value)
    return {'registered':str(output/'REGISTERED.json'),'source_sha256':value['source']['sha256'],'development_worlds':6,'evaluation_worlds':10,'fixed_split_status':'REGISTERED_NOT_EVALUATED','next':'Change directory to '+str(source)+' and run this frozen module there: python3 -m experiments.comparator050 tune --output '+str(output)}


def validate_inventory(manifest,root,phase):
    from adaptive_enterprise.instruments import SOURCE_PATHS
    with tempfile.TemporaryDirectory(prefix='comparator050-origin-') as temporary:
        origin=Path(temporary)
        for name in SOURCE_PATHS:
            target=origin/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(Path(root)/name,target)
        expected=make_manifest(origin,'workloads/comparator050-'+phase,PROTOCOL['development_cohort_seed'] if phase=='development' else PROTOCOL['cohort_seed'])
        if _inventory_identity(manifest)!=_inventory_identity(expected):raise ValueError('REGISTERED_COMPARATOR_COHORT_CHANGED')
        for job in expected['jobs']:
            for field in ('input','artifact','receipt'):
                if (Path(root)/job[field]).read_bytes()!=(origin/job[field]).read_bytes():raise ValueError('REGISTERED_COMPARATOR_ARTIFACT_CHANGED')


def plan(output):
    output=Path(output).resolve();frozen=read(output/'REGISTERED.json')
    if ROOT.resolve()!=(output/'source').resolve():raise ValueError('EXECUTE_FROM_REGISTERED_FROZEN_SOURCE_BEFORE_ACCOUNT_CREATION')
    if frozen['protocol']!=PROTOCOL or frozen['source']!=identity(ROOT) or frozen['source']!=identity(output/'source'):raise ValueError('SOURCE_BOUND_COMPARATOR_CHANGED')
    for phase in ('development','evaluation'):validate_inventory(frozen['manifests'][phase],output/'source',phase)
    for case in PROTOCOL['cases']:
        for share in SHARES:
            cfg,_,arm=configuration(frozen['manifests']['development'],case,'tuned_fixed_split',output/'source',split_bps=share)
            if frozen['configs']['development'][case][str(share)]!={'config':cfg,'engine_arm':arm}:raise ValueError('REGISTERED_DEVELOPMENT_CONFIG_CHANGED')
        for name in ARMS[:-1]:
            cfg,_,arm=configuration(frozen['manifests']['evaluation'],case,name,output/'source')
            if frozen['configs']['evaluation'][case][name]!={'config':cfg,'engine_arm':arm}:raise ValueError('REGISTERED_EVALUATION_CONFIG_CHANGED')
    return output,frozen


def public_row(config,phase,case,arm,result,checked,resumed):
    s=result['summary']
    if s['profit']!=s['revenue']+s['recoveryIncome']-s['expenses']:raise ValueError('COMPLETE_PROFIT_IDENTITY_FAILED')
    return {'phase':phase,'case':case,'arm':arm,'status':'COMPLETED','opening_microUSD':config['opening'],'operating_days':config['horizon_days'],
        'complete':result['complete'],'audit_accepted':checked['accepted'],'audit_sha256':digest(checked),'result_sha256':digest(result),'config_sha256':digest(config),
        'native_actions_sha256':result['owned_account']['ledger']['actions_sha256'],'resume_financially_unchanged':resumed,'summary':s,
        'paid_jobs':result['paid_jobs'],'paying_customers':result['customers'],'repeat_customers':result['repeat_customers'],
        'settled_packets':sum(o['offer']['service_id']=='receivables_packet' and o['outcome']=='SETTLED' for o in result['orders']),
        'actual_exposures':sum(d['realized_exposures'] for d in result['channels']['exposures_by_day'].values()),
        'investments':[{k:i.get(k) for k in ('id','kind','capacity_units','cost','purchased_time')} for i in result['investments']],
        'commercial_gate':result['conditional_simulated_commercial_success'],'actual_commerce_profit':None,'actual_host_model_engineering_billing':None}


def persisted_after_resume(original,resumed,folder):
    if original['owned_account']!=resumed['owned_account']:
        raise ValueError('SAME_ACCOUNT_RESUME_CHANGED_NATIVE_HISTORY')
    persisted=read(Path(folder)/'RESULT.json')
    if digest(persisted)!=digest(resumed):
        raise ValueError('RESUMED_RESULT_NOT_PERSISTED_BYTES')
    return persisted


def validate_recorded_cells(output,frozen,phase,configs,arms,seed,report):
    allowed={(case,arm) for case in PROTOCOL['cases'] for arm in arms}
    keys=[(row['case'],row['arm']) for row in report['rows']]
    if len(keys)!=len(set(keys)) or not set(keys)<=allowed:raise ValueError('RECORDED_COMPARATOR_COVERAGE_CHANGED')
    from connected_enterprise.verify import audit
    for row in report['rows']:
        registered=configs[row['case']][row['arm']]
        result=read(output/'private'/phase/(row['case']+'-'+row['arm'])/'RESULT.json')
        if not result['complete'] or result['config']!=registered['config'] or result['seed']!=seed or result['arm']!=registered['engine_arm'] or result['source']!=frozen['source']:raise ValueError('RECORDED_CELL_NOT_COMPLETE_REGISTERED_NATIVE_RESULT')
        checked=audit(ROOT,frozen['manifests'][phase],result)
        if not checked['accepted'] or row!=public_row(registered['config'],phase,row['case'],row['arm'],result,checked,True):raise ValueError('RECORDED_NATIVE_CELL_CHANGED')


def verify_development(output,frozen,development):
    expected={(case,str(share)) for case in PROTOCOL['cases'] for share in SHARES}
    if development.get('status')!='COMPLETED' or development.get('phase')!='development' or development.get('source_sha256')!=frozen['source']['sha256'] or development.get('protocol_sha256')!=digest(PROTOCOL) or len(development['rows'])!=6 or {(r['case'],r['arm']) for r in development['rows']}!=expected:raise ValueError('COMPLETE_SOURCE_BOUND_TUNING_REQUIRED')
    from connected_enterprise.verify import audit
    for row in development['rows']:
        registered=frozen['configs']['development'][row['case']][row['arm']]
        result=read(output/'private/development'/(row['case']+'-'+row['arm'])/'RESULT.json')
        if result['config']!=registered['config'] or result['seed']!=PROTOCOL['development_seed'] or result['arm']!=registered['engine_arm'] or result['source']!=frozen['source']:raise ValueError('TUNING_RESULT_NOT_REGISTERED')
        checked=audit(ROOT,frozen['manifests']['development'],result)
        if not checked['accepted'] or row!=public_row(registered['config'],'development',row['case'],row['arm'],result,checked,True):raise ValueError('TUNING_FINANCIAL_RESULT_CHANGED')


def choose(development):
    rows=development['rows'];expected={(case,str(share)) for case in PROTOCOL['cases'] for share in SHARES}
    if development['status']!='COMPLETED' or len(rows)!=6 or {(r['case'],r['arm']) for r in rows}!=expected:raise ValueError('COMPLETE_REGISTERED_TUNING_REQUIRED')
    scores={share:tuple(r['summary']['profit'] for r in rows if r['arm']==str(share)) for share in SHARES}
    selected=max(SHARES,key=lambda share:(min(scores[share]),sum(scores[share]),-abs(share-5000),-share))
    cost=sum(r['summary']['expenses'] for r in rows)
    quotient,remainder=divmod(cost,len(PROTOCOL['cases']))
    return {'schema':'comparator050-selected-share/v1','selected_acquisition_bps':selected,'selected_capacity_bps':10000-selected,
        'selection_rule':PROTOCOL['fixed_split']['selection_rule'],'scores':{str(s):{'minimum_profit':min(scores[s]),'sum_profit':sum(scores[s])} for s in SHARES},
        'development_public_sha256':digest(development),'tuning_expense_microUSD':cost,
        'evaluation_cost_attribution':{case:quotient+(1 if i<remainder else 0) for i,case in enumerate(PROTOCOL['cases'])},
        'account_balances_transferred':False,'study_financial_sum':None,'actual_external_tuning_bill':None,'authority':[]}


def selected_evaluation(output,frozen):
    development=read(output/'DEVELOPMENT.json');selection=read(output/'SELECTED.json')
    verify_development(output,frozen,development)
    if selection!=choose(development) or development['source_sha256']!=frozen['source']['sha256'] or development['protocol_sha256']!=digest(PROTOCOL):raise ValueError('FROZEN_SELECTION_CHANGED')
    evaluation=copy.deepcopy(frozen['configs']['evaluation'])
    for case in PROTOCOL['cases']:
        cfg,_,arm=configuration(frozen['manifests']['evaluation'],case,'tuned_fixed_split',output/'source',split_bps=selection['selected_acquisition_bps'],tuning_charge=selection['evaluation_cost_attribution'][case])
        evaluation[case]['tuned_fixed_split']={'config':cfg,'engine_arm':arm}
    expected={'source_sha256':frozen['source']['sha256'],'protocol_sha256':digest(PROTOCOL),'selection':selection,'configs':evaluation}
    path=output/'EVALUATION_FROZEN.json'
    if path.exists():
        if read(path)!=expected:raise ValueError('EVALUATION_FREEZE_CHANGED')
    else:write(path,expected)
    return evaluation,selection


def operate(output,phase,max_events=None):
    if max_events is not None and (type(max_events) is not int or max_events<1):raise ValueError('POSITIVE_CHECKPOINT_EVENT_COUNT_REQUIRED')
    output,frozen=plan(output)
    if phase=='development':
        configs=frozen['configs']['development'];arms=tuple(str(s) for s in SHARES);seed=PROTOCOL['development_seed'];public=output/'DEVELOPMENT.json'
    else:
        configs,selection=selected_evaluation(output,frozen);arms=ARMS;seed=PROTOCOL['seed'];public=output/'PUBLIC.json'
    manifest=frozen['manifests'][phase]
    report=read(public) if public.exists() else {'protocol_sha256':digest(PROTOCOL),'source_sha256':frozen['source']['sha256'],'phase':phase,'rows':[],'status':'RUNNING','authority':[]}
    if report['source_sha256']!=frozen['source']['sha256'] or report['protocol_sha256']!=digest(PROTOCOL) or report['phase']!=phase:raise ValueError('RECORDED_COMPARATOR_IDENTITY_CHANGED')
    from connected_enterprise.engine import run_world
    from connected_enterprise.verify import audit
    validate_recorded_cells(output,frozen,phase,configs,arms,seed,report)
    completed={(r['case'],r['arm']) for r in report['rows']};start,cpu=time.monotonic(),time.process_time()
    previous_wall=report.get('wall_seconds',0);previous_cpu=report.get('process_cpu_seconds',0)
    for case in PROTOCOL['cases']:
        for arm in arms:
            if (case,arm) in completed:continue
            registered=configs[case][arm];folder=output/'private'/phase/(case+'-'+arm)
            result=run_world(ROOT,manifest,registered['config'],seed,registered['engine_arm'],folder,source=frozen['source'],stop_after_events=max_events)
            if not result['complete']:
                report.update(checkpoint=str(folder/'STATE.json'),status='INCOMPLETE',wall_seconds=previous_wall+time.monotonic()-start,process_cpu_seconds=previous_cpu+time.process_time()-cpu);write(public,report);return report
            again=run_world(ROOT,manifest,registered['config'],seed,registered['engine_arm'],folder,source=frozen['source'])
            result=persisted_after_resume(result,again,folder)
            checked=audit(ROOT,manifest,result)
            if not checked['accepted']:raise ValueError('NATIVE_AUDIT_OR_SAME_ACCOUNT_RESUME_FAILED')
            if arm=='capability_only' and any(i['kind']=='acquisition' for i in result['investments']):raise ValueError('CAPABILITY_ONLY_ACQUISITION_ABLATION_FAILED')
            if arm=='commerce_only' and any(i['kind']=='capacity' for i in result['investments']):raise ValueError('COMMERCE_ONLY_CAPACITY_ABLATION_FAILED')
            report['rows'].append(public_row(registered['config'],phase,case,arm,result,checked,True))
            report['wall_seconds']=previous_wall+time.monotonic()-start;report['process_cpu_seconds']=previous_cpu+time.process_time()-cpu;write(public,report)
    report.pop('checkpoint',None);report['status']='COMPLETED';write(public,report)
    if phase=='development':
        verify_development(output,frozen,report)
        selection=choose(report);path=output/'SELECTED.json'
        if path.exists() and read(path)!=selection:raise ValueError('TUNING_CANNOT_RESELECT_AFTER_EVALUATION')
        if not path.exists():write(path,selection)
        selected_evaluation(output,frozen)
    else:
        report['five_policy_comparison_complete']=True;report['selection_sha256']=digest(selection);write(public,report)
    return report


def verify(output):
    output,frozen=plan(output);evaluation,selection=selected_evaluation(output,frozen)
    from connected_enterprise.verify import audit
    totals={}
    for phase,configs,arms,seed,name in [('development',frozen['configs']['development'],tuple(str(s) for s in SHARES),PROTOCOL['development_seed'],'DEVELOPMENT.json'),('evaluation',evaluation,ARMS,PROTOCOL['seed'],'PUBLIC.json')]:
        report=read(output/name);expected={(case,arm) for case in PROTOCOL['cases'] for arm in arms}
        if report['status']!='COMPLETED' or len(report['rows'])!=len(expected) or {(r['case'],r['arm']) for r in report['rows']}!=expected:raise ValueError('COMPLETE_COMPARATOR_COVERAGE_REQUIRED')
        if phase=='evaluation' and (report.get('five_policy_comparison_complete') is not True or report.get('selection_sha256')!=digest(selection)):raise ValueError('FROZEN_TUNING_NOT_BOUND_TO_EVALUATION')
        for row in report['rows']:
            registered=configs[row['case']][row['arm']];result=read(output/'private'/phase/(row['case']+'-'+row['arm'])/'RESULT.json')
            if result['config']!=registered['config'] or result['seed']!=seed or result['arm']!=registered['engine_arm'] or result['source']!=frozen['source']:raise ValueError('REGISTERED_NATIVE_RESULT_CHANGED')
            checked=audit(ROOT,frozen['manifests'][phase],result)
            if not checked['accepted'] or row!=public_row(registered['config'],phase,row['case'],row['arm'],result,checked,True):raise ValueError('NATIVE_COMPARATOR_PUBLIC_RESULT_CHANGED')
        totals[phase]=len(expected)
    if sum(selection['evaluation_cost_attribution'].values())!=selection['tuning_expense_microUSD']:raise ValueError('TUNING_COST_ALLOCATION_NOT_EXACT')
    value={'accepted':True,'worlds':totals,'five_policy_comparison_complete':True,'source_sha256':frozen['source']['sha256'],'selection':selection,'public_sha256':digest(read(output/'PUBLIC.json')),'authority':[]}
    write(output/'VERIFY.json',value);return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','tune','run','verify'))
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-events', type=int)
    args = parser.parse_args()
    result = prepare(args.output) if args.command=='prepare' else operate(args.output,'development' if args.command=='tune' else 'evaluation',args.max_events) if args.command in {'run','tune'} else verify(args.output)
    print(json.dumps({'command':args.command,'status':result.get('status'),'accepted':result.get('accepted'),'available_worlds':result.get('available_worlds'),'next':result.get('next'),'output':str(args.output)},sort_keys=True))


if __name__ == '__main__':
    main()
