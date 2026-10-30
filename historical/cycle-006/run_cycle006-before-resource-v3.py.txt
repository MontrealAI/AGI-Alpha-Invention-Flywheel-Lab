"""Bounded offline reproduction of the source-bound cycle-006 connected experiment.

The protected experiment was executed once before its outcomes were exposed.
This command reconstructs mechanisms and replays that now-exposed experiment;
it does not manufacture another confirmation or native Omega generation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
FREEZE = 'campaign/cycle-006/REPRODUCTION_FREEZE.json'
CANDIDATE = 'campaign/cycle-006/CANDIDATE_FREEZE.json'
NOMINATIONS = 'evidence/cycle-006/prediction-nominations-001-run/artifacts'
WESSELS = 'evidence/cycle-006/verifier-wessels-preparation-run/artifacts/public'
DEVELOPMENT = 'evidence/cycle-006/norman-development-constructor-001c-run/artifacts'
REPAIR = 'evidence/cycle-006/norman-repair-constructor-002b-mapped-run/artifacts'
ORIGINAL_JUDGMENT = 'evidence/cycle-006/verifier-symmetry-original/ADJUDICATION.json'
REPAIR_JUDGMENT = 'evidence/cycle-006/verifier-symmetry-mapped-003-run/artifacts/ADJUDICATION.json'
CONTRACT = 'verification/cycle006_functional_contract.json'
TRUTHS = 'evidence/cycle-006/exposed-confirmation'
REQUIRED = {'run_cycle006.py', 'experiments/resource006.py', 'flywheel/baseline005.py',
            'flywheel/archive_v2.py', 'flywheel/sandbox.py', 'flywheel/retention.py',
            'mechanisms/policy006.py', 'mechanisms/mapping.py',
            'experiments/norman006/model.py', 'experiments/norman006/inheritance.py',
            'experiments/norman006/policy_comparison.py', 'experiments/norman006/run_policy_comparison.py',
            'experiments/norman006/controls.py', 'experiments/commerce006.py',
            'verification/cycle006_symmetry_adjudication.py', 'verification/cycle006_confirm.py',
            'verification/cycle006_norman_protocol.json', 'verification/cycle006_wessels_protocol.json',
            'verification/cycle006_functional_obligations.json', CONTRACT, CANDIDATE,
            'historical/cycle-005/mechanism-completion-release.zip',
            'historical/cycle-006/verifier-symmetry-original.py.txt',
            'experiments/interaction006_data/development.npz',
            'experiments/interaction006_data/heldout_features.npz', 'experiments/interaction006_data/SPLIT.json',
            DEVELOPMENT + '/ARTIFACT.json', DEVELOPMENT + '/SEARCH.json', DEVELOPMENT + '/PROPOSALS.json',
            REPAIR + '/ARTIFACT.json', REPAIR + '/REPORT.json', ORIGINAL_JUDGMENT, REPAIR_JUDGMENT}
REQUIRED |= {WESSELS + '/' + name for name in ('development.npz', 'heldout_features.npz', 'SPLIT.json')}
REQUIRED |= {TRUTHS + '/' + name + '-truth.npz' for name in ('norman', 'wessels')}
REQUIRED |= {NOMINATIONS + '/' + name + '/ARM_MANIFEST.json' for name in ('norman', 'wessels')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def complete(output, report):
    pending = Path(output) / 'PENDING_COMPLETE.json'
    write(pending, {'state': 'COMPLETE', 'report_sha256': sha(report),
                    'scope': 'Exposed-data reproduction, not another protected confirmation'})
    os.link(pending, Path(output) / 'COMPLETE.json')


def source_identity(root, freeze_path, expected=None):
    """Authenticate every declared byte before importing any application module."""
    root, freeze_path = Path(root).resolve(), Path(freeze_path)
    if freeze_path.is_symlink() or any(parent.is_symlink() for parent in freeze_path.absolute().parents):
        raise ValueError('REPRODUCTION_FREEZE_SYMLINK')
    identity = sha(freeze_path)
    if expected is not None and identity != expected:
        raise ValueError('REPRODUCTION_FREEZE_IDENTITY_MISMATCH')
    frozen = read(freeze_path)
    pins = frozen.get('sources')
    if frozen.get('schema') != 'agi-alpha/cycle006-reproduction-freeze/v1' or type(pins) is not dict or not REQUIRED <= set(pins):
        raise ValueError('REPRODUCTION_SOURCE_CLOSURE_REQUIRED')
    for name, expected_source in sorted(pins.items()):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or not relative.parts:
            raise ValueError('REPRODUCTION_UNSAFE_SOURCE_PATH')
        source = root / relative
        if source.is_symlink() or any(parent.is_symlink() for parent in source.parents) or not source.is_file() or sha(source) != expected_source:
            raise ValueError('REPRODUCTION_SOURCE_IDENTITY_MISMATCH ' + name)
    if frozen.get('candidate_freeze_sha256') != sha(root / CANDIDATE):
        raise ValueError('CANDIDATE_FREEZE_IDENTITY_MISMATCH')
    candidate = read(root / CANDIDATE)
    for name, expected_source in candidate['sources'].items():
        if pins.get(name) != expected_source:
            raise ValueError('CANDIDATE_CLOSURE_NOT_PRESERVED ' + name)
    return frozen, identity


def array_data(path):
    import numpy as np
    with np.load(path, allow_pickle=False) as source:
        return {key: source[key].copy() for key in source.files}


def command(arguments, output, timeout=150):
    with Path(output).open('xb') as stream:
        result = subprocess.run([sys.executable, *map(str, arguments)], stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    if result.returncode:
        raise RuntimeError('SUBCOMMAND_FAILED ' + str(arguments[0]) + '; inspect ' + str(output))


def worker(output, freeze_path, expected):
    started = time.monotonic()
    frozen, freeze_sha = source_identity(ROOT, freeze_path, expected)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'STARTED.json', {'state': 'STARTED', 'freeze_sha256': freeze_sha})
    # All application imports happen only after the complete closure passes.
    sys.path.insert(0, str(ROOT))
    import numpy as np
    from flywheel import baseline005, retention, sandbox
    from experiments.norman006 import model, inheritance, controls
    from verification import cycle006_symmetry_adjudication as adjudicator
    from verification import cycle006_confirm as confirmer
    from experiments import commerce006
    qualification = sandbox.qualify()
    write(output / 'SANDBOX.json', qualification)
    if not qualification['qualified']:
        raise ValueError('SANDBOX_UNQUALIFIED')
    with tempfile.TemporaryDirectory(prefix='alpha006-old005-') as temporary:
        snapshot = Path(temporary) / 'source'
        baseline = baseline005.materialize(ROOT, snapshot)
        write(output / 'BASELINE005_SOURCE.json', baseline)
        command([snapshot / 'run_completion.py', '--output', output / 'baseline005-replay'], output / 'baseline005.log')
    data = array_data(ROOT / 'experiments/interaction006_data/development.npz')
    source_sha = sha(ROOT / 'experiments/norman006/model.py')
    historical_search = read(ROOT / DEVELOPMENT / 'SEARCH.json')
    proposals = read(ROOT / DEVELOPMENT / 'PROPOSALS.json')
    replayed = model.search(data, proposals['configurations'], source_sha)
    if replayed['selected_configuration'] != historical_search['selected_configuration']:
        raise ValueError('HISTORICAL_PROPOSAL_SEARCH_REPLAY_CHANGED_SELECTION')
    write(output / 'SEARCH_REPLAY.json', {**replayed, 'proposal_origin': 'Exact retained native Omega proposals, replayed without distributing or claiming to rerun its unlicensed source',
                                         'protected_confirmation': False})
    # Local generator interfaces can be checked without inventing extra scientific attempts.
    local = model.generate_configurations(seed=20261029, count=4)
    for configuration in local['configurations']:
        model.validate_configuration(configuration)
    write(output / 'LOCAL_GENERATOR_INTERFACE.json', {**local, 'status': 'GENERATED_AND_TYPED_ONLY_NOT_SCIENTIFICALLY_FITTED',
                                                   'not_native_omega_generation': True})
    before = read(ROOT / DEVELOPMENT / 'ARTIFACT.json')
    historical_after = read(ROOT / REPAIR / 'ARTIFACT.json')
    original = adjudicator.evaluate(ROOT, ROOT / DEVELOPMENT / 'ARTIFACT.json', source_sha, output / 'criticism-reproduced')
    if original['status'] != 'established':
        raise ValueError('ORIGINAL_DEFECT_NOT_REPRODUCED')
    mapped = inheritance.exchange_mapping('norman-simultaneous-interventions')
    constraint = inheritance.constructive_constraint(ROOT / ORIGINAL_JUDGMENT, mapped)
    transformation = model.repair(before['configuration'], [constraint])
    if transformation['configuration'] != historical_after['configuration']:
        raise ValueError('MAPPING_CONSTRAINT_REPAIR_IDENTITY_CHANGED')
    reconstructed = model.fit(data, transformation['configuration'], source_sha)
    write(output / 'MAPPING.json', mapped)
    write(output / 'CONSTRUCTIVE_CONSTRAINT.json', constraint)
    write(output / 'TRANSFORMATION.json', transformation)
    write(output / 'RECONSTRUCTED_ARTIFACT.json', reconstructed)
    rechecked = adjudicator.evaluate(ROOT, output / 'RECONSTRUCTED_ARTIFACT.json', source_sha, output / 'repair-rechecked', repaired=True)
    if rechecked['status'] != 'repair_verified_in_functional_scope':
        raise ValueError('RECONSTRUCTED_REPAIR_FAILED')
    # Acquisition preserves original source-bound receipts, and recomputes the claimed
    # failed/repaired behavior before it will promote any stored capability.
    record = inheritance.acquire(before, historical_after, historical_search, ROOT / ORIGINAL_JUDGMENT, ROOT / REPAIR_JUDGMENT, ROOT)
    stored = retention.store(output / 'memory', record)
    if retention.store(output / 'memory', record) != stored:
        raise ValueError('DUPLICATE_ACQUISITION_NOT_IDEMPOTENT')
    write(output / 'ACQUIRED_CAPABILITY.json', record)
    write(output / 'ACQUISITION_LINEAGE.json', {'record_id': stored, 'original_receipts_preserved': True,
          'live_defect_and_reconstructed_repair_rechecked': True,
          'reason': 'Receipt hashes contain original timing/worker identities. Original judgments remain exact; replay does not silently substitute a new verifier for the original.'})
    successor = output / 'fresh-successor'
    command([ROOT / 'experiments/norman006/run_policy_comparison.py', '--data', ROOT / WESSELS / 'development.npz',
             '--heldout-features', ROOT / WESSELS / 'heldout_features.npz', '--store', output / 'memory',
             '--capability', output / 'ACQUIRED_CAPABILITY.json', '--search', ROOT / DEVELOPMENT / 'SEARCH.json',
             '--repair-report', ROOT / REPAIR / 'REPORT.json', '--output', successor,
             '--cell-line', 'THP-1', '--perturbation', 'CRISPR-cas13', '--seed', '41', '--fits', '4'],
            output / 'fresh-successor.log')
    reconstruction = {}
    for family in ('norman', 'wessels'):
        manifest = read(ROOT / NOMINATIONS / family / 'ARM_MANIFEST.json')
        features = array_data(ROOT / manifest['features_path'])
        training = array_data(ROOT / manifest['development_path'])
        qualified = controls.qualify(training)
        control_predictions = controls.predict_all(qualified, features)
        checks = {}
        for name, arm in manifest['arms'].items():
            if name in control_predictions:
                predicted = control_predictions[name]
            elif family == 'norman':
                predicted = model.predict(reconstructed if name == 'candidate' else before, features)['prediction']
            else:
                artifact = read(successor / 'refitted-all-development' / (name + '.json'))
                predicted = model.predict(artifact, features)['prediction']
            old = array_data(ROOT / arm['prediction_path'])['prediction']
            difference = float(np.max(np.abs(predicted - old)))
            if not np.allclose(predicted, old, rtol=1e-9, atol=1e-10):
                raise ValueError('RECONSTRUCTED_PREDICTION_MISMATCH ' + family + '/' + name)
            checks[name] = {'maximum_absolute_difference': difference, 'passed': True}
        write(output / (family + '-RECONSTRUCTED_CONTROLS.json'), qualified)
        reconstruction[family] = checks
    write(output / 'PREDICTION_RECONSTRUCTION.json', reconstruction)
    evaluated, settlements = {}, {}
    contract_sha = sha(ROOT / CONTRACT)
    for family in ('norman', 'wessels'):
        destination = output / (family + '-exposed-evaluation')
        evaluated[family] = confirmer.confirm(ROOT, ROOT / NOMINATIONS / family / 'ARM_MANIFEST.json',
            ROOT / TRUTHS / (family + '-truth.npz'), destination, ROOT / CANDIDATE,
            frozen['candidate_freeze_sha256'], contract_path=ROOT / CONTRACT, contract_sha=contract_sha)
        write(destination / 'REPLAY_SCOPE.json', {'status': 'EXPOSED_DATA_REPLAY_NOT_FRESH_CONFIRMATION',
              'source_bound_original_predictions_reconstructed': True})
        receipt = destination / 'FUNCTIONAL_ACCEPTANCE.json'
        settlements[family] = commerce006.run(destination / 'REPORT.json', receipt, ROOT / CONTRACT,
            output / (family + '-conditional-settlement'), expected_contract_sha256=contract_sha,
            expected_receipt_sha256=sha(receipt))
    report = {'schema': 'agi-alpha/cycle006-connected-reproduction/v1', 'status': 'EXECUTED_EXPOSED_REPRODUCTION',
        'source_freeze_sha256': freeze_sha, 'candidate_freeze_sha256': frozen['candidate_freeze_sha256'],
        'connected_path': ['exact005baseline', 'retained-native-proposal-search-replay', 'actual-nonseeded-defect-reproduction',
            'structural-mapping', 'constructive-constraint', 'reconstructed-repair', 'independent-functional-recheck',
            'trace-bound-acquisition', 'actual-memory-retrieval-and-fresh-data-refit', 'qualified-control-reconstruction',
            'frozen-exposed-evaluation', 'same-report-conditional-acceptance-and-settlement'],
        'source_bound_record_id': stored,
        'all_predictions_reconstructed': True,
        'scientific_pilot_threshold_met': {family: value['practical_pilot_threshold_met'] for family, value in evaluated.items()},
        'conditional_settlement_checks_passed': {family: value['all_qualification_checks_passed'] for family, value in settlements.items()},
        'verdicts': {'engineering_qualification': 'DEMONSTRATED_IN_DECLARED_SCOPE',
            'consequential_enabling_capability': 'NOT_ESTABLISHED', 'combination_advantage': 'NOT_ESTABLISHED',
            'experience_advantage': 'NOT_ESTABLISHED_OVER_EQUIVALENT_REUSE', 'improved_discovery_policy': 'NOT_ESTABLISHED',
            'conditional_modeled_commercial_viability': 'UNKNOWN_COMPLETE_COSTS_AND_DEMAND',
            'investment_attractiveness': 'UNKNOWN', 'AGI_ALPHA_value_capture': 'UNKNOWN',
            'earned_funded_successor_benefit': 'NOT_ESTABLISHED', 'live_commercial_success': 'NOT_ESTABLISHED'},
        'actual_receipts': 0, 'available_commercial_earned_funds': 0, 'funded_successor': False,
        'resources': {'wall_seconds': time.monotonic() - started, 'complete_monetary_cost': None,
                      'scope': 'Disjoint enclosing prospective resource receipt; original acquisition/development/verification costs remain in published evidence and are not erased by replay.'},
        'limits': ['Original outcomes remain exposed; replay adds no independent confirmation or statistical alpha.',
            'Native Omega source was historically executed but is not redistributed; retained proposals replay explicitly.',
            'Finite developer-authored grammar and established group averaging; no novel mathematical primitive or biological discovery claim.',
            'Models and libraries share a host. Functional audit acceptance is an artificial contract, not demand, buyer payment, or commercially earned cash.']}
    write(output / 'REPORT.json', report)
    complete(output, output / 'REPORT.json')
    return report


def interrupted(signum, frame):
    raise KeyboardInterrupt('SIGNAL_' + str(signum))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, default=ROOT / FREEZE)
    parser.add_argument('--freeze-sha256')
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--run-id', default='cycle006-connected-reproduction')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        worker(args.output.resolve(), args.freeze.absolute(), args.freeze_sha256)
        return 0
    signal.signal(signal.SIGTERM, interrupted)
    output, owned = args.output.absolute(), False
    try:
        if output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
            raise ValueError('REPRODUCTION_OUTPUT_SYMLINK')
        # A pending signal must not land between successful mkdir and ownership.
        # Restore the caller's mask only after ownership is recorded; the normal
        # exception path then records the interruption without touching old paths.
        prior_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            output.mkdir(parents=True, exist_ok=False)
            owned = True
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
        write(output / 'STARTED.json', {'state': 'STARTED', 'phase': 'identity-before-import',
              'scope': 'Bounded exposed reproduction; rerun at a new exclusive path after any interruption'})
        frozen, freeze_sha = source_identity(ROOT, args.freeze.absolute(), args.freeze_sha256)
        write(output / 'SOURCE_IDENTITY.json', {'freeze_sha256': freeze_sha, 'sources_checked': len(frozen['sources'])})
        sys.path.insert(0, str(ROOT))
        from experiments import resource006
        command_line = [sys.executable, '-I', str(ROOT / 'run_cycle006.py'), '--worker', '--output', str(output / 'bounded/artifacts'),
                        '--freeze', str(args.freeze.absolute()), '--freeze-sha256', freeze_sha]
        result = resource006.run(command_line, output / 'bounded', args.ledger or output / 'RESOURCE_LEDGER.json', args.run_id,
            {'wall_seconds': 360, 'cpu_seconds': 300, 'memory_bytes': 4*1024**3,
             'output_bytes': 64*1024**2, 'storage_bytes': 512*1024**2}, cwd=ROOT)
        if result['receipt']['state'] != 'complete':
            raise RuntimeError('CONNECTED_WORKER_INCOMPLETE; retain bounded/RECEIPT.json and logs')
        report = output / 'REPORT.json'
        with report.open('xb') as stream:
            stream.write((output / 'bounded/artifacts/REPORT.json').read_bytes())
        complete(output, report)
        print(json.dumps({'output': str(output), 'report_sha256': sha(report), 'scope': 'exposed reproduction'}))
    except BaseException as error:
        if owned and not (output / 'COMPLETE.json').exists():
            marker = output / 'INTERRUPTED.json'
            if not marker.exists():
                write(marker, {'state': 'INCOMPLETE', 'reason': type(error).__name__, 'detail': str(error)[:500],
                               'recovery': 'Preserve all evidence; rerun at a new exclusive output path'})
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
