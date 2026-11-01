"""Consume a pinned applicability lesson, then execute a fixed native scaling comparison.
This driver uses the existing engine, Account, JournalAccount, producer and auditor.
It neither owns a second ledger nor treats forecasts/capsules as spending authority.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from commercial.ledger import canonical, digest, strict_json
from connected_enterprise.engine import run_world, validate_config
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit
from adaptive_enterprise.instruments import prepare_complete_offer_services
from experiments import arrangement_cycle046 as prior

ROOT = Path(__file__).resolve().parents[1]
MICRO = 1_000_000
SCHEMA = 'agi-alpha/retained-arrangement-transfer047/v1'
LESSON_PATH = 'campaign/arrangement-transfer-047/LESSON.json'
DRIVERS = ('experiments/arrangement_cycle046.py', 'experiments/arrangement_transfer047.py',
           'tests/test_arrangement_transfer047.py', LESSON_PATH)


def protocol():
    return {'schema': SCHEMA, 'scope': 'FINITE_AUTHORED_NATIVE_TRANSFER_NOT_REAL_COMMERCE',
        'opening_microUSD': 100_000*MICRO, 'external_funding_microUSD': 0,
        'arms': ['one_unit', 'ordinary_complement', 'retained_complement'],
        'cases': [
            {'id': 'fresh_transfer', 'buyers': 24, 'days': 28, 'max_slots': 6, 'seed': 2611010471, 'rival_price': 180*MICRO},
            {'id': 'larger_workload', 'buyers': 48, 'days': 42, 'max_slots': 9, 'seed': 2611010472, 'rival_price': 180*MICRO},
            {'id': 'strong_outside', 'buyers': 48, 'days': 42, 'max_slots': 9, 'seed': 2611010472, 'rival_price': 15*MICRO}],
        'services': {'cohort_seed': 2611010470, 'primitive_jobs_per_service': 64, 'packet_jobs': 128, 'rows_per_packet': 12},
        'reuse_adaptation_cost_microUSD': 5*MICRO,
        'lesson_acquisition_cost_scope': 'Prior research is sunk shared history, not earned capital. Retained arm additionally charges a declared $5 adaptation/checking envelope; actual host/development bills are unknown.',
        'selection': 'Highest audited complete modeled profit with obligations covered. Simpler ordinary policy wins ties. Selection is local to each authored case, not a transferable optimality certificate.',
        'limits': ['All cases and seeds fixed before execution; losses and ties are valid outcomes.',
                   'Identical market, customer budgets, prices, work and initial capital within each case; never pool balances.',
                   'A larger synthetic population is a workload, not acquired real demand or scale aggregation.',
                   'Retained recipe narrows a search grammar, never forces a purchase or transfers current proof/authority.',
                   'Observed outcomes on these fixed cases are not general recursive improvement or a billion-dollar result.']}


def require(ok, reason):
    if not ok: raise ValueError(reason)


def lesson_record(root=ROOT):
    record = strict_json((Path(root)/LESSON_PATH).read_bytes())
    require(set(record) == {'capsule', 'capsule_sha256', 'provenance'}, 'EXACT_LESSON_RECORD_REQUIRED')
    c = record['capsule']
    require(record['capsule_sha256'] == digest(c), 'LESSON_DIGEST_MISMATCH')
    require(c.get('schema') == 'agi-alpha/applicability-capsule046/v1'
            and c.get('known_method_not_new_invention') is True
            and c.get('execution_authority') is False and c.get('authority') == []
            and c.get('current_proof') is None, 'INERT_SCOPED_CAPSULE_REQUIRED')
    p = record['provenance']
    require(p.get('commit') == '7dc2210fa5f4718ceac752e044e42661578e6148'
            and p.get('artifact_sha256') == 'e3b5e363f31abe81c2b09533a188c2cb50142f19cd4b38a06f9bf5936e178878',
            'PINNED_PREDECESSOR_ARTIFACT_REQUIRED')
    return record


def retained_policy(capsule, expected_pin, *, required_units, initial_slots, max_slots, max_customers):
    """A known complement bound informed by retained applicability, not a new inventor.

    All currently admitted outcomes must fit the declared required_units bound.
    The native controller still recomputes actual menus, current cash and expiry.
    """
    require(digest(capsule) == expected_pin, 'EXTERNALLY_PINNED_CAPSULE_CHANGED')
    require(capsule.get('schema') == 'agi-alpha/applicability-capsule046/v1'
            and capsule.get('execution_authority') is False and capsule.get('authority') == []
            and capsule.get('current_proof') is None, 'NO_INHERITED_AUTHORITY_OR_PROOF')
    for value in (required_units, initial_slots, max_slots, max_customers):
        require(type(value) is int and value > 0, 'POSITIVE_CURRENT_CAPACITY_CONTRACT_REQUIRED')
    require(max_slots >= initial_slots, 'CONSISTENT_CAPACITY_ENVELOPE_REQUIRED')
    rows = capsule.get('observed_regions')
    require(type(rows) is dict and rows, 'APPLICABILITY_EVIDENCE_REQUIRED')
    supported = []
    for name, row in rows.items():
        require(type(row.get('observed_profit_delta_microUSD')) is int, 'EXACT_OBSERVED_DELTA_REQUIRED')
        if row.get('choice') == 'COMPLEMENTARY_CAPACITY_SEARCH' and row['observed_profit_delta_microUSD'] > 0:
            supported.append(name)
    # Buying beyond all offered simultaneous work is not useful under positive
    # capacity prices in this fixed menu. This is ordinary resource reasoning.
    bound = min(max_slots-initial_slots, max(1, max_customers*required_units-initial_slots))
    choice = 'COMPLEMENTARY_CAPACITY_SEARCH' if supported else 'RETAIN_ONE_UNIT_POLICY'
    return {'schema': 'agi-alpha/inert-transfer-recipe047/v1', 'choice': choice,
        'max_quantity': bound if supported else min(1, max_slots-initial_slots),
        'support_regions': sorted(supported), 'capsule_sha256': expected_pin,
        'required_units': required_units, 'max_customers': max_customers,
        'current_proof': None, 'authority': [], 'execution_authority': False,
        'limits': 'An admissible policy configuration only. Full native cash, buyer choice, quality, expiry and reservation checks remain mandatory.'}


def configure(case, arm, manifest, lesson):
    p = protocol()
    require(case in p['cases'] and arm in p['arms'], 'FIXED_CASE_ARM_REQUIRED')
    old = prior.protocol()
    cfg, admitted = prior.config(old, old['cases'][1], 'complementary', manifest)
    cfg.update(opening=p['opening_microUSD'], horizon_days=case['days'], customer_pool=case['buyers'],
               maximum_slots=case['max_slots'])
    cfg['channels']['pilot']['owned_audience_count'] = case['buyers']
    profile = cfg['complete_offer_policy']['profiles'][0]
    for option in profile['outside_options']:
        if option['provider'] == 'rival': option['price'] = case['rival_price']
    requested = {f'SIM-customer-{i:03d}': [] for i in range(case['buyers'])}
    for service in profile['services']:
        jobs = sorted((j for j in manifest['jobs'] if j['accepted'] and j['service_id'] == service), key=lambda j: j['id'])
        for i, job in enumerate(jobs): requested[f'SIM-customer-{i%case["buyers"]:03d}'].append(job['id'])
    cfg['complete_offer_policy']['requested_jobs'] = requested
    recipe = None
    if arm == 'one_unit': quantity = 1
    elif arm == 'ordinary_complement': quantity = case['max_slots']-1
    else:
        # Obtain the current known packet contract from the actual implementation,
        # not an inherited claim about what the new mission requires.
        from connected_enterprise.packet_contract import synthetic_input, work_contract
        units = work_contract(synthetic_input(rows=12))['capacity_units']
        recipe = retained_policy(lesson['capsule'], lesson['capsule_sha256'], required_units=units,
            initial_slots=cfg['initial_slots'], max_slots=case['max_slots'],
            max_customers=cfg['strategic_allocation_policy']['max_customers'])
        quantity = recipe['max_quantity']
        cfg['setup_cost'] += p['reuse_adaptation_cost_microUSD']
    cfg['strategic_allocation_policy']['capacity_menu']['max_quantity'] = quantity
    return validate_config(cfg), admitted, recipe


def experiment_identity(root):
    out = {}
    for name in DRIVERS:
        path = Path(root)/name
        require(path.is_file() and not any(p.is_symlink() for p in [path, *path.parents]), 'NORMAL_EXPERIMENT_SOURCE_REQUIRED')
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def check_freeze(output):
    f = strict_json((output/'FREEZE.json').read_bytes())
    require(identity(ROOT) == f['source'] and experiment_identity(ROOT) == f['drivers'], 'SOURCE_CHANGED')
    require(canonical(strict_json((output/'PROTOCOL.json').read_bytes())) == canonical(protocol()), 'PROTOCOL_CHANGED')
    require(f['protocol_sha256'] == digest(protocol()), 'PROTOCOL_DIGEST_CHANGED')
    return f


def covered(world):
    s = world['summary']
    return (world.get('audit_accepted') is True and s['payables'] == 0 and not s['investmentStopped']
            and s['cash'] >= s['custodyReserve']+s['tailReserve']+s['workingCapital'])


def select_from_results(worlds):
    result = {}
    for case in protocol()['cases']:
        choices = []
        for i, arm in enumerate(protocol()['arms']):
            row = worlds[case['id']+'-'+arm]
            require(row.get('audit_accepted') is True, 'ALL_COMPARISONS_MUST_BE_AUDITED')
            if covered(row) and row['summary']['profit'] > 0:
                # Ordinary complete search wins an exact tie with retained search;
                # the cheapest/simple one-unit policy wins a tie with either.
                choices.append((row['summary']['profit'], -i, arm))
        selected = max(choices)[2] if choices else None
        base = worlds[case['id']+'-one_unit']
        full = worlds[case['id']+'-ordinary_complement']
        reuse = worlds[case['id']+'-retained_complement']
        result[case['id']] = {'selected': selected,
            'ordinary_vs_one_unit_profit_microUSD': full['summary']['profit']-base['summary']['profit'],
            'retained_vs_ordinary_profit_microUSD': reuse['summary']['profit']-full['summary']['profit'],
            'selection_scope': 'OBSERVED_THIS_FIXED_AUTHORED_CASE_ONLY', 'funding_authority': False}
    return result


def execute(output):
    f = check_freeze(output); p = protocol(); lesson = lesson_record()
    path = output/'SERVICES.json'
    if path.exists(): manifest = strict_json(path.read_bytes())
    else:
        spec = p['services']
        manifest = prepare_complete_offer_services(ROOT, 'transfer047-inputs', cohort_seed=spec['cohort_seed'],
            jobs_per_service=spec['primitive_jobs_per_service'], packet_jobs=spec['packet_jobs'], packet_rows=spec['rows_per_packet'])
        prior.write(path, manifest)
    worlds = {}; started, cpu = time.monotonic(), time.process_time()
    for case in p['cases']:
        for arm in p['arms']:
            name = case['id']+'-'+arm
            cfg, admitted, recipe = configure(case, arm, manifest, lesson)
            r = run_world(ROOT, admitted, cfg, case['seed'], 'competitive_growth', output/'private'/name, source=f['source'])
            checked = audit(ROOT, admitted, r)
            row = prior.project(r, checked); row['recipe'] = recipe
            row['capacity_search_bound'] = cfg['strategic_allocation_policy']['capacity_menu']['max_quantity']
            row['days'] = case['days']; row['prospects'] = case['buyers']
            worlds[name] = row
            prior.write(output/'public'/'PROGRESS.json', {'complete': False, 'source_sha256': f['source']['sha256'], 'completed': worlds})
            print(json.dumps({'world': name, 'profit': r['summary']['profit'], 'settled': r['paid_jobs'],
                              'packets': row['accepted_packets'], 'witness': row['mechanism']['status']}), flush=True)
    result = {'schema': SCHEMA, 'scope': p['scope'], 'complete': True,
        'source_sha256': f['source']['sha256'], 'driver_sha256': digest(f['drivers']), 'protocol_sha256': digest(p),
        'lesson_sha256': lesson['capsule_sha256'], 'opening_per_world_microUSD': p['opening_microUSD'],
        'external_funding_microUSD': 0, 'worlds': worlds, 'decisions': select_from_results(worlds),
        'measured_wall_seconds': time.monotonic()-started, 'process_cpu_seconds': time.process_time()-cpu,
        'python': sys.version, 'actual_customers': 0, 'actual_collections_microUSD': 0, 'actual_profit_microUSD': None,
        'inventor_improvement': False, 'funding_authority': False, 'unmeasured_costs': ['actual host billing', 'development labor', 'actual model billing'],
        'limits': p['limits']}
    prior.write(output/'public'/'RESULT.json', result)
    prior.write(output/'public'/'ADOPTION.json', {'schema': SCHEMA, 'result_sha256': digest(result),
        'decisions': result['decisions'], 'current_proof': None, 'authority': [],
        'rule': 'Retain complete-outcome resource complements where native results support them; do not adopt costlier inheritance when ordinary complete search is as good.',
        'automatic_promotion': False})
    (output/'public'/'PROGRESS.json').unlink(missing_ok=True)
    return result


def verify(output):
    f = check_freeze(output); p = protocol(); lesson = lesson_record()
    record = strict_json((output/'public'/'RESULT.json').read_bytes())
    require(record.get('schema') == SCHEMA and record.get('scope') == p['scope']
        and record.get('complete') is True and record.get('source_sha256') == f['source']['sha256']
        and record.get('driver_sha256') == digest(f['drivers']) and record.get('protocol_sha256') == digest(p)
        and record.get('lesson_sha256') == lesson['capsule_sha256'], 'EXACT_COMPLETED_RECORD_REQUIRED')
    for field, expected in [('opening_per_world_microUSD', p['opening_microUSD']), ('external_funding_microUSD', 0),
                             ('actual_customers', 0), ('actual_collections_microUSD', 0), ('actual_profit_microUSD', None),
                             ('inventor_improvement', False), ('funding_authority', False), ('limits', p['limits'])]:
        require(canonical(record.get(field)) == canonical(expected), 'INVALID_CLAIM:'+field)
    manifest = strict_json((output/'SERVICES.json').read_bytes()); actual = {}
    for case in p['cases']:
        for arm in p['arms']:
            name = case['id']+'-'+arm; cfg, admitted, recipe = configure(case, arm, manifest, lesson)
            r = strict_json((output/'private'/name/'RESULT.json').read_bytes())
            require(canonical(r['config']) == canonical(cfg) and r['seed'] == case['seed']
                    and r['arm'] == 'competitive_growth', 'REGISTERED_WORLD_CHANGED')
            actual[name] = prior.project(r, audit(ROOT, admitted, r))
            actual[name].update(recipe=recipe, capacity_search_bound=cfg['strategic_allocation_policy']['capacity_menu']['max_quantity'], days=case['days'], prospects=case['buyers'])
    require(canonical(actual) == canonical(record['worlds']), 'PUBLIC_OUTCOMES_CHANGED')
    require(canonical(select_from_results(actual)) == canonical(record['decisions']), 'SELECTION_CHANGED')
    capsule = strict_json((output/'public'/'ADOPTION.json').read_bytes())
    expected = {'schema': SCHEMA, 'result_sha256': digest(record), 'decisions': record['decisions'],
        'current_proof': None, 'authority': [],
        'rule': 'Retain complete-outcome resource complements where native results support them; do not adopt costlier inheritance when ordinary complete search is as good.',
        'automatic_promotion': False}
    require(canonical(capsule) == canonical(expected), 'ADOPTION_CLAIM_CHANGED')
    return {'accepted': True, 'worlds': len(actual), 'source_sha256': f['source']['sha256'],
            'driver_sha256': digest(f['drivers']), 'scope': 'FULL_NATIVE_REAUDIT_NOT_REAL_COMMERCE', 'funding_authority': False}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['run', 'operate', 'resume', 'verify']); ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv); output = args.output.absolute()
    require('..' not in output.parts and not any(x.is_symlink() for x in [output, *output.parents]), 'NORMAL_PRIVATE_OUTPUT_REQUIRED')
    if args.command == 'verify': print(json.dumps(verify(output), sort_keys=True)); return 0
    if args.command == 'run':
        require(not output.exists() and output.parent.is_dir(), 'FRESH_OUTPUT_REQUIRED')
        source, drivers = identity(ROOT), experiment_identity(ROOT)
        lesson_record(); output.mkdir(mode=0o700); (output/'public').mkdir()
        for name in set(source['files'])|set(drivers):
            target = output/'source'/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(ROOT/name, target)
        prior.write(output/'PROTOCOL.json', protocol())
        prior.write(output/'FREEZE.json', {'source': source, 'drivers': drivers, 'protocol_sha256': digest(protocol())})
    if args.command in ('run', 'resume'):
        return subprocess.call([sys.executable, '-m', 'experiments.arrangement_transfer047', 'operate', '--output', str(output)], cwd=output/'source')
    execute(output); return 0


if __name__ == '__main__': raise SystemExit(main())
