"""Optional earned-funded, bounded replay of inherited invention mechanisms.

This supporting engineering experiment does not assert a new scientific
instrument, broad autonomous invention, or superiority to equal-content reuse.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
from commercial.ledger import TapeExchange, audit, canonical, digest
from flywheel.strategy import discover, interpret, synthesize
from flywheel.evidence_executor import execute
from flywheel.retention import retrieve, store

MICRO = 1_000_000
BUDGET = 25 * MICRO
SOURCES = ('enterprise/frontier.py', 'flywheel/strategy.py', 'flywheel/evidence_executor.py', 'flywheel/retention.py')
RESEARCH_HYPOTHESIS = {
    'expected_avoided_rework_microUSD': 30 * MICRO,
    'basis': 'Authored optional research hypothesis: two future interrupted evidence-packet recoveries could each avoid $15 of autonomous rework under the declared successful scoped test. The $30 expected avoided-rework value is a planning assumption, not observed savings, measured ROI, collected revenue or earned income. Actual future frequency and economic benefit are unknown.',
}


def _task(identity, phases):
    return {'id': identity, 'phases': phases, 'dependencies': [[a, b] for a, b in zip(phases, phases[1:])]}


def _capture(path):
    return {child.name: {'sha256': hashlib.sha256(child.read_bytes()).hexdigest(),
                         'utf8': child.read_text()} for child in sorted(path.iterdir()) if child.is_file()}


def _execute(task, program, destination, phase):
    receipt = execute(task, program, destination, phase)
    predicted = interpret({'task': task, 'program': program, 'interrupt_at': phase})
    if any(receipt[key] != predicted[key] for key in ('state', 'completed', 'interrupted_marker', 'trace')):
        raise ValueError('FRONTIER_INTERPRETER_EFFECT_DISAGREEMENT')
    return {'receipt': receipt, 'artifact_files': _capture(destination),
            'independent_contract_check': not receipt['completed'] and receipt['interrupted_marker'],
            'checking_scope': 'Fixed effect executor compared with inherited pure interpreter and explicit interruption/marker requirements; shared authors and host, not external certification.'}


def _experiment(root, directory):
    began = time.process_time()
    donor = {'id': 'inherited-experiment-initialization-guard',
             'nodes': [{'id': 'guard', 'kind': 'guard', 'unit': 'event'}, {'id': 'initialize', 'kind': 'effect', 'unit': 'event'}],
             'relations': [['guard', 'protects', 'initialize']],
             'conditions': {'failure': 'python_interrupt'}}
    target = {'id': 'source-evidence-packet-construction',
              'nodes': [{'id': 'capture', 'kind': 'guard', 'unit': 'event'}, {'id': 'open_packet', 'kind': 'effect', 'unit': 'event'}],
              'relations': [['capture', 'protects', 'open_packet']],
              'conditions': {'failure': 'python_interrupt'}}
    mappings = discover([donor], target)
    inapplicable = copy.deepcopy(target)
    inapplicable['id'] = 'unqualified-host-power-loss-transfer'
    inapplicable['conditions']['failure'] = 'host_power_loss'
    failed_transfer = discover([donor], inapplicable)
    development = _task('development-source-evidence-packet', ['reserve', 'start', 'work', 'complete'])
    original = synthesize(development, [])
    counterexample = _execute(development, original['program'], directory / 'development-original', 'start')
    established = not counterexample['receipt']['interrupted_marker'] and not counterexample['receipt']['completed']
    if not established:
        raise ValueError('FRONTIER_CRITICISM_NOT_REPRODUCED')
    constraints = [{'status': 'established', 'kind': 'protect_phase', 'phase': 'start',
                    'evidence_sha256': digest(counterexample)}]
    repaired = synthesize(development, constraints)
    repair_receipt = _execute(development, repaired['program'], directory / 'development-repaired', 'start')
    if not repair_receipt['independent_contract_check']:
        raise ValueError('FRONTIER_REPAIR_NOT_VERIFIED')
    operator = {'operator': 'protect_initialization', 'language': 'bounded-evidence/v1'}
    memory = {'instrument': {'path': 'flywheel/evidence_executor.py', 'sha256': hashlib.sha256((root / 'flywheel/evidence_executor.py').read_bytes()).hexdigest()},
              'applicability': {'schema_version': 1, 'conditions': {'exclusive_output': True, 'python_interrupt': True},
                  'assumptions': ['Reservation occurs before interruptible effects.', 'Only the inherited seven-operation typed language is available.', 'Trusted executor writes fixed exclusive local evidence files.'],
                  'uncertainty': 'No host-power-loss durability, discovery advantage, economic benefit or novel scientific enablement is established.',
                  'failures': [{'conditions': {'phase_before_reserve': True}, 'reason': 'The mechanism cannot guarantee evidence before the reservation effect; this is a declared applicability boundary.'}]},
              'generative_operator': {'language': 'bounded-evidence-v1', 'program': {'inherited_operator': operator, 'development_program': repaired['program']}},
              'provenance': {'origin': 'Existing developer-supplied representation and fixed operator menu; exhaustive structural matcher selects mapping and inherited bounded synthesizer selects executable phase order/guard.', 'mapping': mappings, 'critic': 'Fixed adjudicator constructs protect_phase constraint only after the executed missing-marker counterexample.', 'development_task': development},
              'verification': {'status': 'verified-in-scope', 'receipt_sha256': digest(repair_receipt)},
              'costs': {'currency': 'USD', 'envelope_usd': 25, 'evidence': 'Conditional all-in optional lane allocation, not observed token billing or human labor.'},
              'exposure': ['development-source-evidence-packet'], 'supersedes': []}
    memory_id = store(directory / 'retained', memory)
    target_conditions = {'schema_version': 1, 'conditions': {'exclusive_output': True, 'python_interrupt': True, 'phase_before_reserve': False}}
    retrieval = retrieve(directory / 'retained', target_conditions, root)
    if len(retrieval['records']) != 1 or retrieval['records'][0]['id'] != memory_id:
        raise ValueError('VERIFIED_SCOPED_MEMORY_RETRIEVAL_REQUIRED')
    blocked = retrieve(directory / 'retained', {'schema_version': 1, 'conditions': {'exclusive_output': True, 'python_interrupt': True, 'phase_before_reserve': True}}, root)
    fresh = []
    tasks = [_task('fresh-source-evidence-export', ['reserve', 'start', 'work', 'complete']),
             _task('fresh-evidence-publication', ['reserve', 'manifest', 'build', 'publish', 'complete'])]
    for task_index, task in enumerate(tasks):
        phase = task['phases'][1]
        obligations = [{'status': 'established', 'kind': 'protect_phase', 'phase': phase}]
        learned = retrieval['records'][0]['record']['generative_operator']['program']['inherited_operator']
        generated = {
            'structured_inheritance': synthesize(task, obligations, inherited=learned),
            'equal_content_ordinary_reuse': synthesize(task, obligations, inherited=copy.deepcopy(operator)),
            'no_inheritance': synthesize(task, obligations),
            'strong_conventional': {'status': 'constructed', 'program': {'body': task['phases'], 'protected_from': 0}, 'attempts': [{'origin': 'Developer supplied standard protect-all-effects control.'}]}}
        arms = {}
        for arm, construction in generated.items():
            if construction['status'] != 'constructed':
                raise ValueError('FRONTIER_CONTROL_CONSTRUCTION_FAILURE')
            receipts = [_execute(task, construction['program'], directory / f'fresh-{task_index}-{arm}-{index}', interrupt)
                        for index, interrupt in enumerate(task['phases'][1:])]
            arms[arm] = {'construction': construction, 'candidate_evaluations': len(construction['attempts']),
                         'all_interruption_contracts_pass': all(r['independent_contract_check'] for r in receipts), 'executed_receipts': receipts}
        fresh.append({'task': task, 'arms': arms, 'same_content_comparison': arms['structured_inheritance']['construction'] == arms['equal_content_ordinary_reuse']['construction']})
    return {'schema': 'agi-alpha/enterprise011-frontier-experiment/v1', 'scope': 'BOUNDED_ENGINEERING_EXPERIMENT',
            'beneficiary': 'Future synthetic service evidence pipelines interrupted during initialization.',
            'constraint': 'An initialization interruption can leave an unmarked incomplete evidence directory.',
            'enabling_mechanism': 'Move the interruption guard to protect initialization while preserving phase dependencies.',
            'discriminating_experiment': 'Execute the missing-marker counterexample, generated repair and fresh matched controls at each interruptible phase using exclusive local file effects.',
            'productive_consequence': 'Scoped incomplete-work evidence becomes available for recovery. No new previously inaccessible scientific or profitable work is demonstrated.',
            'donor_target_mapping': mappings, 'failed_transfer': failed_transfer,
            'origin': 'Developer-supplied tasks and donor representation; mapping inferred by existing exhaustive matcher; executable adaptation generated by existing finite synthesizer, not a new primitive or unrestricted model invention.',
            'critic_counterexample': counterexample, 'adjudicated_constraints': constraints,
            'original_strategy': original, 'generated_repair': repaired, 'repair_receipt': repair_receipt,
            'memory_record': memory, 'memory_id': memory_id, 'retrieval': retrieval,
            'failed_scope_retrieval': blocked, 'fresh_comparisons': fresh,
            'capability_compounding': 'NOT_ESTABLISHED', 'blue_sky_enablement': 'NOT_ESTABLISHED',
            'result': 'The inherited mechanism repairs its scoped interruption defect. Structured inheritance and equal-content ordinary reuse tie on all fresh cases; the strong conventional control also passes. Lower bounded search counts versus no inheritance do not establish discovery superiority or net economic benefit.',
            'budget_usd': 25, 'budget_evidence': 'Conditional all-in cost envelope for construction, search, failures, tests, inference/tool/compute/storage assumptions and retention. No paid model call or inserted human-review labor.',
            'cpu_seconds': time.process_time() - began}


def run_frontier(root, manifest, representative_result, *, research_hypothesis=None):
    """Continue one audited trajectory with a separate optional investment."""
    root = Path(root).absolute()
    if not isinstance(representative_result, dict) or representative_result.get('scope') != 'SIMULATED' or not isinstance(representative_result.get('ledger'), dict):
        raise ValueError('AUDITED_SIMULATED_REPRESENTATIVE_REQUIRED')
    tape = representative_result['ledger']
    checked = audit(tape, root=root, manifest=manifest, expected_actions_sha256=tape.get('actions_sha256'))
    if representative_result.get('summary') != checked['summary']:
        raise ValueError('REPRESENTATIVE_SUMMARY_MISMATCH')
    prior = checked['summary']
    hypothesis = copy.deepcopy(RESEARCH_HYPOTHESIS if research_hypothesis is None else research_hypothesis)
    if not isinstance(hypothesis, dict) or set(hypothesis) != set(RESEARCH_HYPOTHESIS) or type(hypothesis['expected_avoided_rework_microUSD']) is not int or not 0 <= hypothesis['expected_avoided_rework_microUSD'] <= 10**12 or not isinstance(hypothesis['basis'], str) or not hypothesis['basis']:
        raise ValueError('EXPLICIT_BOUNDED_RESEARCH_VALUE_HYPOTHESIS_REQUIRED')
    expected_net_value = hypothesis['expected_avoided_rework_microUSD'] - BUDGET
    valuation = {'hypothesis': hypothesis, 'bounded_allocation_microUSD': BUDGET,
                 'expected_net_value_microUSD': expected_net_value,
                 'actual_economic_benefit': 'UNKNOWN',
                 'zero_expected_benefit_alternative': {'expected_avoided_rework_microUSD': 0, 'expected_net_value_microUSD': -BUDGET, 'would_invest': False},
                 'admission_rule': 'Invest only when the declared expected avoided-rework hypothesis exceeds this bounded allocation and native unrestricted earned funds cover it. No assumed benefit enters the ledger as income.'}
    source_hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in SOURCES}
    report = {'schema': 'agi-alpha/enterprise011-frontier/v1', 'scope': 'SIMULATED_EARNED_FUNDED_SUPPORTING_EXPERIMENT',
              'commercial_trajectory_actions_sha256': tape['actions_sha256'], 'source_hashes': source_hashes,
              'budget_microUSD': BUDGET, 'before': prior, 'capability_compounding': 'NOT_ESTABLISHED', 'blue_sky_enablement': 'NOT_ESTABLISHED',
              'research_valuation': valuation,
              'accounting_scope': 'Supplemental continuation of this one trajectory. The base commercial summary is preserved; do not add base and supplemental revenue or spend the same pre-allocation balance twice.',
              'funding_status': 'SKIPPED_INSUFFICIENT_UNRESTRICTED_EARNINGS', 'experiment': None, 'supplemental_ledger': None, 'after': prior}
    if expected_net_value <= 0:
        report['funding_status'] = 'SKIPPED_NONPOSITIVE_RESEARCH_VALUE_HYPOTHESIS'
        return report
    if prior['unrestrictedEarned'] < BUDGET or prior['investmentStopped']:
        return report
    with tempfile.TemporaryDirectory(prefix='enterprise011-frontier-') as temporary:
        directory = Path(temporary)
        config = tape['config']
        exchange = TapeExchange(directory / 'supplemental.sqlite', root=root, manifest=manifest, opening=config['opening'], working=config['working'], contract=config['contract'], durable=False)
        try:
            for event in tape['actions']:
                if exchange.ex.snapshot() != event['before']:
                    raise ValueError('FRONTIER_REPLAY_BEFORE_MISMATCH')
                after = exchange.execute(event['op'], event['args'], event['day'])
                if after != event['after']:
                    raise ValueError('FRONTIER_REPLAY_AFTER_MISMATCH')
            day = max([event['day'] for event in tape['actions']], default=0) + 1
            intent = {'purpose': 'Bounded inherited interruption-guard repair and fresh ordinary-reuse controls', 'budget_microUSD': BUDGET, 'source_hashes': source_hashes, 'novelty_claim': False, 'research_valuation': valuation}
            exchange.execute('reserve', {'id': 'enterprise011-frontier-optional-001', 'amount': BUDGET, 'expected_net_value': expected_net_value, 'intent_sha256': digest(intent)}, day)
            experiment = _experiment(root, directory / 'experiment')
            experiment_sha256 = digest(experiment)
            exchange.execute('finish', {'id': 'enterprise011-frontier-optional-001', 'amount': BUDGET, 'artifact_sha256': experiment_sha256}, day)
            supplemental = exchange.export()
        finally:
            exchange.close()
    supplemental_checked = audit(supplemental, root=root, manifest=manifest, expected_actions_sha256=supplemental['actions_sha256'])
    after = supplemental_checked['summary']
    if after['collections'] != prior['collections'] or after['cash'] != prior['cash'] - BUDGET or after['expenses'] != prior['expenses'] + BUDGET or after['tailReserve'] != prior['tailReserve'] or after['workingCapital'] != prior['workingCapital']:
        raise ValueError('FRONTIER_SUPPLEMENTAL_ACCOUNTING_MISMATCH')
    report.update({'funding_status': 'SIMULATED_UNRESTRICTED_EARNINGS_RESERVED_AND_SPENT', 'funding_valuation': f"The declared ${hypothesis['expected_avoided_rework_microUSD'] / MICRO:.2f} avoided-rework hypothesis minus the ${BUDGET / MICRO:.2f} allocation supplies a conditional ${expected_net_value / MICRO:.2f} expected net value. This prospective research assumption is not observed savings, measured ROI, revenue or earned income; actual economic benefit remains unknown.", 'intent': intent, 'experiment': experiment, 'experiment_sha256': experiment_sha256, 'supplemental_ledger': supplemental, 'after': after})
    return report
