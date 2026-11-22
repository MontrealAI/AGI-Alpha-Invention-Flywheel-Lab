import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import time

from . import fabric as f
from . import reference as r

HERE = Path(__file__).resolve().parent


def run():
    start = time.perf_counter()
    blocks, operand = f.fixture(3)
    exhaustive = {}
    for kind in ['linear', 'gram']:
        plan = {'kind': kind, 'field': f.P, 'threshold': f.recovery_threshold(kind),
                'workers': [{'x': x, 'domain': (x - 4) // 3} for x in range(4, 11)]}
        cache, _ = f.encode(blocks, plan)
        binding, returned = f.execute(cache, plan, operand if kind == 'linear' else None)
        passed = refused = 0
        for mask in range(128):
            subset = [row for i, row in enumerate(returned) if mask & (1 << i)]
            try:
                output = f.decode(subset, plan, binding)
            except ValueError as e:
                if str(e) != 'INSUFFICIENT_RETURNS':
                    raise
                refused += 1
            else:
                if not r.accept(blocks, kind, operand, output):
                    raise AssertionError('WRONG_COMPLETE_OUTPUT')
                passed += 1
        exhaustive[kind] = {'subsets': 128, 'correct': passed, 'refused': refused}
    blocks, operand = f.fixture(16)
    plans = {kind: f.construct(kind) for kind in ['linear', 'gram']}
    predecessor, first_cost = f.encode(blocks, plans['linear'])
    successor, reuse_cost = f.encode(blocks, plans['gram'], predecessor)
    ordinary, ordinary_cost = f.encode(blocks, plans['gram'], copy.deepcopy(predecessor))
    fresh, fresh_cost = f.encode(blocks, plans['gram'])
    if ordinary != successor or fresh != successor:
        raise AssertionError('UNEQUAL_USEFUL_CONTENT')
    outcomes = {}
    for kind, cache in [('linear', predecessor), ('gram', successor)]:
        p = plans[kind]
        b, returns = f.execute(cache, p, operand if kind == 'linear' else None)
        accepted = []
        for lost in range(3):
            output = f.decode([row for row in returns if row['domain'] != lost], p, b)
            accepted.append(r.accept(blocks, kind, operand, output))
        if not all(accepted):
            raise AssertionError('DOMAIN_OUTAGE_FAILURE')
        bad = copy.deepcopy(returns)
        bad[0]['value'][0][0] = (bad[0]['value'][0][0] + 1) % f.P
        corruption_rejected = not r.accept(blocks, kind, operand, f.decode(bad, p, b))
        if not corruption_rejected:
            raise AssertionError('CORRUPTION_ACCEPTED')
        conventional = r.conventional_coded(kind)
        repl = r.replication()
        outputs = r.direct(blocks, kind, operand)
        replica_returns = [{**w, 'value': f.operation(blocks[w['block']], kind, operand)} for w in repl['workers']]
        replication_accepted = []
        for lost in range(3):
            delivered = {w['block']: w['value'] for w in replica_returns if w['domain'] != lost}
            replication_accepted.append(r.accept(blocks, kind, operand, [delivered[i] for i in range(3)]))
        q, n = p['threshold'], 16
        outcomes[kind] = {'plan': p, 'single_domain_outages_accepted': sum(accepted),
            'corruption_rejected_by_full_recomputation': corruption_rejected,
            'conventional_coded': conventional, 'replication': repl,
            'replication_single_domain_outages_accepted': sum(replication_accepted),
            'output_sha256': f.digest(outputs),
            'worker_scalar_multiplications': p['worker_units'] * n ** 3,
            'decode_scalar_multiplications': 3 * q * n ** 2,
            'independent_verification_scalar_multiplications': 3 * n ** 3,
            'return_field_elements_all_workers': p['worker_units'] * n * n,
            'replication_worker_scalar_multiplications': repl['worker_units'] * n ** 3,
            'reliable_local_production_scalar_multiplications': 3 * n ** 3}
    bad_contract = copy.deepcopy(plans['gram'])
    bad_contract['threshold'] = 3
    b, returns = f.execute(successor, plans['gram'])
    try:
        f.decode(returns[:3], bad_contract, b)
    except ValueError as e:
        changed_degree_rejected = str(e) == 'CURRENT_OPERATION_CONTRACT_REQUIRED'
    else:
        changed_degree_rejected = False
    legacy = [f.combine([v['value'] for v in returns[:3]], f.weights([v['x'] for v in returns[:3]], x)) for x in [1, 2, 3]]
    legacy_wrong = not r.accept(blocks, 'gram', None, legacy)
    if not changed_degree_rejected or not legacy_wrong:
        raise AssertionError('SUCCESSOR_COUNTEREXAMPLE_MISSING')
    return {'scope': 'AUTHORED_EXACT_FIELD_COMPUTATION_AND_DECLARED_ERASURE_MODEL',
        'sources': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.iterdir()) if p.suffix == '.py' or p.name == 'PROTOCOL.md'},
        'exhaustive': exhaustive, 'outcomes': outcomes,
        'successor': {'predecessor_encoding': first_cost, 'retained': reuse_cost,
            'no_retention': fresh_cost, 'equal_content_ordinary': ordinary_cost,
            'all_outputs_equal': True, 'inherited_linear_threshold_wrong_output': legacy_wrong,
            'degree_aware_contract_rejects': changed_degree_rejected,
            'improved_discovery_advantage': False},
        'two_domain_loss_coded_gram_feasible': f.construct('gram', losses=2) is not None,
        'verdict': 'NO_SUPER_ALPHA_ESTABLISHED_STRONG_ORDINARY_ALTERNATIVE_RETAINED',
        'actual_commercial_orders': 0, 'native_trailing365_profit_usd': None,
        'milestone_achieved': False,
        'telemetry': {'wall_seconds': time.perf_counter() - start, 'billing_usd': None}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'verdict': result['verdict'], 'exhaustive': result['exhaustive'],
                      'successor': result['successor']}))


if __name__ == '__main__':
    main()
