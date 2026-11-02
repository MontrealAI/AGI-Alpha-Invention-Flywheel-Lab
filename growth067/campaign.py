"""Finite63-case campaign; selection is locked before any holdout outcome."""
from pathlib import Path
import argparse,json
from commercial.ledger import digest,strict_json
from .registration import design
from .run import run,save


def development_cases():
    r=design()
    return [{'id':f'dev-{capital}-{policy}','world':'central','seed':670001,'capital':capital,'unit_cost':10,'policy_name':policy,'funding_mode':'capital_available','grow':True} for capital in r['capital_candidates_usd'] for policy in sorted(r['allocation_policies'])]


def select(results):
    expected={c['id'] for c in development_cases()}
    if set(results)!=expected:raise ValueError('ALL24_DEVELOPMENT_RESULTS_REQUIRED_NO_SEARCH_UNTIL_WIN')
    rows=[]
    for ident,r in results.items():
        if not r.get('operating_audit',{}).get('accepted'):raise ValueError('AUDITED_DEVELOPMENT_REQUIRED')
        cfg=r['configuration'];rows.append({'case':ident,'capital_usd':cfg['opening']//1_000_000,'policy_name':cfg['policy_name'],'accounting_profit_microUSD':r['annual']['trailing_365_day_profit_microUSD'],'economic_profit_microUSD':r['rolling365_economic_profit_microUSD']['0.08'],'attainment':r['attainment'],'result_sha256':digest(r)})
    winner=min([x for x in rows if x['policy_name']=='finite_game'],key=lambda x:(-x['economic_profit_microUSD'],x['capital_usd'],x['policy_name']))
    hit=[x['capital_usd'] for x in rows if x['policy_name']=='finite_game' and x['attainment']['first_daily_attainment'] is not None]
    return {'schema':'growth067/locked-development-selection/v1','winner':winner,'all_development':rows,'minimum_tested_attaining_capital_usd':min(hit) if hit else None,'capital_boundary':winner['capital_usd'] in {min(design()['capital_candidates_usd']),max(design()['capital_candidates_usd'])},'holdout_reselection':False,'calibration':'ONE_AUTHORED_DEVELOPMENT_SEED_NOT_GLOBAL_OPTIMUM'}


def holdout_cases(selection):
    w=selection['winner'];capital=w['capital_usd'];policy=w['policy_name'];rows=[]
    for world,seed in zip(['favorable','central','adverse'],[679101,679102,679103]):
        for cost in [5,10,15]:rows.append({'id':f'holdout-{world}-{cost}','world':world,'seed':seed,'capital':capital,'unit_cost':cost,'policy_name':policy,'funding_mode':'capital_available','grow':True})
        for level in design()['capital_candidates_usd']:
            if level!=capital:
                rows.append({'id':f'frontier-{world}-{level}','world':world,'seed':seed,'capital':level,'unit_cost':10,'policy_name':policy,'funding_mode':'capital_available','grow':True})
        rows.append({'id':f'control100k-{world}','world':world,'seed':seed,'capital':100_000,'unit_cost':10,'policy_name':'balanced','funding_mode':'capital_available','grow':True})
    for name,world,mode,grow in [('earned-only','central','earned_only',True),('no-growth','central','capital_available',False),('no-demand','no_demand','capital_available',True),('invalid-quality','invalid_quality','capital_available',True),('capacity-outage','capacity_outage','capital_available',True)]:
        rows.append({'id':'control-'+name,'world':world,'seed':679102,'capital':capital,'unit_cost':10,'policy_name':policy,'funding_mode':mode,'grow':grow})
    for month in [3,6,18,24]:rows.append({'id':f'compression-{month}','world':f'compression_{month}','seed':679102,'capital':capital,'unit_cost':10,'policy_name':policy,'funding_mode':'capital_available','grow':True})
    for world in ['legacy_demand','aggressive_allocation','volume_automation59']:
        rows.append({'id':'matched-'+world,'world':world,'seed':679102,'capital':capital,'unit_cost':10,'policy_name':policy,'funding_mode':'capital_available','grow':True})
    return rows


def run_case(root,out,case):
    return run(root,out/case['id'],case['world'],case['seed'],case['capital'],case['unit_cost'],case['grow'],case['funding_mode'],case['policy_name'])


def campaign(root,out):
    if out.exists():raise ValueError('NEW_CAMPAIGN_DIRECTORY_REQUIRED')
    out.mkdir(parents=True);results={}
    for case in development_cases():
        results[case['id']]=run_case(root,out,case)
        save(out/'development-progress.json',{k:{'summary':v['summary'],'annual':v['annual']} for k,v in results.items()})
    selection=select(results);save(out/'LOCKED_SELECTION.json',selection)
    # No holdout result exists or enters select above.
    held={}
    for case in holdout_cases(selection):held[case['id']]=run_case(root,out,case)
    report={'registration_sha256':digest(design()),'selection':selection,'holdouts':{k:{'configuration':v['configuration'],'summary':v['summary'],'annual':v['annual'],'economic_profit_microUSD':v['rolling365_economic_profit_microUSD'],'attainment':v['attainment'],'operating_audit':v['operating_audit']} for k,v in held.items()},'separate_accounts_not_pooled':True,'case_count':len(results)+len(held)}
    save(out/'SUMMARY.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=campaign(a.root,a.output);print(json.dumps({'case_count':r['case_count'],'winner':r['selection']['winner']}))
