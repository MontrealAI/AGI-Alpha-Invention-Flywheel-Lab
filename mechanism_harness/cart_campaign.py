"""Registered V4 cart-capable comparisons; synthetic evidence, never demand.

The equal-content control intentionally gets the very same retained constraint
content and constructor. A different wrapper does not constitute discovery.
Every case and unsuccessful attempt remains in the resource denominator.
"""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import platform
import time

import scipy
from commercial.ledger import canonical, digest, strict_json
from . import cart_program as v
from .cart_synthesis import synthesize, retain
from .market_cases import market

CASES = ((392101, 'complementary'), (392102, 'substitute'), (392103, 'competitive'))
ARMS = ('inherited', 'cold', 'full_control', 'separate', 'bundle',
        'equal_content_reuse', 'nonentry')
SOURCE_NAMES = (
    'commercial/ledger.py',
    'mechanism_harness/market_program.py',
    'mechanism_harness/mechanism_synthesis.py',
    'mechanism_harness/cart_program.py',
    'mechanism_harness/cart_synthesis.py',
    'mechanism_harness/market_cases.py',
    'mechanism_harness/cart_campaign.py',
    'campaign/omega-inventor/PROTOCOL_V4.md',
    'campaign/omega-economy-v4/PROTOCOL.md',
    'campaign/omega-economy-v4/SUCCESSOR_PROTOCOL.md',
)
TELEMETRY = frozenset(('construction_cpu_ns', 'solver_cpu_ns',
                       'independent_verification_cpu_ns', 'retention_cpu_ns'))


def source_identity():
    root = Path(__file__).resolve().parents[1]
    result = {}
    for name in SOURCE_NAMES:
        path = root / name
        if not path.is_file() or any(x.is_symlink() for x in (path, *path.parents)):
            raise ValueError('REGULAR_SOURCE_REQUIRED:' + name)
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def logical(value):
    """Timing is observation rather than deterministic replay identity."""
    if isinstance(value, dict):
        return {k: logical(v) for k, v in value.items() if k not in TELEMETRY}
    if isinstance(value, list):
        return [logical(v) for v in value]
    return value


def _private(typ):
    return {key: copy.deepcopy(typ[key]) for key in
            ('values', 'budget_cents', 'outside_utility')}


def _nonentry(m):
    start = time.process_time_ns()
    program = v.null_program(m)
    checked = v.verify(m, program)
    return {
        'schema': 'omega/cart-nonentry-control/v4', 'market_sha256': digest(m),
        'mode': 'nonentry', 'restriction': None, 'memory_sha256': None,
        'status': 'VERIFIED_NONENTRY', 'program': program,
        'verification': checked, 'history': [], 'total_rows_built': 0,
        'total_nonzeros_built': 0, 'deviation_checks': checked['deviation_checks'],
        'construction_cpu_ns': time.process_time_ns() - start,
        'scope': 'No construction or sales; zero opportunity contribution, not an account.',
    }


def execute(cases=None):
    """One finite registered campaign. Custom cases are exposed pilot fixtures."""
    selected_cases = tuple(CASES if cases is None else cases)
    if not selected_cases:
        raise ValueError('NONEMPTY_REGISTERED_CASES_REQUIRED')
    memory = None
    rows = []
    prior_rows = 0
    prior_checks = 0
    for seed, family in selected_cases:
        # Retained content is frozen before the fresh market is constructed.
        memory_before = copy.deepcopy(memory)
        m = market(seed, family)
        inherited = synthesize(m, memory=memory_before)
        runs = {
            'inherited': inherited,
            'cold': synthesize(m),
            'full_control': synthesize(m, mode='full'),
            'separate': synthesize(m, mode='full', restriction='separate'),
            'bundle': synthesize(m, mode='full', restriction='bundle'),
            # Serialization removes any object identity/state advantage. This
            # is ordinary equal-content reuse, intentionally the same method.
            'equal_content_reuse': synthesize(
                m, memory=None if memory_before is None else
                strict_json(canonical(memory_before))),
            'nonentry': _nonentry(m),
        }
        began = time.process_time_ns()
        checked = {}
        for name, run in runs.items():
            checked[name] = None if run['program'] is None else v.verify(m, run['program'])
            if checked[name] is not None and checked[name] != run['verification']:
                raise ValueError('CONSTRUCTOR_VERIFICATION_CHANGED')
        verification_cpu = time.process_time_ns() - began
        valid = all(cert is not None and cert['accepted'] for cert in checked.values())
        row = {
            'market': m, 'runs': runs,
            'status': 'VERIFIED' if valid else 'UNRESOLVED',
            'memory_before': memory_before, 'memory_after': copy.deepcopy(memory),
            'prior_discovery_rows': prior_rows,
            'prior_discovery_deviation_checks': prior_checks,
            'independent_verification_cpu_ns': verification_cpu,
            'independent_verification_checks': sum(
                cert['deviation_checks'] for cert in checked.values() if cert is not None),
            'retention_cpu_ns': 0,
            'all_exact_checks_pass': valid,
        }
        if valid:
            contribution = lambda name: Fraction(checked[name]['expected_contribution_cents'])
            best_standard = max(('separate', 'bundle'),
                                key=lambda name: (contribution(name), name == 'bundle'))
            choices = []
            for typ, rule in zip(m['types'], inherited['program']['rules']):
                choice = v.buyer_choose(m, inherited['program'], _private(typ))
                if (choice['outcome_id'], choice['price_cents']) != (
                        rule['outcome_id'], rule['price_cents']):
                    raise ValueError('DECLARED_INCENTIVE_DOES_NOT_SURVIVE_CART_CHOICE')
                choices.append(choice)
            copycat = []
            for typ in m['types']:
                private = _private(typ)
                choice = v.buyer_choose(m, inherited['program'], private)
                # The rival supplies the whole best affordable cart. Runtime
                # utility is incremental to the previous outside option.
                private['outside_utility'] += max(0, choice['utility_cents'])
                copycat.append(v.buyer_choose(m, inherited['program'], private))
            began = time.process_time_ns()
            memory = retain(m, inherited, memory_before)
            row['retention_cpu_ns'] = time.process_time_ns() - began
            reuse_same = logical(inherited) == logical(runs['equal_content_reuse'])
            row.update({
                'memory_after': copy.deepcopy(memory), 'best_standard': best_standard,
                'actual_supported_buyer_choices': choices, 'copycat_choices': copycat,
                'expected_gain_over_standard_cents': str(contribution('inherited') - contribution(best_standard)),
                'expected_gain_over_full_control_cents': str(contribution('inherited') - contribution('full_control')),
                'expected_gain_over_equal_content_reuse_cents': str(contribution('inherited') - contribution('equal_content_reuse')),
                'equal_content_same_logical_run': reuse_same,
                'equal_optimum_to_full_control': contribution('inherited') == contribution('full_control'),
                'inherited_vs_cold_rows_saved': runs['cold']['total_rows_built'] - inherited['total_rows_built'],
                'successor_ablation': {
                    'is_successor': len(rows) > 0,
                    'removed': 'all transferred constraints; same market, solver and limits',
                    'cold_verified': checked['cold']['accepted'],
                    'cold_expected_contribution_cents': str(contribution('cold')),
                    'inherited_expected_contribution_cents': str(contribution('inherited')),
                    'ordinary_equal_content_verified': checked['equal_content_reuse']['accepted'],
                    'causally_required_for_output': contribution('inherited') > contribution('cold'),
                    'prior_acquisition_rows': prior_rows,
                    'acquisition_plus_current_use_rows': prior_rows + inherited['total_rows_built'],
                    'cold_current_use_rows': runs['cold']['total_rows_built'],
                    'equal_content_acquisition_plus_current_use_rows': prior_rows + runs['equal_content_reuse']['total_rows_built'],
                    'equal_content_acquisition_policy': 'same substantive predecessor acquisition charged to both retained-content arms',
                    'interpretation': 'Rows measure construction work only; they are not complete costs or money.',
                },
            })
        rows.append(row)
        # Include failed attempts as well as successful construction.
        prior_rows += inherited['total_rows_built']
        prior_checks += inherited['deviation_checks']
    valid_rows = [row for row in rows if row['status'] == 'VERIFIED']
    totals = {name: sum(row['runs'][name]['total_rows_built'] for row in rows) for name in ARMS}
    checks = {name: sum(row['runs'][name]['deviation_checks'] for row in rows) for name in ARMS}
    cpus = {name: sum(row['runs'][name]['construction_cpu_ns'] for row in rows) for name in ARMS}
    return {
        'schema': 'omega/private-mechanism-campaign/v4', 'cases': rows,
        'registered_cases': len(selected_cases), 'registered_case_ids': [list(x) for x in selected_cases],
        'completed_cases': len(valid_rows), 'registered_arms': list(ARMS),
        'total_rows_built': totals, 'total_deviation_checks': checks,
        'construction_cpu_ns': cpus,
        'independent_verification_cpu_ns': sum(row['independent_verification_cpu_ns'] for row in rows),
        'independent_verification_checks': sum(row['independent_verification_checks'] for row in rows),
        'retention_cpu_ns': sum(row['retention_cpu_ns'] for row in rows),
        'all_synthesized_programs_verified': len(valid_rows) == len(rows),
        'registered_template_advantage_cases': sum(Fraction(row['expected_gain_over_standard_cents']) > 0 for row in valid_rows),
        'beats_strong_full_solver': any(Fraction(row['expected_gain_over_full_control_cents']) > 0 for row in valid_rows),
        'beats_equal_content_reuse': any(Fraction(row['expected_gain_over_equal_content_reuse_cents']) > 0 for row in valid_rows),
        'constraint_transfer_rows_saved': totals['cold'] - totals['inherited'],
        'cost_boundary': {
            'construction_and_failed_attempts': 'all solver histories included, including unresolved cases',
            'retention_and_campaign_checks': 'separately measured process CPU and exact check counts',
            'ordinary_reuse': 'identical substantive memory and constructor; no exclusive-content advantage',
            'operating_costs': 'native accounts reported separately; these contribution values exclude fixed lifecycle costs',
            'actual_model_developer_host_cost_usd': None,
            'complete_lifecycle_superiority_established': False,
        },
        'actual_revenue_usd': 0,
        'scope': 'Finite synthetic composed-purchase mechanism construction and verified constraint transfer. No empirical demand, complete-lifecycle superiority, or general invention claim.',
        'runtime': {'python': platform.python_version(), 'scipy': scipy.__version__},
    }


def audit(report):
    if report.get('source') != source_identity():
        raise ValueError('SOURCE_CHANGED')
    if (report.get('actual_revenue_usd') != 0 or
            report.get('registered_cases') != len(CASES) or
            report.get('registered_case_ids') != [list(x) for x in CASES] or
            report.get('registered_arms') != list(ARMS) or
            len(report.get('cases', ())) != len(CASES)):
        raise ValueError('UNSUPPORTED_CLAIM_OR_DENOMINATOR')
    memory = None
    for row, (seed, family) in zip(report['cases'], CASES):
        m = market(seed, family)
        if m != row['market'] or row['memory_before'] != memory or set(row['runs']) != set(ARMS):
            raise ValueError('MARKET_INHERITANCE_OR_ARM_CHANGED')
        for run in row['runs'].values():
            if run['program'] is None:
                continue
            checked = v.verify(m, run['program'])
            if checked != run['verification']:
                raise ValueError('UNVERIFIED_MECHANISM')
        if row['status'] == 'VERIFIED':
            memory = retain(m, row['runs']['inherited'], memory)
        if memory != row['memory_after']:
            raise ValueError('UNSUPPORTED_LEARNING')
    # Replay also checks all cost totals, failure denominators, control results
    # and source-bound inputs. Timing is measured observation, not reproduced.
    actual = execute()
    if logical({k: value for k, value in report.items() if k != 'source'}) != logical(actual):
        raise ValueError('CAMPAIGN_REPLAY_CHANGED')
    return {'accepted': True, 'report_logical_sha256': digest(logical(report)),
            'scope': 'Exact independent cart checks plus source-matched numerical replay; no external certification.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit', action='store_true')
    args = parser.parse_args(argv)
    if any(x.is_symlink() for x in (args.output, *args.output.absolute().parents)):
        raise ValueError('NO_SYMLINKS')
    if args.audit:
        print(json.dumps(audit(strict_json(args.output.read_bytes())), indent=2))
        return
    if args.output.exists():
        raise FileExistsError('PRESERVE_EXISTING_EVIDENCE')
    before = source_identity()
    report = execute()
    if before != source_identity():
        raise ValueError('SOURCE_CHANGED_DURING_RUN')
    report['source'] = before
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as file:
        file.write(canonical(report) + b'\n')
    print(json.dumps({k: value for k, value in report.items() if k not in ('cases', 'source')}, indent=2))


if __name__ == '__main__':
    main()
