"""Supplemental review probes using public fixtures; no frozen-case changes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np

ROOT = Path('/workspace/scratch/e2ed86e4c5fa/frontier-first-proof/research/frontier_qec_transfer')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'fixtures'))
from recovery import Recovery
from noise_experiment import NoiseExperiment
from public_fixtures import apply_local, pollatsek_ruskai_7, shor_9
from second_public_fixtures import pauli_hypotheses


def identity(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def small(value, tolerance=2e-8):
    value = float(value)
    if not np.isfinite(value) or value > tolerance:
        raise AssertionError(f'{value} > {tolerance}')
    return value


def exported_matrix(experiment):
    matrix = np.zeros((len(experiment.measurement_operators()), 2,
                       1 << experiment.n), complex)
    for o, rows in enumerate(experiment.measurement_operators()):
        for i, row in enumerate(rows):
            for w, z in row.items():
                matrix[o, i, w] = z
    return matrix


def main():
    started = time.perf_counter()
    cpu = time.process_time()
    source_before = {name: identity(ROOT / name)
                     for name in ('recovery.py', 'noise_experiment.py')}
    probes = []
    rng = np.random.default_rng(20261121)

    # The original frozen recovery cohort ends at n=15. This public product-code
    # probe checks the implemented sparse n=20,K=4 boundary, without changing it.
    _, shor = shor_9()
    code20 = [{((x << 9) | y) << 2: a*b
               for x, a in left.items() for y, b in right.items()}
              for left in shor for right in shor]
    recovery = Recovery(20, code20)
    logical = np.array([1+.2j, -.1+.7j, .8-.4j, -.5-.3j])
    logical *= np.sqrt(.37) / np.linalg.norm(logical)
    encoded = recovery.encode(logical)
    target = np.outer(logical, logical.conj())
    gamma = .29
    kraus = [np.diag([1, np.sqrt(1-gamma)]),
             np.array([[0, np.sqrt(gamma)], [0, 0]])]
    errors = []
    for q in range(20):
        result = recovery.recover([apply_local(encoded, 20, q, a) for a in kraus])
        errors.append(small(np.max(abs(result['logical_density']-target))))
        small(abs(result['input_probability']-.37))
        small(abs(result['correctable_probability']-.37))
        small(abs(result['erasure_probability']))
    probes.append({'name': 'public_product_code_n20_K4', 'pass': True,
                   'local_channels_checked': 20,
                   'max_logical_density_error': max(errors),
                   'initial_code_amplitudes': sum(map(len, code20)),
                   'scope': 'Supplemental boundary probe, not original frozen qualification.'})

    # Optional convenience methods are not exercised directly by the frozen
    # successor checker. Compare them to physically exported operators.
    for factory in (pollatsek_ruskai_7, shor_9):
        n, code = factory()
        experiment = NoiseExperiment(n, code, pauli_hypotheses(n))
        matrix = exported_matrix(experiment)
        d = 1 << n
        rows = matrix.reshape(-1, d)
        effect = np.eye(d)-rows.conj().T @ rows
        small(np.max(abs(experiment.erasure_effect()-effect)))
        small(max(0, -np.linalg.eigvalsh(effect)[0]))
        small(max(0, np.linalg.eigvalsh(effect)[-1]-1))
        branches = []
        target_density = np.zeros((2, 2), complex)
        target_probabilities = np.zeros(matrix.shape[0])
        target_erasure = 0.0
        input_mass = 0.0
        for mass in (.13, .37, 2.3):
            vector = rng.normal(size=d)+1j*rng.normal(size=d)
            vector *= np.sqrt(mass)/np.linalg.norm(vector)
            branches.append(dict(enumerate(vector)))
            values = np.einsum('oid,d->oi', matrix, vector)
            target_density += values.T @ values.conj()
            target_probabilities += np.sum(abs(values)**2, axis=1)
            target_erasure += float(np.vdot(vector, effect @ vector).real)
            input_mass += mass
        result = experiment.measure(branches)
        residuals = {
            'density': small(np.max(abs(result['logical_density']-target_density))),
            'outcome_probabilities': small(np.max(abs(result['outcome_probabilities']-target_probabilities))),
            'erasure': small(abs(result['erasure_probability']-target_erasure)),
            'raw_input_mass': small(abs(result['input_probability']-input_mass)),
            'mass_balance': small(abs(result['mass_balance_residual'])),
        }
        zero = experiment.measure([])
        small(abs(zero['input_probability']))
        small(abs(zero['erasure_probability']))
        small(np.max(abs(zero['logical_density'])))
        probes.append({'name': factory.__name__+'/convenience_execution',
                       'pass': True, 'residuals': residuals})

    # Convexly dependent, nonduplicate channels exercise feasible quotient
    # inversion at simplex boundaries; no extra distinguishability is assumed.
    n, code = pollatsek_ruskai_7()
    identity2 = np.eye(2)
    x = np.array([[0, 1], [1, 0]])
    models = [
        {'name': 'identity', 'qubit': 0, 'kraus': [identity2]},
        {'name': 'x', 'qubit': 0, 'kraus': [x]},
        {'name': 'convex', 'qubit': 0,
         'kraus': [np.sqrt(.4)*identity2, np.sqrt(.6)*x]},
    ]
    experiment = NoiseExperiment(n, code, models)
    a = experiment.response_matrix()
    info = experiment.identifiability()
    assert info['rank'] == 2 and not info['unique']
    methods = []
    errors = []
    for truth in [np.array([1.,0.,0.]), np.array([0.,1.,0.]),
                  np.array([0.,0.,1.]), np.array([.17,.28,.55])]:
        for scale in (1., 1e200):
            result = experiment.estimate(scale*(a @ truth))
            w = result['mixture_weights']
            small(max(0., -float(np.min(w))))
            small(abs(np.sum(w)-1))
            errors.append(small(np.max(abs(result['identifiable_coordinates']
                                          -info['identifiable_projector'] @ truth)), 2e-6))
            small(np.max(abs(result['predicted_frequencies']-a @ truth)), 2e-6)
            methods.append(result['fit_method'])
    probes.append({'name': 'convex_dependence_and_boundary_inference', 'pass': True,
                   'rank': info['rank'], 'hypotheses': len(models),
                   'max_identifiable_coordinate_error': max(errors),
                   'fit_methods_exercised': sorted(set(methods))})
    source_after = {name: identity(ROOT / name) for name in source_before}
    assert source_before == source_after
    receipt = {'schema': 'frontier.qec.independent_review_probes.v1',
               'scope': 'Public-fixture supplemental review; no source repairs, private-case copying, or primary-gate changes.',
               'pass': True, 'source_sha256': source_after,
               'source_files_unchanged': True, 'probes': probes,
               'wall_seconds': time.perf_counter()-started,
               'cpu_seconds': time.process_time()-cpu,
               'maximum_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    (OUT / 'supplemental_checks.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (10*1024**3, 10*1024**3))
    main()
