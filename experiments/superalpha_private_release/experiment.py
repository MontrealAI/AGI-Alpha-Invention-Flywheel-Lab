"""Synthetic release feasibility; no cryptography, clinical inference or buyer model."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
RATIOS = (Fraction(11, 10), Fraction(2), Fraction(10), Fraction(19), Fraction(57))
TOL = 1e-8


def synthesize(states, ratio):
    """Optimize all channel probabilities, including refusal; no stored answers."""
    outputs = states + 1
    variables = states * outputs + 1
    objective = np.zeros(variables)
    objective[-1] = -1
    equalities, bounds, inequalities = [], [], []
    for i in range(states):
        row = np.zeros(variables)
        row[i * outputs:(i + 1) * outputs] = 1
        equalities.append(row)
        bounds.append(1)
        row = np.zeros(variables)
        row[-1], row[i * outputs + i] = 1, -1
        inequalities.append(row)
        for j in range(states):
            if i == j:
                continue
            for y in range(outputs):
                row = np.zeros(variables)
                row[i * outputs + y] = 1
                row[j * outputs + y] = -float(ratio)
                inequalities.append(row)
    result = linprog(objective, A_ub=inequalities,
                     b_ub=np.zeros(len(inequalities)), A_eq=equalities,
                     b_eq=bounds, bounds=(0, 1), method='highs')
    if not result.success:
        raise RuntimeError(result.message)
    return result.x[:-1].reshape(states, outputs)


def verify(channel, ratio):
    """Independent direct probability check, not the optimizer's status."""
    n = len(channel)
    if n < 2 or any(len(row) != n + 1 for row in channel):
        raise ValueError('channel shape')
    rows = [[float(p) for p in row] for row in channel]
    if not all(np.isfinite(p) and -TOL <= p <= 1 + TOL for row in rows for p in row):
        raise ValueError('invalid probability')
    if any(abs(sum(row) - 1) > TOL for row in rows):
        raise ValueError('not normalized')
    violation = max(rows[i][y] - float(ratio) * rows[j][y]
                    for i in range(n) for j in range(n) if i != j
                    for y in range(n + 1))
    return {'privacy_accepted': violation <= TOL,
            'max_privacy_violation': max(0.0, violation),
            'worst_complete_accuracy': min(rows[i][i] for i in range(n)),
            'max_refusal': max(row[-1] for row in rows)}


def ordinary_channel(states, ratio):
    # Generalized randomized response; Fraction arithmetic independent of LP.
    ratio = Fraction(ratio)
    denominator = ratio + states - 1
    return [[ratio / denominator if i == j else Fraction(1) / denominator
             for j in range(states)] + [Fraction(0)] for i in range(states)]


def exact_bound(states, ratio):
    # If every diagonal >=t, DP makes every off-diagonal >=t/ratio.
    # Each row sums to >=t+(states-1)*t/ratio; refusal cannot raise t.
    ratio = Fraction(ratio)
    return ratio / (ratio + states - 1)


def split_channel(ratio):
    # Two binary results about the SAME family; total budget is log(ratio).
    root = float(ratio) ** 0.5
    correct = root / (1 + root)
    return [[np.prod([correct if ((i >> k) & 1) == ((j >> k) & 1)
                      else 1 - correct for k in range(2)])
             for j in range(4)] + [0.0] for i in range(4)]


def run():
    cases = []
    for states in (2, 4):
        for ratio in RATIOS:
            generated = synthesize(states, ratio)
            checked = verify(generated, ratio)
            ordinary = verify(ordinary_channel(states, ratio), ratio)
            upper = exact_bound(states, ratio)
            assert checked['privacy_accepted'] and ordinary['privacy_accepted']
            assert abs(checked['worst_complete_accuracy'] - float(upper)) <= TOL
            assert abs(ordinary['worst_complete_accuracy'] - float(upper)) <= TOL
            case = {'states': states, 'likelihood_ratio_bound': str(ratio),
                    'optimum_exact': str(upper), 'generated': checked,
                    'ordinary_joint': ordinary,
                    'advantage_over_strongest_ordinary': checked['worst_complete_accuracy'] - ordinary['worst_complete_accuracy'],
                    'illustrative_95_percent_contract_feasible': upper >= Fraction(95, 100)}
            if states == 4:
                case['independent_split_budget'] = verify(split_channel(ratio), ratio)
            cases.append(case)
    exact = [[1, 0, 0], [0, 1, 0]]
    refusal = [[0, 0, 1], [0, 0, 1]]
    baseline = verify(exact, 2)
    assert not baseline['privacy_accepted']
    return {'scope': 'SYNTHETIC_PROBABILITY_CONTRACT_NOT_CLINICAL_OR_CRYPTO_VALIDATION',
            'cases': cases, 'exact_release_at_ratio_2': baseline,
            'consent_authorized_exact_release': {'accuracy': 1, 'same_privacy_contract': False,
                                                  'participant_acceptance_observed': False},
            'no_release': verify(refusal, 2),
            'successor': {'with_predecessor': 'same synthesis function, four states',
                          'without_predecessor': 'direct ordinary joint channel, identical optimum',
                          'equal_content_ordinary_reuse': 'identical optimum',
                          'earned_capital_enabled': False, 'discovery_method_gain': False},
            'decision': 'STOP_STRICT_OFFER_NO_SUPER_ALPHA; RETAIN_ORDINARY_METHOD',
            'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in HERE.iterdir()
                              if p.suffix == '.py' or p.name == 'PROTOCOL.md'}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = run()
    content = json.dumps(report, sort_keys=True, indent=2) + '\n'
    if args.output:
        args.output.write_text(content)
    else:
        print(content, end='')
