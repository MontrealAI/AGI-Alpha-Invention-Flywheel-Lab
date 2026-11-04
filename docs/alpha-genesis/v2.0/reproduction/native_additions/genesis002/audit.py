"""Independent operating-policy and actual-artifact audit over canonical finance.

Does not call the operating selector or producer to approve a delivered artifact.
Native money is independently replayed by the repository's existing audit_journal.
"""
from __future__ import annotations
from pathlib import Path
from .backend import Backend
from .common import canonical, digest, package_identity, read
from .decision import validate
from .routing import qualify, learn_and_test

CENT=10_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def best_option(c, qualification, before, ordinal):
    """Separately enumerate each method/price pair; no production select() call."""
    eligible=[]
    for offer in c['offers']:
        for method in c['methods']:
            if method['access']!='local_public_code' or offer['service_id'] not in method['supported_services']:
                continue
            check=qualification.get(method['id'],{}).get(offer['service_id'],{})
            if check.get('accepted') is not True: continue
            for price in offer['prices_cents']:
                if price>offer['buyer_budget_cents']: continue
                surplus=offer['buyer_value_cents']-price-offer['buyer_friction_cents']-offer['outside_utility_cents']
                if surplus<=0: continue
                fees=(price*c['fee_bps']+9999)//10000+c['fee_fixed_cents']
                total=sum(method['costs'].values())+c['acquisition_cents']+fees
                gain=price-total
                if gain<=0 or before['available']<(max(price,20)+total)*CENT:continue
                if ordinal>0 and c['continuation_funding_policy']=='EARNED_ONLY' and before['unrestrictedEarned']<total*CENT:continue
                eligible.append((gain,total,offer['id'],method['id'],price,fees,surplus))
    if not eligible:return None
    return sorted(eligible,key=lambda x:(-x[0],x[1],x[2],x[3],x[4]))[0]


def audit(repo, output):
    out=Path(output).absolute();b=Backend(Path(repo))
    contract=read(out/'CONTRACT.json');original=contract['configuration'];validate(original)
    c=__import__('copy').deepcopy(original)
    if contract['stress']=='no_demand':
        for offer in c['offers']:offer['buyer_value_cents']=0
    require(contract['source']=={'native':b.identity(),'genesis':package_identity()},'SOURCE_IDENTITY_MISMATCH')
    require(contract['external_authority']=='NONE' and contract['evidence_role']=='FINITE_AUTHORED_INTEGRATION','SCOPE_CHANGED')
    manifest=read(out/'MANIFEST.json');runtime=out/'runtime'
    record=read(out/'NATIVE_EXPORT.json');report=read(out/'REPORT.json')
    native=b.finance.audit_journal(record,root=runtime,manifest=manifest)
    header=record['connected_journal']
    require(header['opening']==c['opening_cents']*CENT and header['working']==c['working_reserve_cents']*CENT,
            'REGISTERED_ACCOUNT_OPENING_CHANGED')
    require(header['contract']=='genesis002-registered-synthetic-enterprise-v1','REGISTERED_ACCOUNT_CONTRACT_CHANGED')
    qualification=read(out/'QUALIFICATION.json')
    require(qualification==qualify(b.substrate,b.checker,c['methods'],c['cohort_seed']),'QUALIFICATION_CHANGED')
    entries=record['connected_journal']['entries'];actions=record['ledger']['actions']
    position=0;native_position=0
    base_work={'contract_sha256':digest(contract),'source_sha256':digest(contract['source'])}

    def consume(request):
        nonlocal position,native_position
        require(position<len(entries),'MISSING_OPERATING_ACTION')
        e=entries[position]
        require(e['request']==request and e['status']=='COMPLETE','OPERATING_ACTION_OR_ORDER_CHANGED')
        if request['operation']=='spend':
            before=actions[native_position]['before']
            expected=('EARNED' if request['expected_net']>0 and
                      min(before['available'],before['unrestrictedEarned'])>=request['amount'] else 'SEED')
            require(e['funding']==expected,'FUNDING_POLICY_CHANGED')
            require(expected!='SEED' or request['allow_seed'],'UNAUTHORIZED_SEED_CONTINUATION')
            native_position=e['receipt']['native_event_sequence']+1
        else:native_position=e['receipt']['sequence']
        position+=1
        return e['receipt']

    def execute(op,args,day):
        return consume({'operation':'execute','op':op,'args':args,'day':day})

    def cost(ident,amount,day):return execute('cost',{'id':ident,'amount':amount},day)

    def spend(ident,kind,amount,day,work,expected_net,seed):
        if amount==0:
            cost(ident+'-zero',0,day)
            return {'funding':'NO_RESOURCE_SPEND','amount_microUSD':0}
        return consume({'operation':'spend','id':ident,'kind':kind,'amount':amount*CENT,
                        'day':day,'work':work,'expected_net':expected_net*CENT,'allow_seed':seed})

    spend('g2-setup','setup',c['setup_cents'],0,base_work,1,True)
    spend('g2-discovery','discovery',c['discovery_cents'],0,base_work,1,True)
    cost('g2-freeze-'+digest({'contract':contract,'qualification':qualification})[:32],0,0)
    revenue=0;expenses=c['setup_cents']+c['discovery_cents'];counts={x:0 for x in ('SETTLED','REFUNDED','NONENTRY','NO_PAYMENT')}
    earned_deliveries=0
    for i in range(c['cycles']):
        intent=read(out/'intents'/f'{i:06d}.json');r=read(out/'episodes'/f'{i:06d}.json');day=2+3*i
        before=actions[native_position]['before'] if native_position<len(actions) else record['ledger']['summary']
        require(intent['ordinal']==i and intent['day']==day and intent['before_sequence']==native_position
                and intent['before']==before,'DECISION_NOT_BOUND_TO_ITS_ACTUAL_NATIVE_PREFIX')
        chosen=intent['decision']['selected'];best=best_option(c,qualification,before,i)
        require(intent['decision']['configuration_sha256']==digest(c),'DECISION_CONFIGURATION_CHANGED')
        require(r['ordinal']==i and r['day']==day and r['intent_sha256']==digest(intent),'EPISODE_IDENTITY_CHANGED')
        if best is None:
            require(chosen is None and intent['decision']['action']=='NONENTRY' and r['status']=='NONENTRY'
                    and intent['job'] is None and r['artifact'] is None and r['funding'] is None,'UNJUSTIFIED_NONENTRY_OR_OPERATION')
        else:
            gain,total,offer_id,method_id,price,fees,surplus=best
            offer=next(x for x in c['offers'] if x['id']==offer_id)
            method=next(x for x in c['methods'] if x['id']==method_id)
            require(chosen is not None and intent['decision']['action']=='OPERATE','BEST_ELIGIBLE_ROUTE_NOT_USED')
            require((chosen['offer_id'],chosen['method_id'],chosen['price_cents'],chosen['complete_cost_cents'],
                     chosen['fee_cents'],chosen['contribution_cents'],chosen['buyer_surplus_cents'])==
                    (offer_id,method_id,price,total,fees,gain,surplus),'FINITE_PRICE_OR_METHOD_OPTIMUM_CHANGED')
            require(chosen['adapter']==method['adapter'] and chosen['service_id']==offer['service_id'],'METHOD_BINDING_CHANGED')
            jobs=[j for j in manifest['jobs'] if j['service_id']==offer['service_id']]
            job=jobs[8+i+i//7]
            require(job==intent['job'],'ADMITTED_REQUEST_CHANGED')
            work={**base_work,'intent_sha256':digest(intent)}
            acquired=spend(f'g2-acquire-{i}','acquisition',c['acquisition_cents'],day,work,gain,i==0 or c['continuation_funding_policy']=='AVAILABLE_NATIVE_CASH')
            require(r['acquisition_funding']==acquired,'ACQUISITION_RECEIPT_CHANGED');expenses+=c['acquisition_cents']
            if contract['stress']=='payment_failure':
                require(r['status']=='NO_PAYMENT' and r['funding'] is None and r['artifact'] is None,'UNPAID_ORDER_COUNTED')
            else:
                buyer,ident=f'SIM-g2-buyer-{i}',f'g2-order-{i}'
                execute('wallet',{'buyer':buyer,'amount':offer['buyer_budget_cents']*CENT},day)
                execute('offer',{'id':ident,'buyer':buyer,'price':price*CENT,'job_id':job['id'],'deadline':day+5},day)
                for action in ('consent','fund'):
                    execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day)
                production=total-fees-c['acquisition_cents']
                paid=spend(f'g2-produce-{i}','production',production,day,work,gain,i==0 or c['continuation_funding_policy']=='AVAILABLE_NATIVE_CASH')
                require(r['funding']==paid and r['native_order_id']==ident,'PRODUCTION_RECEIPT_CHANGED')
                expenses+=production
                delivery=read(out/'deliveries'/f'{i:06d}.json');raw=read(runtime/job['input'])
                require(delivery['input_sha256']==digest(raw),'PRODUCED_INPUT_CHANGED')
                independent=b.checker(job['service_id'],raw,delivery['artifact'])
                equivalent=b.substrate._semantics(read(runtime/job['artifact']))==b.substrate._semantics(delivery['artifact'])
                require(independent==delivery['check'] and equivalent==delivery['admitted_outcome_equal']
                        and digest(delivery)==r['artifact'],'DELIVERED_ARTIFACT_OR_ACCEPTANCE_CHANGED')
                cost(f'g2-output-{i}-'+digest(delivery)[:32],0,day)
                accepted=independent['accepted'] is True and equivalent and delivery['artifact']['outcome_scope']=='complete_outcome'
                require(r['status']==('SETTLED' if accepted else 'REFUNDED'),'WRONG_SETTLEMENT_VERDICT')
                if accepted:
                    cost(f'g2-fee-{i}',fees*CENT,day);expenses+=fees;revenue+=price
                    sequence=('prepare','release')
                    if i>0 and paid['funding'] in ('EARNED','NO_RESOURCE_SPEND'):earned_deliveries+=1
                else:sequence=('refund',)
                for action in sequence:
                    execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},day+1)
        counts[r['status']]+=1
        expected_summary=actions[native_position-1]['after']
        require(r['after']['sequence']==native_position and r['after']['summary']==expected_summary,'EPISODE_SNAPSHOT_CHANGED')
    final_day=3*c['cycles']+3
    tax=max(0,revenue-expenses)*c['tax_bps']//10000
    cost('g2-modeled-tax',tax*CENT,final_day)
    rd=read(out/'RESEARCH_DECISION.json');amount=c['successor_research_cents']
    before=actions[native_position-1]['after']
    eligible=(amount>0 and c['successor_expected_benefit_cents']>amount and
              min(before['available'],before['unrestrictedEarned'])>=amount*CENT)
    require(rd['conduct']==eligible and rd['before']['summary']==before and rd['before']['sequence']==native_position
            and rd['cost_cents']==amount and rd['expected_benefit_cents']==c['successor_expected_benefit_cents'],
            'RESEARCH_VALUE_OR_FUNDING_DECISION_CHANGED')
    research=None
    if eligible:
        funding=spend('g2-successor','research',amount,final_day,
            {**base_work,'decision_sha256':digest(rd)},c['successor_expected_benefit_cents']-amount,False)
        study=read(out/'ROUTING_STUDY.json')
        # Exact rerun is regression checking, not another independent confirmation.
        require(study==learn_and_test(b.substrate,b.checker,c['cohort_seed']+100),'ROUTING_STUDY_CHANGED')
        cost('g2-study-'+digest(study)[:32],0,final_day)
        research={'funding':funding,'study_sha256':digest(study),'decision':study['decision']}
    else:require(not (out/'ROUTING_STUDY.json').exists(),'UNFUNDED_STUDY_PRESENT')
    require(position==len(entries) and native_position==len(actions),'EXTRA_UNREGISTERED_NATIVE_ACTION')
    for folder in ('intents','episodes'):
        require({p.name for p in (out/folder).glob('*.json')}=={f'{i:06d}.json' for i in range(c['cycles'])},'UNREGISTERED_EPISODE_FILE')
    expected={'contract_sha256':digest(contract),'source':contract['source'],'stress':contract['stress'],
        'cycles':c['cycles'],'settled':counts['SETTLED'],'refunded':counts['REFUNDED'],
        'nonentry':counts['NONENTRY'],'no_payment':counts['NO_PAYMENT'],
        'modeled_revenue_cents':revenue,'modeled_operating_cost_cents':expenses,'modeled_tax_cents':tax,
        'modeled_research_cost_cents':amount if eligible else 0,
        'modeled_profit_cents':revenue-expenses-tax-(amount if eligible else 0),
        'native_summary':record['ledger']['summary'],'native_export_sha256':digest(record),
        'research':research,'actual_revenue_usd':0,'external_model_calls':0,
        'complete_actual_lifecycle_cost':'UNMEASURED','blue_sky_breakthrough':'NOT_ESTABLISHED',
        'autonomous_frontier_model_campaign':'NOT_EXECUTED','meta_discovery_superiority':'NOT_ESTABLISHED',
        'schema':'genesis002/result/v1','complete':True,'scope':'SIMULATED_NATIVE_ACCOUNT','native_audit':native}
    require(canonical(report)==canonical(expected),'REPORTED_RESULT_DIFFERS_FROM_RECONSTRUCTED_OPERATION')
    return {'accepted':True,'native_journal_entries':len(entries),'native_actions':len(actions),
            'settled_deliveries':counts['SETTLED'],'earned_funded_repeat_deliveries':earned_deliveries,
            'research_paid_from_earnings':eligible,'modeled_profit_cents':expected['modeled_profit_cents'],
            'scope':'Source-bound execution and hypothetical commerce; no actual customer, profit or discovery claim.'}
