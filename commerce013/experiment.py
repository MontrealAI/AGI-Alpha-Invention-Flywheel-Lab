"""Native-earned distribution test; synthetic buyers, no customer-sales inference."""
from __future__ import annotations
import argparse, copy, hashlib, json, math, tempfile, time
from pathlib import Path
from enterprise.growth012 import default_config, run_growth
from enterprise.model import money
from enterprise.services import prepare_services

SCHEMA = 'agi-alpha/commerce013-native-distribution/v1'
ARMS = {
    'retain_existing_channel': {'slots': 0, 'setup_usd': 0, 'daily_usd': 0},
    'buy_small_channel': {'slots': 2, 'setup_usd': 4, 'daily_usd': .2},
    'buy_large_channel': {'slots': 5, 'setup_usd': 8, 'daily_usd': .4},
}
FAMILIES = {
    'ordinary': {'market':'ordinary', 'weight_bps':2500, 'channel_delivery_fraction':1},
    'price_war': {'market':'price_war', 'weight_bps':2000, 'channel_delivery_fraction':1},
    'differentiation': {'market':'differentiation', 'weight_bps':2000, 'channel_delivery_fraction':1},
    'correlated_shock': {'market':'correlated_shock', 'weight_bps':1500, 'channel_delivery_fraction':1},
    'failed_channel': {'market':'ordinary', 'weight_bps':2000, 'channel_delivery_fraction':0},
}
DEV_SEEDS = (12001,12002)
CONFIRMATION_SEEDS = (14013,14017,14021,14027)


def canonical(x): return json.dumps(x, sort_keys=True, separators=(',',':'), allow_nan=False).encode()
def sha(x): return hashlib.sha256(canonical(x)).hexdigest()


def validate_design(arms=ARMS, families=FAMILIES):
    if not isinstance(arms,dict) or not arms or 'retain_existing_channel' not in arms:
        raise ValueError('NO_PURCHASE_CONTROL_REQUIRED')
    if not isinstance(families,dict) or set(families)!=set(FAMILIES):
        raise ValueError('FROZEN_MARKET_FAMILY_REQUIRED')
    if sum(f['weight_bps'] for f in families.values())!=10000:
        raise ValueError('MODEL_WEIGHTS_NOT_NORMALIZED')
    for a in arms.values():
        if not isinstance(a,dict) or set(a)!= {'slots','setup_usd','daily_usd'}:
            raise ValueError('CHANNEL_CONTRACT_SCHEMA')
        if type(a['slots']) is not int or a['slots']<0 or a['slots']>20:
            raise ValueError('INTEGER_ADDITIONAL_CONTACT_SLOTS_REQUIRED')
        for name in ['setup_usd','daily_usd']:
            if type(a[name]) not in (float,int) or not math.isfinite(a[name]) or a[name]<0:
                raise ValueError('FINITE_NONNEGATIVE_CHANNEL_COST_REQUIRED')
    for f in families.values():
        if type(f['channel_delivery_fraction']) not in (float,int) or not 0<=f['channel_delivery_fraction']<=1:
            raise ValueError('DECLARED_CHANNEL_REALIZATION_REQUIRED')
        if type(f['weight_bps']) is not int or f['weight_bps']<=0:
            raise ValueError('EXPLICIT_MODEL_WEIGHTS_REQUIRED')


def configured(base, family, arm):
    validate_design()
    if not isinstance(base,dict) or family not in FAMILIES or arm not in ARMS:
        raise ValueError('FROZEN_ARM_AND_FAMILY_REQUIRED')
    f,a=FAMILIES[family],ARMS[arm]
    config=copy.deepcopy(base)
    config['market_regime']=f['market']
    config['contacts_per_day'] = base['contacts_per_day'] + int(math.floor(a['slots']*f['channel_delivery_fraction']))
    config['intervention_setup_cost'] = money(a['setup_usd'])
    config['intervention_daily_cost'] = money(a['daily_usd'])
    return config


def world_row(root, manifest, base, seed, family, arm):
    c=configured(base,family,arm)
    r=run_growth(root,manifest,c,seed,'joint',persist=False)
    proof=r['native_replay']
    if proof.get('accepted') is not True or r['actual_revenue']!=0:
        raise ValueError('NATIVE_SIMULATED_AUDIT_REQUIRED')
    moneyfields=r['metrics']
    return {'family':family,'arm':arm,'seed':seed,'config_sha256':sha(c),
            'manifest_sha256':r['manifest_sha256'],
            'native_actions_sha256':r['ledger']['actions_sha256'],
            'native_audit_scope':proof['scope'],
            'contacts':r['counts']['contacts'],'won':r['counts']['won'],
            'paid':r['counts']['paid'],'executed_accepted_work':r['metrics']['qualified_unique_work_executed'],
            'collections_microUSD':moneyfields['collections_microUSD'],
            'profit_microUSD':moneyfields['profit_microUSD'],
            'unrestricted_earned_microUSD':moneyfields['unrestricted_earned_microUSD'],
            'earned_funded_deliveries':moneyfields['earned_funded_deliveries'],
            'cash_survived':r['cash_survival'],
            'scope':'NATIVE_AUDITED_SIMULATED_ENGINEERING_ONLY',
            'actual_sales':0,'observed_acquisition_rate':None}


def summarize(rows):
    index={(x['family'],x['seed'],x['arm']):x for x in rows}
    selected=sorted({x['arm'] for x in rows});cases=sorted({(x['family'],x['seed']) for x in rows})
    out={}
    for arm in selected:
        deltas=[]
        family_rows={}
        for family,seed in cases:
            a=index.get((family,seed,arm));b=index.get((family,seed,'retain_existing_channel'))
            if a is None or b is None:
                raise ValueError('MATCHED_NATIVE_CONTROL_MISSING')
            delta=a['profit_microUSD']-b['profit_microUSD']
            deltas.append((FAMILIES[family]['weight_bps'],delta))
            family_rows.setdefault(family,[]).append(delta)
        value=sum(weight*sum(family_rows[f])/len(family_rows[f]) for f,weight in ((k,FAMILIES[k]['weight_bps']) for k in FAMILIES)) / 10000
        out[arm]={'assumption_weighted_mean_profit_advantage_microUSD':value,
                  'matched_profit_deltas_microUSD_by_family':family_rows,
                  'cash_survival_fraction':sum(x['cash_survived'] for x in rows if x['arm']==arm)/len(cases),
                  'family_failure_signs':{k: sum(x<=0 for x in arr) for k,arr in family_rows.items()},
                  'units':'simulated_microUSD'}
    return out


def choose_dev(rows):
    scores=summarize(rows)
    allowed=[(x['assumption_weighted_mean_profit_advantage_microUSD'],name) for name,x in scores.items() if x['cash_survival_fraction']>=.95]
    selected=max(allowed,default=(0,'retain_existing_channel'))
    if selected[0]<=0: selected=(0,'retain_existing_channel')
    return {'selected':selected[1], 'risk_criterion':'>=95% cash survival in development scenarios',
            'modeled_expected_incremental_profit_microUSD':selected[0],
            'source':'AUTHOR_PRIORS_AND_DEVELOPMENT_NATIVE_SIMULATION_NOT_EMPIRICAL_DEMAND'}


def base_config():
    c=default_config()
    c.update(horizon_hours=96,customer_pool=6,contacts_per_day=1,
             initial_capacity=4,maximum_capacity=4,opening=money(10000),
             setup_cost=money(1), daily_overhead=money(.01),
             repeat_interval_hours=24, settlement_hours=12,sales_cycle_hours=1,
             rival_update_hours=24, choice_model='utility',human_ai_complete_cost_ratio=1.2)
    return c


def execute(root, manifest, outdir, *, only_confirm=False, locked_selection=None):
    validate_design()
    outdir=Path(outdir)
    if outdir.exists(): raise FileExistsError('REFUSE_OVERWRITE_PRIOR_EVIDENCE')
    outdir.mkdir(parents=True)
    source={'design_schema':SCHEMA,'arm_contracts':ARMS,'market_families':FAMILIES,
            'development_seeds':DEV_SEEDS,'confirmation_seeds':CONFIRMATION_SEEDS,
            'fixed_config':base_config(),'manifest_sha256':sha(manifest)}
    source['identity_sha256']=sha(source)
    (outdir/'FROZEN.json').write_bytes(canonical(source)+b'\n')
    started=time.monotonic();development=[]
    if not only_confirm:
        for fam in FAMILIES:
            for seed in DEV_SEEDS:
                for arm in ARMS:
                    development.append(world_row(root,manifest,source['fixed_config'],seed,fam,arm))
        (outdir/'DEVELOPMENT.json').write_bytes(canonical(development)+b'\n')
        chosen=choose_dev(development)
    else:
        if locked_selection not in ARMS: raise ValueError('LOCKED_DEVELOPMENT_SELECTION_REQUIRED')
        chosen={'selected':locked_selection,'source':'IMPORTED_PREDECLARED_DEVELOPMENT_SELECTION'}
    (outdir/'DECISION.json').write_bytes(canonical(chosen)+b'\n')
    confirmation=[]
    for fam in FAMILIES:
        for seed in CONFIRMATION_SEEDS:
            for arm in dict.fromkeys(['retain_existing_channel',chosen['selected']]):
                confirmation.append(world_row(root,manifest,source['fixed_config'],seed,fam,arm))
    analysis=summarize(confirmation)
    result={'schema':SCHEMA,'source':source,'decision':chosen,'development_count':len(development),
            'confirmation_count':len(confirmation), 'confirmation':analysis,
            'first_billion_trailing_revenue':'NOT_EVALUABLE_AT_96_HOUR_NATIVE_COHORT',
            'customer_market_origin':'SYNTHETIC_SIX_BUYERS_ONLY',
            'workload_stock':'PREQUALIFIED_REPLAYED_SYNTHETIC_ARTIFACTS_NOT_REAL_CUSTOMER_DEMAND',
            'unreached_milestones_included':True,'actual_collected_usd':0,
            'observed_business_flywheel':'NOT_ESTABLISHED',
            'conditional_growth_scope':'PILOT_FINITE_NATIVE_4_DAYS',
            'market_rate_calibration':'UNOBSERVED',
            'elapsed_seconds':time.monotonic()-started}
    (outdir/'RESULT.json').write_bytes(canonical(result)+b'\n')
    (outdir/'CONFIRMATION.json').write_bytes(canonical(confirmation)+b'\n')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='commerce013-fixture-',dir=root) as d:
        manifest=prepare_services(root,str((Path(d)/'qualified').relative_to(root)))
        result=execute(root,manifest,args.output)
    print(json.dumps({k:result[k] for k in ('decision','development_count','confirmation_count','first_billion_trailing_revenue')},indent=2))

if __name__=='__main__':main()
