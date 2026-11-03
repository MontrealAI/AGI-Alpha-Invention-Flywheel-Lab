import argparse, csv, json
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

@dataclass(frozen=True)
class Batch:
    name: str
    values: tuple
    domain: str
    construction: F
    full_verification: F
    trace_overhead: F
    certificate_verification: F

@dataclass(frozen=True)
class Policy:
    name: str
    speed: F = F(1)
    trace: bool = False
    checker: bool = False
    reuse: bool = True

PRIMARY = Batch('primary', tuple(range(1, 13)), 'affine', F(4), F(12), F(1), F(1))
SUCCESSOR = Batch('prespecified_successor', tuple(range(101, 111)), 'affine', F(8), F(20), F(1), F(2))
POLICIES = (
    Policy('baseline'),
    Policy('faster_construction', F(4)),
    Policy('trace_producer_only', trace=True),
    Policy('certificate_checker_only', checker=True),
    Policy('complementary_bundle', trace=True, checker=True),
    Policy('bundle_and_faster_construction', F(4), True, True),
    Policy('bundle_rebuilt_on_successor', F(4), True, True, False)
)

def target(domain, x):
    if domain == 'affine': return 3*x + 7
    if domain == 'quadratic': return x*x + 7
    raise ValueError('Unknown task domain')

def construct(batch, x, policy):
    value = target(batch.domain, x)
    certificate = {'domain': 'affine', 'x': x, 'a': 3, 'b': 7} if policy.trace else None
    return {'value': value, 'certificate': certificate}

def full_verify(batch, x, product):
    if batch.domain == 'affine': expected = x+x+x+7
    elif batch.domain == 'quadratic': expected = pow(x, 2)+7
    else: return False
    return product['value'] == expected

def certificate_verify(batch, x, product):
    c = product.get('certificate')
    return bool(batch.domain == 'affine' and c == {'domain': 'affine', 'x': x, 'a': 3, 'b': 7} and product['value'] == c['a']*x + c['b'])

def setup_ledger(policy, successor=False):
    if not (policy.trace or policy.checker): return {}
    initial = {'search': F(4), 'producer_construction': F(6) if policy.trace else F(0), 'checker_construction': F(6) if policy.checker else F(0), 'integration': F(2)*int(policy.trace + policy.checker), 'qualification': F(2)*int(policy.trace + policy.checker)}
    if not successor: return initial
    transfer = {'adaptation': F(4), 'successor_requalification': F(4)}
    return transfer if policy.reuse else initial | transfer

def execute(batch, policy, successor=False, force_invalid_transfer=False):
    ledger = setup_ledger(policy, successor)
    setup = sum(ledger.values(), F(0))
    use_certificate = policy.trace and policy.checker and (batch.domain == 'affine' or force_invalid_transfer)
    d = batch.construction/policy.speed + (batch.trace_overhead if policy.trace else 0)
    v = batch.certificate_verification if use_certificate else batch.full_verification
    end_construction = end_verification = setup
    trace = []
    for i, x in enumerate(batch.values, 1):
        product = construct(batch, x, policy)
        accepted = certificate_verify(batch, x, product) if use_certificate else full_verify(batch, x, product)
        end_construction += d
        start_verification = max(end_construction, end_verification)
        end_verification = start_verification + v
        trace.append({'job': i, 'input': x, 'value': product['value'], 'accepted': accepted, 'construction_end': end_construction, 'verification_start': start_verification, 'verification_end': end_verification})
    n = len(batch.values)
    expected = setup + d + v + (n-1)*max(d, v)
    assert end_verification == expected
    return {'jobs': n, 'accepted': sum(x['accepted'] for x in trace), 'setup_ledger': ledger, 'setup_time': setup, 'construction_per_job': d, 'verification_per_job': v, 'verification_method': 'certificate' if use_certificate else 'full', 'elapsed_time': end_verification, 'resource_work': setup+n*(d+v), 'trace': trace}

def scalar(value):
    if isinstance(value, F): return value.numerator if value.denominator == 1 else str(value)
    raise TypeError(type(value).__name__)

def run_checks(results):
    assert [results[p.name]['total_time'] for p in POLICIES] == [356, 347, 380, 378, 185, 89, 113]
    assert [results[p.name]['total_resource_work'] for p in POLICIES] == [472, 376, 516, 494, 214, 118, 142]
    assert all(b['accepted'] == b['jobs'] for r in results.values() for b in (r['primary'], r['successor']))
    assert results['trace_producer_only']['total_time'] > results['baseline']['total_time']
    assert results['certificate_checker_only']['total_time'] > results['baseline']['total_time']
    assert results['bundle_rebuilt_on_successor']['total_time'] - results['bundle_and_faster_construction']['total_time'] == 24
    p = POLICIES[5]
    for batch in (PRIMARY, SUCCESSOR):
        for x in batch.values:
            product = construct(batch, x, p)
            assert full_verify(batch, x, product) and certificate_verify(batch, x, product)
            product['value'] += 1
            assert not full_verify(batch, x, product) and not certificate_verify(batch, x, product)
            for field, bad_value in (('a', 4), ('b', 8), ('domain', 'quadratic'), ('x', x+1)):
                product = construct(batch, x, p)
                product['certificate'][field] = bad_value
                assert not certificate_verify(batch, x, product)
    bad = Batch('invalid_transfer', tuple(range(3, 7)), 'quadratic', F(4), F(12), F(1), F(1))
    rejected = execute(bad, p, successor=True, force_invalid_transfer=True)
    fallback = execute(bad, p, successor=True)
    assert rejected['accepted'] == 0 and fallback['accepted'] == 4
    short = Batch('short_horizon', (1,), 'affine', F(4), F(12), F(1), F(1))
    short_runs = {x.name: execute(short, x) for x in (POLICIES[0], POLICIES[1], p)}
    assert short_runs['bundle_and_faster_construction']['elapsed_time'] == 27
    assert short_runs['faster_construction']['elapsed_time'] == 13
    assert short_runs['baseline']['elapsed_time'] == 16
    for n in range(1, 20):
        for d, v, speed, delta, c, k in [(F(4), F(12), F(4), F(1), F(1), F(24)), (F(8), F(20), F(4), F(1), F(2), F(8))]:
            local = d/speed + n*v
            bundle = k + c + n*(d/speed+delta)
            assert (bundle < local) == (n*(v-d/speed-delta) > k+c-d/speed)
    return {'checks_passed': True, 'coverage': ['exact pipeline recurrence', 'frozen result totals', 'complementarity regressions', 'charged successor rebuilding', 'contract equality', 'corrupted products rejected', 'incorrect certificate coefficients/domain/input rejected', 'invalid transfer rejected', 'valid fallback retained', 'short-horizon loss', 'break-even equivalence'], 'short_horizon': short_runs, 'invalid_transfer_attempt': rejected, 'invalid_transfer_fallback': fallback}

def run():
    results = {}
    for p in POLICIES:
        primary, successor = execute(PRIMARY, p), execute(SUCCESSOR, p, successor=True)
        results[p.name] = {'primary': primary, 'successor': successor, 'total_time': primary['elapsed_time']+successor['elapsed_time'], 'total_resource_work': primary['resource_work']+successor['resource_work']}
    checks = run_checks(results)
    choice = min(POLICIES, key=lambda p: results[p.name]['total_time'])
    assert choice.name == 'bundle_and_faster_construction'
    ordinary = Policy('supplied_ordinary_workflow', F(4), True, True)
    ordinary_runs = [execute(PRIMARY, ordinary), execute(SUCCESSOR, ordinary, successor=True)]
    ordinary_time = sum(r['elapsed_time'] for r in ordinary_runs)
    ordinary_work = sum(r['resource_work'] for r in ordinary_runs)
    assert ordinary_time == 89 and ordinary_work == 118
    return {'evidence_status': 'Authored exact analytical illustration, not an empirical AI benchmark. Durations, tool effects, and domain applicability are stipulated. Inputs are public and prespecified, not concealed confirmation data.', 'units': {'time': 'abstract elapsed time units', 'resource_work': 'abstract worker-time units; concurrent stage work is summed'}, 'contract': 'Return the exact integer result for the declared task. The certificate checker is valid only for the affine domain; other domains require full verification.', 'assumptions': ['Two independent serial servers with an unlimited intermediate queue.', 'Acquisition and adaptation precede the batch and cannot overlap it.', 'All baseline and candidate input facts and permissions are identical.', 'A fourfold construction engine is available with zero incremental acquisition cost to every policy.', 'Each candidate bears its own stated search, construction, integration and qualification costs.', 'The comparison experiment itself is not a cost-free policy selector; no autonomous discovery performance is claimed.', 'Batches run consecutively, not simultaneously.'], 'results': results, 'equal_content_conventional_comparator': {'scope': 'Supplied fixed ordinary workflow executes the same combined design and pays identical costs; no automated discovery or free selection is assumed.', 'supplied_policy': ordinary.name, 'total_time': ordinary_time, 'total_resource_work': ordinary_work, 'tie_with_proposed_combination': True, 'finite_family_arithmetic_minimum': {'policy': choice.name, 'time': results[choice.name]['total_time'], 'scope': 'Transparent minimum over seven specified policies, not global optimality or autonomous optimization.'}}, 'checks': checks}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent/'results')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result = run()
    (args.output_dir/'results.json').write_text(json.dumps(result, default=scalar, indent=2)+'\n')
    with (args.output_dir/'summary.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['policy', 'primary_time', 'successor_time', 'total_time', 'primary_work', 'successor_work', 'total_work', 'accepted_jobs'])
        for name, r in result['results'].items():
            writer.writerow([name, r['primary']['elapsed_time'], r['successor']['elapsed_time'], r['total_time'], r['primary']['resource_work'], r['successor']['resource_work'], r['total_resource_work'], r['primary']['accepted']+r['successor']['accepted']])
    print(json.dumps({'checks_passed': result['checks']['checks_passed'], 'policies': len(result['results']), 'best_total_time': result['equal_content_conventional_comparator']['total_time'], 'output_dir': str(args.output_dir)}, default=scalar))

if __name__ == '__main__': main()
