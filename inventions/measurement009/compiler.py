import hashlib
import itertools
import json
import math
from fractions import Fraction
import time
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def _corpus(corpus):
    if corpus.get('schema') != 'agi-alpha/measurement-corpus009/v1' or corpus.get('units') != 'source_contribution_percentage_points':
        raise ValueError('CORPUS_SCHEMA_OR_UNITS')
    nodes, sources, times = corpus['nodes'], corpus['sources'], corpus['times_seconds']
    if not nodes or not sources or not times or len(set(nodes)) != len(nodes) or len(set(sources)) != len(sources):
        raise ValueError('EMPTY_OR_DUPLICATE_IDENTITIES')
    a = np.asarray(corpus['signal'], dtype=float)
    if a.shape != (len(sources), len(times), len(nodes)) or not np.isfinite(a).all():
        raise ValueError('SIGNAL_SHAPE_OR_NONFINITE')
    return a

def synthesize_operator(operands=('read', 'zero_reference')):
    units = {'read': 'source_contribution_percentage_points', 'zero_reference': 'source_contribution_percentage_points', 'previous_read': 'source_contribution_percentage_points'}
    if any(x not in units for x in operands):
        raise ValueError('UNQUALIFIED_PRIMITIVE')
    attempts = []
    for right in operands:
        if right == 'read':
            continue
        for left_coeff, right_coeff in itertools.product((-1, 0, 1), repeat=2):
            retained_signal = left_coeff == 1 and right == 'zero_reference'
            cancelled_bias = left_coeff + right_coeff == 0
            attempt = {'left': 'read', 'right': right, 'coefficients': [left_coeff, right_coeff],
                'same_units': units['read'] == units[right], 'same_nuisance_group': 'sensor_offset',
                'bias_coefficient': left_coeff + right_coeff,
                'preserves_current_signal': retained_signal, 'admissible': retained_signal and cancelled_bias}
            attempts.append(attempt)
            if attempt['admissible']:
                return {'schema': 'agi-alpha/generated-observation-expression009/v1', 'status': 'CONSTRUCTED',
                    'ast': {'op': 'subtract', 'left': {'op': 'read', 'sensor': '$sensor', 'time': '$time'},
                            'right': {'op': 'zero_reference', 'sensor': '$sensor'}},
                    'ancestry': {'generator': 'bounded-coefficient-enumeration-v1', 'attempts': attempts,
                        'primitive_proposal_author': 'builder, following reproduced missing-DC-information witness',
                        'generated_parts': ['signed coefficients', 'typed expression', 'sensor assignment in downstream solver'],
                        'prior_art': 'Calibration subtraction and test multicover are established methods; no novelty inferred.'},
                    'qualification': {'unit_preserved': True, 'offset_coefficient': 0,
                        'sample_noise_coefficient': 1, 'reference_noise_coefficient': -1,
                        'required_assumptions': ['Known-zero reference', 'same constant sensor offset at reference and all samples', 'each raw read, including reference, has bounded noise']}}
    return {'schema': 'agi-alpha/generated-observation-expression009/v1', 'status': 'MISSING_PRIMITIVE',
        'attempts': attempts, 'reason': 'No expression preserves present signal and cancels arbitrary sensor offset from available operands.'}

def relation_matrix(corpus, noise_bound_pp='1', operator='known-zero-reference'):
    a = _corpus(corpus)
    epsilon = float(Fraction(str(noise_bound_pp)))
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError('POSITIVE_FINITE_NOISE_BOUND_REQUIRED')
    pairs = list(itertools.combinations(range(len(corpus['sources'])), 2))
    rows, summaries = [], []
    for i, j in pairs:
        d = a[i] - a[j]
        lo, hi = d.min(axis=0), d.max(axis=0)
        if operator == 'known-zero-reference':
            score = np.maximum.reduce((hi, -lo, hi-lo))
        elif operator == 'uncalibrated-time-trace':
            score = hi-lo
        elif operator == 'naive-offset-free':
            score = np.maximum(hi, -lo) * 2
        else:
            raise ValueError('UNSUPPORTED_OPERATOR')
        separated = score > 4*epsilon
        scale = max(1.0, float(np.abs(a).max()), abs(epsilon))
        critical = np.flatnonzero(np.abs(score - 4*epsilon) <= np.finfo(float).eps*64*scale)
        for k in critical:
            exact = [Fraction(str(corpus['signal'][i][t][k]))-Fraction(str(corpus['signal'][j][t][k])) for t in range(len(corpus['times_seconds']))]
            if operator == 'naive-offset-free':
                separated[k] = max(abs(x) for x in exact) > 2*Fraction(str(noise_bound_pp))
            else:
                separated[k] = sensor_separates(min(exact), max(exact), noise_bound_pp, operator)
        rows.append(separated)
        summaries.append({'sources': [corpus['sources'][i], corpus['sources'][j]],
            'separating_sensors': [corpus['nodes'][k] for k in np.flatnonzero(separated)],
            'minimum_difference': lo.tolist(), 'maximum_difference': hi.tolist()})
    return np.asarray(rows, dtype=np.int8), summaries

def _choose(matrix, required, algorithm, seconds=30):
    n = matrix.shape[1]
    if np.any(matrix.sum(axis=1) < required):
        return [], {'status': 'INFEASIBLE', 'proof': 'At least one pair has fewer available separating sensors than required, even with every sensor.'}
    if algorithm == 'exhaustive':
        if n > 16:
            raise ValueError('EXHAUSTIVE_LIMIT_16_SENSORS')
        examined = 0
        for k in range(n+1):
            for selected in itertools.combinations(range(n), k):
                examined += 1
                if np.all(matrix[:, selected].sum(axis=1) >= required):
                    return list(selected), {'status': 'OPTIMAL', 'subsets_examined': examined, 'objective': k}
    elif algorithm == 'greedy':
        selected, coverage = [], np.zeros(matrix.shape[0], dtype=int)
        while np.any(coverage < required):
            candidates = [(int(np.minimum(matrix[:, k], np.maximum(required-coverage, 0)).sum()), -k, k) for k in range(n) if k not in selected]
            score, _, best = max(candidates)
            if not score:
                return [], {'status': 'INFEASIBLE'}
            selected.append(best); coverage += matrix[:, best]
        return sorted(selected), {'status': 'FEASIBLE_HEURISTIC', 'objective': len(selected)}
    elif algorithm == 'milp':
        fit = milp(np.ones(n), integrality=np.ones(n), bounds=Bounds(np.zeros(n), np.ones(n)),
                   constraints=LinearConstraint(matrix.astype(float), np.full(matrix.shape[0], required), np.full(matrix.shape[0], np.inf)),
                   options={'time_limit': seconds, 'mip_rel_gap': 0.0})
        if fit.x is None:
            return [], {'status': 'UNKNOWN', 'solver_status': int(fit.status), 'message': str(fit.message)}
        selected = np.flatnonzero(fit.x > .5).tolist()
        if not np.all(matrix[:, selected].sum(axis=1) >= required):
            return [], {'status': 'UNKNOWN', 'message': 'Returned incumbent failed direct cover check.'}
        return selected, {'status': 'OPTIMAL' if fit.status == 0 else 'FEASIBLE_UNPROVEN', 'objective': len(selected),
            'solver_status': int(fit.status), 'mip_gap': float(fit.mip_gap), 'dual_bound': float(fit.mip_dual_bound),
            'message': str(fit.message)}
    else:
        raise ValueError('UNSUPPORTED_ALGORITHM')
    raise RuntimeError('UNREACHABLE_SOLVER_STATE')

def sensor_separates(minimum_difference, maximum_difference, noise_bound_pp='1', operator='known-zero-reference'):
    lo, hi, eps = Fraction(str(minimum_difference)), Fraction(str(maximum_difference)), Fraction(str(noise_bound_pp))
    if lo > hi or eps <= 0:
        raise ValueError('INVALID_SEPARATION_INTERVAL')
    if operator == 'known-zero-reference':
        return hi > 4*eps or lo < -4*eps or hi-lo > 4*eps
    if operator == 'uncalibrated-time-trace':
        return hi-lo > 4*eps
    raise ValueError('UNQUALIFIED_SEPARATION_OPERATOR')

def solve_relations(matrix, required=2, algorithm='milp', seconds=30):
    array = np.asarray(matrix)
    if array.ndim != 2 or not len(array) or not array.shape[1] or not np.isin(array, (0, 1)).all() or type(required) is not int or required < 1:
        raise ValueError('INVALID_TYPED_RELATIONS')
    return _choose(array.astype(np.int8), required, algorithm, seconds)

def compile_plan(corpus, noise_bound_pp='1', max_sensor_erasures=1, algorithm='milp', operator='known-zero-reference'):
    if type(max_sensor_erasures) is not int or max_sensor_erasures < 0 or max_sensor_erasures >= len(corpus['nodes']):
        raise ValueError('INVALID_ERASURE_BUDGET')
    start, own = time.monotonic(), time.process_time()
    matrix, summaries = relation_matrix(corpus, noise_bound_pp, operator)
    selected, control = _choose(matrix, max_sensor_erasures+1, algorithm)
    generated = synthesize_operator() if operator == 'known-zero-reference' else None
    accepted = control['status'] in {'OPTIMAL', 'FEASIBLE_HEURISTIC', 'FEASIBLE_UNPROVEN'}
    plan = {'schema': 'agi-alpha/observation-plan009/v1', 'network': corpus['network'],
        'numeric_semantics': corpus.get('numeric_semantics', 'canonical-json-finite-binary64-decimal-rational-v1'),
        'network_sha256': corpus['network_sha256'], 'corpus_sha256': digest(corpus),
        'sensors': [corpus['nodes'][x] for x in selected], 'operator': operator,
        'noise_bound_pp': str(noise_bound_pp), 'max_sensor_erasures': max_sensor_erasures,
        'nuisance': 'arbitrary-per-sensor-offset-constant-across-reference-and-trace',
        'status': 'CONSTRUCTED_MODEL_PLAN' if accepted else control['status'], 'solver': control,
        'algorithm': algorithm, 'generated_expression': generated,
        'pair_certificates': [{'sources': row['sources'], 'separating_selected_sensors': [node for node in row['separating_sensors'] if node in [corpus['nodes'][x] for x in selected]]} for row in summaries],
        'unresolved_pairs': [row for row in summaries if len(row['separating_sensors']) < max_sensor_erasures+1],
        'acquisition_obligations': {'known_zero_references': len(selected) if operator == 'known-zero-reference' else 0,
            'trace_readings': len(selected)*len(corpus['times_seconds']), 'last_sample_seconds': corpus['times_seconds'][-1],
            'scope': 'Prospective modeled measurement requirements. No references/sensors are physically acquired. Simulator acquisition/setup costs remain counted.'},
        'program': {'op': 'adaptive-diagnostic-readout', 'policy': 'select next unused sensor that distinguishes most remaining source pairs; test current version space, then verify all remaining supplied traces before acceptance',
            'stop': 'one compatible source or no usable sensors; empty set is MODEL_INCONSISTENT, multiple sources ABSTAIN',
            'not_claimed': 'No avoided hardware, physical acquisition, or elapsed monitoring time from readout order.'},
        'construction_cost': {'wall_seconds': time.monotonic()-start, 'process_cpu_seconds': time.process_time()-own,
            'complete_monetary_cost': None},
        'scope': 'Finite source-pinned engineering model only. Independent verifier acceptance required. Conventional calibration/multicover are prior art.'}
    return plan

def uncalibrated_witness(corpus, noise_bound_pp='1'):
    matrix, summaries = relation_matrix(corpus, noise_bound_pp, 'uncalibrated-time-trace')
    failing = np.flatnonzero(matrix.sum(axis=1) == 0)
    if not len(failing):
        return {'status': 'NO_ALL_SENSOR_AMBIGUITY_ESTABLISHED'}
    row = summaries[int(failing[0])]; left, right = [corpus['sources'].index(x) for x in row['sources']]
    epsilon = Fraction(str(noise_bound_pp)); records = []
    for k, sensor in enumerate(corpus['nodes']):
        x = [Fraction(str(v[k])) for v in corpus['signal'][left]]
        z = [Fraction(str(v[k])) for v in corpus['signal'][right]]
        difference = [v-w for v,w in zip(x,z)]
        offset_right = (max(difference)+min(difference))/2
        observed = [(v+w+offset_right)/2 for v,w in zip(x,z)]
        noise_left = [y-v for y,v in zip(observed,x)]
        noise_right = [y-w-offset_right for y,w in zip(observed,z)]
        if any(abs(e)>epsilon for e in noise_left+noise_right):
            raise RuntimeError('WITNESS_CONSTRUCTION_FAILED_EXACT_NOISE_BOUND')
        records.append({'sensor': sensor, 'left_offset': '0', 'right_offset': str(offset_right),
            'shared_observations': [str(v) for v in observed], 'left_noise': [str(v) for v in noise_left],
            'right_noise': [str(v) for v in noise_right]})
    return {'schema': 'agi-alpha/calibration-ambiguity-witness009/v1', 'status': 'EXACT_FEASIBLE_TWO_TRUTHS',
        'corpus_sha256': digest(corpus), 'sources': row['sources'], 'noise_bound_pp': str(noise_bound_pp),
        'all_sensors': records, 'scope': 'Rational interpretation of source-pinned finite simulator decimals; unbounded constant offsets are authored model assumptions.'}

def evaluate_expression(ast, observation, sensor, time_index):
    if type(ast) is not dict:
        raise ValueError('AST_TYPE')
    op = ast.get('op')
    if op == 'subtract' and set(ast) == {'op', 'left', 'right'}:
        return evaluate_expression(ast['left'], observation, sensor, time_index) - evaluate_expression(ast['right'], observation, sensor, time_index)
    if op == 'read' and ast == {'op': 'read', 'sensor': '$sensor', 'time': '$time'}:
        return Fraction(str(observation['trace'][sensor][time_index]))
    if op == 'zero_reference' and ast == {'op': 'zero_reference', 'sensor': '$sensor'}:
        return Fraction(str(observation['reference'][sensor]))
    raise ValueError('UNQUALIFIED_AST')

class ObservationInterpreter:
    def __init__(self, corpus, plan):
        if digest(corpus) != plan['corpus_sha256'] or plan.get('operator') != 'known-zero-reference':
            raise ValueError('PLAN_SOURCE_OR_OPERATOR_MISMATCH')
        _corpus(corpus)
        self.plan = json.loads(canonical(plan))
        self.sources = tuple(corpus['sources']); self.nodes = tuple(corpus['nodes'])
        self.time_count = len(corpus['times_seconds'])
        self.epsilon = Fraction(plan['noise_bound_pp'])
        self.signals = tuple(tuple(tuple(Fraction(str(v)) for v in row) for row in source) for source in corpus['signal'])
        self.relations = {(tuple(row['sources'])): frozenset(row['separating_selected_sensors']) for row in plan['pair_certificates']}
        self.expression = self.plan['generated_expression']['ast']

    def diagnose(self, observations):
        plan, epsilon = self.plan, self.epsilon
        if observations.get('known_zero_valid') is not True or observations.get('offset_constant') is not True:
            return {'status': 'ASSUMPTIONS_UNQUALIFIED', 'sources': [], 'trace': []}
        available = [x for x in plan['sensors'] if x not in observations.get('outages', [])]
        missing = [x for x in available if x not in observations.get('trace', {}) or x not in observations.get('reference', {}) or len(observations['trace'][x]) != self.time_count]
        if missing:
            return {'status': 'INCOMPLETE_OBSERVATIONS', 'sources': [], 'missing': missing, 'trace': []}
        corrected = {}
        def matches(source, sensor):
            if sensor not in corrected:
                corrected[sensor] = tuple(evaluate_expression(self.expression, observations, sensor, t) for t in range(self.time_count))
            i, k = self.sources.index(source), self.nodes.index(sensor)
            lower, upper = -epsilon, epsilon
            for t, value in enumerate(corrected[sensor]):
                residual = value-self.signals[i][t][k]
                lower = max(lower, -epsilon-residual); upper = min(upper, epsilon-residual)
                if lower > upper:
                    return False
            return True
        compatible, trace = list(self.sources), []
        while available and len(compatible) > 1:
            remaining_pairs = [pair for pair in self.relations if pair[0] in compatible and pair[1] in compatible]
            chosen = min(available, key=lambda sensor: (-sum(sensor in self.relations[pair] for pair in remaining_pairs), sensor))
            remaining = [source for source in compatible if matches(source, chosen)]
            trace.append({'sensor': chosen, 'before': compatible, 'after': remaining})
            compatible = remaining; available.remove(chosen)
            if not compatible:
                break
        if len(compatible) == 1 and not all(matches(compatible[0], sensor) for sensor in available):
            compatible = []
        exceeded = len(set(observations.get('outages', [])) & set(plan['sensors'])) > plan['max_sensor_erasures']
        status = 'MODEL_INCONSISTENT' if not compatible else 'UNIQUE' if len(compatible) == 1 else 'ABSTAIN'
        if exceeded:
            status = 'OUTAGE_ENVELOPE_EXCEEDED'
        return {'status': status, 'sources': compatible, 'trace': trace,
            'scope': 'Compatibility under asserted known-zero, constant-offset and noise assumptions, not field validation.'}

def diagnose(corpus, plan, observations):
    return ObservationInterpreter(corpus, plan).diagnose(observations)
