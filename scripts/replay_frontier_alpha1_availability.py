#!/usr/bin/env python3
"""Verify ALPHA-1's published decisions and isolate its date assumption."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / 'publication/frontier-alpha-1-availability.json'
BASE = '5cced81256c965797988cd682fb5f910fe72c981'
RESEARCH = 'products/frontier-omega-alpha/research/economic_alpha'
FROZEN = {
    'protocol.json': 'f148678e6f2247b2ff0326a9cd997a4babc2c2c43b5de35d4560b038bc07fff9',
    'registered_cases.json': 'a10f848ff49cef8119972e62bea095292f465fd5d1f511aa1176b4fe271cff10',
    'fresh_cases.json': 'd7d8ad16f20fe57ee4f431f4c4d939688f26e2fb93d29c28b8501ab76a9a4a6f',
    'qualification.json': '694bc304a349135956109795c11967d287725bab5a2ee28e847d70a6eff65c8d',
}
EARLIER = '2026-09-29'


def frozen_data(name):
    raw = subprocess.check_output(['git', 'show', f'{BASE}:{RESEARCH}/{name}'], cwd=ROOT)
    if sha256(raw).hexdigest() != FROZEN[name]:
        raise ValueError(f'Unexpected frozen input: {name}')
    return json.loads(raw)


def replay():
    protocol = frozen_data('protocol.json')
    registered = frozen_data('registered_cases.json')
    fresh = frozen_data('fresh_cases.json')
    original = frozen_data('qualification.json')
    catalog = protocol['catalog']
    stock = catalog['standard_nozzle_c']
    retrofit = catalog['retrofit_nozzle_c']
    models = {label: (model, spec['chamber_limit_c'])
              for model, spec in catalog['eligible'].items() for label in spec['labels']}
    excluded = set(catalog['explicit_exclusions'])

    def facts(case):
        request = case['input']
        label = ' '.join(request['model'].lower().split())
        return request, models.get(label), label.removeprefix('prusa ') in excluded

    def direct_route(db, case, available):
        request, model, rejected = facts(case)
        return db.execute('''
            SELECT CASE
                WHEN :use != 'non_safety_critical' THEN 'external-review-required'
                WHEN :excluded THEN 'unsupported-configuration'
                WHEN :model IS NULL THEN 'need-model-evidence'
                WHEN :requirement <= :stock THEN 'existing-envelope'
                WHEN :available AND :requirement <= :retrofit THEN 'retrofit-candidate'
                ELSE 'no-documented-path'
            END
        ''', {'use': request['use'], 'excluded': rejected, 'model': model[0] if model else None,
              'requirement': request['nozzle_requirement_c'], 'stock': stock, 'available': available,
              'retrofit': retrofit}).fetchone()[0]

    def process_route(db, case):
        fit = direct_route(db, case, True)
        if fit not in ('existing-envelope', 'retrofit-candidate'):
            return fit
        request, (_, chamber), _ = facts(case)
        if request['claimed_installed'] == 'unknown' or (
            fit == 'retrofit-candidate' and request['claimed_installed'] != 'retrofit'
        ):
            return 'installed-configuration-unverified'
        if chamber is None:
            return 'need-chamber-evidence'
        if request['required_chamber_c'] > chamber:
            return 'outside-chamber-envelope'
        if request['sheet'] != catalog['successor_sheet']:
            return 'accessory-evidence-required'
        if request['site_review'] != 'approved-evidence':
            return 'site-evidence-required'
        return 'documented-process-envelope'

    before, after = protocol['before'], protocol['after']
    s1 = registered['s1'] + fresh['s1']
    s2 = registered['s2'] + fresh['s2']
    if not EARLIER < before < after or not s1 or not s2:
        raise ValueError('Unexpected comparison scope')
    with sqlite3.connect(':memory:') as db:
        for case, expected in zip(s1, original['s1'], strict=True):
            absent = direct_route(db, case, False)
            present = direct_route(db, case, True)
            if (case['id'], absent, present, case['expected']) != (
                    expected['case'], expected['before'], expected['after'], present):
                raise ValueError(f"Compatibility decision disagrees: {case['id']}")
            if expected['baseline_before'] != absent or expected['baseline_after'] != present:
                raise ValueError("Published conventional compatibility route disagrees")
        for case, expected in zip(s2, original['s2'], strict=True):
            result = process_route(db, case)
            if case['id'] != expected['case'] or {
                result, case['expected'], expected['with_inheritance'],
                expected['direct_without_inheritance'], expected['ordinary_reuse'],
            } != {result}:
                raise ValueError(f"Process-screening decision disagrees: {case['id']}")

        def changes(assumed_date):
            return [
                case['id'] for case in s1
                if direct_route(db, case, before >= assumed_date) == 'no-documented-path'
                and direct_route(db, case, after >= assumed_date) == 'retrofit-candidate'
            ]

        original_changes = changes(after)
        earlier_changes = changes(EARLIER)
    if original_changes != original['frontier_replay']['changed']:
        raise ValueError('Registered date replay differs from the original receipt')

    return {
        'schema': 'frontier-omega-alpha/alpha-1-availability-replay-v1',
        'registered_revision': BASE,
        'inputs_sha256': FROZEN,
        'frozen_case_decisions_reproduced': {'compatibility': len(s1), 'process_screening': len(s2)},
        'comparison_days': {'before': before, 'after': after},
        'registered_scenario': {'assumed_available_from': after, 'new_route_cases': original_changes},
        'earlier_scenario': {'assumed_available_from': EARLIER, 'new_route_cases': earlier_changes},
        'historical_manufacturer_snapshot_confirmed': False,
        'economic_advantage_established': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare the result with the published receipt')
    args = parser.parse_args()
    result = replay()
    if args.check and json.loads(RECEIPT.read_text(encoding='utf-8')) != result:
        raise SystemExit('Availability replay differs from the published receipt.')
    print(json.dumps(result, indent=2))
