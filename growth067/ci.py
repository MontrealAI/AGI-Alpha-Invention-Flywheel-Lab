"""Finite hosted stages; publishes only explicitly selected key-free evidence."""
import argparse,json,shutil
from pathlib import Path
from .campaign import development_cases,holdout_cases,select,run_case
from .run import save
from commercial.ledger import strict_json,digest

def pack(root,output,evidence,case,result):
    dest=evidence/case['id'];dest.mkdir(parents=True)
    for name in ['manifest.json','result.json','public-export.json']:
        shutil.copyfile(output/case['id']/name,dest/name)
    manifest=strict_json((dest/'manifest.json').read_bytes())
    for job in manifest['jobs']:
        for path in [job['delivery_path'],job['delivery_path'].replace('/deliveries/','/decisions/')]:
            source=root/path
            if source.exists():
                target=dest/'source'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    # Whitelist above excludes private native recovery/signing authority.
    save(dest/'PACKAGE.json',{'case':case,'result_sha256':digest(result),'private_account_included':False})

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['plan','case','select','summarize']);p.add_argument('--case-json');p.add_argument('--input',type=Path,default=Path('incoming'));p.add_argument('--output',type=Path,default=Path('states'));p.add_argument('--evidence',type=Path,default=Path('public-evidence'));a=p.parse_args();root=Path('.').resolve()
    if a.stage=='plan':print(json.dumps({'include':development_cases()},separators=(',',':')));return
    if a.stage=='case':
        case=json.loads(a.case_json);result=run_case(root,a.output,case);pack(root,a.output,a.evidence,case,result)
        print(json.dumps({'case':case,'annual':result['annual'],'audit':result['operating_audit'],'attainment':result['attainment']}));return
    if a.stage=='select':
        results={path.parent.name:strict_json(path.read_bytes()) for path in a.input.rglob('result.json')}
        selected=select(results);save(a.evidence/'LOCKED_SELECTION.json',selected)
        print(json.dumps({'include':holdout_cases(selected)},separators=(',',':')));return
    results={path.parent.name:strict_json(path.read_bytes()) for path in a.input.rglob('result.json')}
    frontier={}
    for world in ['favorable','central','adverse']:
        rows=[{'case':key,'capital_usd':r['configuration']['opening']//1_000_000,'annual_profit_microUSD':r['annual']['trailing_365_day_profit_microUSD'],'attainment':r['attainment']} for key,r in sorted(results.items()) if (key.startswith('frontier-') or key==f'holdout-{world}-10') and r['configuration']['world']==world]
        hit=[x['capital_usd'] for x in rows if x['attainment']['first_daily_attainment'] is not None]
        frontier[world]={'all_tested':rows,'minimum_tested_attaining_capital_usd':min(hit) if hit else None,'policy_reselected':False,'financing_secured':False}
    save(a.evidence/'HELDOUT_CAPITAL_FRONTIERS.json',frontier)
    save(a.evidence/'HOLDOUT_SUMMARY.json',{key:{'configuration':r['configuration'],'summary':r['summary'],'annual':r['annual'],'attainment':r['attainment'],'economic_profit':r['rolling365_economic_profit_microUSD'],'audit':r['operating_audit']} for key,r in sorted(results.items())})

if __name__=='__main__':main()
