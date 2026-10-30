"""Actual source-checked memory retrieval and matched successor construction controls."""
from fractions import Fraction as F
from pathlib import Path
import argparse, hashlib, json, resource, time
from flywheel import retention
from inventions.consequential009.circuit import parse_netlist, generate_actions, compile_plan, exhaustive_plan
from inventions.consequential009.experiment import hypotheses

ROOT = Path(__file__).resolve().parents[1]

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream: json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')

def run(primary, receipt, expected_receipt, output):
    started, cpu = time.monotonic(), time.process_time()
    primary, receipt, output = Path(primary), Path(receipt), Path(output)
    accepted = read(receipt)
    if sha(receipt) != expected_receipt or accepted.get('accepted') is not True:
        raise ValueError('SOURCE_BOUND_INDEPENDENT_ACCEPTANCE_REQUIRED')
    artifact_path = primary / 'REPORT.json'
    if accepted['artifact_sha256'] != sha(artifact_path): raise ValueError('ACCEPTED_REPORT_IDENTITY')
    if accepted['verifier_sha256'] != sha(ROOT / 'verification/consequential009/cohort_check.py'):
        raise ValueError('VERIFIER_SOURCE_IDENTITY')
    circuit_path = ROOT / 'inventions/consequential009/circuit.py'
    if accepted['candidate_sha256'] != sha(circuit_path): raise ValueError('INSTRUMENT_SOURCE_IDENTITY')
    protocol = read(primary / 'PROTOCOL.json')
    if accepted['protocol_sha256'] != sha(primary / 'PROTOCOL.json'): raise ValueError('PROTOCOL_IDENTITY')
    program = read(primary / 'primary-GENERATED.json')['generated_extension']
    if program is None: raise ValueError('NO_VERIFIED_GENERATIVE_EXTENSION')
    output.mkdir(parents=True, exist_ok=False)
    record = {
        'instrument': {'path': 'inventions/consequential009/circuit.py', 'sha256': sha(circuit_path)},
        'applicability': {'schema_version': 1,
            'conditions': {'model_family': 'passive-RCL-one-port', 'observable': 'coherent-normalized-admittance'},
            'assumptions': program['required_model'],
            'uncertainty': 'Authored finite model and sensor envelope only; calibration not measured.',
            'failures': [{'conditions': {'sensor_gain': 'unbounded'}, 'reason': 'Impedance-scale/current-gain symmetry; current measurement alone cannot identify scale.'}]},
        'generative_operator': {'language': 'circuit_measurement_v1', 'program': program},
        'provenance': {'accepted_artifact_sha256': sha(artifact_path), 'protocol_sha256': accepted['protocol_sha256'],
            'insight_origin': 'Developer supplied physical constitutive laws and conjugate-observable rule. Runtime derives network expressions and verifies witness; no autonomous broad-discovery priority.'},
        'verification': {'status': 'verified-in-scope', 'receipt_sha256': expected_receipt},
        'costs': {'observed_predecessor_cpu_seconds': read(artifact_path)['cpu_seconds'], 'complete_acquisition_money': None,
            'recovery_horizon': 'No justified amortization volume; all predecessor and inherited costs remain in lifecycle unknown K.'},
        'exposure': ['primary and successor model definitions exposed DEVELOPMENT before this memory experiment; no untouched confirmation'],
        'supersedes': []}
    store_path = output / 'memory'
    identity = retention.store(store_path, record)
    target = {'schema_version': 1, 'conditions': {'model_family': 'passive-RCL-one-port',
              'observable': 'coherent-normalized-admittance', 'sensor_gain': 'bounded'}}
    retrieval = retention.retrieve(store_path, target, ROOT)
    if len(retrieval['records']) != 1: raise ValueError('ACTUAL_MEMORY_RETRIEVAL_FAILED')
    inherited = retrieval['records'][0]['record']['generative_operator']['program']
    write(output / 'RETRIEVAL.json', retrieval)
    negative = retention.retrieve(store_path, {'schema_version': 1, 'conditions': {**target['conditions'], 'sensor_gain': 'unbounded'}}, ROOT)
    if negative['records'] or not negative['failures']: raise ValueError('NEGATIVE_KNOWLEDGE_DID_NOT_REFUSE')
    write(output / 'NEGATIVE_RETRIEVAL.json', negative)
    successor = parse_netlist((ROOT / 'research/consequential009/analog/MonteCarlo.sp').read_text())
    hs = hypotheses(successor, protocol['successor_tolerance_elements'])
    p = {**protocol, 'omega_rad_s': protocol['successor_omega_rad_s']}
    arms = []
    for policy in ['old-greedy', 'new-reverse-delete']:
        for toolbox in ['old-voltage', 'new-current']:
            for memory in ['retained', 'equal-content-ordinary-reuse', 'reset']:
                begin, own = time.monotonic(), time.process_time()
                supplied = inherited if memory != 'reset' else None
                generated = generate_actions(successor, {**p, 'allow_flux_extension': toolbox == 'new-current'}, supplied)
                result = compile_plan(successor, hs, generated['actions'], protocol['policies'],
                                      allow_extension=toolbox == 'new-current', prune=policy == 'new-reverse-delete')
                label = policy + '__' + toolbox + '__' + memory
                write(output / 'plans' / (label + '.json'), result)
                arms.append({'policy': policy, 'toolbox': toolbox, 'memory': memory,
                    'admitted_hypotheses': len(hs), 'admitted_pairs': result['admitted_pairs'],
                    'separated_pairs': result['separated_pairs'], 'accepted': result['complete_finite_model_acceptance'],
                    'actions': len(result['selected_actions']), 'relative_acquisition_units': result['selected_relative_acquisition_units'],
                    'generated_inherited_flag': bool(generated['generated_extension'] and generated['generated_extension']['inherited']),
                    'cpu_seconds': time.process_time() - own, 'wall_seconds': time.monotonic() - begin})
    gen = generate_actions(successor, p)
    best = exhaustive_plan(successor, hs, gen['actions'], protocol['policies'])
    write(output / 'STRONG_ORDINARY.json', best)
    groups = {}
    for arm in arms: groups.setdefault((arm['policy'], arm['toolbox']), []).append(arm)
    tied = all(len({(a['accepted'], a['separated_pairs'], a['actions'], a['relative_acquisition_units']) for a in group}) == 1 for group in groups.values())
    if not tied: raise AssertionError('UNEXPECTED_MEMORY_DIFFERENCE_REQUIRES_ADJUDICATION')
    old = next(a for a in arms if a['policy'] == 'old-greedy' and a['toolbox'] == 'new-current' and a['memory'] == 'retained')
    new = next(a for a in arms if a['policy'] == 'new-reverse-delete' and a['toolbox'] == 'new-current' and a['memory'] == 'retained')
    policy_effect = {'old_relative_acquisition_units': old['relative_acquisition_units'],
        'new_relative_acquisition_units': new['relative_acquisition_units'],
        'coverage_preserved': old['separated_pairs'] == new['separated_pairs'],
        'cost_reduced': new['relative_acquisition_units'] < old['relative_acquisition_units'],
        'methods': 'known reverse deletion and finite single-action replacement; no novel search algorithm claim'}
    result = {'schema': 'agi-alpha/consequential009-retained-successor/v1',
        'record_sha256': identity, 'accepted_predecessor_artifact_sha256': sha(artifact_path),
        'independent_receipt_sha256': expected_receipt, 'instrument_sha256': sha(circuit_path),
        'memory_paths_executed': ['flywheel.retention.store', 'flywheel.retention.retrieve', 'generate_actions(inherited_program)', 'compile_plan'],
        'actual_negative_retrieval_refused': bool(negative['failures']),
        'successor_source_sha256': successor.source_sha256, 'arms': arms, 'strong_ordinary': best,
        'equal_content_and_reset_tie': tied, 'policy_effect': policy_effect,
        'decision': {'technical_transfer': 'EXECUTED_ON_DIFFERENT_RCL_TOPOLOGY_IN_EXPOSED_FINITE_MODEL',
            'new_toolbox_information_benefit': 'INPUT_CURRENT_BREAKS_VOLTAGE_ONLY_SCALE_AMBIGUITY_UNDER_AUTHORED_CALIBRATION',
            'new_policy_effect': policy_effect,
            'retained_discovery_advantage': 'NOT_ESTABLISHED_EQUAL_CONTENT_AND_RESET_TIE',
            'net_economic_advantage': 'UNKNOWN; relative acquisition units are not dollars; complete inference/construction/lifecycle cost unbounded',
            'earned_funding': 'NONE; this technical experiment uses declared original campaign resources, not simulated earnings',
            'future_scope': 'Uncalibrated-gain work is a real model constraint still unresolved; known calibrated reference/bridge methods are competent comparators.'},
        'resources': {'cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - started,
            'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'complete_monetary_cost': None},
        'claim_limits': ['Twelve arms are matched engineering controls, not independent customers or protected statistical confirmation.',
            'Different topology/model cohort is nontrivial but was already exposed in development; no fresh confirmation claim.',
            'Retention is source checked and scope checked data interpreted by a fixed executable, never arbitrary retrieved code.',
            'Acquisition, abstraction, retrieval, adaptation and checking costs remain charged; CPU differences are not discovery superiority.',
            'No live commerce, physical measurement, scientific novelty or earned-funded construction is inferred.']}
    write(output / 'RESULT.json', result)
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--primary-directory', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--expected-receipt-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.primary_directory, args.receipt, args.expected_receipt_sha256, args.output)
    print(json.dumps({'arms': len(result['arms']), 'tie': result['equal_content_and_reset_tie'], 'decision': result['decision']}))
