"""Execute the frozen finite experiment and preserve unsuccessful cases.

The public source commit must precede the first call. This runner has no network,
account, billing, acquisition-device, outreach or transaction operation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import resource
import sys
import time


ROOT = Path(__file__).resolve().parent
IDENTITY = 'paired-acquisition-20261102-c2355228'
MANIFEST = ROOT / 'SOURCE_MANIFEST.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    def invalid(value):
        raise ValueError('nonfinite JSON is not allowed: ' + value)
    return json.loads(path.read_text(), parse_constant=invalid)


def save(path, value):
    payload = json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n'
    with path.open('x', encoding='utf-8') as handle:
        handle.write(payload)
    return digest(path)


def verify_sources(expected):
    if not re.fullmatch('[0-9a-f]{64}', expected) or digest(MANIFEST) != expected:
        raise ValueError('external source-manifest digest does not match')
    manifest = read_json(MANIFEST)
    if manifest.get('schema') != 'paired-acquisition/source-freeze/v1' or manifest.get('experiment_id') != IDENTITY:
        raise ValueError('wrong registered experiment identity')
    files = manifest.get('files', {})
    required = {'__init__.py', 'run.py', 'instrument.py', 'verifier.py',
                'economic_frontier.py', 'test_economic_frontier.py',
                'PREREGISTRATION.md', 'VERIFIER_CONTRACT.md', 'ECONOMIC_CONTRACT.md',
                'ECONOMIC_PLAN.json', 'PERMISSIONS.json', 'requirements.txt'}
    if not required <= set(files):
        raise ValueError('incomplete source manifest')
    for name, expected_file in files.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid manifest path')
        path = ROOT / relative
        if path.is_symlink() or not path.is_file() or digest(path) != expected_file:
            raise ValueError('frozen source differs: ' + name)
    actual_python = {path.relative_to(ROOT).as_posix() for path in ROOT.rglob('*.py')
                     if '__pycache__' not in path.parts and 'evidence' not in path.parts}
    if actual_python != {name for name in files if name.endswith('.py')}:
        raise ValueError('unregistered executable Python file in experiment')
    return manifest


def economic_inputs(science, science_sha):
    from . import economic_frontier as economics
    plan = read_json(ROOT / 'ECONOMIC_PLAN.json')
    if plan['schema'] != 'paired-acquisition/registered-economic-plan/v1':
        raise ValueError('unregistered economic plan')
    full = science.get('numerical_contract_accepted') is True
    bulk, spatial = science.get('bulk', []), science.get('spatial', [])
    blank = (len(bulk) == 80 and len(spatial) == 12
             and all(row.get('blank_all_components_covered') is True for row in bulk + spatial)
             and all(row.get('blank_uncertain_cells') == 0
                     if row.get('family') == 'separated_threshold'
                     else isinstance(row.get('blank_uncertain_cells'), int)
                     and row['blank_uncertain_cells'] >= 1 for row in spatial)
             and all(isinstance(row.get('blank_area_interval_cm2'), list)
                     and len(row['blank_area_interval_cm2']) == 2
                     and row['blank_area_interval_cm2'][0] - 2e-9
                     <= row['true_contaminated_area_cm2']
                     <= row['blank_area_interval_cm2'][1] + 2e-9 for row in spatial))
    causal = any(row.get('id') == 'fixed_unequal_gain_scope_expansion'
                 and row.get('passed') is True for row in science.get('controls', {}).get('checks', []))
    qualities = {'single_read': 'refused' if causal else 'unresolved',
                 'independent_calibration': 'accepted' if blank else 'unresolved',
                 'paired_swap': 'accepted' if full else 'unresolved',
                 'ordinary_paired_swap': 'accepted' if full else 'unresolved'}
    inputs = []
    for cash in plan['available_cash_hypotheses_usd']:
        for cap in plan['specimen_exposure_caps']:
            choices = []
            for method in economics.METHODS:
                choice = {'method': method, 'quality': qualities[method],
                          'quality_receipt_sha256': science_sha if qualities[method] != 'unresolved' else None,
                          'resources': plan['resources_per_ray'][method],
                          'rights_and_capacity': plan['rights_and_capacity'],
                          'complete_episode_cost_scope': plan['complete_episode_cost_scope'],
                          'other_cash_cost_usd': plan['other_cash_cost_usd'],
                          'other_opportunity_cost_usd': plan['other_opportunity_cost_usd']}
                choices.append(choice)
            inputs.append({
                'schema': economics.SCHEMA,
                'case_id': f'cash-{cash}-specimen-cap-{cap}',
                'scientific_contract_sha256': digest(ROOT / 'PREREGISTRATION.md'),
                'permission_contract_sha256': digest(ROOT / 'PERMISSIONS.json'),
                'quality_scope': 'Conditional synthetic interval coverage and registered K2 decision completion/abstention only; no physical delivery qualification.',
                'budgets': {**plan['fixed_budgets'], 'specimen_exposures': cap},
                'cash_usd_per_unit': {key: None for key in economics.RESOURCES},
                'opportunity_usd_per_unit': {key: None for key in economics.RESOURCES},
                'choices': choices,
                'available_cash_usd': cash,
                'protected_cash_usd': plan['protected_cash_usd'],
                'prior_campaign_cost_usd': plan['prior_campaign_cost_usd'],
                'offer_hypothesis': plan['offer_hypothesis'],
                'price_basis': plan['price_basis'],
                'funding_received': False,
                'input_scope': plan['scope'],
            })
    return inputs


def execute(output, expected, source_commit, label):
    if not output.is_absolute():
        raise ValueError('absolute fresh output path required')
    if not re.fullmatch('[0-9a-f]{40}', source_commit):
        raise ValueError('exact public source commit required')
    output.mkdir(parents=True, exist_ok=False)
    started_utc = datetime.now(timezone.utc).isoformat()
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    hashes, failure, accepted = {}, None, False
    source_before, source_after, scientific_started = False, False, False
    try:
        manifest = verify_sources(expected)
        source_before = True
        # Import scientific code only after validating its public frozen bytes.
        import numpy as np
        from . import economic_frontier, instrument, verifier
        scientific_started = True
        science = verifier.run_verification(
            instrument.decode_pair, instrument.decode_spatial,
            fresh_pair_decoder=instrument.fresh_pair,
            fresh_spatial_decoder=instrument.fresh_spatial)
        hashes['SCIENCE.json'] = save(output / 'SCIENCE.json', science)
        inputs = economic_inputs(science, hashes['SCIENCE.json'])
        hashes['ECONOMIC_INPUTS.json'] = save(output / 'ECONOMIC_INPUTS.json', inputs)
        projections = [economic_frontier.compare(document) for document in inputs]
        hashes['ECONOMICS.json'] = save(output / 'ECONOMICS.json', projections)
        retained = {'schema': 'paired-acquisition/retained-interface/v1',
                    'source_manifest_sha256': expected,
                    'scientific_receipt_sha256': hashes['SCIENCE.json'],
                    'coefficient_matrix_cm2_g': instrument.RETAINED[0].tolist(),
                    'spectral_decoder_g_cm2': instrument.RETAINED[1].tolist(),
                    'spectral_residual_map': instrument.RETAINED[2].tolist(),
                    'applicability': 'Qualified positive corrected reads; true blank; unchanged ray, basis and specimen; bounded relative path-gain drift and corrected-read error.',
                    'invalidation': 'Coherent drift, coefficient or reference errors may remain undetected; physical bounds and exchange semantics are unqualified.',
                    'new_downstream_decision': 'Copper density >0.10 g/cm^3 and certified above-threshold area on fresh fields.'}
        hashes['RETAINED_INTERFACE.json'] = save(output / 'RETAINED_INTERFACE.json', retained)
        verify_sources(expected)
        source_after = True
        accepted = science.get('numerical_contract_accepted') is True
        summary = {
            'schema': 'paired-acquisition/finite-stage-summary/v1',
            'experiment_id': IDENTITY, 'source_commit': source_commit,
            'source_manifest_sha256': expected, 'execution_label': label,
            'registered_case_counts': science['registered_counts'],
            'bulk_passed': sum(row['passed'] for row in science['bulk']),
            'spatial_passed': sum(row['passed'] for row in science['spatial']),
            'control_checks_passed': sum(row['passed'] for row in science['controls']['checks']),
            'limitation_witnesses_observed': sum(row['expected_undetected_wrong_answer_observed'] for row in science['controls']['limitations']),
            'numerical_contract_accepted': accepted,
            'physical_qualification': False, 'same_observation_ordinary_advantage': False,
            'economic_projection_count': len(projections),
            'economic_states': {r['case_id']: {k: v['offer_state'] for k, v in r['choices'].items()} for r in projections},
            'capital_selected_for_execution_usd': None,
            'native_account_actions': 0, 'actual_revenue_usd': 0,
            'completed_trailing_365_day_profit_usd': None,
            'one_billion_profit_milestone_achieved': False,
            'three_billion_profit_milestone_achieved': False,
            'cost_scope': 'Finite numerical run measured separately; model/host invoice, upstream labor, physical acquisition and commercial complete costs unknown.',
            'frozen_files_checked_before_and_after': len(manifest['files']),
            'evidence_sha256': dict(hashes),
            'learning': 'Paired exchange can cancel fixed unequal path gains under the explicit contract; ordinary same-information fitting supplies the same result. Keep explicit abstention and coherent-mismatch limitations. Physical and complete commercial evidence are required before deployment.',
        }
        hashes['SUMMARY.json'] = save(output / 'SUMMARY.json', summary)
    except Exception as error:
        source_after_error = None
        try:
            verify_sources(expected)
            source_after = True
        except Exception as source_error:
            source_after = False
            source_after_error = f'{type(source_error).__name__}: {source_error}'
        failure = {'schema': 'paired-acquisition/execution-failure/v1',
                   'experiment_id': IDENTITY, 'source_commit': source_commit,
                   'source_manifest_sha256': expected, 'execution_label': label,
                   'error_type': type(error).__name__, 'error': str(error),
                   'source_integrity_after_attempt': source_after,
                   'source_integrity_error': source_after_error,
                   'scientific_execution_started': scientific_started,
                   'partial_evidence_sha256': dict(hashes),
                   'numerical_contract_accepted': False,
                   'denominators_remain_registered': {'bulk': 80, 'spatial': 12, 'controls': 8, 'limitations': 4}}
        hashes['FAILURE.json'] = save(output / 'FAILURE.json', failure)
    runtime = {
        'schema': 'paired-acquisition/execution-resources/v1',
        'source_commit': source_commit, 'source_manifest_sha256': expected,
        'execution_label': label, 'started_utc': started_utc,
        'finished_utc': datetime.now(timezone.utc).isoformat(),
        'wall_seconds': time.perf_counter() - started_wall,
        'process_cpu_seconds': time.process_time() - started_cpu,
        'peak_process_rss_kib_linux': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if sys.platform.startswith('linux') else None,
        'python': platform.python_version(), 'platform': sys.platform,
        'machine': platform.machine(),
        'numpy': sys.modules['numpy'].__version__ if 'numpy' in sys.modules else None,
        'actual_model_and_host_invoice_usd': None,
        'upstream_human_and_ai_search_cost_usd': None,
        'physical_acquisition_cost_usd': None,
        'scope': 'This process only; excludes prior reasoning, source acquisition, review and CI queueing. Included execution does not imply zero economic cost.',
        'source_integrity_before': source_before,
        'source_integrity_after': source_after,
        'scientific_execution_started': scientific_started,
        'evidence_sha256': hashes,
        'numerical_contract_accepted': accepted and failure is None,
    }
    save(output / 'EXECUTION.json', runtime)
    print(json.dumps({'output': str(output), 'accepted': runtime['numerical_contract_accepted'],
                      'wall_seconds': runtime['wall_seconds'], 'failure': failure}, sort_keys=True))
    return 0 if runtime['numerical_contract_accepted'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-freeze-sha256', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--execution-label', required=True)
    args = parser.parse_args()
    raise SystemExit(execute(args.output, args.expected_freeze_sha256,
                             args.source_commit, args.execution_label))


if __name__ == '__main__':
    main()
