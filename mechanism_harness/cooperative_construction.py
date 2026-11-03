"""Finite cooperative capability construction, with actual bounded adapter work.

The economic result is an audited proposed arrangement, not an account or receipt.
All productive primitives/grammar and the game are developer-authored. Discovery
executes a finite data-only search; no shell, network, credentials or eval exist.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import time

from commercial.ledger import canonical, digest, strict_json
from adaptive_enterprise import instruments as substrate
from adaptive_enterprise.checkers import audit_delivery
from . import inventor

ROOT=Path(__file__).resolve().parents[1]
DEVELOPMENT=(61011,8)
SUCCESSORS=((61012,9),(61013,14))
COST_ENVELOPE={'acquisition':100,'construction':500,'verification':150,'support':100,'maintenance':50}
MARGIN_CENTS=60
MODES=('retained','cold','equal_content_reuse','conventional','nonentry')


def validate_spec(spec):
    if type(spec) is not dict or set(spec)!={'participants','costs','margin_cents'}:
        raise ValueError('EXACT_COOPERATIVE_SPEC_REQUIRED')
    people=spec['participants'];costs=spec['costs']
    if not isinstance(people,list) or not 1<=len(people)<=12:
        raise ValueError('FINITE_NONEMPTY_PARTICIPANTS_REQUIRED')
    if type(costs) is not dict or set(costs)!=set(COST_ENVELOPE):
        raise ValueError('COMPLETE_ENVELOPE_REQUIRED')
    for x in [*costs.values(),spec['margin_cents']]:
        if type(x) is not int or not 0<=x<=10**12:raise ValueError('NONNEGATIVE_INTEGER_CENTS_REQUIRED')
    ids=[]
    for p in people:
        if type(p) is not dict or set(p)!={'id','value_cents','budget_cents','outside_utility_cents'}:
            raise ValueError('EXPLICIT_PARTICIPANT_REQUIRED')
        if type(p['id']) is not str or not p['id'] or len(p['id'])>80:raise ValueError('PARTICIPANT_ID_REQUIRED')
        ids.append(p['id'])
        for key in ('value_cents','budget_cents','outside_utility_cents'):
            if type(p[key]) is not int or not 0<=p[key]<=10**12:raise ValueError('PARTICIPANT_INTEGER_CENTS_REQUIRED')
    if len(ids)!=len(set(ids)):raise ValueError('UNIQUE_PARTICIPANT_IDS_REQUIRED')
    return spec


def fixture(stress='central'):
    people=[{'id':f'beneficiary-{i}','value_cents':800,'budget_cents':650,'outside_utility_cents':0} for i in range(3)]
    costs=dict(COST_ENVELOPE)
    if stress=='weak':
        for p in people:p['value_cents']=250
    elif stress=='no_demand':
        for p in people:p['value_cents']=0
    elif stress=='copycat':
        for p in people:p['outside_utility_cents']=p['value_cents']
    elif stress=='withdrawal':people=people[:-1]
    elif stress=='overrun':costs['construction']+=1100
    elif stress not in ('central','delayed_commitment','failed_verification'):raise ValueError('REGISTERED_STRESS_REQUIRED')
    return {'participants':people,'costs':costs,'margin_cents':MARGIN_CENTS}


def verify_arrangement(spec,proposal):
    """Independent all-payer withdrawal check, including public free riding.

    Binary public capability, all-or-nothing production. Simultaneous coalition
    deviations, strategic value reporting and transferability are not certified.
    """
    validate_spec(spec)
    required=sum(spec['costs'].values())+spec['margin_cents']
    if type(proposal) is not dict or set(proposal)!={'contributions_cents','delivery'} or proposal['delivery']!='public_capability':
        raise ValueError('EXACT_PUBLIC_CAPABILITY_CONTRACT_REQUIRED')
    contributions=proposal['contributions_cents']
    if type(contributions) is not dict or set(contributions)!={p['id'] for p in spec['participants']}:
        raise ValueError('COMPLETE_CONTRIBUTION_MAP_REQUIRED')
    if any(type(x) is not int or x<0 or x>10**12 for x in contributions.values()):raise ValueError('INTEGER_CONTRIBUTIONS_REQUIRED')
    total=sum(contributions.values());errors=[];deviations=[]
    if not any(contributions.values()):errors.append({'kind':'NO_VOLUNTARY_PAYER'})
    if total<required:errors.append({'kind':'UNDERFUNDED','required_cents':required,'proposed_cents':total})
    for p in spec['participants']:
        amount=contributions[p['id']]
        if amount>p['budget_cents']:errors.append({'kind':'BUDGET','participant':p['id']})
        if not amount:continue
        if p['value_cents']-amount<=p['outside_utility_cents']:
            errors.append({'kind':'DECLINE','participant':p['id']})
        # A nonpayer retains public outcome access if others cover the threshold.
        others=total-amount
        withdrawal=(max(p['value_cents'],p['outside_utility_cents']) if others>=required else p['outside_utility_cents'])
        paying=max(p['value_cents'],p['outside_utility_cents'])-amount if total>=required else p['outside_utility_cents']
        deviations.append({'participant':p['id'],'pay_utility_cents':paying,'withdraw_utility_cents':withdrawal,'remaining_cents':others})
        if withdrawal>paying:errors.append({'kind':'PROFITABLE_WITHDRAWAL','participant':p['id'],'gain_cents':withdrawal-paying})
    return {'accepted':not errors,'errors':errors,'deviations':deviations,'required_cents':required,
            'proposed_cents':total,'scope':'Finite binary public-good unilateral withdrawal; public assumed values, no truthful-elicitation or coalition-proofness claim.'}


def _proposals(spec):
    """Generated data-only contracts: every nonempty coalition, equal cost shares."""
    people=spec['participants'];required=sum(spec['costs'].values())+spec['margin_cents']
    for size in range(1,len(people)+1):
        for coalition in itertools.combinations(people,size):
            amounts={p['id']:0 for p in people};q,r=divmod(required,size)
            for j,p in enumerate(coalition):amounts[p['id']]=q+(j<r)
            yield {'contributions_cents':amounts,'delivery':'public_capability'}


def construct_arrangement(spec):
    validate_spec(spec);criticisms=[];attempts=0
    # A natural but defective proposal: pledge every participant's spare budget.
    naive={'contributions_cents':{p['id']:min(p['budget_cents'],max(0,p['value_cents']-p['outside_utility_cents']-1)) for p in spec['participants']},'delivery':'public_capability'}
    check=verify_arrangement(spec,naive);attempts+=1
    if not check['accepted']:criticisms.append({'program':naive,'verification':check})
    accepted=[]
    for proposal in _proposals(spec):
        checked=verify_arrangement(spec,proposal);attempts+=1
        if checked['accepted']:accepted.append(proposal)
    # Neutral public rule: minimal payer count, then lexical identity. No private
    # values are learned from realized future acceptance.
    best=min(accepted,key=lambda p:(sum(x>0 for x in p['contributions_cents'].values()),digest(p))) if accepted else None
    return {'proposal':best,'verification':None if best is None else verify_arrangement(spec,best),
            'attempted_contracts':attempts,'criticisms':criticisms,'decision':'PROPOSE' if best else 'NONENTRY',
            'cash_received_cents':0,'revenue_cents':0,'financial_execution':False}


def ordinary_shared_commission(spec):
    """Strong independent exhaustive control; same complete feasible set."""
    validate_spec(spec);people=spec['participants'];threshold=sum(spec['costs'].values())+spec['margin_cents'];candidates=[]
    for bits in range(1,1<<len(people)):
        payers=[p for j,p in enumerate(people) if bits&(1<<j)]
        shares={p['id']:0 for p in people}
        for j,p in enumerate(payers):shares[p['id']]=threshold//len(payers)+int(j<threshold%len(payers))
        if any(shares.values()) and all(shares[p['id']]<=p['budget_cents'] and p['value_cents']-shares[p['id']]>p['outside_utility_cents'] for p in payers):
            # Exact threshold makes each positive payer pivotal.
            candidates.append({'contributions_cents':shares,'delivery':'public_capability'})
    return min(candidates,key=lambda p:(sum(x>0 for x in p['contributions_cents'].values()),digest(p))) if candidates else None


def _measured(raw,policy=None,*,conventional=False):
    start=time.process_time_ns()
    if conventional:artifact=substrate.produce(raw,'generated_schema',mode='conventional')
    else:artifact=inventor.execute(raw,policy)
    construction_cpu=time.process_time_ns()-start
    start=time.process_time_ns();check=audit_delivery('reconciliation',raw,artifact);verification_cpu=time.process_time_ns()-start
    return {'source_sha256':digest(raw),'artifact':artifact,'artifact_sha256':digest(artifact),'verification':check,
            'complete':artifact['outcome_scope']=='complete_outcome','work':artifact['plan']['search']['operation_count'],
            'construction_cpu_ns':construction_cpu,'verification_cpu_ns':verification_cpu}


def execute_production(*, include_telemetry=False):
    """Actual bounded productive successor; finance must be posted by the caller."""
    first=substrate.synthetic_raw('reconciliation',DEVELOPMENT[1],DEVELOPMENT[0]);start=time.process_time_ns()
    learned=inventor.learn([first]);learning_cpu=time.process_time_ns()-start
    first_result=_measured(first,learned['policy']);successors=[]
    for seed,index in SUCCESSORS:
        raw=substrate.synthetic_raw('reconciliation',index,seed)
        runs={'retained':_measured(raw,learned['policy']),'cold':_measured(raw,inventor.policy()),
              'equal_content_reuse':_measured(raw,copy.deepcopy(learned['policy'])),
              'conventional':_measured(raw,conventional=True),'nonentry':{'complete':False,'work':0,'reason':'NO_PRODUCTION'}}
        old_mapping_executes=False;old_mapping_accepts=False;old_mapping_failure=None
        try:
            prior_plan=first_result['artifact']['plan']
            normalized=substrate.execute_plan(raw,prior_plan)
            old_mapping_executes=normalized is not None
            old_artifact={'order_id':raw['order_id'],'service_id':'reconciliation','scope':raw['scope'],'currency':'USD',
                          'outcome_scope':'complete_outcome','method':'generated_schema','plan':prior_plan,
                          'normalized_input':normalized,'useful_outcome':inventor.deliver('reconciliation',normalized)}
            old_check=audit_delivery('reconciliation',raw,old_artifact)
            old_mapping_accepts=old_check['accepted'];old_mapping_failure=old_check['errors']
        except (ValueError,KeyError,TypeError) as exc:old_mapping_failure=type(exc).__name__+':'+str(exc)
        successors.append({'seed':seed,'index':index,'source_sha256':digest(raw),'runs':runs,
                           'direct_predecessor_mapping_executes':old_mapping_executes,'direct_predecessor_mapping_accepted':old_mapping_accepts,
                           'direct_predecessor_mapping_failure':old_mapping_failure})
    all_checked=first_result['verification']['accepted'] and first_result['complete'] and all(r['verification']['accepted'] and r['complete'] for case in successors for key,r in case['runs'].items() if key!='nonentry')
    reuse_ties=all(logical(x['runs']['retained'])==logical(x['runs']['equal_content_reuse']) for x in successors)
    same_outcomes=all(digest(x['runs']['retained']['artifact']['useful_outcome'])==digest(x['runs']['conventional']['artifact']['useful_outcome'])==digest(x['runs']['cold']['artifact']['useful_outcome']) for x in successors)
    result={'first':first_result,'learned_policy':learned['policy'],'acquisition_work':learned['acquisition_work'],
            'candidate_count':len(learned['development_candidates']),'learning_cpu_ns':learning_cpu,'successors':successors,
            'all_accepted_complete':all_checked,'equal_content_reuse_ties':reuse_ties,'strong_conventional_outcome_ties':same_outcomes,
            'total_retained_work_including_acquisition':learned['acquisition_work']+first_result['work']+sum(x['runs']['retained']['work'] for x in successors),
            'successor_cold_work':sum(x['runs']['cold']['work'] for x in successors),
            'successor_retained_work':sum(x['runs']['retained']['work'] for x in successors),
            'scope':'Existing finite developer-authored grammar; generated policy and freshly inferred mappings. CPU is measured separately when requested; lifecycle dollar costs unknown. Conventional counters have different scope.'}
    return result if include_telemetry else logical(result)


def verify_production(result):
    # Every artifact is independently checked against its original input; exact
    # deterministic reconstruction additionally rejects changed cost/learning claims.
    expected=execute_production()
    return {'accepted':logical(result)==expected and expected['all_accepted_complete'],
            'logical_sha256':digest(logical(result)),
            'scope':'Independent artifact checks plus bounded deterministic source-matched replay; no financial settlement.'}


def execute():
    production=execute_production(include_telemetry=True);cases=[]
    for stress in ('central','weak','no_demand','copycat','withdrawal','delayed_commitment','failed_verification','overrun'):
        spec=fixture(stress);generated=construct_arrangement(spec);ordinary=ordinary_shared_commission(spec)
        separate=[]
        for p in spec['participants']:
            single={**spec,'participants':[p]};separate.append(construct_arrangement(single)['decision'])
        # No conditional pledge is spendable. An unreceived promise or failed
        # verification cannot be promoted into an executed accepted commission.
        stress_check=None
        if stress=='failed_verification':
            raw=substrate.synthetic_raw('reconciliation',DEVELOPMENT[1],DEVELOPMENT[0])
            corrupted=copy.deepcopy(production['first']['artifact']);corrupted['useful_outcome']={'counterfeit':True}
            stress_check=audit_delivery('reconciliation',raw,corrupted)
        ready=generated['proposal'] is not None and stress!='delayed_commitment' and production['all_accepted_complete'] and (stress_check is None or stress_check['accepted'])
        cases.append({'stress':stress,'spec':spec,'generated':generated,'ordinary_shared_proposal':ordinary,
                      'ordinary_ties':generated['proposal']==ordinary,'separate_decisions':separate,
                      'conditionally_feasible':ready,'financial_execution':False,'nonentry_cents':0,'injected_delivery_check':stress_check,
                      'blocking_reason':('COMMITMENTS_NOT_RECEIVED' if stress=='delayed_commitment' else 'INDEPENDENT_ACCEPTANCE_FAILED' if stress=='failed_verification' else None)})
    return {'schema':'omega/cooperative-construction/v1','production':production,'arrangements':cases,
            'newly_attainable_vs_strong_incumbent':False,'discovery_superiority_established':False,
            'native_financial_execution':False,'actual_revenue_usd':0,'complete_lifecycle_cost_usd':None,
            'scope':'Executed productive prototype and audited conditional game proposals. No assurance-contract settlement, observed demand, novel discovery advantage or Blue Sky admission.'}


def logical(value):
    if isinstance(value,dict):return {k:logical(v) for k,v in value.items() if not k.endswith('_cpu_ns')}
    if isinstance(value,list):return [logical(v) for v in value]
    return value


def source_identity():
    names=set(substrate.SOURCE_PATHS)|{'mechanism_harness/cooperative_construction.py','mechanism_harness/inventor.py','campaign/omega-economy-v4/COOPERATIVE_PROTOCOL.md'}
    result={}
    for name in sorted(names):
        p=ROOT/name
        if not p.is_file() or any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('REGULAR_SOURCE_REQUIRED')
        result[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def audit(report):
    if report.get('source')!=source_identity():raise ValueError('SOURCE_CHANGED')
    for case in report['arrangements']:
        proposal=case['generated']['proposal']
        if proposal and verify_arrangement(case['spec'],proposal)!=case['generated']['verification']:raise ValueError('GAME_VERIFICATION_CHANGED')
    actual=execute()
    if logical({k:v for k,v in report.items() if k!='source'})!=logical(actual):raise ValueError('REPLAY_CHANGED')
    return {'accepted':True,'logical_sha256':digest(logical(report)),'scope':actual['scope']}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--audit',action='store_true');args=parser.parse_args(argv)
    p=args.output.absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):raise ValueError('REGULAR_OWNED_OUTPUT_REQUIRED')
    if args.audit:print(json.dumps(audit(strict_json(p.read_bytes())),indent=2));return
    if p.exists():raise FileExistsError('PRESERVE_EXISTING_EVIDENCE')
    before=source_identity();report=execute()
    if before!=source_identity():raise ValueError('SOURCE_CHANGED_DURING_EXECUTION')
    report['source']=before;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as stream:stream.write(canonical(report)+b'\n')
    print(json.dumps({'all_accepted_complete':report['production']['all_accepted_complete'],'equal_content_reuse_ties':report['production']['equal_content_reuse_ties'],'strong_conventional_outcome_ties':report['production']['strong_conventional_outcome_ties'],'native_financial_execution':False,'cases':[{k:v for k,v in c.items() if k in ('stress','conditionally_feasible','ordinary_ties','blocking_reason')} for c in report['arrangements']]},indent=2))

if __name__=='__main__':main()
