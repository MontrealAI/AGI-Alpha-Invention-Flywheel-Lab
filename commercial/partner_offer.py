"""Proof-bound, incentive-compatible *proposal* for partner-distributed outcomes.

No lead is invented, no customer is contacted, and no cash moves. A proposal
cannot become a native order or native business profit without a separate,
authorized buyer decision and native settlement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from commercial.portable_offer import verify as verify_proof

SCHEMA = 'agi-alpha/proof-led-partner-offer/v1'
MAX = 10**14


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:raise ValueError('DUPLICATE_FIELD')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def integer(value, name):
    if type(value) is not int or not 0 <= value <= MAX:
        raise ValueError('NONNEGATIVE_INTEGER_CENTS_REQUIRED:' + name)
    return value


def safe(path):
    p = Path(path).absolute()
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise ValueError('SYMLINK_PATH_REFUSED')
    return p


def quote_terms(price, distributor_cost, distributor_min_gain,
                provider_complete_cost, provider_min_gain,
                activation_cost, provider_loss_cost, protected_cash, opening_cash):
    """Fixed-price bilateral participation gate, not a calibrated market equilibrium.

    Complete settled cost includes inference, delivery, independent review,
    transaction costs, support, taxes and amortized construction/failures.
    """
    amounts = dict(price=price, distributor_cost=distributor_cost,
                   distributor_min_gain=distributor_min_gain,
                   provider_complete_cost=provider_complete_cost,
                   provider_min_gain=provider_min_gain,
                   activation_cost=activation_cost,
                   provider_loss_cost=provider_loss_cost,
                   protected_cash=protected_cash, opening_cash=opening_cash)
    for key, value in amounts.items():integer(value, key)
    if price == 0 or provider_complete_cost == 0:
        raise ValueError('POSITIVE_PRICE_AND_COMPLETE_DELIVERY_COST_REQUIRED')
    minimum_share = distributor_cost + distributor_min_gain
    maximum_share = price - provider_complete_cost - activation_cost - provider_min_gain
    funded = opening_cash >= activation_cost + protected_cash + provider_loss_cost
    feasible = minimum_share <= maximum_share and funded
    share = minimum_share if feasible else None
    provider_gain = (price - share - provider_complete_cost - activation_cost) if feasible else None
    return {'scenario': amounts,
            'status': 'CONDITIONALLY_FEASIBLE_QUOTE' if feasible else 'NO_BID',
            'partner_share_if_collected_cents': share,
            'partner_gain_if_collected_cents': distributor_min_gain if feasible else None,
            'provider_gain_if_collected_cents': provider_gain,
            'failed_collection_provider_loss_cents': activation_cost + provider_loss_cost,
            'no_sale_provider_loss_cents': activation_cost,
            'required_upfront_liquidity_cents': activation_cost + protected_cash + provider_loss_cost,
            'no_demand_means_no_sales': True,
            'terms_are_assumptions_not_observed_partner_acceptance': True}


def expected(proof_dir, costs):
    proof_dir = safe(proof_dir)
    checked = verify_proof(proof_dir)
    if checked['qualification'] != 'QUALIFIED_SYNTHETIC_DELIVERY':
        raise ValueError('UNQUALIFIED_OUTCOME_CANNOT_SUPPORT_PARTNER_OFFER')
    quoted = strict_json((proof_dir/'OFFER.json').read_bytes())['quoted_price_cents']
    if checked['quoted_price_cents'] != quoted:
        raise ValueError('SOURCE_QUOTE_AND_VERIFIER_DISAGREE')
    contract = quote_terms(quoted, **costs)
    return {'schema': SCHEMA, 'source_proof_sha256': checked['manifest_sha256'],
            'proof_qualification': checked['qualification'],
            'proposal': contract,
            'scope': 'SYNTHETIC_UNEXECUTED_COMMERCIAL_PROPOSAL',
            'buyer_accepted': False, 'partner_accepted': False,
            'native_financial_authority': False, 'actual_collections_cents': 0,
            'actual_profit_cents': None,
            'limits': ['Price and participation thresholds are uncalibrated assumptions.',
                       'External buyer value, conversion, collections and partner willingness are unknown.',
                       'Partner share is contingent on verified collection; no partner has accepted these terms.',
                       'No refunds, deposits or native account transactions are performed here.']}


def build(proof_dir, output, **costs):
    record = expected(proof_dir, costs)
    target = safe(output)
    target.mkdir(parents=True, exist_ok=False)
    (target/'PARTNER_OFFER.json').write_bytes(canonical(record))
    return verify(proof_dir, target)


def verify(proof_dir, package, *, expected_sha256=None):
    target = safe(package)
    if not target.is_dir() or {p.relative_to(target).as_posix() for p in target.rglob('*')} != {'PARTNER_OFFER.json'}:
        raise ValueError('EXACT_PARTNER_PACKAGE_REQUIRED')
    source = safe(target/'PARTNER_OFFER.json')
    if not source.is_file():
        raise ValueError('REGULAR_PARTNER_PROPOSAL_REQUIRED')
    raw = source.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None:
        if (not isinstance(expected_sha256,str) or len(expected_sha256)!=64
                or any(c not in '0123456789abcdef' for c in expected_sha256)):
            raise ValueError('EXACT_EXTERNAL_PROPOSAL_PIN_REQUIRED')
        if actual_sha256 != expected_sha256:
            raise ValueError('EXTERNALLY_PINNED_PARTNER_TERMS_CHANGED')
    if len(raw) > 50000:raise ValueError('PARTNER_PROPOSAL_TOO_LARGE')
    record = strict_json(raw)
    if not isinstance(record, dict) or record.get('schema') != SCHEMA:
        raise ValueError('EXACT_PARTNER_SCHEMA_REQUIRED')
    proposal = record.get('proposal')
    if not isinstance(proposal, dict):
        raise ValueError('COST_AND_PARTICIPATION_CONTRACT_REQUIRED')
    costs = proposal.get('scenario')
    if not isinstance(costs, dict):
        raise ValueError('COST_AND_PARTICIPATION_CONTRACT_REQUIRED')
    recomputed = expected(proof_dir, {k:v for k,v in costs.items() if k!='price'})
    if record != recomputed or raw != canonical(recomputed):
        raise ValueError('PARTNER_PROPOSAL_OR_SOURCE_BINDING_CHANGED')
    return {'proof_sha256': record['source_proof_sha256'],
            'proposal_status': record['proposal']['status'],
            'provider_gain_if_collected_cents': record['proposal']['provider_gain_if_collected_cents'],
            'partner_share_if_collected_cents': record['proposal']['partner_share_if_collected_cents'],
            'rechecked': True, 'proposal_sha256': actual_sha256,
            'partner_terms_externally_pinned': expected_sha256 is not None,
            'actual_collections_cents': 0, 'native_financial_authority': False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build')
    b.add_argument('--proof-dir',required=True)
    b.add_argument('--output',required=True)
    for key in ('distributor_cost','distributor_min_gain','provider_complete_cost',
                'provider_min_gain','activation_cost','provider_loss_cost',
                'protected_cash','opening_cash'):
        b.add_argument('--'+key.replace('_','-'),type=int,required=True)
    v=sub.add_parser('verify')
    v.add_argument('--proof-dir',required=True)
    v.add_argument('--package',required=True)
    v.add_argument('--expected-sha256')
    args=p.parse_args()
    try:
        if args.command=='build':
            costs={key:getattr(args,key) for key in ('distributor_cost','distributor_min_gain','provider_complete_cost',
                'provider_min_gain','activation_cost','provider_loss_cost','protected_cash','opening_cash')}
            result=build(args.proof_dir,args.output,**costs)
        else:result=verify(args.proof_dir,args.package,expected_sha256=args.expected_sha256)
    except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as exc:
        p.exit(2,'REFUSED: '+str(exc)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
