"""Event-time operator; canonical native state is the only spending authority."""
from pathlib import Path
from math import ceil
import argparse,json,time
from commercial.ledger import canonical,digest,strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.scale import trailing_profit
from .registration import design
from .policy import initial_state,propose
from .native import Native,MICRO
from .money import floor_share,payment
from . import service
from .producer import reconcile
from .quality import public_packet
from .planning import expected_net

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);atomic_bytes(path,canonical(value))

def run(root,output,world_name,seed,opening_usd,unit_cost,grow=True,funding_mode="capital_available",policy_name="balanced"):
    root=Path(root).resolve();output=Path(output).resolve();reg=design()
    if output.exists():raise ValueError('FRESH_SEPARATE_REGISTERED_ACCOUNT_REQUIRED')
    if reg['status']!='FROZEN':raise ValueError('ECONOMIC_REGISTRATION_NOT_FROZEN')
    if world_name not in reg['worlds'] or opening_usd not in reg['capital_candidates_usd'] or unit_cost not in reg['resource_cases_usd'] or seed not in reg['development_seeds']+reg['holdout_seeds']:raise ValueError('REGISTERED_CASE_REQUIRED')
    world=reg['worlds'][world_name];months=(reg['operating_days']-1)//reg['month_days']+1
    runid=f'{output.name}-{world_name}-{seed}-{opening_usd}-{unit_cost}-{int(grow)}-{funding_mode}-{policy_name}'
    cfg={'mode':'ECONOMIC','world':world_name,'seed':seed,'opening':opening_usd*MICRO,'unit_cost':unit_cost,'grow':grow,'funding_mode':funding_mode,'policy_name':policy_name}
    manifest=service.manifest(root,runid,months,cfg);output.mkdir(parents=True);save(output/'manifest.json',manifest)
    n=Native(root,manifest,output/'account.json',opening_usd*MICRO);pending=[];state=initial_state();rows=[];tax_paid=0
    start=time.monotonic();cpu=time.process_time()
    try:
        receipt=n.spend('initial-development',int(reg['setup_usd']*MICRO),0,{'registration':digest(reg),'kind':'shared_development'},0,seed=True)
        if not receipt:raise ValueError('INITIAL_CAPITAL_CANNOT_FUND_SETUP')
        def settle(until):
            nonlocal pending,tax_paid
            ready=sorted([x for x in pending if x['hour']<=until],key=lambda x:(x['hour'],x['id']))
            pending=[x for x in pending if x['hour']>until]
            for x in ready:
                n.cost('processing-'+x['id'],x['payment_fee'],x['hour'])
                if x.get('refund'):n.refund(x['id'],x['hour'])
                else:n.release(x['id'],x['hour'])
            n.advance(until)
            pretax=n.summary()['profit']+tax_paid;due=max(0,floor_share(max(0,pretax),reg['tax_rate'])-tax_paid)
            if due:n.cost('tax-'+str(until),due,until);tax_paid+=due
        for month in range(months):
            hour=month*reg['month_days']*24;settle(hour)
            before=n.summary();proposal=propose(state,before,world,reg,seed,unit_cost,opening_usd*MICRO,grow=grow,funding_mode=funding_mode,policy_name=policy_name)
            snap=n.book.snapshot()
            decision={'native_sequence_before':snap['sequence'],'native_actions_before_sha256':snap['actions_sha256'],'state':state,'summary':before,'proposal':proposal,'native_before_sha256':digest(before),'previous_decision_sha256':digest(rows[-1]['decision']) if rows else None}
            decision_path=service.safe(root,manifest['jobs'][month]['delivery_path'].replace('/deliveries/','/decisions/'));save(decision_path,decision)
            costs=proposal['costs_microUSD'];funded=True;receipts={}
            for kind in ['capacity','acquisition','maintenance','resource','onboarding']:
                amount=costs[kind]
                if not amount:continue
                expected=expected_net(proposal,world,reg,unit_cost)
                receipt=n.spend(f'm{month}-{kind}',amount,hour,{'decision_sha256':digest(decision),'kind':kind,'registration_sha256':digest(reg)},expected,seed=(funding_mode=='capital_available' or month==0 or kind in {'maintenance','resource','onboarding'}))
                receipts[kind]=receipt
                if receipt is None:funded=False;break
            row={'decision':decision,'funding':receipts,'funded':funded,'actual_production':None,'native_after':None}
            if not funded:
                row['stop']='RESOURCE_RESERVATION_REFUSED_NO_RESEED';row['native_after']=n.summary();rows.append(row);break
            state=proposal['state_after'];count=proposal['collected_units']
            if proposal['chosen_orders']:
                job=manifest['jobs'][month];ident=job['id'];price=round(proposal['unit_price_usd']*MICRO)
                collection=hour+world['settlement_days']*24;maturity=collection+world['tail_days']*24
                path=service.safe(root,job['delivery_path'].replace('/deliveries/','/decisions/'));save(path,decision)
                failed=proposal['chosen_orders']-count
                if failed:
                    n.offer(ident+'-uncollected',ident,failed,price,hour+1,collection,maturity,round(world['residual_per_unit_usd']*MICRO))
                    pending.append({'id':ident+'-uncollected','hour':collection,'payment_fee':0,'refund':True})
                if not count:
                    row['native_after']=n.summary();rows.append(row);continue
                n.offer(ident,ident,count,price,hour+1,collection,maturity,round(world['residual_per_unit_usd']*MICRO))
                decision=strict_json(path.read_bytes());row['decision']=decision
                packet=public_packet(job['request']['actual_seed']);t=time.monotonic();c=time.process_time();actual=reconcile(packet)
                row['actual_production']={'wall_seconds':time.monotonic()-t,'cpu_seconds':time.process_time()-c,'actual_packets':1,'input_sha256':digest(packet),'output_sha256':digest(actual),'external_model_calls':0,'whole_agent_billing':None}
                artifact={'schema':'growth067/bulk-delivery/v1','request_sha256':digest(job['request']),'actual_output':actual,'modeled_fulfillment_count':count,'actual_template_count':1,'empirical_per_unit_acceptance':False,'market_receipt':proposal}
                n.prepare(ident,ident,artifact,hour+2)
                payment_unit=payment(price,world)
                pending.append({'id':ident,'hour':collection,'payment_fee':count*payment_unit})
            row['native_after']=n.summary();rows.append(row);save(output/'progress.json',{'completed_months':len(rows),'state':state,'pending':pending,'source_bound':True})
        end=reg['operating_days']*24;settle(end-1)
        operating_tape=n.export()['ledger'];complete=True  # terminal resource refusal is an observed stop, not a reset
        stopped=bool(rows and not rows[-1]['funded'])
        annual=trailing_profit(operating_tape,operating_end_hour=end,operating_complete=complete)
        terms=[a['args']['terms'] for a in n.export()['ledger']['actions'] if a['op']=='register_terms']
        drain=max([end]+[t['maturity_day']+1 for t in terms]);settle(drain)
        export=n.export();audit=n.audit()
        annual=trailing_profit(export['ledger'],operating_end_hour=end,operating_complete=complete)
        result={'scope':'NATIVE_SIM_BULK_CONTRACTS_ACTUAL_SAMPLE_WORK_NOT_MILLIONS_RENDERED','configuration':cfg,'complete':complete,'financially_stopped':stopped,'operating_end_hour':end,'settlement_drain_hour':drain,'annual':annual,'summary':n.summary(),'audit':audit,'rows':rows,'actual_packets':sum(bool(r['actual_production']) for r in rows),'modeled_collected_units':sum(r['decision']['proposal']['collected_units'] for r in rows if r['funded']),'opportunity_cost_sensitivity':{str(rate):opening_usd*rate*reg['operating_days']/365 for rate in reg['capital_opportunity_rates']},'wall_seconds':time.monotonic()-start,'cpu_seconds':time.process_time()-cpu,'actual_model_billing':None}
        from .audit import audit as audit_operation,daily_attainment
        result['rolling365_economic_profit_microUSD']={str(rate):annual['trailing_365_day_profit_microUSD']-floor_share(opening_usd*MICRO,rate) for rate in reg['capital_opportunity_rates']}
        result['attainment']=daily_attainment(export['ledger'],end,reg['primary_target_trailing365_profit_usd']*MICRO)
        result['operating_audit']=audit_operation(root,manifest,result,export)
        save(output/'public-export.json',export);save(output/'result.json',result);return result
    finally:n.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--output',type=Path,required=True);p.add_argument('--world',required=True);p.add_argument('--seed',type=int,required=True);p.add_argument('--capital',type=int,required=True);p.add_argument('--unit-cost',type=int,required=True);p.add_argument('--no-growth',action='store_true');a=p.parse_args();r=run(a.root,a.output,a.world,a.seed,a.capital,a.unit_cost,not a.no_growth);print(json.dumps({k:r[k] for k in ['complete','summary','annual']}))
