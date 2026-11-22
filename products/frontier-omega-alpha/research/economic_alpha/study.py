"""Replay the dated release, qualify the frozen asset and run the successor controls."""

from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter, process_time

from ..reflective_gate import assess_source_groups
from . import baseline, eligibility, process
from .observations import assert_observation

ROOT = Path(__file__).resolve().parent
IMPLEMENTATION = ('__main__.py', 'baseline.py', 'eligibility.py', 'process.py', 'observations.py', 'economics.py', 'study.py')
PUBLIC_COMMERCIAL_STATUS = {'eligible_real_beneficiary': None, 'orders_accepted': None, 'fulfilled_orders': None,
                            'customer_benefit': None, 'collected_funds': None, 'incremental_net_value': None,
                            'level_2_to_6': 'not-established'}


def named(name):
    return json.loads((ROOT / name).read_bytes())


def source_digest(name):
    return sha256((ROOT / name).read_bytes()).hexdigest()


def registered():
    original = named('registered_cases.json')
    fresh = named('fresh_cases.json')
    return {key: original[key] + fresh[key] for key in original}


def measured(rows, run):
    wall, cpu = perf_counter(), process_time()
    results = [run(row['input']) for row in rows]
    return results, {'wall_seconds': perf_counter() - wall, 'cpu_seconds': process_time() - cpu}


def qualify(observation):
    protocol = named('protocol.json')
    assert_observation(observation, protocol)
    opportunity = named('opportunities.json')
    if opportunity['selection'] != 'parts-retrofit':
        raise ValueError('The authorized candidate selection changed')
    digest = source_digest('eligibility.py')
    asset = named('s1_freeze.json')
    if digest != asset['asset_sha256'] or source_digest('protocol.json') != asset['protocol_sha256']:
        raise ValueError('The retained S1 changed after the qualification freeze')
    inputs = registered()
    before, older_time = measured(inputs['s1'], lambda item: eligibility.assess(item, protocol, protocol['before']))
    after, s1_time = measured(inputs['s1'], lambda item: eligibility.assess(item, protocol, protocol['after']))
    retained, s2_time = measured(inputs['s2'], lambda item: process.screen(item, protocol))
    with baseline.equipment(protocol) as db:
        direct_before, _ = measured(inputs['s1'], lambda item: baseline.compatibility(db, item, protocol, protocol['before']))
        direct_after, baseline_time = measured(inputs['s1'], lambda item: baseline.compatibility(db, item, protocol, protocol['after']))
        direct_s2, direct_s2_time = measured(inputs['s2'], lambda item: baseline.direct_process(db, item, protocol))
        ordinary_s2, ordinary_time = measured(inputs['s2'], lambda item: baseline.ordinary_process(db, item, protocol))
    s1 = [{'case': row['id'], 'before': old['decision'], 'after': new['decision'], 'baseline_before': base_before,
           'baseline_after': base_after, 'expected': row['expected'], 'part': new['part'], 'source_ids': new['source_ids']}
          for row, old, new, base_before, base_after in zip(inputs['s1'], before, after, direct_before, direct_after, strict=True)]
    s2 = [{'case': row['id'], 'with_inheritance': reuse['decision'], 'direct_without_inheritance': direct,
           'ordinary_reuse': simple, 'expected': row['expected']}
          for row, reuse, direct, simple in zip(inputs['s2'], retained, direct_s2, ordinary_s2, strict=True)]
    groups = assess_source_groups(protocol['sources'][key]['upstream'] for key in ('release', 'upgrade', 'stock', 'large'))
    report = {
        'schema': 'frontier-omega-alpha/alpha-1-technical-receipt-v1',
        'scope': 'Registered technical decisions using public catalog facts and constructed challenge inquiries',
        'candidate': opportunity['selection'], 'source_receipt': observation,
        'registration_sha256': source_digest('protocol.json'), 's1_asset_sha256': digest,
        'implementation_sha256': {path: source_digest(path) for path in IMPLEMENTATION},
        'fresh_cases_sha256': source_digest('fresh_cases.json'),
        'frontier_replay': {'before': protocol['before'], 'after': protocol['after'],
                            'changed': [row['case'] for row in s1 if row['before'] == 'no-documented-path' and row['after'] == 'retrofit-candidate']},
        's1': s1, 's2': s2,
        'source_group_check': {**groups, 'upstream_authority': 'Prusa', 'independent_physical_witness': None},
        'cost_observations': {'registered_replay': older_time, 's1_retained': s1_time, 's1_sql': baseline_time,
                              's2_retained': s2_time, 's2_sql': direct_s2_time, 's2_ordinary': ordinary_time,
                              'labor': None, 'billing': None, 'development': None, 'failed_attempts': None,
                              'beneficiary_integration': None,
                              'complete_cost': None},
        'outside_options': {'same_information_conventional': 'measured', 'OEM_lookup': 'public sources reviewed',
                            'frontier_model_at_full_workflow': 'unmeasured', 'human_supplier_workflow': 'unmeasured',
                            'commercial_specialist': 'unmeasured', 'continue_or_outsource': 'unmeasured'},
        'commercial': PUBLIC_COMMERCIAL_STATUS.copy(),
        'successor': {'frozen_asset_consumed': True, 'causal_invention_improvement': 'unproven'},
        'external_action_authorized': False,
    }
    metrics = verify(report)
    return {**report, 'verification': metrics}


def verify(report):
    """Independently reproduce named outcomes using the ordinary relational implementation."""
    protocol = named('protocol.json')
    assert_observation(report['source_receipt'], protocol)
    if (report['registration_sha256'] != source_digest('protocol.json')
            or report['s1_asset_sha256'] != named('s1_freeze.json')['asset_sha256']
            or report['s1_asset_sha256'] != source_digest('eligibility.py')
            or report['implementation_sha256'] != {path: source_digest(path) for path in IMPLEMENTATION}
            or report['fresh_cases_sha256'] != source_digest('fresh_cases.json')):
        raise ValueError('Unrecognized freeze or input identity')
    if (report['commercial'] != PUBLIC_COMMERCIAL_STATUS or report['external_action_authorized'] is not False
            or report['successor']['causal_invention_improvement'] != 'unproven'):
        raise ValueError('A public case replay cannot create commercial or causal evidence')
    tests = registered()
    before_date, after_date = protocol['before'], protocol['after']
    with baseline.equipment(protocol) as db:
        replay_changed = []
        for case, claimed in zip(tests['s1'], report['s1'], strict=True):
            expected_old = baseline.compatibility(db, case['input'], protocol, before_date)
            expected_new = baseline.compatibility(db, case['input'], protocol, after_date)
            part = protocol['sku'] if expected_new == 'retrofit-candidate' else None
            if (claimed['case'] != case['id'] or claimed['before'] != claimed['baseline_before'] or claimed['before'] != expected_old
                    or len({claimed['after'], claimed['baseline_after'], expected_new, case['expected'], claimed['expected']}) != 1
                    or part != claimed['part']
                    or ('upgrade' not in claimed['source_ids'] and part is not None)
                    or not set(claimed['source_ids']) <= protocol['sources'].keys()):
                raise ValueError('Compatibility replay disagreement: ' + case['id'])
            if expected_old == 'no-documented-path' and expected_new == 'retrofit-candidate':
                replay_changed.append(case['id'])
        for case, claimed in zip(tests['s2'], report['s2'], strict=True):
            direct = baseline.direct_process(db, case['input'], protocol)
            ordinary = baseline.ordinary_process(db, case['input'], protocol)
            if claimed['case'] != case['id'] or len({direct, ordinary, case['expected'], claimed['expected'],
                    claimed['with_inheritance'], claimed['direct_without_inheritance'], claimed['ordinary_reuse']}) != 1:
                raise ValueError('Successor replay disagreement: ' + case['id'])
    if report['frontier_replay'] != {'before': before_date, 'after': after_date, 'changed': replay_changed}:
        raise ValueError('The registered threshold comparison changed')
    return {'s1_reproduced': len(tests['s1']), 's2_reproduced': len(tests['s2']),
            'new_catalog_routes': len(replay_changed), 'technical_equivalence': True, 'technical_level': 1,
            'economic_promotion_authorized': False}
