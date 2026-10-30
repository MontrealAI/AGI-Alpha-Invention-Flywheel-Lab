"""Independent exact KCL checker for exposed passive one-port development cases."""
import argparse
import hashlib
import itertools
import json
from fractions import Fraction as F
from pathlib import Path
import re
import resource
import time

ZERO = (F(0), F(0))
ONE = (F(1), F(0))


def plus(a, b):
    return a[0] + b[0], a[1] + b[1]


def neg(a):
    return -a[0], -a[1]


def times(a, b):
    return a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]


def divide(a, b):
    d = b[0] ** 2 + b[1] ** 2
    if not d:
        raise ValueError('ZERO_COMPLEX_DENOMINATOR')
    return (a[0] * b[0] + a[1] * b[1]) / d, (a[1] * b[0] - a[0] * b[1]) / d


def value(text):
    match = re.fullmatch(r'([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)([A-Za-z]*)', text)
    if not match:
        raise ValueError('UNSUPPORTED_SPICE_VALUE ' + text)
    scales = {'': F(1), 't': F(10 ** 12), 'g': F(10 ** 9), 'meg': F(10 ** 6), 'k': F(1000),
              'm': F(1, 1000), 'u': F(1, 10 ** 6), 'n': F(1, 10 ** 9), 'p': F(1, 10 ** 12), 'f': F(1, 10 ** 15)}
    suffix = match[2].lower()
    if suffix not in scales:
        raise ValueError('UNSUPPORTED_SPICE_SUFFIX ' + suffix)
    return F(match[1]) * scales[suffix]


def parse(path):
    parts, source, names, control = [], None, set(), False
    for lineno, line in enumerate(Path(path).read_text().splitlines()):
        text = line.strip()
        if lineno == 0 or not text or text.startswith('*'):
            continue
        fields = text.lower().split()
        if fields[0] == '.control':
            control = True
            continue
        if fields[0] == '.endc':
            control = False
            continue
        if control:
            continue
        if fields[0] == '.end':
            break
        if fields[0].startswith('.'):
            if fields[0] not in {'.global', '.ac', '.meas', '.measure', '.option', '.options', '.save', '.print', '.plot'}:
                raise ValueError('UNSUPPORTED_DIRECTIVE ' + fields[0])
            continue
        name, kind = fields[0], fields[0][0]
        if name in names:
            raise ValueError('DUPLICATE_ELEMENT ' + name)
        names.add(name)
        if kind in 'rcl' and len(fields) == 4:
            number = value(fields[3])
            if number <= 0 or fields[1] == fields[2]:
                raise ValueError('NONPOSITIVE_OR_DEGENERATE_PASSIVE')
            parts.append((kind, name, fields[1], fields[2], number))
        elif kind == 'v' and source is None and len(fields) in {5, 7}:
            settings = fields[3:]
            attributes = {}
            for index in range(0, len(settings), 2):
                key = settings[index]
                if key not in {'dc', 'ac'} or key in attributes:
                    raise ValueError('UNSUPPORTED_OR_DUPLICATE_SOURCE_PARAMETER')
                attributes[key] = value(settings[index + 1])
            if 'ac' not in attributes or attributes.get('dc', F(0)) != 0:
                raise ValueError('ONLY_ZERO_DC_ZERO_PHASE_SOURCE_SUPPORTED')
            source = (fields[1], fields[2], attributes['ac'])
        else:
            raise ValueError('UNSUPPORTED_ELEMENT ' + name)
    if source is None or not parts or control or source[1] not in {'0', 'gnd'} or source[0] in {'0', 'gnd'} or source[2] == 0:
        raise ValueError('ONE_GROUNDED_NONZERO_AC_SOURCE_REQUIRED')
    return parts, source


def transformed(parts, scale):
    scale = F(scale)
    if scale <= 0:
        raise ValueError('POSITIVE_SCALE_REQUIRED')
    return [(k, name, a, b, x / scale if k == 'c' else x * scale) for k, name, a, b, x in parts]


def admittance(part, omega):
    kind, _, _, _, x = part
    if kind == 'r':
        return F(1) / x, F(0)
    if kind == 'c':
        return F(0), F(omega) * x
    return F(0), -F(1) / (F(omega) * x)


def solve(parts, source, omega):
    if F(omega) <= 0:
        raise ValueError('POSITIVE_ANGULAR_FREQUENCY_REQUIRED')
    known = {'0': ZERO, 'gnd': ZERO, source[0]: (source[2], F(0))}
    nodes = sorted({n for _, _, a, b, _ in parts for n in [a, b]} - known.keys())
    table = {node: i for i, node in enumerate(nodes)}
    size = len(nodes)
    matrix = [[ZERO for _ in range(size + 1)] for _ in range(size)]
    for part in parts:
        y = admittance(part, omega)
        a, b = part[2:4]
        for own, other in [(a, b), (b, a)]:
            if own not in table:
                continue
            row = matrix[table[own]]
            row[table[own]] = plus(row[table[own]], y)
            if other in table:
                row[table[other]] = plus(row[table[other]], neg(y))
            else:
                row[-1] = plus(row[-1], times(y, known[other]))
    for column in range(size):
        pivots = [row for row in range(column, size) if matrix[row][column] != ZERO]
        if not pivots:
            raise ValueError('SINGULAR_NODAL_MATRIX')
        pivot = pivots[0]
        matrix[column], matrix[pivot] = matrix[pivot], matrix[column]
        d = matrix[column][column]
        matrix[column] = [divide(cell, d) for cell in matrix[column]]
        for row in range(size):
            if row != column:
                amount = matrix[row][column]
                matrix[row] = [plus(cell, neg(times(amount, center))) for cell, center in zip(matrix[row], matrix[column])]
    voltage = {**known, **{node: matrix[i][-1] for node, i in table.items()}}
    residuals = {node: ZERO for node in nodes}
    input_current = ZERO
    for part in parts:
        a, b = part[2:4]
        branch = times(admittance(part, omega), plus(voltage[a], neg(voltage[b])))
        if a in residuals:
            residuals[a] = plus(residuals[a], branch)
        if b in residuals:
            residuals[b] = plus(residuals[b], neg(branch))
        if a == source[0]:
            input_current = plus(input_current, branch)
        if b == source[0]:
            input_current = plus(input_current, neg(branch))
    if any(x != ZERO for x in residuals.values()):
        raise AssertionError('KCL_RESIDUAL_NONZERO')
    return voltage, divide(input_current, (source[2], F(0)))


def encode(q):
    return [str(q[0]), str(q[1])]


def rectangles_disjoint(a, b, epsilon):
    return any(abs(x - y) > 2 * F(epsilon) for x, y in zip(a, b))


def inspect(netlist, scales, omegas, epsilon):
    parts, source = parse(netlist)
    scales, omegas = [F(x) for x in scales], [F(x) for x in omegas]
    epsilon = F(epsilon)
    if len(scales) != len(set(scales)) or len(scales) < 2 or any(x <= 0 for x in scales) or epsilon < 0 or not omegas:
        raise ValueError('UNSATISFIABLE_PROTOCOL_PARAMETERS')
    responses = {str(scale): [] for scale in scales}
    symmetry, compensation = [], []
    base = [solve(parts, source, w) for w in omegas]
    for scale in scales:
        changed = transformed(parts, scale)
        all_branch_scaled = all(admittance(p, 1) == times(admittance(q, 1), (scale, F(0))) for p, q in zip(parts, changed))
        same_voltage, inverse_current, gain_compensated = True, True, True
        for j, w in enumerate(omegas):
            volt, current = solve(changed, source, w)
            reference_volt, reference_current = base[j]
            same_voltage &= volt == reference_volt
            inverse_current &= times(current, (scale, F(0))) == reference_current
            gain_compensated &= times(current, (scale, F(0))) == reference_current
            responses[str(scale)].append({'omega_rad_per_second': str(w), 'input_admittance_S': encode(current),
                                          'voltage_ratios': {node: encode(divide(v, (source[2], F(0)))) for node, v in volt.items() if node not in {'0', 'gnd'}}})
        symmetry.append({'scale': str(scale), 'all_branch_admittances_inverse_scale': all_branch_scaled,
                         'exact_all_node_voltage_ratios_equal': same_voltage, 'exact_input_admittance_inverse_scale': inverse_current})
        compensation.append({'scale': str(scale), 'sensor_gain': str(scale), 'exact_gain_times_changed_current_equal': gain_compensated})
    pair_checks = []
    for a, b in itertools.combinations(scales, 2):
        differences = []
        for index, w in enumerate(omegas):
            x = tuple(F(t) for t in responses[str(a)][index]['input_admittance_S'])
            y = tuple(F(t) for t in responses[str(b)][index]['input_admittance_S'])
            differences.append({'omega_rad_per_second': str(w), 'disjoint_calibrated_rectangles': rectangles_disjoint(x, y, epsilon)})
        pair_checks.append({'a': str(a), 'b': str(b), 'current_measurement_actions': differences,
                            'ordinary_full_VI_discriminates': any(x['disjoint_calibrated_rectangles'] for x in differences)})
    return {'netlist_sha256': hashlib.sha256(Path(netlist).read_bytes()).hexdigest(), 'parts': len(parts),
            'scales': [str(x) for x in scales], 'omega_rad_per_second': [str(x) for x in omegas],
            'absolute_per_component_admittance_error_S': str(epsilon), 'source_amplitude_V': str(source[2]),
            'symmetry_checks': symmetry, 'unknown_gain_counterexamples': compensation, 'pairs': pair_checks, 'responses': responses,
            'all_calibrated_pairwise_satisfiable': all(p['ordinary_full_VI_discriminates'] for p in pair_checks),
            'proof_scope': 'Exact finite arithmetic and branch-law scaling for positive passive RCL model; topology, ideal source, finite scale hypotheses, and authored calibrated error bounds assumed. No physical measurement, empirical sensor calibration, all-parameter identifiability, or novel physical law.',
            'technical_control': 'Ordinary complete voltage/current experiment with equal information can discriminate exactly the same finite pairs. A compiler tie is retained, not scientific superiority.',
            'sensor_gain_scope': 'Free unknown positive scalar gain restores exact scale ambiguity: gain a times admittance divided by a. This counterexample does not falsify a qualified calibrated-gain obligation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scales', nargs='+', default=['1/2', '1', '2'])
    parser.add_argument('--omegas', nargs='+', default=['1000', '10000', '100000', '1000000', '10000000'])
    parser.add_argument('--epsilon', default='1/1000000000')
    args = parser.parse_args()
    before, wall = resource.getrusage(resource.RUSAGE_SELF), time.monotonic()
    result = inspect(args.netlist, args.scales, args.omegas, args.epsilon)
    after = resource.getrusage(resource.RUSAGE_SELF)
    result.update({'schema': 'agi-alpha/consequential009-independent-analog-check/v1', 'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'resources': {'cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 'wall_seconds': time.monotonic() - wall,
                                 'max_rss_kib': after.ru_maxrss, 'complete_monetary_cost': None}, 'confirmation': False})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'passed_symmetry': all(all(item[k] for k in ['all_branch_admittances_inverse_scale', 'exact_all_node_voltage_ratios_equal', 'exact_input_admittance_inverse_scale']) for item in result['symmetry_checks']),
                      'calibrated_pairwise_satisfiable': result['all_calibrated_pairwise_satisfiable'], 'confirmation': False}))


if __name__ == '__main__':
    main()
