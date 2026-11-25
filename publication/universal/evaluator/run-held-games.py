"""Run the frozen candidate and comparators against the evaluator's sealed games."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
from math import comb
import os
from pathlib import Path
import platform
from shutil import copyfile
import subprocess
import sys
from time import perf_counter


HERE = Path(__file__).resolve().parent
PLAN_SHA = '0f6560943e26a5e65a598500cf23c7ba90b5a13474b0f64debec662f5a679620'
CASES_SHA = '678eec8a0d2f42f708c3f2e85226a80f64528dde13f9c39c7165de74797d7c25'
RUN_ENV = {**os.environ, 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}
METHODS = ('sparse-path-lp', 'dense', 'double-oracle')


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    with path.open('x', encoding='utf-8') as file:
        json.dump(value, file, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        file.write('\n')


def run(argv, cwd, timeout=90):
    start = perf_counter()
    try:
        result = subprocess.run([sys.executable, *map(str, argv)], cwd=cwd, env=RUN_ENV,
                                capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {'status': 'process-timeout', 'wall_s': perf_counter() - start, 'timeout_s': timeout}
    return {'status': 'process-complete', 'wall_s': perf_counter() - start,
            'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}


def candidate_pack_to_independent(cert):
    den = cert['denominator']
    return {
        'row_strategy': [{'allocation': value['allocation'], 'p': [value['mass'], den]} for value in cert['row']],
        'column_strategy': [{'allocation': value['allocation'], 'p': [value['mass'], den],
                             'scenario': value['scenario']} for value in cert['column']],
    }


def check_cert(certificate, game, checker, work, source, label):
    result = {'certificate_sha256': digest(certificate)}
    data = json.loads(certificate.read_bytes())
    start = perf_counter()
    result['independent'] = checker.exact_bounds(game, candidate_pack_to_independent(data))
    result['independent']['wall_s'] = perf_counter() - start
    supplied = run(['-I', '-S', source/'verify.py', work/'input.json', certificate], source, timeout=30)
    (work/f'{label}.supplied-verification.txt').write_text(supplied.get('stdout', ''), encoding='utf-8')
    if supplied.get('returncode') != 0:
        raise ValueError(f'Supplied verifier failed: {supplied}')
    supplied = json.loads(supplied['stdout'])
    result['supplied_verdict'] = supplied['verdict']
    result['exact_bound_agreement'] = all(
        Fraction(result['independent'][independent]) == Fraction(supplied[provided], supplied['denominator'])
        for independent, provided in (('row_lower', 'lower_numerator'), ('col_upper', 'upper_numerator')))
    result['verdict_agreement'] = (supplied['verdict'] == 'QUALIFIED') == result['independent']['passed_gap']
    return result


def negative_controls(work, source, checker, game):
    candidate = json.loads((work/'sparse-path-lp.certificate.json').read_bytes())
    tampered = deepcopy(candidate)
    tampered['row'][0]['mass'] += 1
    path = work/'tampered-mass.json'
    save(path, tampered)
    supplied = run(['-I', '-S', source/'verify.py', work/'input.json', path], source, timeout=30)
    independent_rejected_mass = False
    try:
        checker.exact_bounds(game, candidate_pack_to_independent(tampered))
    except ValueError as error:
        independent_rejected_mass = str(error) == 'Probability masses do not sum to one exactly'
    weak = deepcopy(candidate)
    lanes = len(game['scenarios'][0]['weights'])
    scenario = game['scenarios'][0]
    weak.update({'denominator': 1,
                 'row': [{'allocation': [game['row_budget'], *[0]*(lanes-1)], 'mass': 1}],
                 'column': [{'allocation': [scenario['column_budget'], *[0]*(lanes-1)], 'mass': 1,
                             'scenario': scenario['id']}]})
    path = work/'feasible-suboptimal.json'
    save(path, weak)
    return {'malformed_mass_independently_rejected': independent_rejected_mass,
            'malformed_mass_supplied_rejected': supplied.get('returncode', 0) != 0,
            'feasible_but_suboptimal': check_cert(path, game, checker, work, source, 'feasible-suboptimal')}


def main(output):
    started = timestamp()
    output.mkdir()
    source = output/'frozen-source'
    source.mkdir()
    original = HERE.parent/'game-theory'
    assert digest(original/'BENCHMARK-PLAN.json') == PLAN_SHA
    assert digest(HERE/'held-games.json') == CASES_SHA
    plan = json.loads((original/'BENCHMARK-PLAN.json').read_bytes())
    assert plan['held_set_sha256'] == CASES_SHA
    copyfile(original/'BENCHMARK-PLAN.json', source/'BENCHMARK-PLAN.json')
    for name, expected in plan['source_sha256'].items():
        copyfile(original/name, source/name)
        assert digest(source/name) == expected
    spec = importlib.util.spec_from_file_location('independent_held_oracle', HERE/'verify-game.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    results = []
    for case in json.loads((HERE/'held-games.json').read_bytes())['cases']:
        game, name = case['game'], case['id']
        work = output/name
        work.mkdir()
        save(work/'input.json', game)
        lanes = len(game['scenarios'][0]['weights'])
        row_count = comb(game['row_budget'] + lanes - 1, lanes - 1)
        column_count = sum(comb(s['column_budget'] + lanes - 1, lanes - 1) for s in game['scenarios'])
        result = {'id': name, 'row_actions': row_count, 'column_actions': column_count,
                  'implicit_pairs': row_count*column_count, 'methods': {}}
        if result['implicit_pairs'] <= plan['registered_matrix_cell_budget']:
            result['explicit_matrix_control'] = checker.matrix_control(game)
        for method in METHODS:
            cert, receipt = (work/f'{method}.{extension}.json' for extension in ('certificate', 'receipt'))
            args = [source/'solve.py'] if method == 'sparse-path-lp' else [source/'baselines.py', method]
            trace = run([*args, work/'input.json', '--certificate', cert, '--receipt', receipt], source)
            if receipt.exists():
                trace['instrumented'] = json.loads(receipt.read_bytes())
            if cert.exists():
                trace.update(check_cert(cert, game, checker, work, source, method))
                if 'explicit_matrix_control' in result:
                    bound = trace['independent']
                    value = result['explicit_matrix_control']['robust_minimax_value']
                    trace['agrees_independent_explicit_matrix'] = (
                        float(Fraction(bound['row_lower'])) - 1e-8 <= value <= float(Fraction(bound['col_upper'])) + 1e-8)
            result['methods'][method] = trace
            print(name, method, trace.get('supplied_verdict', trace.get('instrumented', trace['status'])),
                  round(trace['wall_s'], 4), flush=True)
        if name == 'shared-policy' and (work/'sparse-path-lp.certificate.json').exists():
            result['negative_controls'] = negative_controls(work, source, checker, game)
        save(work/'case-report.json', result)
        results.append(result)
    runtime = run(['-c', 'import numpy, scipy; print(numpy.__version__, scipy.__version__)'], source)
    save(output/'INDEPENDENT-REPORT.json', {
        'started_utc': started, 'completed_utc': timestamp(), 'owner_ambition': plan['owner_ambition'],
        'frozen_plan_sha256': PLAN_SHA, 'held_sha256': CASES_SHA, 'source_sha256': plan['source_sha256'],
        'independent_verifier_sha256': digest(HERE/'verify-game.py'), 'protocol_wall_timeout_s': 90,
        'results': results, 'runtime': {'platform': platform.platform(), 'python': platform.python_version(),
                                        'numpy_scipy': runtime.get('stdout', '').strip(), 'threads': 1},
    })


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    main(parser.parse_args().output.resolve())
