from __future__ import annotations
import argparse, json, time
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import verify_finance as main
import verify_science as base


def micro(value):
    return int((Decimal(str(value))*1000000).quantize(Decimal(1),rounding=ROUND_HALF_EVEN))


def independent_profile(protocol,route,scenario):
    profile=protocol['profiles_usd'][route];result={}
    for key,value in profile.items():
        if key=='price_grid':
            result[key]=[micro(v) for v in value]
        else:
            multiplier=scenario.get('maintenance_multiplier',1) if key in ('support_term','compatibility_maintenance_term','monthly_fixed_overhead') else 1
            result[key]=micro(Decimal(str(value))*Decimal(str(multiplier)))
    return result


def quote_cash_bounds(record,decision):
    tape=record['ledger'];index=int(decision['buyer'].rsplit('p',1)[1]);stage=decision['stage'];kind=decision['kind']
    keys=['spend:fulfillment-'+stage+'-'+kind+'-'+str(index),
          'spend:contact-'+kind+'-'+stage+'-'+str(index),
          'spend:contact-'+stage+'-'+kind+'-'+str(index)]
    entries={e['key']:e for e in record['connected_journal']['entries']}
    for key in keys:
        entry=entries.get(key)
        if entry is None or entry['status']!='COMPLETE':
            continue
        if entry['funding']=='EARNED':
            plan_id=entry['plan']['plan_id']
            action=next(a for a in tape['actions'] if a['op']=='reserve' and a['args']['id']==plan_id)
        else:
            action=tape['actions'][entry['receipt']['native_event_sequence']]
        cash=action['before']['available'];return cash,cash,'exact_native_spend_prefix'
    hour=decision['hour'];values=[]
    earlier=[a for a in tape['actions'] if a['day']<hour]
    if earlier:
        values.append(earlier[-1]['after']['available'])
    for action in tape['actions']:
        if action['day']==hour:
            values.extend([action['before']['available'],action['after']['available']])
    if not values:
        values.append(tape['config']['opening'])
    return min(values),max(values),'bounded_same_hour_prefix_no_admitted_spend'


def run(public_root,summary_path=None):
    protocol=main.read(public_root/'protocol.json');summary_file=summary_path or public_root/'RESULTS.json';summary=main.read(summary_file)
    scenarios={s['id']:s for s in protocol['registered_scenarios']};rows=[]
    for compact in summary['cases']:
        route=compact['route'];scenario=scenarios[compact['scenario']];expected_id=route+'-'+scenario['id']
        if compact['case_id']!=expected_id or route not in ('purpose','interface','complementarity','arrangement','foundry'):
            raise ValueError('unregistered case path')
        folder=public_root/expected_id;state=main.read(folder/'RESULT.json');record=main.read(folder/'account.public.json')
        p=independent_profile(protocol,route,scenario)
        fulfillment=sum(p[k] for k in ('onboarding','compute','verification','correction','delivery_storage_isolation','support_term','compatibility_maintenance_term'))
        capital=(p['research_and_failed_work']+p['rights_and_setup']+max(p['price_grid'])+3*(fulfillment+p['acquisition'])+3*p['monthly_fixed_overhead']) if scenario['capital_usd']=='stress-formula' else micro(scenario['capital_usd'])
        failures=[];ambiguous=[];quotes_checked=0
        if state['scenario']!=scenario or state['cost_profile_microUSD']!=p or state['opening_microUSD']!=capital or record['ledger']['config']['opening']!=capital:
            failures.append('registered_scenario_profile_or_capital_changed')
        for d in state['decisions']:
            if 'choice' not in d:
                continue
            quotes_checked+=1;lower,upper,basis=quote_cash_bounds(record,d)
            index=int(d['buyer'].rsplit('p',1)[1])
            value=int(Decimal(p['buyer_base_value'])*(80+5*index)*Decimal(str(scenario.get('demand_multiplier',1)))/100)
            q=d['choice']
            if {a['price_microUSD'] for a in q['actions'][1:]}!=set(p['price_grid']):
                failures.append('unregistered_price_grid')
            for a in q['actions'][1:]:
                needed=fulfillment+p['acquisition']+protocol['obligations']['native_fee_microUSD']+a['price_microUSD']+p['monthly_fixed_overhead']
                if a['buyer_utility_microUSD']!=value-a['price_microUSD']-p['adoption'] or a['required_company_cash_microUSD']!=needed:
                    failures.append('posted_value_or_required_cash_changed')
                if lower>=needed:
                    expected=True
                elif upper<needed:
                    expected=False
                else:
                    ambiguous.append({'hour':d['hour'],'buyer':d['buyer'],'price':a['price_microUSD'],'lower_cash':lower,'upper_cash':upper,'basis':basis});continue
                if bool(a['funding_feasible'])!=expected:
                    failures.append('prefunding_flag_disagrees_with_native_prefix')
        rows.append({'case_id':expected_id,'passed':not failures,'failures':failures,'quotes_checked':quotes_checked,'ambiguous_cash_contexts':ambiguous})
    return {'schema':'public-portfolio-independent-financial-supplement/v1','checker_sha256':base.digest(__file__),
            'producer_summary_sha256':base.digest(summary_file),'cases':rows,'passed':all(r['passed'] for r in rows),
            'ambiguities':sum(len(r['ambiguous_cash_contexts']) for r in rows),
            'registration_note':'Separate read-only supplement added after the first3 public purpose outputs were available; no economics or frozen primary verifier source changed, and no account rerun, reset or tuning occurred.',
            'scope':'Independently checks registered seed/cost profile and posted value plus exact or bounded pre-quote native cash. Ambiguous same-hour refused contacts remain explicitly unresolved.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public-root',required=True);p.add_argument('--output',required=True);p.add_argument('--summary');args=p.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('refuse overwrite of independent supplement')
    started=time.time();result=run(Path(args.public_root),Path(args.summary) if args.summary else None);result['wall_seconds']=time.time()-started
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'passed':result['passed'],'accounts':len(result['cases']),'ambiguous_cash_contexts':result['ambiguities']}))
    raise SystemExit(0 if result['passed'] else 1)
