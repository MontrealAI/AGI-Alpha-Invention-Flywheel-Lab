"""Two accepted material-service cycles through the existing native account.

Run with --output NEW_ABSOLUTE_DIRECTORY. Outputs are private except public/.
No external transactions, model calls or real supplier/customer connections.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import time
from commercial.ledger import canonical, digest
from commercial.terms_exact_v2 import prospective_terms
from .finance import JournalAccount
from .material054 import solve, ordinary_milp, textbook_order, successor_order
from .material_verify054 import audit_plan, audit_transfer
from .material_service054 import freeze_jobs, SOURCES

USD=1000000
OPENING=100000*USD


def economics(raw, artifact, *, budget, value, transport=20*USD, rival=None, outside_salvage=0, fixed_cost=0):
    """Authored costs; all ordinary alternatives receive the same available stock.

    A complete contractor/partner price includes material, labor and delivery.
    No-purchase utility is zero. No parameter is an empirical willingness to pay.
    """
    material=artifact['material_cost_microUSD'];n=len(raw['pieces'])
    alternatives={'self_service':material+n*3*USD+40*USD+transport,
        'human_plus_software':material+n*4*USD+50*USD+transport,
        'existing_partner':material+n*2*USD+50*USD+transport}
    # Only the self-service route buys and keeps the full stock; contractor
    # quotes are pieces-only with producer-retained residues. Salvage is an
    # explicit realizable outside bid, not an inferred physical scrap value.
    alternatives['self_service']-=outside_salvage
    if rival is not None:alternatives['cheap_rival']=rival
    outside=min(alternatives.values())
    costs={'material':material,'cutting':n*USD,'shipping':transport,
        'source_checking':(len(raw['stocks'])+n)*250000,'production':3*USD,
        'acquisition':2*USD,'maintenance':USD,'payment_fee':200000}
    quote=min(budget,value,outside-10*USD)
    viable=quote>sum(costs.values())+fixed_cost and quote>0
    price=quote if viable else None
    best_outside_utility=max(0,max(value-c for c in alternatives.values() if c<=budget) if any(c<=budget for c in alternatives.values()) else 0)
    buy=price is not None and value-price>best_outside_utility and price<=budget
    return {'price_microUSD':price,'costs_microUSD':costs,'alternatives_microUSD':alternatives,
        'budget_microUSD':budget,'value_microUSD':value,'best_outside_utility_microUSD':best_outside_utility,
        'buyer_choice':'BUY' if buy else 'NO_PURCHASE_FROM_US','buyer_surplus_microUSD':value-price if buy else 0,
        'minimum_saving_microUSD':10*USD,'outside_salvage_microUSD':outside_salvage,
        'fixed_cost_considered_microUSD':fixed_cost,
        'residual_title_terms':'Pieces-only purchase; supplier retains all unused stock and remnants. Buyer may decline and use self-service, including its declared realizable salvage bid.',
        'conditional':True}


def run(output):
    started=time.process_time(); root=Path(__file__).resolve().parents[1]
    output=Path(output)
    if not output.is_absolute() or output.exists() or output.is_symlink():raise ValueError('NEW_ABSOLUTE_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    # Frozen admission contains exact deterministic artifacts. Runtime production
    # below is repeated after paid action; the first planner receives only first.
    first=textbook_order(); a,work1=solve(first)
    if a is None:raise ValueError('FIRST_NOT_FEASIBLE')
    second=successor_order(a);b,work2=solve(second)
    if b is None:raise ValueError('SECOND_NOT_FEASIBLE')
    ordinary_a=ordinary_milp(first);ordinary_b=ordinary_milp(second)
    ordinary_own_second=successor_order(ordinary_a)
    ordinary_own_b=ordinary_milp(ordinary_own_second)
    equal_b,_=solve(copy.deepcopy(second))
    cold=copy.deepcopy(second);cold['order_id']='successor-without-first-asset';cold['stocks']=[s for s in cold['stocks'] if s['id']=='new-virgin']
    cold_b,_=solve(cold)
    # All observations/controls are public authored inputs, not hidden future draws.
    deals=[economics(first,a,budget=1500*USD,value=1500*USD,fixed_cost=30*USD),economics(second,b,budget=100*USD,value=130*USD,fixed_cost=8*USD)]
    cold_deal=economics(cold,cold_b,budget=100*USD,value=130*USD)
    controls={'no_first_asset':cold_deal,
        'first_buyer_realizable_salvage_bid':economics(first,a,budget=1500*USD,value=1500*USD,outside_salvage=70*USD,fixed_cost=30*USD),
        'cheap_rival':economics(second,b,budget=100*USD,value=130*USD,rival=30*USD),
        'low_value':economics(second,b,budget=100*USD,value=25*USD),
        'expensive_transport':economics(second,b,budget=100*USD,value=130*USD,transport=100*USD)}
    compared={'first_candidate_cost_microUSD':a['material_cost_microUSD'],
        'first_ordinary_cost_microUSD':ordinary_a['material_cost_microUSD'],
        'second_candidate_cost_microUSD':b['material_cost_microUSD'],
        'second_ordinary_cost_microUSD':ordinary_b['material_cost_microUSD'],
        'ordinary_acceptance':[audit_plan(first,ordinary_a),audit_plan(second,ordinary_b)],
        'equal_content_artifact_identical':equal_b==b,'equal_content_economics_identical':economics(second,equal_b,budget=100*USD,value=130*USD,fixed_cost=8*USD)==deals[1],
        'ordinary_own_first_asset_successor_cost_microUSD':ordinary_own_b['material_cost_microUSD'],
        'ordinary_own_first_asset_successor_acceptance':audit_plan(ordinary_own_second,ordinary_own_b),
        'ordinary_own_first_asset_transfer':audit_transfer(first,ordinary_a,ordinary_own_second),
        'ordinary_own_first_asset_successor_decision':economics(ordinary_own_second,ordinary_own_b,budget=100*USD,value=130*USD,fixed_cost=8*USD),
        'advantage':'NO_NEW_OPTIMIZER_OR_RETAINED_METHOD_ADVANTAGE',
        'cold_start_material_cost_microUSD':cold_b['material_cost_microUSD']}
    if not all(x['buyer_choice']=='BUY' for x in deals):raise ValueError('CENTRAL_BUYER_REFUSAL')
    if not all(x['buyer_choice']=='NO_PURCHASE_FROM_US' for x in controls.values()):raise ValueError('ADVERSE_CONTROL_FAILED')
    evidence=output/'evidence'
    # Native source loader uses paths relative to root. Output must therefore be
    # under this reviewed source tree; accounts themselves are never exported.
    try: relative=str(evidence.relative_to(root))
    except ValueError:raise ValueError('OUTPUT_MUST_BE_UNDER_REVIEWED_SOURCE_ROOT')
    manifest=freeze_jobs(root,relative,[(first,a,None),(second,b,first['order_id'])])
    (output/'PROTOCOL.json').write_bytes((root/'campaign/material-054/PROTOCOL.json').read_bytes())
    public=output/'public';public.mkdir()
    account=JournalAccount(root,manifest,output/'account.sqlite',opening=OPENING,working=0,contract='fresh-material054-two-cycle')
    funding=[];snapshots=[];audits=[]
    try:
        setup=account.spend('construction-and-search','setup',30*USD,0,
            {'protocol_sha256':hashlib.sha256((output/'PROTOCOL.json').read_bytes()).hexdigest(),'included':'construction, unsuccessful checks, ordinary comparison, search and qualification'},1,allow_seed=True)
        if setup is None:raise ValueError('SETUP_NOT_FUNDED')
        funding.append(setup)
        for index,(raw,artifact,deal) in enumerate(zip([first,second],[a,b],deals)):
            day=index*48
            if index:
                account.advance_financial(day)
                # Not necessary seed financing: removal of first earnings alone
                # would still leave the original 100k. No necessity claim is made.
                receipt=account.spend('remnant-handover-connector','inventory_handover',8*USD,day,
                    {'parent_artifact_sha256':digest(a),'successor_input_sha256':digest(second),'transfer':audit_transfer(first,a,second)},10*USD,allow_seed=False)
                if receipt is None:raise ValueError('SUCCESSOR_CONNECTOR_NOT_EARNED_FUNDED')
                funding.append(receipt)
            if index:
                native=account.export()['ledger']
                if not any(o['id']=='material-sale-0' and o['state']=='released' for o in native['orders']):
                    raise ValueError('MATERIAL_PARENT_NOT_RELEASED_BEFORE_PAID_PRODUCTION')
            direct_costs={k:v for k,v in deal['costs_microUSD'].items() if k!='payment_fee'}
            paid=account.spend('production-'+str(index),'material_fulfillment',sum(direct_costs.values()),day,
                {'cost_categories_microUSD':direct_costs,'input_sha256':digest(raw),'artifact_sha256':digest(artifact)},deal['price_microUSD']-sum(deal['costs_microUSD'].values()),allow_seed=True)
            if paid is None:raise ValueError('PRODUCTION_NOT_FUNDED')
            funding.append(paid)
            current,_=solve(raw)
            if current!=artifact or not audit_plan(raw,current)['accepted']:raise ValueError('RUNTIME_PRODUCTION_NOT_ACCEPTED')
            buyer='authored-buyer-'+str(index);ident='material-sale-'+str(index);price=deal['price_microUSD']
            account.execute('wallet',{'buyer':buyer,'amount':deal['budget_microUSD']},day)
            terms=prospective_terms(ident,price,day+24,day+1,fee=deal['costs_microUSD']['payment_fee'],counterparty_obligations=deal['residual_title_terms'])
            account.execute('register_terms',{'id':ident+'-terms','terms':terms},day)
            account.execute('offer',{'id':ident,'buyer':buyer,'price':price,'job_id':raw['order_id'],'deadline':day+12,'terms_id':ident+'-terms'},day)
            for action in ['consent','fund','prepare','release']:
                account.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day+1)
            account.advance_financial(day+25)
            # Provision 20% of positive incremental modeled profit; no negative
            # tax refund and no assumed real tax jurisdiction or measured bill.
            before_tax=account.snapshot()['summary']['profit']
            prior_after=snapshots[-1]['profit'] if snapshots else 0
            tax=max(0,before_tax-prior_after)//5
            account.cost('modeled-tax-'+str(index),tax,day+25)
            snapshots.append(account.snapshot()['summary']);audits.append(account.audit())
        final=account.snapshot()['summary'];audit=account.audit()
        # Export only the supported key-free record for independent semantic audit;
        # private account files and signing authority are not included.
        record=account.export()
        from .finance import audit_journal
        independent=audit_journal(record,root=root,manifest=manifest)
        result={'schema':'material054/result/v1','scope':'CONDITIONAL_AUTHORED_SIMULATION','opening_microUSD':OPENING,
            'operating_hours':74,'trailing_365_day_profit_microUSD':None,'target_reached':False,
            'source_hashes':manifest['source_hashes'],'manifest_sha256':digest(manifest),'protocol_sha256':hashlib.sha256((output/'PROTOCOL.json').read_bytes()).hexdigest(),
            'buyer_decisions':deals,'controls':controls,'comparisons':compared,'native_snapshots':snapshots,
            'native_final':final,'native_audit_accepted':audit['accepted'],'independent_native_audit_accepted':independent['accepted'],
            'account_continuity':'One fresh isolated 100,000 USD native account; no resets, pooling or top-ups',
            'finance_receipts':funding,'artifact_acceptance':[audit_plan(first,a),audit_plan(second,b)],
            'transfer_acceptance':audit_transfer(first,a,second),'registered_orders':2,'accepted_paid_orders':2,
            'first_total_remnant_mm':sum(r['length_mm'] for r in a['remnants']),
            'second_virgin_stock_saved_mm':9000 if b['material_cost_microUSD']==0 else 0,
            'second_piece_output_mm':sum(p['length_mm'] for p in second['pieces']),
            'first_work':work1,'second_work':work2,'command_process_cpu_seconds':time.process_time()-started,
            'actual_host_model_developer_billing':None,
            'enabling_verdict':'First-cycle simulated material inventory enables the second accepted low-budget order against the registered virgin-only route. Existing ordinary optimization/reuse ties. Earnings pay the connector but are not necessary given the same 100k seed.',
            'limits':['No empirical market or physical material verification','Finite authored supplier pool does not rule out cheaper outside remnants','Zero-kerf textbook instance is not an industrial production qualification','No autonomous discovery or general transformational advantage','No annualization, buyer multiplication or billion-dollar proof']}
        if final['cash']-OPENING!=final['profit'] or final['profit']!=final['revenue']-final['expenses'] or not audit['accepted'] or not independent['accepted']:
            raise ValueError('NATIVE_PROFIT_IDENTITY_FAILED')
        (public/'RESULT.json').write_bytes(canonical(result))
        (public/'FIRST_PLAN.json').write_bytes(canonical(a));(public/'SECOND_PLAN.json').write_bytes(canonical(b))
        (public/'INPUTS.json').write_bytes(canonical({'first':first,'second':second,'cold_start':cold}))
        return result
    finally:
        account.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    result=run(args.output)
    print(json.dumps({'accepted_paid_orders':result['accepted_paid_orders'],'profit_microUSD':result['native_final']['profit'],'target_reached':False,'public_result':str(Path(args.output)/'public/RESULT.json')}))

if __name__=='__main__':main()
