"""A public-evidence operating gate, not a new discovery or profit theorem.

All compared programs already exist in the charged campaign. Its construction,
failures and verification remain sunk costs whichever program is reused next.
No realized buyer choice, collection or future account outcome is an input.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
from pathlib import Path

from commercial.ledger import digest
from . import cart_campaign as campaign, cart_program as program

CANDIDATES = ('inherited', 'equal_content_reuse', 'full_control',
              'separate', 'bundle', 'nonentry')
POLICY = {
    'objective': 'Largest verified expected seller contribution in the declared public market; fixed lifecycle costs excluded.',
    'nonentry': 'Do not quote or observe a private buyer when no candidate has positive expected contribution.',
    'positive_ties': 'Remove only Pareto-dominated same-constructor construction rows and deviation checks; retain all remaining ties.',
    'last_tie_break': 'Lexical arm name, an explicit reproducibility convention with no economic superiority claim.',
    'cost_boundary': 'Work counts are comparable within this cart constructor only; all campaign work is already incurred and remains charged. Unknown dollar costs are not zero.',
}


def _counter(value):
    if type(value) is not int or value < 0:
        raise ValueError('NONNEGATIVE_OBSERVED_WORK_REQUIRED')
    return value


def _decision(case):
    market = case['market']
    candidates = []
    for name in CANDIDATES:
        run = case['runs'][name]
        rows = _counter(run['total_rows_built'])
        checks = _counter(run['deviation_checks'])
        check = None if run['program'] is None else program.verify(market, run['program'])
        eligible = check is not None and check['accepted']
        candidates.append({
            'arm': name, 'eligible': eligible,
            'program_sha256': None if run['program'] is None else digest(run['program']),
            'expected_contribution_cents': None if not eligible else check['expected_contribution_cents'],
            'construction_rows': rows, 'deviation_checks': checks,
            'reason': 'INDEPENDENT_CART_CHECK_ACCEPTED' if eligible else 'NO_ACCEPTED_EXECUTABLE_PROGRAM',
        })
    eligible = [x for x in candidates if x['eligible']]
    nonentry = next(x for x in eligible if x['arm'] == 'nonentry')
    if Fraction(nonentry['expected_contribution_cents']) != 0:
        raise ValueError('ZERO_CONTRIBUTION_NONENTRY_REQUIRED')
    best = max(Fraction(x['expected_contribution_cents']) for x in eligible)
    ties = [x for x in eligible if Fraction(x['expected_contribution_cents']) == best]
    if best <= 0:
        frontier = [nonentry]
    else:
        def dominates(left, right):
            keys = ('construction_rows', 'deviation_checks')
            return (all(left[k] <= right[k] for k in keys)
                    and any(left[k] < right[k] for k in keys))
        frontier = [x for x in ties if not any(dominates(y, x) for y in ties)]
    chosen = min(frontier, key=lambda x: x['arm'])
    return {
        'market_sha256': digest(market), 'selected_arm': chosen['arm'],
        'program_sha256': chosen['program_sha256'],
        'action': 'NONENTRY' if chosen['arm'] == 'nonentry' else 'OPERATE',
        'expected_contribution_cents': chosen['expected_contribution_cents'],
        'contribution_ties': sorted(x['arm'] for x in ties),
        'workload_frontier': sorted(x['arm'] for x in frontier),
        'lexical_tie_break_used': len(frontier) > 1,
        'candidates': candidates,
    }


def select(study):
    """Use a fully replayed public campaign before any private offer is made."""
    campaign.audit(study)
    return {
        'schema': 'omega/public-evidence-operating-gate/v1',
        'selector_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'study_logical_sha256': digest(campaign.logical(study)),
        'policy': copy.deepcopy(POLICY),
        'decisions': [_decision(case) for case in study['cases']],
        'sunk_study_work': {
            'construction_rows_by_arm': copy.deepcopy(study['total_rows_built']),
            'deviation_checks_by_arm': copy.deepcopy(study['total_deviation_checks']),
            'independent_verification_checks': study['independent_verification_checks'],
            'basis': 'All study arms and failed attempts remain incurred; selected-program work is not the cost of the complete study.',
        },
        'unknown_complete_lifecycle_cost_usd': None,
        'scope': 'Decision gate over available verified programs using declared public expectations. No new invention advantage, observed demand, strategic response cycle or complete-cost optimality claim.',
    }


def verify(study, receipt):
    expected = select(study)
    if receipt != expected:
        raise ValueError('PUBLIC_OPERATING_DECISION_CHANGED')
    return {'accepted': True, 'decision_sha256': digest(receipt),
            'scope': 'Public study replay, independent cart checks and deterministic decision reconstruction.'}


def selected_program(study, receipt, index):
    """Resolve one already-verified decision; callers verify the full receipt once."""
    if type(index) is not int or not 0 <= index < len(study['cases']):
        raise ValueError('REGISTERED_CASE_INDEX_REQUIRED')
    case = study['cases'][index]
    decision = receipt['decisions'][index]
    if decision['market_sha256'] != digest(case['market']):
        raise ValueError('OPERATING_MARKET_CHANGED')
    if decision['selected_arm'] not in CANDIDATES:
        raise ValueError('REGISTERED_OPERATING_CANDIDATE_REQUIRED')
    selected = case['runs'][decision['selected_arm']]['program']
    if (selected is None or digest(selected) != decision['program_sha256']
            or not program.verify(case['market'], selected)['accepted']):
        raise ValueError('OPERATING_PROGRAM_CHANGED')
    return copy.deepcopy(selected)
