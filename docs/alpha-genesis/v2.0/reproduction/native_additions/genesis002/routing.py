"""Learn a small service-to-method router; challenge it on disjoint synthetic tasks.

This selects among existing constructors. It is not new strategy synthesis,
open-ended self-improvement, or a population-level statistical superiority claim.
"""
from __future__ import annotations
from .common import digest
from .decision import METHODS, SERVICES


def execute(substrate, checker, raw, method):
    artifact = substrate.produce(raw, 'generated_schema', mode=method)
    check = checker(raw['service_id'], raw, artifact)
    return artifact, {'accepted': check['accepted'] is True,
                      'work': artifact['plan']['search']['operation_count'],
                      'artifact_sha256': digest(artifact),
                      'outcome_sha256': digest(substrate._semantics(artifact)),
                      'scope': 'counted intake mapping work only; not money or full execution cost'}


def qualify(substrate, checker, methods, seed):
    results = {}
    for method in methods:
        if method['access'] != 'local_public_code':
            continue
        per_service = {}
        for service in method['supported_services']:
            checks = []
            for index in (8, 9, 10):
                raw = substrate.synthetic_raw(service, index, seed)
                _, row = execute(substrate, checker, raw, method['adapter'])
                checks.append(row)
            per_service[service] = {'accepted': all(r['accepted'] for r in checks),
                                    'cases': len(checks), 'receipt_sha256': digest(checks)}
        results[method['id']] = per_service
    return results


def learn_and_test(substrate, checker, seed):
    # The selection code reads development rows only. Confirmation has another seed.
    train, confirmation = [], []
    for service in SERVICES:
        for index in (8, 9, 10, 11, 12, 13):
            raw = substrate.synthetic_raw(service, index, seed)
            for method in METHODS:
                _, row = execute(substrate, checker, raw, method)
                train.append({'service': service, 'index': index, 'method': method, **row})
    mapping = {}
    for service in SERVICES:
        ranked = []
        for method in METHODS:
            cases = [r for r in train if r['service'] == service and r['method'] == method]
            ranked.append((sum(not r['accepted'] for r in cases), sum(r['work'] for r in cases),
                           method != 'conventional', method))
        mapping[service] = min(ranked)[-1]
    policy = {'schema': 'genesis002/service-router/v1', 'mapping': mapping,
              'training_sha256': digest(train),
              'construction': 'Empirical selection among existing methods; no new method invented.'}
    frozen = digest(policy)
    for service in SERVICES:
        for index in (8, 10, 12, 14, 16, 18, 20, 22):
            raw = substrate.synthetic_raw(service, index, seed + 1)
            row = {'service': service, 'index': index, 'input_sha256': digest(raw), 'arms': {}}
            for name, method in [('learned_router', mapping[service]),
                                 ('direct_conventional', 'conventional'),
                                 ('generated_control', 'generated')]:
                _, evidence = execute(substrate, checker, raw, method)
                row['arms'][name] = evidence
            confirmation.append(row)
    if digest(policy) != frozen:
        raise ValueError('ROUTER_CHANGED_DURING_CONFIRMATION')
    summary = {}
    for arm in ('learned_router', 'direct_conventional', 'generated_control'):
        summary[arm] = {'accepted': sum(r['arms'][arm]['accepted'] for r in confirmation),
                        'total_cases': len(confirmation),
                        'mapping_work': sum(r['arms'][arm]['work'] for r in confirmation)}
    comparable = all(len({a['outcome_sha256'] for a in r['arms'].values()}) == 1 for r in confirmation)
    learned, ordinary = summary['learned_router'], summary['direct_conventional']
    if not comparable:
        verdict = 'OUTCOME_MISMATCH_NO_ADOPTION'
    elif learned == ordinary:
        verdict = 'RETAIN_DIRECT_CONVENTIONAL_TIE'
    elif learned['accepted'] >= ordinary['accepted'] and learned['mapping_work'] < ordinary['mapping_work']:
        verdict = 'FINITE_MAPPING_WORK_GAIN_ONLY'
    else:
        verdict = 'RETAIN_DIRECT_CONVENTIONAL'
    return {'schema': 'genesis002/routing-study/v1', 'policy': policy,
            'frozen_policy_sha256': frozen, 'development': train, 'confirmation': confirmation,
            'summary': summary, 'equal_outcomes': comparable, 'decision': verdict,
            'freshness': 'Disjoint declared synthetic seeds within this run; exposed reproduction thereafter.',
            'meta_discovery_superiority': 'NOT_ESTABLISHED',
            'cost_scope': 'Native research envelope is separately paid. Mapping-work counts are not dollars.'}
