import argparse
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys


def integer(value, name, lower=0):
    if type(value) is not int or not lower <= value <= 10**9:
        raise ValueError('INVALID_INTEGER:' + name)
    return value


def exact_fraction(value):
    if type(value) not in (str, int, Decimal, Fraction):
        raise ValueError('EXACT_FRACTION_REQUIRED')
    try:
        result = Fraction(value)
    except (ValueError, TypeError, OverflowError, ZeroDivisionError) as error:
        raise ValueError('INVALID_FRACTION') from error
    if not 0 <= result <= 1:
        raise ValueError('REDUCTION_FRACTION_OUT_OF_RANGE')
    return result


def normalize(contract, candidate_count=None):
    if type(contract) is not dict:
        raise ValueError('CONTRACT_OBJECT_REQUIRED')
    if contract.get('schema') == 'agi-alpha/denovo-pilot-protocol007/v1':
        if candidate_count is None:
            raise ValueError('MEASURED_CANDIDATE_COUNT_REQUIRED_FOR_LEGACY_PROTOCOL')
        threshold = contract['primary_pilot_threshold']
        return {'schema': 'agi-alpha/shortlist-constraint007/v1', 'candidate_count': candidate_count,
                'selector': {'kind': 'tie_inclusive_top_k', 'k': threshold['true_graph_in_tie_inclusive_first_rank_positions']},
                'minimum_reduction': threshold['minimum_fraction_candidate_reduction'],
                'maximum_retained': threshold['maximum_shortlist_size'], 'claim': 'possible', 'evidence_state': 'ORIGINAL_FROZEN_PROTOCOL'}
    required = {'schema', 'candidate_count', 'selector', 'minimum_reduction', 'maximum_retained', 'claim', 'evidence_state'}
    if set(contract) != required or contract['schema'] != 'agi-alpha/shortlist-constraint007/v1':
        raise ValueError('CONTRACT_SCHEMA')
    if candidate_count is not None and candidate_count != contract['candidate_count']:
        raise ValueError('CANDIDATE_COUNT_CONFLICT')
    return contract


def assess(contract, candidate_count=None):
    contract = normalize(contract, candidate_count)
    total = integer(contract['candidate_count'], 'candidate_count', 1)
    maximum = integer(contract['maximum_retained'], 'maximum_retained')
    reduction = exact_fraction(contract['minimum_reduction'])
    selector = contract['selector']
    if type(selector) is not dict:
        raise ValueError('SELECTOR_SCHEMA')
    if selector.get('kind') == 'tie_inclusive_top_k' and set(selector) == {'kind', 'k'}:
        requested = integer(selector['k'], 'k', 1)
        lower, upper = min(requested, total), total
        basis = 'A tie-inclusive first-k shortlist includes at least min(k,N) and may include all N when scores tie.'
    elif selector.get('kind') == 'exact_count' and set(selector) == {'kind', 'count'}:
        count = integer(selector['count'], 'count')
        if count > total:
            raise ValueError('COUNT_EXCEEDS_UNIVERSE')
        lower = upper = count
        basis = 'An explicitly defined exact-count operation has that arithmetic count. This is not a tie-inclusive rank selector or a truth-retention guarantee.'
    else:
        raise ValueError('UNSUPPORTED_SELECTOR')
    if contract['claim'] not in ('possible', 'guaranteed_for_selector_counts'):
        raise ValueError('UNSUPPORTED_CLAIM')
    if type(contract['evidence_state']) is not str or not contract['evidence_state']:
        raise ValueError('EVIDENCE_STATE_REQUIRED')
    residual = (1-reduction)*total
    reduction_cap = residual.numerator // residual.denominator
    permitted = min(total, maximum, reduction_cap)
    possible, guaranteed = lower <= permitted, upper <= permitted
    accepted = possible if contract['claim'] == 'possible' else guaranteed
    return {'schema': 'agi-alpha/protocol-preflight007/v1', 'accepted_arithmetic_claim': accepted,
            'decision': 'CONSISTENT_COUNTS_ONLY' if accepted else 'REFUSED_INCOMPATIBLE_COUNT_CONSTRAINTS',
            'candidate_count': total, 'selector': selector, 'selector_possible_count_interval': [lower, upper],
            'minimum_reduction_exact_fraction': str(reduction), 'maximum_count_from_reduction': reduction_cap,
            'maximum_retained_explicit': maximum, 'combined_maximum_allowed': permitted,
            'some_selector_count_can_satisfy': possible, 'all_selector_counts_satisfy': guaranteed,
            'requested_claim': contract['claim'], 'evidence_state': contract['evidence_state'], 'selector_basis': basis,
            'scope': 'Checks exact count-constraint arithmetic only. It does not certify actual tie counts, truth retention, statistical coverage, beneficiary utility, source validity, chemical identification, economic feasibility or an invention-policy improvement.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract', required=True)
    parser.add_argument('--candidate-count', type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source, output = Path(args.contract), Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    raw = source.read_bytes()
    result = assess(json.loads(raw, parse_float=Decimal), args.candidate_count)
    result.update({'contract_sha256': hashlib.sha256(raw).hexdigest(), 'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2);stream.write('\n')
    print(json.dumps({'decision': result['decision'], 'possible_count_interval': result['selector_possible_count_interval'], 'maximum_allowed': result['combined_maximum_allowed']}))
    sys.exit(0 if result['accepted_arithmetic_claim'] else 1)
