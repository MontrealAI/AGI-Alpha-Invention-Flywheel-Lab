"""Bounded conditional service operation, not actual commerce or annual scale."""
import argparse,hashlib,json,time
from pathlib import Path
from commercial.ledger import digest
from commercial.terms_exact_v2 import prospective_terms
from industrial064.native import BusinessAccount
from industrial064.service import prepare_manifest
from industrial064.construct import construct
M=1000000

def choose(menu,outside,budget,value,slack,cost):
    bound=min(min(outside.values()),budget,value)
    feasible=[p for p in menu if bound-p>=slack and p*.98-cost>0]
    return max(feasible) if feasible else None

def operate(root,state):
    root=Path(root).resolve();state=Path(state).resolve();state.mkdir(parents=True,exist_ok=False)
    e=json.loads((root/'industrial064/economics.json').read_text());reg=json.loads((root/'industrial064/registration.json').read_text())
    rows=[{'id':q['id'],'request':q,'delivery_path':'industrial064/deliveries/'+q['id']+'.json'} for q in reg['requests']]
    for row in rows:
        if (root/row['delivery_path']).exists():raise ValueError('PRIOR_DELIVERY_REFUSED')
    manifest=prepare_manifest(root,rows);(state/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    report={'scope':'CONDITIONAL_SIMULATED_ONE_MANUFACTURER_TWO_REQUESTS','actual_buyers':0,'actual_collections':0,'actual_profit':None,'native_seed_usd':100000,'registered_requests_sha256':digest(reg),'economics_sha256':digest(e),'deliveries':[],'failure':None,'first_stage':None,'previously_uneconomic_claim':False,'annual_profit_claim':False}
    c=e['costs_usd'];first=sum(v for k,v in c.items() if not k.startswith('successor'))
    quotes=[choose(e['first_offer_menu_usd'],e['first_outside_total_usd'],e['buyer_budget_first_usd'],e['buyer_value_first_usd'],e['minimum_participation_slack_usd'],first),choose(e['successor_offer_menu_usd'],e['successor_outside_total_usd'],e['buyer_budget_successor_usd'],e['buyer_value_successor_usd'],e['minimum_participation_slack_usd'],c['successor_complete_production_verification_support'])]
    report['quotes_usd']=quotes
    with BusinessAccount(root,manifest,state/'private-owned-account.json',opening=100000*M,working=0,contract='industrial064-primary') as a:
        a.cost('acquisition-including-no-purchases',c['acquisition_including_refusals']*M,0)
        taxed=0
        for i,row in enumerate(rows):
            day=10 if i==0 else 72; price=quotes[i]
            if price is None: report['failure']='VOLUNTARY_PURCHASE_OR_VENDOR_PROFIT_REFUSED';break
            amount=first-c['acquisition_including_refusals'] if i==0 else c['successor_complete_production_verification_support']
            if i:
                report['first_stage']=a.snapshot()
            order='industrial064-'+row['id']
            terms=prospective_terms(order,price*M,day+49,day+1,residual=100*M,fee=200000,counterparty_obligations='Conditional engineering-plan buyer only. No physical execution or savings guarantee. Prepaid support/remedy envelope and $100 retained native residual; adverse claims remain producer obligations.')
            a.begin_order(row['id'],order,'one-manufacturer',price*M,54000*M,day,day+2,terms=terms)
            before=a.snapshot()
            funded=a.spend('construct-'+row['id'],'industrial_network_complete_plan',amount*M,day,{'request_sha256':digest(row['request']),'cost_envelope_usd':amount,'actual_billing':'unknown','fresh_output_required':True},expected_net=int((price*.98-amount-.2)*M),allow_seed=(i==0))
            if funded is None:
                a.refund(order,day);report['failure']='NATIVE_EARNED_RESOURCE_REFUSAL';break
            journal=a.export()['connected_journal']['entries'][-1]
            marker={'request_id':row['id'],'before':before,'funding':journal['funding'],'journal_request':journal['request'],'authorized_at_ns':time.time_ns(),'output_absent':not (root/row['delivery_path']).exists()}
            (state/(row['id']+'-funding.json')).write_text(json.dumps(marker,indent=2)+'\n')
            out=state/('production-'+row['id'])
            started=time.time_ns()
            try:
                artifact,production=construct(root,row['request'],out)
                receipt=a.complete_order(order,row['id'],artifact,day+1)
                if not receipt['accepted']:raise ValueError('CLIENT_REJECTED:'+str(receipt['errors']))
                a.cost('payment-'+row['id'],int(price*M*e['payment_fraction']),day+1)
                a.release(order,day+1)
                a.advance(day+50)
                p=a.snapshot()['summary']['profit'];tax=max(0,int((p+taxed)*e['income_tax_fraction'])-taxed)
                if tax:a.cost('tax-'+row['id'],tax,day+51);taxed+=tax
                # Subsequent tax applies to additional PRE-tax profit, not a
                # repeated tax on an already after-tax cumulative balance.
                report['deliveries'].append({'request':row['request'],'order_id':order,'price_usd':price,'funding':journal['funding'],'authorization_ns':marker['authorized_at_ns'],'production_started_ns':started,'production_finished_ns':time.time_ns(),'production':production,'acceptance':receipt,'summary':a.snapshot()['summary']})
            except Exception as error:
                report['failure']=type(error).__name__+':'+str(error)
                try:a.refund(order,day+1)
                except Exception as refund_error:report['refund_error']=str(refund_error)
                break
        report['summary']=a.snapshot()['summary'];report['native_audit']=a.audit()
        export=a.export();(state/'public-native-export.json').write_text(json.dumps(export,indent=2)+'\n')
        report['public_export_sha256']=hashlib.sha256((state/'public-native-export.json').read_bytes()).hexdigest()
    (state/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'deliveries':len(report['deliveries']),'failure':report['failure'],'summary':report['summary'],'audit':report['native_audit']}),flush=True)
    return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--state',required=True);a=p.parse_args();operate(a.root,a.state)
