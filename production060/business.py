"""Costed repeat operation of an owned industrial planning capability.

The public requests are real. Customer purchase, three-year recurrence and all
commercial budgets below are CONDITIONAL scenarios, never observed buyers.
No source-day pseudonym is converted into an additional software customer.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import resource
import time

from production060.dispatch import DispatchConfig, InputDataError, rolling_schedule
from production060.native import BusinessAccount
from production060.service import prepare_manifest
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.scale import trailing_profit

MICRO = 1_000_000


def money(value):
    return int((Decimal(str(value))*MICRO).to_integral_value(rounding=ROUND_CEILING))


def pricing(evaluation, n_days):
    """Enumerate the declared price menu against a complete modeled substitute.

    Within this conditional complete-information model, the buyer picks the
    least expensive eligible alternative, breaking equal prices against us.
    The policy may charge for maintained execution; algorithms are not exclusive.
    """
    c = evaluation['costs_usd']
    internal_annual = c['annual_maintenance']+c['annual_hosting']+12*c['support_per_network_month']+n_days*c['service_per_day']
    # A buyer may reproduce the ordinary open-source-component construction.
    # Three years is a declared sensitivity, not empirical retention evidence.
    self_build_annual = internal_annual+c['initial_construction']/3
    public_reference = 8*4389  # single-location packages; not equal feature scope
    budget = 12000  # private commercial fact unavailable; conditional test only
    bound = min(self_build_annual, public_reference, budget)
    choices = []
    for p in evaluation['business_evaluation']['price_choices_usd_network_year']:
        if p <= 0:
            continue
        accepted = p < bound
        annual_variable = n_days*c['service_per_day']+12*c['support_per_network_month']+p*c['payment_percent']+n_days*c['payment_fixed_per_invoice']+.2*n_days
        choices.append({'annual_price_usd': p, 'buyer_accepts': accepted,
                        'yearly_incremental_contribution_usd': p-annual_variable if accepted else 0})
    eligible = [r for r in choices if r['buyer_accepts']]
    selected = max(eligible, key=lambda r:r['yearly_incremental_contribution_usd']) if eligible else None
    if selected:
        p = selected['annual_price_usd']
        # Initial instrument construction is already incurred and fully charged.
        # A three-year test is chosen only if it covers prospective operating cost.
        future = 3*(selected['yearly_incremental_contribution_usd']-c['annual_maintenance']-c['annual_hosting']-c['acquisition_attempt'])-c['operator_onboarding']
        selected = dict(selected, three_year_incremental_before_tax_usd=future,
                        operating_decision='CONDITIONAL_TEST' if future>0 else 'DECLINE_UNPROFITABLE_CONTRACT')
    return {'scope':'FINITE_MENU_CONDITIONAL_COST_MODEL_NOT_OBSERVED_MARKET_OR_UNIVERSAL_EQUILIBRIUM',
            'outside_options':{'self_build_annual_equivalent_usd':self_build_annual,
                               'full_dispatch_reference_usd':public_reference,
                               'conditional_budget_usd':budget,
                               'no_benefit_or_equal_free_copy':'No purchase; tested separately by rights_market'},
            'menu':choices,'selected':selected}


def operate(root, state_dir, arm='conditional_repeat', max_days=None):
    root=Path(root).resolve(); state_dir=Path(state_dir).resolve()
    state_dir.mkdir(parents=True,exist_ok=True)
    ep=root/'production060/evaluation.json'
    evaluation=json.loads(ep.read_text())
    catalog=json.loads((root/'production060/data/catalog.json').read_text())
    days=[r for r in catalog if r['operating_data_complete']]
    if max_days is not None:
        days=days[:max_days]  # only a labeled integration diagnostic, never enterprise
    cfg=DispatchConfig(time_limit_s=evaluation['solver']['time_limit_s_per_day'],
                       window_size=evaluation['solver']['window_size'],
                       candidate_trucks=evaluation['solver']['candidate_trucks'])
    quote=pricing(evaluation,len(days))
    # A negative prospective value produces a refusal, not a manufactured sale.
    selected=quote['selected']
    operate_contract=selected and selected['operating_decision']=='CONDITIONAL_TEST' and arm!='zero_demand'
    price=money(selected['annual_price_usd']) if operate_contract else 0
    requests=[{'id':r['id'],'instance_path':r['path'],'resources_path':'production060/data/resources.json',
               'mode':'ordinary','planning_scope':'rolling','config':asdict(cfg),
               'delivery_path':f'production060/deliveries/{arm}/{r["id"]}.json'} for r in days]
    manifest=prepare_manifest(root,requests)
    (state_dir/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    report={'schema':'production060/native-operating-result/v1','scope':'SIMULATED_CONDITIONAL_ONE_OPERATOR',
            'evaluation_sha256':hashlib.sha256(ep.read_bytes()).hexdigest(),
            'native_seed_usd':100000,'quote':quote,'arm':arm,'diagnostic_day_limit':max_days,
            'observed_customer_purchases':0,'source_networks':1,'deliveries':[],'costs':[],
            'limits':['The source has operating work, not software purchase evidence.',
                      'Repeated-year demand, budgets, support and construction labor allocations are modeled.',
                      'No industrial operation, outreach, publication or real transfer occurs.']}
    account_path=state_dir/'owned-account.json'
    c=evaluation['costs_usd']
    with BusinessAccount(root,manifest,account_path,contract='production060-'+arm) as account:
        def cost(ident,dollars,hour):
            if dollars<=0:return
            account.cost(ident,money(dollars),hour)
            report['costs'].append({'id':ident,'usd':dollars,'hour':hour})
        cost('all-instrument-construction',c['initial_construction'],0)
        cost('acquisition-including-refusals',c['acquisition_attempt'],1)
        if operate_contract:
            cost('annual-maintenance',c['annual_maintenance'],2)
            cost('annual-hosting',c['annual_hosting'],2)
            cost('operator-integration',c['operator_onboarding'],2)
            cost('annual-prepaid-support',12*c['support_per_network_month'],2)
            resources=json.loads((root/'production060/data/resources.json').read_text())
            for i,row in enumerate(days):
                hour=24*(i+1)
                account.advance(hour)
                order_id=f'{arm}-{i:03d}'
                unit=price//len(days)+(i<price%len(days))
                terms=prospective_terms(order_id,unit,hour+49,hour+1,residual=min(money(1),unit),fee=200_000,
                    counterparty_obligations='Conditional buyer pays for benchmark planning artifact, not physical deliveries; all claims retained. Producer retains $1 residual per order; no external guarantee.')
                account.begin_order(row['id'],order_id,'one-operator-year1',unit,price,hour,hour+2,terms=terms)
                payment=account.spend('production-'+row['id'],'industrial_planning',money(c['service_per_day']),hour,
                    {'request_id':row['id'],'scope':'construct+independent replay of new public day'},
                    expected_net=max(0,unit-money(c['service_per_day'])-200_000),allow_seed=True)
                if payment is None:
                    account.refund(order_id,hour)
                    report['deliveries'].append({'id':row['id'],'accepted':False,'reason':'native_resource_refusal'})
                    continue
                before=resource.getrusage(resource.RUSAGE_SELF); started=time.monotonic()
                target=root/f'production060/deliveries/{arm}/{row["id"]}.json'
                if target.exists():
                    artifact=json.loads(target.read_text())
                else:
                    day=json.loads((root/row['path']).read_text())
                    try:
                        artifact=rolling_schedule(resources,day,mode='ordinary',config=cfg)
                    except InputDataError as error:
                        # An infeasible public request remains in the full
                        # denominator. Retain incurred work and refund its
                        # funded order; never invent a larger truck or alter
                        # the frozen quantity split to manufacture acceptance.
                        after=resource.getrusage(resource.RUSAGE_SELF)
                        cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
                        cost('compute-'+row['id'],cpu/3600*c['compute_per_cpu_hour'],hour+1)
                        account.refund(order_id,hour+1)
                        failure={'id':row['id'],'order_id':order_id,'price_microUSD':unit,
                                 'accepted':False,'reason':'producer_input_infeasible',
                                 'errors':[str(error)],'cpu_s':cpu,
                                 'wall_s':time.monotonic()-started,
                                 'input_sha256':hashlib.sha256((root/row['path']).read_bytes()).hexdigest()}
                        failure_dir=state_dir/'production-failures'
                        failure_dir.mkdir(exist_ok=True)
                        (failure_dir/(row['id']+'.json')).write_text(json.dumps(failure,indent=2)+'\n')
                        report['deliveries'].append(failure)
                        continue
                receipt=account.complete_order(order_id,row['id'],artifact,hour+1)
                after=resource.getrusage(resource.RUSAGE_SELF)
                cpu=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
                cost('compute-'+row['id'],cpu/3600*c['compute_per_cpu_hour'],hour+1)
                if receipt['accepted']:
                    cost('payment-processing-'+row['id'],unit/MICRO*c['payment_percent']+c['payment_fixed_per_invoice'],hour+1)
                    account.release(order_id,hour+1)
                else:
                    account.refund(order_id,hour+1)
                report['deliveries'].append({'id':row['id'],'order_id':order_id,'price_microUSD':unit,
                    'accepted':receipt['accepted'],'errors':receipt['errors'],'artifact_sha256':receipt['artifact_sha256'],
                    'cpu_s':cpu,'wall_s':time.monotonic()-started})
                if (i+1)%20==0:
                    (state_dir/'progress.json').write_text(json.dumps({'completed':i+1,'latest':row['id'],'summary':account.snapshot()['summary']},indent=2)+'\n')
                    print(json.dumps({'native_completed':i+1,'latest':row['id']}),flush=True)
        # Costs belong inside the exclusive year endpoint, even in a short run.
        account.advance(8758)
        summary=account.snapshot()['summary']
        cost('income-tax',max(0,summary['profit']/MICRO)*c['tax_rate_positive_income'],8759)
        checkpoint=account.seal_checkpoint({'completed_public_requests':len(report['deliveries']),
                    'operating_end_hour':8760,'arm':arm,'costs_complete_for_declared_model':True})
        account.verify_checkpoint(checkpoint)
        exported=account.export()
        audited=account.audit()
        report.update(summary=account.snapshot()['summary'],native_audit=audited,
                      checkpoint=checkpoint,
                      native_trailing_profit=trailing_profit(exported['ledger'],operating_end_hour=8760,operating_complete=True))
        (state_dir/'public-native-export.json').write_text(json.dumps(exported,indent=2)+'\n')
        (state_dir/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path('.'))
    ap.add_argument('--state-dir',type=Path,required=True)
    ap.add_argument('--arm',default='conditional_repeat',choices=['conditional_repeat','zero_demand'])
    ap.add_argument('--diagnostic-days',type=int)
    args=ap.parse_args()
    result=operate(args.root,args.state_dir,args.arm,args.diagnostic_days)
    print(json.dumps({'summary':result['summary'],'native_trailing_profit':result['native_trailing_profit']}))
