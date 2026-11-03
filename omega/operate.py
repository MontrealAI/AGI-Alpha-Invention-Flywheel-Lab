"""Fresh native annual realizations of a preregistered hypothetical strategy game."""
from pathlib import Path
import hashlib
import json
import shutil
from commercial.ledger import canonical, digest, strict_json
from connected_enterprise.finance import JournalAccount, source_paths_for_manifest, audit_journal
from connected_enterprise.scale import trailing_profit
from experiments.commerce006 import PINS
from omega import product, strategy
MODES=('expected','no_research','nonentry','robust','static_all')
CENT=10000

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(canonical(value)+b'\n')

def hashes(root):
    paths=set(source_paths_for_manifest({'schema':product.SCHEMA}))|set(PINS)|{'omega/strategy.py','omega/operate.py'}
    return {p:hashlib.sha256((Path(root)/p).read_bytes()).hexdigest() for p in sorted(paths)}

def orders(plan):
    return [(r,o) for r in plan['trace'] for o in r['orders'] if o['status'] in {'accepted','rejected_refunded'}]

def costs(game):
    return {**{p:{'fulfillment':game.costs.native_order_cents[i]*CENT,'processing':game.costs.processing_cents[i]*CENT} for i,p in enumerate(strategy.PRODUCTS)},'group_session':{'prepaid_by_operating_policy':0}}

def fixed(index,row):
    if row['action']['kind']=='research':return [(f'step{index}:research',row['cost_cents']*CENT)]
    if row['action']['kind']=='operate':return [(f'step{index}:{k}',row[k]*CENT) for k in ('build_cost_cents','outreach_cost_cents','session_cost_cents')]
    return []

def expected_commands(plan,manifest,source):
    commands=[];paid=set();pending=[];oi=0
    def add(op,args,hour):commands.append((op,args,hour))
    for si,row in enumerate(plan['trace']):
        hour=row['hour']
        for cid,amount in fixed(si,row):add('cost',{'id':cid,'amount':amount},hour)
        for order in row['orders']:
            if order['status'] not in {'accepted','rejected_refunded'}:continue
            ident=f'order{oi}';buyer=f'synthetic{oi}';job=manifest['jobs'][oi];price=order['price_cents']*CENT
            for cid,amount in product.cost_rows(job,ident,manifest['costs']):
                if cid not in paid:add('cost',{'id':cid,'amount':amount},hour);paid.add(cid)
            terms=product.terms_for(manifest,ident,job['product'],hour)
            add('register_terms',{'id':ident+':terms','terms':terms},hour)
            add('wallet',{'buyer':buyer,'amount':price},hour)
            add('offer',{'id':ident,'buyer':buyer,'price':price,'job_id':job['id'],'deadline':hour+24,'terms_id':ident+':terms'},hour)
            actions=['consent','fund','prepare','release'] if order['status']=='accepted' else ['consent','fund','refund']
            for action in actions:
                args={'id':ident,'action':action,'event_id':ident+':'+action}
                if action=='prepare':args['artifact_sha256']=digest(product.delivery(source,manifest,job['id']))
                add('event',args,hour)
            if order['status']=='accepted':pending.append((ident,terms))
            oi+=1
        if row['action']['kind']=='operate':
            maturity=row['maturity_hour']
            for ident,terms in list(pending):
                if maturity>terms['maturity_day']:
                    add('mature',{'id':ident,'event_id':'maturity:'+ident+':'+digest(terms)[:20]},maturity)
                    pending.remove((ident,terms))
    add('cost',{'id':'annual-endpoint','amount':0},8759)
    return commands

def derive(record,manifest,plan,*,source,game):
    if manifest['costs']!=costs(game) or manifest['claim_window_hours']!=720 or manifest['residual_bps']!=100:raise ValueError('REGISTERED_COSTS_OR_TERMS_CHANGED')
    audit=audit_journal(record,root=source,manifest=manifest)
    cfg=record['ledger']['config']
    if cfg['opening']!=game.capital_cents*CENT or cfg['working']!=0 or cfg['contract']!='omega-policy:'+digest(plan):raise ValueError('FRESH_REGISTERED_ACCOUNT_REQUIRED')
    events=record['ledger']['actions'];wanted=orders(plan)
    if any(e['after']['expensePaid']-e['before']['expensePaid']!=e['args']['amount'] for e in events if e['op']=='cost'):raise ValueError('POLICY_COST_INCURRED_NOT_FULLY_PAID')
    if [(e['op'],e['args'],e['day']) for e in events]!=expected_commands(plan,manifest,source):raise ValueError('EXACT_POLICY_NATIVE_SEQUENCE_CHANGED')
    expected=[(cid,amount,r['hour']) for i,r in enumerate(plan['trace']) for cid,amount in fixed(i,r)]
    for i,(r,o) in enumerate(wanted):expected += [(cid,amount,r['hour']) for cid,amount in product.cost_rows(manifest['jobs'][i],f'order{i}',manifest['costs'])]
    expected.append(('annual-endpoint',0,8759))
    actual=[(a['args']['id'],a['args']['amount'],a['day']) for a in events if a['op']=='cost']
    if sorted(actual)!=sorted(set(expected)):raise ValueError('COMPLETE_POLICY_COST_SEQUENCE_CHANGED')
    offers=[a for a in events if a['op']=='offer']
    if len(offers)!=len(wanted):raise ValueError('POLICY_ORDER_COUNT_CHANGED')
    for i,(a,(r,o)) in enumerate(zip(offers,wanted)):
        if a['day']!=r['hour'] or a['args']!={'id':f'order{i}','buyer':f'synthetic{i}','price':o['price_cents']*CENT,'job_id':manifest['jobs'][i]['id'],'deadline':r['hour']+24,'terms_id':f'order{i}:terms'}:raise ValueError('POLICY_ORDER_SEQUENCE_CHANGED')
        actions=[e['args']['action'] for e in events if e['op']=='event' and e['args']['id']==f'order{i}']
        if actions!=(['consent','fund','prepare','release'] if o['status']=='accepted' else ['consent','fund','refund']):raise ValueError('POLICY_ACCEPTANCE_SEQUENCE_CHANGED')
    if any(a['op'] not in {'cost','wallet','offer','register_terms','event','mature'} for a in events):raise ValueError('UNREGISTERED_NATIVE_OPERATION')
    summary=record['ledger']['summary']
    if summary['profit']!=plan['realized_cash_profit_cents']*CENT or summary['available']!=plan['working_available_cents']*CENT:raise ValueError('POLICY_NATIVE_FINANCE_DIVERGED')
    return {'world_id':plan['world_id'],'policy_mode':plan['policy_mode'],'trace':plan,'native_summary_microUSD':summary,
        'native_actions_sha256':record['ledger']['actions_sha256'],'public_record_sha256':digest(record),'manifest_sha256':digest(manifest),
        'native_audit_accepted':audit['accepted'],'trailing_profit':trailing_profit(record['ledger'],operating_end_hour=8760,operating_complete=True),
        'accepted_orders':sum(o['status']=='accepted' for _,o in wanted),'refunded_orders':sum(o['status']=='rejected_refunded' for _,o in wanted),
        'economic_profit_cents':plan['realized_profit_cents']}

def policy_tree(node):
    return {'action':node.action.as_dict(),'value':str(node.value),'support':list(node.support),
            'children':[[observation,policy_tree(child)] for observation,child in node.children.items()]}


def result_document(registration,reports):
    return {'schema':'omega/native-policy-result/v1','registration_sha256':digest(registration),
            'account_count':len(reports),'accounts':reports,
            'actual_complete_cost_profit_microUSD':None,'actual_taxes_microUSD':None,
            'actual_host_model_billing_microUSD':None,'three_billion_milestone_established':False,
            'scope':'Independent authored simulated scenarios; not real earned profit, observed demand, enforceability, or global optimality'}


def run(output,*,root=None,game=None,modes=MODES):
    root=Path(root or Path(__file__).resolve().parents[1]).resolve();output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    game=game or strategy.make_game();identity=hashes(root);source=output/'source'
    for name in identity:
        dest=source/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,dest)
    policies={mode:strategy.solve(game,mode) for mode in modes}
    registration={'policy_trees':{mode:policy_tree(p.root) for mode,p in policies.items()},'schema':'omega/native-policy-registration/v1','source_hashes':identity,'game':strategy.model_disclosure(game),
        'capital_cents':game.capital_cents,'founder_value_cents':game.founder_value_cents,'modes':list(modes),
        'scope':'INDEPENDENT_HYPOTHETICAL_ACCOUNTS_NOT_ONE_BUSINESS_OR_REAL_SALES'}
    write(output/'registration.json',registration);reports=[]
    for mode in modes:
        policy=policies[mode]
        for wi,world in enumerate(game.worlds):
            plan=strategy.execute(game,policy,world.id);wanted=orders(plan);ident=f'{mode}-{wi}';directory=output/'accounts'/ident;directory.mkdir(parents=True)
            products=[o['product'] for _,o in wanted] or ['self_hosted'];outcomes=[{'accepted':o['status']=='accepted'} for _,o in wanted] or [{}]
            sessions=[f'quarter{r["quarter"]}' if o['product']=='group_webinar' else None for r,o in wanted] or [None]
            manifest=product.prepare_manifest(source,source/'deliveries'/ident,jobs=products,outcomes=outcomes,costs=costs(game),session_ids=sessions,hypothetical_rights=True)
            write(directory/'manifest.json',manifest)
            with JournalAccount(source,manifest,directory/'account.sqlite',opening=game.capital_cents*CENT,working=0,contract='omega-policy:'+digest(plan)) as a:
                oi=0
                for si,row in enumerate(plan['trace']):
                    for cid,amount in fixed(si,row):
                        if a.snapshot()['summary']['available']<amount:raise ValueError('NATIVE_FIXED_COST_UNFUNDED')
                        a.cost(cid,amount,row['hour'])
                    for order in row['orders']:
                        if order['status'] not in {'accepted','rejected_refunded'}:continue
                        if a.snapshot()['summary']['available']<(order['price_cents']+order['cost_cents']+20)*CENT:raise ValueError('NATIVE_ORDER_PREFLIGHT_FAILED')
                        result=product.fulfill(a,source,manifest,manifest['jobs'][oi]['id'],order_id=f'order{oi}',buyer=f'synthetic{oi}',hour=row['hour'])
                        if result['status']!=('released' if order['status']=='accepted' else 'refunded'):raise ValueError('NATIVE_OUTCOME_DIVERGED')
                        oi+=1
                    if row['action']['kind']=='operate':a.advance_financial(row['maturity_hour'])
                    if a.snapshot()['summary']['available']!=row['mature_available_cents']*CENT:raise ValueError('QUARTER_NATIVE_AVAILABLE_DIVERGED')
                a.cost('annual-endpoint',0,8759);record=a.export();report=derive(record,manifest,plan,source=source,game=game)
            write(directory/'public.json',record);reports.append({'account':ident,**report})
    result=result_document(registration,reports)
    write(output/'result.json',result);return result

def replay(output):
    output=Path(output);registration=strict_json((output/'registration.json').read_bytes());source=output/'source'
    if hashes(source)!=registration['source_hashes'] or hashes(Path(__file__).resolve().parents[1])!=registration['source_hashes']:raise ValueError('REGISTERED_POLICY_SOURCE_CHANGED')
    d=registration['game'];cv={k:tuple(v) if isinstance(v,list) else v for k,v in d['cost_parameter_values'].items()}
    game=strategy.make_game(costs=strategy.Costs(**cv),capital_cents=registration['capital_cents'],founder_value_cents=registration['founder_value_cents'],quarters=d['horizon_quarters'])
    if canonical(strategy.model_disclosure(game))!=canonical(d):raise ValueError('REGISTERED_GAME_CHANGED')
    reports=[]
    for mode in registration['modes']:
        policy=strategy.solve(game,mode)
        if canonical(policy_tree(policy.root))!=canonical(registration['policy_trees'][mode]):raise ValueError('COMMON_CAUSAL_POLICY_CHANGED')
        for wi,world in enumerate(game.worlds):
            ident=f'{mode}-{wi}';directory=output/'accounts'/ident
            manifest=strict_json((directory/'manifest.json').read_bytes());record=strict_json((directory/'public.json').read_bytes())
            reports.append({'account':ident,**derive(record,manifest,strategy.execute(game,policy,world.id),source=source,game=game)})
    result=result_document(registration,reports)
    if canonical(result)!=canonical(strict_json((output/'result.json').read_bytes())):raise ValueError('NATIVE_POLICY_REPORT_CHANGED')
    return result

def replay_audit(output):
    result=replay(output)
    return {'accepted':True,'account_count':result['account_count'],'result_sha256':digest(result)}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--audit',action='store_true');args=p.parse_args()
    result=replay(args.output) if args.audit else run(args.output)
    print(json.dumps({'account_count':result['account_count'],'result_sha256':digest(result)}))
