"""Reproducible public-input development checks; not private qualification."""
import datetime
import hashlib
import json
import math
from pathlib import Path
import resource
import time
import traceback

import numpy as np
from scipy import sparse

from recovery import Recovery
from public_fixtures import (
    pollatsek_ruskai_7, shor_9, archived_controlled_s_15, apply_local,
)

RNG = np.random.default_rng(41702413)
PAULIS = [np.eye(2), np.array([[0, 1], [1, 0]]),
          np.array([[0, -1j], [1j, 0]]), np.diag([1, -1])]
TOL = 2e-8


def combine(states, weights):
    result = {}
    for state, weight in zip(states, weights):
        for word, amplitude in state.items():
            result[word] = result.get(word, 0j) + weight * amplitude
    return {word: complex(a) for word, a in result.items() if a != 0}


def norm2(state):
    return math.fsum(abs(a)**2 for a in state.values())


def random_unitary(size):
    a = RNG.normal(size=(size, size)) + 1j * RNG.normal(size=(size, size))
    return np.linalg.qr(a)[0]


def channel_set():
    result = [[np.eye(2)], [random_unitary(2)]]
    gamma = 0.37
    result.append([np.diag([1, math.sqrt(1-gamma)]),
                   np.array([[0, math.sqrt(gamma)], [0, 0]])])
    for count in (2, 4):
        a = RNG.normal(size=(2*count, 2)) + 1j*RNG.normal(size=(2*count, 2))
        v = np.linalg.qr(a)[0]
        ks = [v[2*i:2*i+2, :] for i in range(count)]
        assert np.max(np.abs(sum(k.conj().T@k for k in ks)-np.eye(2))) < 1e-14
        result.append(ks)
    return result


def correction_checks(n, words, recovery, all_channels=True):
    count = 0
    density_error = 0.0
    mass_error = 0.0
    encode_error = 0.0
    channels = channel_set()
    if not all_channels:
        channels = [channels[1], channels[-1]]
    for scale in (0.0, 0.23, 1.0, 3.1):
        logical = RNG.normal(size=len(words)) + 1j*RNG.normal(size=len(words))
        logical *= scale / np.linalg.norm(logical)
        expected = np.outer(logical, logical.conj())
        encoded = recovery.encode(logical)
        encode_error = max(encode_error, abs(norm2(encoded) - scale**2))
        for q in range(n):
            for kraus in channels:
                branches = [apply_local(encoded, n, q, k) for k in kraus]
                answer = recovery.recover(branches)
                raw = norm2(encoded)
                error = float(np.max(np.abs(answer['logical_density'] - expected)))
                mass = max(abs(answer['input_probability'] - raw),
                           abs(answer['correctable_probability'] - raw),
                           abs(answer['erasure_probability']))
                assert error < TOL * max(1, raw), (n, q, scale, error)
                assert mass < TOL * max(1, raw), (n, q, scale, mass)
                density_error = max(density_error, error)
                mass_error = max(mass_error, mass)
                count += 1
    return {'channel_state_qubit_cases': count,
            'max_logical_density_abs_error': density_error,
            'max_mass_abs_error': mass_error,
            'max_encode_squared_norm_error': encode_error}


def certificate_checks(n, words, recovery):
    exported = recovery.kraus()
    assert len(exported) == recovery.syndrome_rank
    assert all(len(op) == len(words) for op in exported)
    # The error columns below are constructed independently through the
    # public local-matrix convention, not the constructor's error routine.
    error_states = []
    for cw in words:
        error_states.append(cw)
        for q in range(n):
            error_states.extend(apply_local(cw, n, q, p) for p in PAULIS[1:])
    active = sorted(set().union(*(set(row) for op in exported for row in op),
                                *(set(state) for state in error_states)))
    index = {word: i for i, word in enumerate(active)}
    r_rows, r_cols, r_values = [], [], []
    for row_num, row in enumerate(row for op in exported for row in op):
        for word, a in row.items():
            r_rows.append(row_num); r_cols.append(index[word]); r_values.append(a)
    r = sparse.csr_matrix((r_values, (r_rows, r_cols)),
                          shape=(len(exported)*len(words), len(active)))
    error_matrix = np.zeros((len(active), len(error_states)), dtype=complex)
    for j, state in enumerate(error_states):
        for word, a in state.items():
            error_matrix[index[word], j] = a
    row_gram = (r @ r.conjugate().T).toarray()
    identity_residual = row_gram - np.eye(row_gram.shape[0])
    spectrum = np.linalg.eigvalsh((row_gram + row_gram.conj().T)/2)
    row_orthogonality = float(np.linalg.norm(identity_residual, ord=2))
    completeness = float(np.linalg.norm(
        r.conjugate().T @ (r @ error_matrix) - error_matrix, ord=2))
    assert row_orthogonality < TOL
    assert completeness < TOL
    assert float(spectrum[-1]) < 1 + TOL
    assert np.linalg.matrix_rank(error_matrix, tol=1e-10) == row_gram.shape[0]

    # Fresh arbitrary states, including coordinates outside active support.
    branches = []
    for _ in range(3):
        keys = np.unique(RNG.integers(0, 1 << n, size=41))
        values = RNG.normal(size=len(keys)) + 1j*RNG.normal(size=len(keys))
        branches.append({int(w): complex(a)/9 for w, a in zip(keys, values)})
    expected_density = np.zeros((len(words), len(words)), complex)
    for state in branches:
        vector = np.asarray([state.get(w, 0j) for w in active])
        output = (r @ vector).reshape(len(exported), len(words))
        expected_density += output.T @ output.conj()
    answer = recovery.recover(branches)
    agreement = float(np.max(np.abs(expected_density - answer['logical_density'])))
    assert agreement < TOL
    assert abs(answer['input_probability'] - sum(norm2(s) for s in branches)) < TOL
    assert abs(answer['input_probability'] - answer['correctable_probability']
               - answer['erasure_probability']) < TOL
    assert answer['erasure_probability'] > -TOL
    assert np.linalg.eigvalsh(answer['logical_density'])[0] > -TOL

    # Construct an erasure vector by applying the exported orthogonal
    # complement.  Its orthogonality is checked independently against E.
    random_vector = RNG.normal(size=len(active)) + 1j*RNG.normal(size=len(active))
    perpendicular = random_vector - r.conjugate().T @ (r @ random_vector)
    perpendicular /= np.linalg.norm(perpendicular)
    assert np.max(np.abs(error_matrix.conj().T @ perpendicular)) < TOL
    erased = {w: complex(a) for w, a in zip(active, perpendicular) if a != 0}
    erased_result = recovery.recover([erased])
    assert np.max(np.abs(erased_result['logical_density'])) < TOL
    assert abs(erased_result['erasure_probability'] - 1) < TOL
    logical = RNG.normal(size=len(words)) + 1j*RNG.normal(size=len(words))
    logical /= np.linalg.norm(logical)
    coherent_mixture = combine([recovery.encode(logical), erased],
                               [math.sqrt(0.35), math.sqrt(0.65)])
    coherent_result = recovery.recover([coherent_mixture])
    assert np.max(np.abs(coherent_result['logical_density']
                         - 0.35*np.outer(logical, logical.conj()))) < TOL
    assert abs(coherent_result['erasure_probability'] - 0.65) < TOL

    # Incoherent branches must not cancel even when their amplitudes do.
    encoded = recovery.encode(logical)
    opposite = {w: -a for w, a in encoded.items()}
    independent = recovery.recover([encoded, opposite])
    assert np.max(np.abs(independent['logical_density']
                         - 2*np.outer(logical, logical.conj()))) < TOL
    split = [{w: a/math.sqrt(2) for w, a in b.items()} for b in branches for _ in range(2)]
    split_result = recovery.recover(split)
    assert np.max(np.abs(split_result['logical_density'] - answer['logical_density'])) < TOL
    mixed_branches = [combine(branches, row) for row in random_unitary(len(branches))]
    mixed_result = recovery.recover(mixed_branches)
    assert np.max(np.abs(mixed_result['logical_density'] - answer['logical_density'])) < TOL
    assert abs(mixed_result['erasure_probability'] - answer['erasure_probability']) < TOL
    for empty in ([], [{}], [{0: 0j}, {}]):
        zero = recovery.recover(empty)
        assert np.count_nonzero(zero['logical_density']) == 0
        assert zero['input_probability'] == zero['correctable_probability'] == zero['erasure_probability'] == 0
    # The public certificate is a copy, not a writable alias of the channel.
    if exported[0][0]:
        key = next(iter(exported[0][0])); exported[0][0][key] = 123j
        unchanged = recovery.recover([encoded])
        assert np.max(np.abs(unchanged['logical_density']-np.outer(logical, logical.conj()))) < TOL
    return {'exported_kraus_count': len(exported),
            'active_coordinates': len(active),
            'kraus_nonzeros': int(r.nnz),
            'row_isometry_spectral_error': row_orthogonality,
            'completeness_on_error_span_spectral_error': completeness,
            'largest_squared_singular_value': float(spectrum[-1]),
            'fresh_input_certificate_density_error': agreement,
            'erasure_and_branch_invariance_checks': 'passed'}


def transformed(factory):
    n, words = factory()
    # All-qubit complex physical basis changes and a complex logical basis
    # change preserve correctability but change the actual sparse inputs.
    for q in range(n):
        unitary = random_unitary(2)
        words = [apply_local(cw, n, q, unitary) for cw in words]
    logical_basis = random_unitary(len(words))
    return n, [combine(words, logical_basis[:, j]) for j in range(len(words))]


def stress_20():
    _, words = shor_9()
    # Eight |+i> ancillas and three |0> ancillas give exactly 4096
    # supplied nonzero amplitudes across the two logical codewords.
    extended = []
    for cw in words:
        extended.append({(word << 11) | (ancilla << 3):
                         amp * (1j**ancilla.bit_count()) / 16
                         for word, amp in cw.items() for ancilla in range(256)})
    return 20, extended


def invalid_checks():
    n, words = pollatsek_ruskai_7()
    cases = [
        ('nonnormalized', n, [{w: 1.01*a for w, a in words[0].items()}, words[1]]),
        ('duplicate', n, [words[0], words[0]]),
        ('orthonormal_uncorrectable', n, [{0: 1}, {(1 << n)-1: 1}]),
        ('nan_amplitude', n, [{0: float('nan')}, words[1]]),
        ('infinite_amplitude', n, [{0: complex(0, float('inf'))}, words[1]]),
        ('out_of_range_word', n, [{1 << n: 1}, words[1]]),
        ('noninteger_word', n, [{0.25: 1}, words[1]]),
    ]
    outcomes = []
    for name, physical_count, cws in cases:
        try:
            Recovery(physical_count, cws)
        except ValueError as exc:
            outcomes.append({'case': name, 'rejected': True, 'reason': str(exc)})
        else:
            raise AssertionError(f'invalid case was accepted: {name}')
    return outcomes


def main():
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    report = {'test': 'public and self-designed development suite',
              'seed': 41702413,
              'source_sha256': hashlib.sha256(Path('recovery.py').read_bytes()).hexdigest(),
              'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'threads': {'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
                          'MKL_NUM_THREADS': '1'},
              'fixtures': []}
    try:
        factories = [
            ('published_pr7', pollatsek_ruskai_7),
            ('shor9', shor_9),
            ('archived_s15', archived_controlled_s_15),
            ('complex_rotated_pr7', lambda: transformed(pollatsek_ruskai_7)),
            ('complex_rotated_shor9', lambda: transformed(shor_9)),
            ('n20_4096_amplitudes', stress_20),
        ]
        for name, factory in factories:
            n, words = factory()
            wall = time.perf_counter(); cpu = time.process_time()
            recovery = Recovery(n, words)
            item = {'id': name, 'n': n, 'K': len(words),
                    'initial_nonzero': sum(map(len, words)),
                    'syndrome_rank': recovery.syndrome_rank,
                    'constructor_wall_seconds': time.perf_counter()-wall,
                    'constructor_cpu_seconds': time.process_time()-cpu,
                    'validation_residuals': recovery.validation_residuals}
            item.update(correction_checks(n, words, recovery, n < 20))
            if n < 20:
                item['certificate'] = certificate_checks(n, words, recovery)
            report['fixtures'].append(item)
            print(json.dumps(item), flush=True)
        report['invalid_inputs'] = invalid_checks()
        report['passed'] = True
    except Exception:
        report['passed'] = False
        report['failure'] = traceback.format_exc()
        raise
    finally:
        report['completed_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        report['wall_seconds'] = time.perf_counter()-start_wall
        report['process_cpu_seconds'] = time.process_time()-start_cpu
        report['max_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        Path('development_results.json').write_text(json.dumps(report, indent=2)+'\n')
        with Path('development_log.jsonl').open('a') as stream:
            stream.write(json.dumps({key: value for key, value in report.items()
                                     if key not in ('fixtures', 'invalid_inputs')})+'\n')
        print(json.dumps({'passed': report['passed'], 'wall_seconds': report['wall_seconds'],
                          'process_cpu_seconds': report['process_cpu_seconds'],
                          'max_rss_kib': report['max_rss_kib']}), flush=True)


if __name__ == '__main__':
    main()
