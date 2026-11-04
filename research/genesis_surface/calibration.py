"""Turn failed robustness into an explicit evidence requirement.

The uncertainty set is the declared rectangular shear-coefficient box. It is not
an experimentally established confidence region. Geometry, modulus, wear and
model discrepancy are not represented, so these are conditional design results.
"""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import math
from pathlib import Path

from .model import validate, basis, digest, read
from .check import check


def box_obstruction(spec: dict) -> dict:
    """Exact necessary ratio bounds; no solver or producer verdict is trusted.

For any nonnegative active contact areas A_i, the lower box ratio is
sum(A_i*s_i_low)/sum(A_i*d_i_high), a weighted average of s_i_low/d_i_high.
The upper box ratio is analogous. Decimal input values are treated exactly.
An obstruction is conditional on this simultaneous rectangular uncertainty set.
"""
    validate(spec)
    low_ratios = [Fraction(str(f['static_range_MPa'][0])) /
                  Fraction(str(f['dynamic_range_MPa'][1])) for f in spec['families']]
    high_ratios = [Fraction(str(f['static_range_MPa'][1])) /
                   Fraction(str(f['dynamic_range_MPa'][0])) for f in spec['families']]
    best_lower, best_upper = max(low_ratios), min(high_ratios)
    witnesses = []
    for i, state in enumerate(spec['states']):
        lower, upper = map(lambda v: Fraction(str(v)), state['ratio'])
        if best_lower < lower:
            witnesses.append({'state_index': i, 'side': 'lower',
                              'bound_exact': str(best_lower), 'target_exact': str(lower),
                              'reason': 'Even the largest family lower-box ratio is below the required lower ratio.'})
        if best_upper > upper:
            witnesses.append({'state_index': i, 'side': 'upper',
                              'bound_exact': str(best_upper), 'target_exact': str(upper),
                              'reason': 'Even the smallest family upper-box ratio is above the required upper ratio.'})
    return {'request_sha256': digest(spec), 'infeasible_in_declared_box': bool(witnesses),
            'witnesses': witnesses,
            'scope': 'Necessary-condition proof in the stated independent positive-area rectangular shear model; NOT physical impossibility.'}


def construct_robust(spec: dict) -> dict:
    """Minimize contact count subject to worst-case declared shear constraints."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    choices, rows = basis(spec)
    lookup = {f['id']: f for f in spec['families']}
    matrix, lower, upper = [], [], []

    def add(coeff, lo, hi):
        finite = [abs(v) for v in (lo, hi) if math.isfinite(v)]
        scale = max([1.] + finite)
        matrix.append(coeff / scale); lower.append(lo / scale); upper.append(hi / scale)

    for target, row in zip(spec['states'], rows):
        add(row[0], *target['normal_N'])
        slo, shi, dlo, dhi = (np.array([
            row[1, j] / lookup[fid]['static_MPa'] * lookup[fid][key][edge]
            for j, (fid, _) in enumerate(choices)])
            for key, edge in (('static_range_MPa', 0), ('static_range_MPa', 1),
                              ('dynamic_range_MPa', 0), ('dynamic_range_MPa', 1)))
        for name, lo_row, hi_row in (('static_N', slo, shi), ('dynamic_N', dlo, dhi)):
            add(lo_row, target[name][0], np.inf)
            add(hi_row, -np.inf, target[name][1])
        add(slo - target['ratio'][0] * dhi, 0., np.inf)
        add(shi - target['ratio'][1] * dlo, -np.inf, 0.)
    add(np.ones(len(choices)), 1., spec['maximum_contacts'])
    sol = milp(np.ones(len(choices)), integrality=np.ones(len(choices)),
               bounds=Bounds(np.zeros(len(choices)), spec['maximum_contacts']),
               constraints=LinearConstraint(np.array(matrix), lower, upper),
               options={'mip_rel_gap': 0.})
    result = {'schema': 'genesis/surface-design/v1', 'request_sha256': digest(spec),
              'family_restriction': None, 'contacts': [], 'solver_status': int(sol.status),
              'solver_message': str(sol.message), 'physical_qualification': False,
              'commercial_qualification': False, 'algorithm': 'Ordinary robust MILP / SciPy-HiGHS',
              'uncertainty': 'DECLARED_RECTANGULAR_SHEAR_BOX_ONLY'}
    if sol.x is None:
        result['status'] = 'INFEASIBLE_IN_DECLARED_MODEL' if sol.status == 2 else 'UNRESOLVED'
    else:
        rounded = np.rint(sol.x)
        if np.max(np.abs(sol.x - rounded)) > 1e-5:
            raise ValueError('nonintegral robust solver output')
        result['contacts'] = [{'family': fid, 'height_mm': h, 'count': int(n)}
                              for (fid, h), n in zip(choices, rounded) if n > 0]
        result['status'] = 'CANDIDATE_REQUIRES_CHECK'
        checked = check(spec, result)
        if not checked['accepted'] or not checked['declared_box_sensitivity_pass']:
            raise ValueError('robust output failed independent scalar acceptance')
    return result


def tolerance_requirement(spec: dict, design: dict) -> dict:
    """Exact algebraic bound for a *fixed* design under uniform relative boxes.

For 0 <= e < 1, coefficients vary independently as nominal*(1 +/- e).
Positive contact areas imply total forces vary by the same relative factor.
The ratio varies between r*(1-e)/(1+e) and r*(1+e)/(1-e).
No claim is made that repeated samples can achieve the required accuracy.
"""
    validate(spec)
    checked = check(spec, design)
    if not checked['accepted']:
        raise ValueError('nominally accepted design required')
    constraints = []
    for i, (target, row) in enumerate(zip(spec['states'], checked['rows'])):
        for key in ('static_N', 'dynamic_N'):
            value = row[key]; lo, hi = target[key]
            if value <= 0 or not lo <= value <= hi:
                raise ValueError('exact nominal target required for sensitivity requirement')
            constraints.extend([{'state_index': i, 'quantity': key, 'side': 'lower', 'epsilon': 1 - lo / value},
                                {'state_index': i, 'quantity': key, 'side': 'upper', 'epsilon': hi / value - 1}])
        r = row['ratio']; lo, hi = target['ratio']
        if not lo <= r <= hi or r <= 0:
            raise ValueError('exact nominal ratio target required')
        constraints.extend([{'state_index': i, 'quantity': 'ratio', 'side': 'lower', 'epsilon': (r - lo) / (r + lo)},
                            {'state_index': i, 'quantity': 'ratio', 'side': 'upper', 'epsilon': (hi - r) / (hi + r)}])
    limiting = min(constraints, key=lambda x: x['epsilon'])
    limit = min(limiting['epsilon'], math.nextafter(1., 0.))
    certified_numeric = math.nextafter(limit, 0.) if limit > 0 else 0.
    return {'schema': 'genesis/calibration-requirement/v1', 'request_sha256': digest(spec),
            'design_sha256': digest(design), 'maximum_uniform_relative_shear_error': certified_numeric,
            'limiting_constraint': limiting, 'constraints': constraints,
            'physical_accuracy_established': False, 'sample_size_recommendation': None,
            'assumptions': ['Fixed geometry and indentation', 'Fixed modulus and independent contact areas',
                            'Simultaneous independent symmetric relative shear bounds',
                            'No unmodeled discrepancy, wear or interaction'],
            'next_evidence': 'Establish a joint mixed-coupon calibration including systematic/model discrepancy, or revise the method/target. This number is a requirement, not achieved accuracy.'}


def relative_box(spec: dict, epsilon: float) -> dict:
    validate(spec)
    if type(epsilon) not in (int, float) or not math.isfinite(epsilon) or not 0 <= epsilon < 1:
        raise ValueError('finite relative error in [0,1) required')
    s = copy.deepcopy(spec)
    s['source']['counterfactual_calibration'] = True
    s['source']['parent_request_sha256'] = digest(spec)
    s['source']['scope'] = 'HYPOTHETICAL symmetric shear calibration requirement; not measured accuracy or a physical qualification.'
    for f in s['families']:
        for key in ('static', 'dynamic'):
            f[key + '_range_MPa'] = [f[key + '_MPa'] * (1 - epsilon), f[key + '_MPa'] * (1 + epsilon)]
    return s


def diagnose(directory: Path, target_epsilon: float | None = None) -> dict:
    from .build import audit
    audit(directory)
    spec = read(Path(directory) / 'request.json')
    candidate = read(Path(directory) / 'design.json')
    robust = construct_robust(spec)
    result = {'schema': 'genesis/calibration-diagnosis/v1', 'request_sha256': digest(spec),
            'box_obstruction': box_obstruction(spec), 'robust_candidate': robust,
            'robust_check': check(spec, robust), 'nominal_check': check(spec, candidate),
            'fixed_design_requirement': tolerance_requirement(spec, candidate),
            'decision': 'REQUIRE_NEW_CALIBRATION_AND_PHYSICAL_TRANSFER_EVIDENCE',
            'actual_physical_measurements': 0, 'actual_revenue_USD': 0}
    if target_epsilon is not None:
        conditional_spec = relative_box(spec, target_epsilon)
        conditional_design = construct_robust(conditional_spec)
        result['hypothetical_calibration_comparison'] = {
            'requested_relative_error': target_epsilon, 'request': conditional_spec,
            'candidate': conditional_design, 'check': check(conditional_spec, conditional_design),
            'scope': 'Conditional redesign only. Required calibration has not been achieved.'}
    return result


def main():
    from .build import save
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target-relative-error', type=float, default=None,
                        help='Optional HYPOTHETICAL calibration error, not an observed capability')
    args = parser.parse_args()
    if any(p.is_symlink() for p in (args.out, *args.out.absolute().parents)):
        raise ValueError('symlink output unsupported')
    result = diagnose(args.design, args.target_relative_error)
    save(args.out, result)
    print(result['decision'])


if __name__ == '__main__':
    main()
