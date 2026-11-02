import argparse
import hashlib
import importlib.util
import json
import platform
import sys
from pathlib import Path

import numpy as np
import scipy


HERE = Path(__file__).resolve().parent
RESULT_SHA256 = '4c36506559fb88cdcfde81f76a12daf0af3ed369a67b0306499b0ecea2d39a8c'
FREEZE_SHA256 = '05bb81b18d96b1e4a6ab1110a26974dfe5cef2002bf8ac33e6141c160ceb408b'
SOURCE_NAMES = ('PREREGISTRATION.md', 'STAGE_B.md', 'instrument.py', 'verifier.py', 'run_stage_b.py')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_bound_json(path, expected, failure):
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError(failure)
    return json.loads(data)


def source_hashes():
    return {name: digest((HERE / name).read_bytes()) for name in SOURCE_NAMES}


def common_midpoint(hypothesis_currents):
    values = np.stack(hypothesis_currents)
    if values.ndim != 3 or values.shape[0] != 2 or not np.isfinite(values).all():
        raise ValueError('REQUIRE_TWO_ALIGNED_FINITE_HYPOTHESES')
    return np.mean(values, axis=0)


def evaluate(result_path, freeze_path):
    result = read_bound_json(result_path, RESULT_SHA256, 'ORIGINAL_RESULT_DIGEST_MISMATCH')
    freeze = read_bound_json(freeze_path, FREEZE_SHA256, 'ORIGINAL_FREEZE_DIGEST_MISMATCH')
    sources = source_hashes()
    if result['freeze_sha256'] != FREEZE_SHA256 or result['source_hashes'] != freeze['sources'] or sources != freeze['sources']:
        raise ValueError('FROZEN_SOURCE_OR_RECEIPT_MISMATCH')
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('frozen_midpoint_verifier', HERE / 'verifier.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    if verifier.sha(verifier.PAIR) != freeze['pair_spec_sha256'] or verifier.PAIR != freeze['pair_spec']:
        raise ValueError('FROZEN_PAIR_MISMATCH')
    pair = verifier.PAIR
    capacities = [[q] + [pair['other_cell_capacity_ah']] * 3 for q in pair['capacity_ah']]
    references = [verifier.reference_trace(q, total_a=pair['pack_total_a'], duration_s=pair['pack_duration_s'], step_s=0.5) for q in capacities]
    reference_hashes = [verifier.sha({key: ref[key].tolist() for key in ('time_s', 'current_a', 'terminal_v')}) for ref in references]
    currents = [ref['current_a'] for ref in references]
    prediction = common_midpoint(currents)
    symmetric = np.array_equal(prediction, common_midpoint(currents[::-1]))
    worlds = []
    for capacity, truth in zip(capacities, currents):
        metrics = verifier.trace_metrics(prediction, truth, total_a=pair['pack_total_a'])
        metrics['nrmse_contract_pass_per_branch'] = [value <= 0.1 for value in metrics['nrmse_per_branch']]
        metrics['peak_contract_pass_per_branch'] = [value <= 0.1 for value in metrics['peak_relative_error_per_branch']]
        metrics['all_contracts_pass'] = all(metrics['nrmse_contract_pass_per_branch']) and all(metrics['peak_contract_pass_per_branch'])
        worlds.append({'capacity_ah': capacity, 'metrics': metrics})
    source_unchanged = source_hashes() == sources
    inputs_unchanged = digest(result_path.read_bytes()) == RESULT_SHA256 and digest(freeze_path.read_bytes()) == FREEZE_SHA256
    hashes_match = reference_hashes == result['numerical_verification']['reference_trace_hashes']
    contracts_pass = all(world['metrics']['all_contracts_pass'] for world in worlds)
    accepted = bool(source_unchanged and inputs_unchanged and hashes_match and symmetric and contracts_pass)
    largest_rmse = max(max(world['metrics']['rmse_a_per_branch']) for world in worlds)
    peaks = [np.max(np.abs(current), axis=0) for current in currents]
    report = {
        'schema': 'agi-alpha/cell-pack-post-result-diagnostic/v2',
        'evidence_class': 'EXPLORATORY_POST_RESULT_SYNTHETIC_NUMERICAL_DIAGNOSTIC',
        'method_selected_after_stage_b_result': True,
        'prospective_confirmation': False,
        'scope': 'The exact two frozen synthetic worlds and registered 2100-second interval. The midpoint policy was selected after Stage B; parameters, thresholds and original results are unchanged.',
        'original_result_sha256': RESULT_SHA256,
        'freeze_sha256': FREEZE_SHA256,
        'source_hashes': sources,
        'diagnostic_source_sha256': digest(Path(__file__).read_bytes()),
        'frozen_source_modified': not source_unchanged,
        'input_receipts_unchanged': inputs_unchanged,
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'recomputed_reference_trace_hashes': reference_hashes,
        'recorded_reference_trace_hashes': result['numerical_verification']['reference_trace_hashes'],
        'reference_hashes_match': hashes_match,
        'common_policy': 'Predict the arithmetic mean of both frozen hypothesis current trajectories. Actual-world identity is never an input to common_midpoint; truth labels are used only for evaluation.',
        'common_policy_invariant_to_hypothesis_order': bool(symmetric),
        'common_prediction_sha256': verifier.sha({'time_s': references[0]['time_s'].tolist(), 'current_a': prediction.tolist()}),
        'thresholds': {'total_current_a': pair['pack_total_a'], 'normalization_current_per_branch_a': pair['pack_total_a'] / 4, 'nrmse_limit': 0.1, 'peak_relative_error_limit': 0.1, 'horizon_s': pair['pack_duration_s'], 'step_s': 0.5, 'points': len(prediction)},
        'worlds': worlds,
        'both_world_contracts_pass': contracts_pass,
        'diagnostic_accepted': accepted,
        'max_nrmse': max(max(world['metrics']['nrmse_per_branch']) for world in worlds),
        'min_rmse_margin_a': 0.1 * pair['pack_total_a'] / 4 - largest_rmse,
        'max_peak_relative_error': max(max(world['metrics']['peak_relative_error_per_branch']) for world in worlds),
        'midpoint_peak_a_per_branch': np.max(np.abs(prediction), axis=0).tolist(),
        'peak_acceptance_interval_intersections_a_per_branch': [[float(max(0.9 * a, 0.9 * b)), float(min(1.1 * a, 1.1 * b))] for a, b in zip(*peaks)],
        'midpoint_current_conservation_max_residual_a': float(np.max(np.abs(np.sum(prediction, axis=1) - pair['pack_total_a']))),
        'worlds_last_time_branch_difference_a': np.abs(currents[0][-1] - currents[1][-1]).tolist(),
        'midpoint_last_time_abs_error_a_per_branch': (np.abs(currents[0][-1] - currents[1][-1]) / 2).tolist(),
        'original_stage_b_claims': result['claims'],
        'additional_probe_needed_within_exact_two_world_contract': False if accepted else None,
        'cost_correction': {'status': 'F=20 h is an assumed nominal-capacity scenario, not a universal measured lower bound.', 'saving_fraction': '6*A/(F+10*A)', 'half_saving_iff': 'F<=2*A', 'A_hours_assumption': 1.04, 'F_max_hours_for_half_saving_given_A': 2.08, 'F_hours_nominal_capacity_scenario_assumption': 20.0, 'saving_fraction_in_that_conditional_scenario': 39 / 190, 'actual_F_unmeasured': True},
        'physical_measurement_count': 0,
        'physical_models_validated': False,
        'interpretation': 'A common prediction meets the stated contract despite unresolved exact model identity within this two-model set. The margin below the 0.2 A RMSE limit is only about 0.829 mA. Additional hypotheses, physical model error, a changed horizon or another objective can invalidate the conclusion. Prior construction and qualification are not free.'
    }
    return report, np.column_stack([references[0]['time_s'], *currents, prediction])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, default=HERE / 'FROZEN_STAGE_B_SERIALIZATION_FIX.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise FileExistsError('REQUIRE_NEW_OUTPUT_DIRECTORY')
    report, traces = evaluate(args.result, args.freeze)
    args.output.mkdir(parents=True, exist_ok=False)
    trace_path = args.output / 'midpoint_reference_traces.csv'
    with trace_path.open('x', encoding='utf-8', newline='') as stream:
        np.savetxt(stream, traces, delimiter=',', header='time_s,a_cell0,a_cell1,a_cell2,a_cell3,b_cell0,b_cell1,b_cell2,b_cell3,midpoint_cell0,midpoint_cell1,midpoint_cell2,midpoint_cell3', comments='')
    report['trace_csv_file'] = trace_path.name
    report['trace_csv_sha256'] = digest(trace_path.read_bytes())
    data = (json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    receipt = args.output / 'DIAGNOSTIC.json'
    with receipt.open('xb') as stream:
        stream.write(data)
    print(json.dumps({'diagnostic_sha256': digest(data), 'trace_csv_sha256': report['trace_csv_sha256'], 'diagnostic_accepted': report['diagnostic_accepted'], 'reference_hashes_match': report['reference_hashes_match'], 'max_nrmse': report['max_nrmse'], 'max_peak_relative_error': report['max_peak_relative_error']}, sort_keys=True))
    return 0 if report['diagnostic_accepted'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
