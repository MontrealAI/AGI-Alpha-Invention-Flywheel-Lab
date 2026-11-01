"""Construct an offered multilateral outcome market from independently checked work.

Pure finite contract design; never owns a ledger, authenticates counterparties,
executes agreements, contacts buyers, or earns money. Synthetic tests only.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import re

SCHEMA = 'agi-alpha/complementary-outcome-market045/v1'
REQUIRED = {'delivery', 'independent-proof', 'distribution', 'portable-trace'}
PRICE_LIMIT = 10**13


def canonical(x):
    return (json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ValueError('DUPLICATE_FIELD')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def need(ok, code):
    if not ok: raise ValueError(code)


def amount(x):
    need(type(x) is int and 0<=x<=PRICE_LIMIT,'FINITE_NONNEGATIVE_CENTS_REQUIRED')
    return x


def name(x):
    need(type(x) is str and re.fullmatch('[a-z][a-z0-9_-]{0,47}',x) is not None,'SAFE_IDENTIFIER_REQUIRED')
    return x


def path(path):
    p=Path(path).absolute()
    need(not any(x.is_symlink() for x in (p,*p.parents)), 'SYMLINK_PATH_REFUSED')
    return p


def validate(buyer,bids):
    need(type(buyer) is dict and set(buyer)=={'schema','scope','buyer_declared_value_cents','buyer_budget_cents',
         'buyer_outside_surplus_cents','available_cash_cents','protected_cash_cents','max_noncollection_loss_cents',
         'required','current_day','maximum_counterparties'},'EXACT_BUYER_DECLARATION_REQUIRED')
    need(buyer['schema']==SCHEMA and buyer['scope']=='SYNTHETIC_PUBLIC_WORKLOAD', 'SYNTHETIC_BUYER_SCOPE_REQUIRED')
    for key in ('buyer_declared_value_cents','buyer_budget_cents','buyer_outside_surplus_cents','available_cash_cents',
                'protected_cash_cents','max_noncollection_loss_cents','current_day'):
        amount(buyer[key])
    need(type(buyer['maximum_counterparties']) is int and 1<=buyer['maximum_counterparties']<=12,'FINITE_COALITION_LIMIT_REQUIRED')
    need(type(buyer['required']) is list and len(buyer['required'])==4 and set(buyer['required'])==REQUIRED,
         'COMPLETE_OUTCOME_REQUIREMENTS_REQUIRED')
    need(all(type(x) is str for x in buyer['required']), 'STRING_REQUIREMENTS_REQUIRED')
    need(type(bids) is list and 1<=len(bids)<=12,'BOUNDED_BID_SET_REQUIRED')
    ids=set()
    for b in bids:
        need(type(b) is dict and set(b)=={'id','provider','coverage','requires','settled_cost_cents',
            'minimum_gain_cents','activation_cost_cents','noncollection_loss_cents','failure_guarantee_cents',
            'expiry_day','rights','evidence_ref'},'EXACT_CAPABILITY_BID_REQUIRED')
        i=name(b['id']); name(b['provider']);name(b['evidence_ref'])
        need(i not in ids,'UNIQUE_BID_REQUIRED');ids.add(i)
        need(type(b['coverage']) is list and 1<=len(b['coverage'])<=len(REQUIRED) and
             all(type(x) is str and x in REQUIRED for x in b['coverage']) and
             len(set(b['coverage']))==len(b['coverage']),'QUALIFIED_CAPABILITY_TAGS_REQUIRED')
        need(type(b['requires']) is list and all(type(x) is str for x in b['requires']) and
             len(set(b['requires']))==len(b['requires']) and len(b['requires'])<=8,'FINITE_DECLARED_DEPENDENCIES_REQUIRED')
        for x in b['requires']:name(x)
        for key in ('settled_cost_cents','minimum_gain_cents','activation_cost_cents',
                    'noncollection_loss_cents','failure_guarantee_cents','expiry_day'):
            amount(b[key])
        need(type(b['rights']) is str and b['rights'] in {'PERMITTED','UNKNOWN','DENIED'},'DECLARED_RIGHTS_STATUS_REQUIRED')
        need(b['failure_guarantee_cents']>=b['noncollection_loss_cents'],'SUPPLIER_DOWNSIDE_COVERAGE_REQUIRED')
    for b in bids:
        need(b['id'] not in b['requires'] and set(b['requires'])<=ids,'EXISTING_NO_SELF_DEPENDENCY_REQUIRED')
    return buyer,bids


def solve(buyer,bids,quoted_price_cents):
    """Exact max-retained-surplus subset among declared posted-price bids.

    Conditional only: all costs, buyer values, rights and provider bids are
    declared, not independently authenticated. No truthful-reporting theorem.
    """
    validate(buyer,bids);amount(quoted_price_cents)
    need(quoted_price_cents>0,'POSITIVE_SOURCE_BOUND_QUOTE_REQUIRED')
    scenarios={'insufficient_buyer_value':0,'incomplete_capability':0,'verification_conflict':0,
               'unfunded_downside':0,'insufficient_surplus':0,'expired_or_rights':0,'missing_dependency':0}
    best=None;candidate_count=0
    for k in range(1, min(len(bids), buyer['maximum_counterparties'])+1):
        for subset in itertools.combinations(bids,k):
            candidate_count+=1; ids={b['id'] for b in subset}; providers=[b['provider'] for b in subset]
            supplied={tag for b in subset for tag in b['coverage']}
            if not REQUIRED<=supplied or len(providers)!=len(set(providers)):
                scenarios['incomplete_capability']+=1;continue
            if any(b['rights']!='PERMITTED' or b['expiry_day']<=buyer['current_day'] for b in subset):
                scenarios['expired_or_rights']+=1;continue
            if any(not set(b['requires'])<=ids for b in subset):
                scenarios['missing_dependency']+=1;continue
            checkers={b['provider'] for b in subset if 'independent-proof' in b['coverage']}
            builders={b['provider'] for b in subset if 'delivery' in b['coverage']}
            if checkers&builders or any({'independent-proof','delivery'}<=set(b['coverage']) for b in subset):
                scenarios['verification_conflict']+=1;continue
            if quoted_price_cents>buyer['buyer_budget_cents'] or (
                buyer['buyer_declared_value_cents']-quoted_price_cents<buyer['buyer_outside_surplus_cents']):
                scenarios['insufficient_buyer_value']+=1;continue
            activation=sum(b['activation_cost_cents'] for b in subset)
            downside=sum(b['failure_guarantee_cents'] for b in subset)+activation
            if downside>buyer['max_noncollection_loss_cents'] or (
                 buyer['available_cash_cents']<buyer['protected_cash_cents']+downside):
                scenarios['unfunded_downside']+=1;continue
            contingent={b['id']:b['settled_cost_cents']+b['minimum_gain_cents'] for b in subset}
            retained=quoted_price_cents-sum(contingent.values())-activation
            if retained<=0:
                scenarios['insufficient_surplus']+=1;continue
            row={'bids':sorted(ids),'providers':sorted(providers),'contingent_supplier_shares_cents':contingent,
                 'total_activation_cents':activation,'funded_noncollection_exposure_cents':downside,
                 'enterprise_retained_gain_if_collected_cents':retained,
                 'buyer_declared_gain_cents':buyer['buyer_declared_value_cents']-quoted_price_cents,
                 'buyer_declared_gain_over_outside_cents':buyer['buyer_declared_value_cents']-quoted_price_cents-buyer['buyer_outside_surplus_cents'],
                 'supplier_declared_gains_cents':{b['id']:b['minimum_gain_cents'] for b in subset},
                 'no_sale_enterprise_loss_cents':activation,'noncollection_enterprise_loss_cents':downside}
            key=(-retained,activation,len(subset),tuple(row['bids']))
            if best is None or key<best[0]:best=(key,row)
    winning=best[1] if best else None
    return {'schema':SCHEMA,'status':'CONDITIONALLY_FEASIBLE_COALITION' if winning else 'NO_BID',
            'source_quote_cents':quoted_price_cents,'winning_coalition':winning,
            'candidates_inspected':candidate_count,'rejection_counts':scenarios,
            'buyer_input_sha256':sha(canonical(buyer)),'supplier_bids_sha256':sha(canonical(bids)),
            'claim_scope':'EXACT_FINITE_DECLARED_POSTED_PRICE_COALITION_SELECTION_NOT_BAYESIAN_IC',
            'buyer_accepted':False,'suppliers_accepted':False,'actual_customers':0,'actual_collections_cents':0,
            'actual_profit_cents':None,'funding_authority':False,'current_proof':None,'authority':[],
            'asset_capsule':({'source_instrument':'portable-source-bound-deliverable','capability_conditions':list(buyer['required']),
                             'requires_fresh_proof':True,'rights_authenticated':False,'authority':[],'current_proof':None}
                             if winning else None)}


def verified_result(proof_dir, buyer, bids):
    from commercial.portable_offer import verify as verify_proof
    checked=verify_proof(path(proof_dir))
    need(checked['qualification']=='QUALIFIED_SYNTHETIC_DELIVERY' and checked['source_bound'] is True,
         'INDEPENDENTLY_REDERIVED_PROOF_REQUIRED')
    result=solve(buyer,bids,checked['quoted_price_cents'])
    return {'schema':SCHEMA,'scope':'SYNTHETIC_PROPOSAL_ONLY_NOT_AN_AGREEMENT',
            'verified_proof_manifest_sha256':checked['manifest_sha256'],
            'buyer':buyer,'supplier_bids':bids,'result':result,
            'settlement_instruction':None,'native_account_mutation':False,
            'external_party_authorizations':[]}


def build(proof_dir, buyer, bids, output):
    record=verified_result(proof_dir,buyer,bids)
    target=path(output)
    target.mkdir(mode=0o700,parents=False,exist_ok=False)
    file=target/'COALITION.json'
    with file.open('xb') as f:
        f.write(canonical(record));f.flush();os.fsync(f.fileno())
    return verify(proof_dir,target)


def verify(proof_dir,package,*,expected_sha256=None):
    target=path(package)
    need(target.is_dir() and {p.relative_to(target).as_posix() for p in target.rglob('*')}=={'COALITION.json'},
         'EXACT_CONTRACT_PACKAGE_REQUIRED')
    raw=(target/'COALITION.json').read_bytes()
    need(len(raw)<=200000,'BOUNDED_CONTRACT_PACKAGE_REQUIRED')
    digest=sha(raw)
    if expected_sha256 is not None:
        need(type(expected_sha256) is str and re.fullmatch('[a-f0-9]{64}',expected_sha256) is not None,
             'EXACT_EXTERNAL_CONTRACT_PIN_REQUIRED')
        need(digest==expected_sha256,'EXTERNALLY_PINNED_COALITION_CHANGED')
    data=strict(raw)
    need(type(data) is dict and set(data)=={'schema','scope','verified_proof_manifest_sha256',
          'buyer','supplier_bids','result','settlement_instruction','native_account_mutation','external_party_authorizations'},
         'EXACT_CONTRACT_FIELDS_REQUIRED')
    expected=verified_result(proof_dir,data['buyer'],data['supplier_bids'])
    need(raw==canonical(expected),'COALITION_CERTIFICATE_OR_SOURCE_CHANGED')
    return {'recomputed':True,'status':expected['result']['status'],'proposal_sha256':digest,
            'source_proof_sha256':expected['verified_proof_manifest_sha256'],
            'actual_customers':0,'funding_authority':False,'cash_moved':False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='cmd',required=True)
    demo=sub.add_parser('demo');demo.add_argument('--output',required=True)
    checked=sub.add_parser('verify');checked.add_argument('--path',required=True);checked.add_argument('--expected-sha256')
    args=parser.parse_args(argv)
    try:
        if args.cmd=='demo':
            from commercial.portable_offer import build as build_proof
            root=path(args.output)
            root.mkdir(mode=0o700,exist_ok=False)
            here=Path(__file__).resolve().parents[1]
            case=strict((here/'campaign/market045/INPUT.json').read_bytes())
            build_proof(case['order'],root/'proof',price_cents=case['price_cents'])
            result=build(root/'proof',case['buyer'],case['bids'],root/'market')
        else:
            result=verify(path(args.path)/'proof',path(args.path)/'market',expected_sha256=args.expected_sha256)
    except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as e:
        parser.exit(2,'REFUSED: '+str(e)+'\n')
    print(json.dumps(result,sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
