#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reconcile exact released-byte evidence without promoting commercial/live gates."""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
import re
import sys

from owner_handoff import DIGEST, SHA, archive_snapshot, digest, json_write, model_evidence_snapshot, operation_summary, read_json, safe_path
from qualify_genesis_successor import PATHS as GENESIS_SOURCE_PATHS

BROWSER_CHECKS = {
    'spawned connector announced its own loopback origin',
    'keyboard skip link reaches workspace',
    'first-run rendered',
    'saved project survives reload; downloaded JSON reopens in fresh browser storage',
    'French interface rendered',
    '390px responsive layout without page overflow',
    'START-HERE opens local files; offline experiment completes without any HTTP requests',
}
STRATEGIES = {'single-model', 'researcher-builder-verifier', 'strategist-economist',
              'parallel-exploration', 'adaptive', 'adversarial-review'}
LIVE_KEYS = {'local_inference', 'single_agent', 'multi_agent', 'parallel_exploration',
             'quote_construction', 'successor_reuse', 'independent_export'}
LIVE_SOURCE_FILES = {'bridge/adapters.py', 'bridge/streaming.py', 'bridge/workflows.py',
                     'bridge/workflow_strategies.py', 'bridge/instruments.py',
                     'scripts/qualify_hosted_local.py', 'scripts/probe_local_workflows.py',
                     'scripts/qualify_quote_workflow_003.py'}
BLOCKED = {'B1', 'B3', 'B4', 'B5'}
UNRESOLVED_GENESIS_FAILURES = {'O4', 'O6'}
GENESIS_SOURCES = {label:path.resolve().relative_to(Path(__file__).resolve().parents[1]).as_posix()
                   for label,path in GENESIS_SOURCE_PATHS.items()}
FIXTURE_MODULES = {
    'E1': ['test_workflows'], 'E2': ['test_workflows'], 'F1': ['test_workflows', 'test_independent_security'],
    'G1': ['test_bridge', 'test_providers'], 'G2': ['test_chatgpt', 'test_independent_security'],
    'G3': ['test_workflows', 'test_independent_security'],
    'G4': ['test_server_integrations', 'test_independent_security'],
    'G5': ['test_release', 'test_qualification'],
    'O1': ['test_genesis_next', 'test_genesis_next_independent'],
    'O9': ['test_proof_to_market', 'test_genesis_http'],
}
REQUIRED_FILES = {
    'START-HERE.html', 'GUIDE.html', 'LICENSE', 'THIRD-PARTY.json', 'SECURITY.md', 'VERSION.json',
    'launch.py', 'Launch-HARNESS.sh', 'Launch-HARNESS.command', 'Launch-HARNESS.cmd',
    'docs/INSTALLATION.md', 'docs/MODEL-CONNECTIONS.md', 'docs/QUICKSTART.md', 'docs/OPERATOR.md',
    'docs/TROUBLESHOOTING.md', 'docs/PRIVACY.md', 'docs/RELEASE-NOTES.md', 'docs/FAQ.md',
    'commercial/listing.md', 'commercial/listing.json', 'commercial/storefront-checklist.md',
    'docs/OMEGA-GENESIS-NEXT.md', 'docs/PROOF-TO-MARKET.md', 'bridge/genesis_next.py',
    'evidence/OMEGA-PROTOCOL.md', 'evidence/OMEGA-FRESH-SUCCESSOR-PROTOCOL.md',
    'scripts/qualify_genesis_successor.py',
}


def has_sequence(command, wanted):
    return any(command[i:i + len(wanted)] == wanted for i in range(len(command) - len(wanted) + 1))


def operation_index(operations, wanted):
    matches = [i for i, row in enumerate(operations, 1) if has_sequence(row['command'], wanted)]
    if len(matches) > 1:
        raise ValueError('Ambiguous operation command: ' + ' '.join(wanted))
    return matches[0] if matches else None


def log_text(directory, index, stream):
    if index is None:
        return ''
    path = Path(directory) / f'operation-{index}.{stream}.txt'
    if not path.is_file():
        return ''
    if path.is_symlink() or path.stat().st_size > 5_000_000:
        raise ValueError('Unsafe operation log')
    return path.read_text(encoding='utf-8', errors='replace')


def module_passed(log, module):
    lines = [line for line in log.splitlines() if re.match(r'^test_\w+ \(' + re.escape(module) + r'\.', line)]
    return bool(lines) and all(re.search(r'\.\.\. ok$', line) for line in lines)


def source_hashes_match(record, content):
    hashes = record.get('source_sha256')
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('Evidence lacks its source-file hashes')
    prefix = 'products/alpha-genesis-harness/'
    for name, value in hashes.items():
        relative = name[len(prefix):] if name.startswith(prefix) else name
        if not safe_path(relative) or relative not in content or digest(content[relative]) != value:
            raise ValueError('Evidence source hash differs from the exact archive: ' + str(name))


def browser_passed(record, source, directory=None, image_prefix=''):
    if record.get('source_revision') != source:
        raise ValueError('Browser receipt has a different source revision')
    if record.get('status') != 'PASS' or record.get('errors') != []:
        return False
    if not BROWSER_CHECKS.issubset(set(record.get('checks', []))):
        return False
    screenshots = record.get('screenshots')
    if not isinstance(screenshots, list) or not screenshots:
        return False
    if directory is not None:
        for name in screenshots:
            if not isinstance(name, str) or not safe_path(name) or '/' in name:
                raise ValueError('Unsafe browser screenshot name')
            path = Path(directory) / (image_prefix + name)
            if path.is_symlink() or not path.is_file() or not path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                return False
    return True


def paired_passed(record, content):
    if record.get('schema') != 'alpha-genesis-paired-retrieval/v1':
        raise ValueError('Unsupported paired fixture schema')
    source_hashes_match(record, content)
    arms = record.get('arms', [])
    if len(arms) != 2 or {arm.get('arm') for arm in arms} != {'no-retrieval', 'retrieval'}:
        return False
    arms = {arm['arm']: arm for arm in arms}
    budget = record.get('protocol', {}).get('shared_per_arm_budget', {})
    for key in ('model_calls', 'tool_actions'):
        if type(budget.get(key)) is not int or budget[key] <= 0:
            return False
    for arm in arms.values():
        if (arm.get('status') != 'complete' or type(arm.get('model_calls')) is not int
                or type(arm.get('actions')) is not int or arm['model_calls'] != budget['model_calls']
                or arm['actions'] != budget['tool_actions'] or type(arm.get('failed_initial_checks')) is not int
                or arm['failed_initial_checks'] < 1 or type(arm.get('fixture_source_fetches')) is not int
                or arm.get('verification', {}).get('passed') is not True):
            return False
    control, treatment = arms['no-retrieval'], arms['retrieval']
    ordinary = record.get('competent_conventional_control', {})
    return (control.get('honest_abstention') is True and control.get('matches_withheld_source') is False
            and control.get('fixture_source_fetches') == 0
            and treatment.get('matches_withheld_source') is True and treatment.get('fixture_source_fetches') == 1
            and ordinary.get('matches_withheld_source') is True and type(ordinary.get('model_calls')) is int
            and ordinary['model_calls'] == 0)


def validate_live_provenance(record, files, content):
    """Require substantive runtime provenance before accepting any PASS flags."""
    if 'PASS' not in record['qualifications'].values():
        return
    hashes = {name.removeprefix('products/alpha-genesis-harness/'):value for name,value in record['source_sha256'].items()}
    if not LIVE_SOURCE_FILES.issubset(hashes):
        raise ValueError('Live PASS lacks required inference and workflow source hashes')
    host = record.get('host', {})
    if (host.get('platform') != 'linux' or not isinstance(host.get('python'), str)
            or host.get('accelerator') != 'CPU' or type(host.get('inference_threads')) is not int
            or host['inference_threads'] <= 0):
        raise ValueError('Live PASS lacks the recorded supported host provenance')
    downloads = record.get('downloads', {})
    for name in ('runtime_archive', 'model'):
        item = downloads.get(name, {})
        if (item.get('verified') is not True or not DIGEST.fullmatch(str(item.get('sha256', '')))
                or type(item.get('bytes')) is not int or item['bytes'] <= 0
                or not str(item.get('url','')).startswith('https://')):
            raise ValueError('Live PASS lacks verified model/runtime download provenance')
    if not DIGEST.fullmatch(str(downloads.get('runtime_binary_sha256', ''))):
        raise ValueError('Live PASS lacks the runtime executable hash')
    commands = record.get('commands', [])
    core_commands = [row for row in commands if Path(str(row.get('entrypoint',''))).name in {'probe_local_workflows.py', 'qualify_quote_workflow_003.py'}]
    if not core_commands or any(type(row.get('returncode')) is not int or type(row.get('timed_out')) is not bool for row in core_commands):
        raise ValueError('Live PASS lacks recorded actual inference driver execution')
    raw_records = []
    for name, tree_key in [('LOCAL-WORKFLOWS-HOSTED.json','source_product_tree'), ('LOCAL-QUOTE-QUALIFICATION-003.json','product_tree_sha')]:
        if name in files:
            raw = json.loads(files[name])
            if raw.get('source_revision') != record['source_revision'] or raw.get(tree_key) != record['source_product_tree']:
                raise ValueError('Raw model receipt has a different source identity')
            raw_records.append(raw)
    events = [event for raw in raw_records for arm in raw.get('runs',raw.get('arms',[])) for event in arm.get('events',[])]
    if not any(event.get('kind') == 'model_completed' for event in events):
        raise ValueError('Live PASS lacks an actual recorded completed model event')
    if any(record['qualifications'][key]=='PASS' for key in ('single_agent','multi_agent','parallel_exploration')):
        if 'LOCAL-WORKFLOWS-HOSTED.json' not in files or not any(Path(str(row.get('entrypoint',''))).name=='probe_local_workflows.py' for row in core_commands):
            raise ValueError('Live workflow PASS lacks its driver and raw receipt')
        workflow = json.loads(files['LOCAL-WORKFLOWS-HOSTED.json'])
        for policy,key in [('single-model','single_agent'),('actor-critic','multi_agent'),('parallel-exploration','parallel_exploration')]:
            if record['qualifications'][key] != 'PASS':
                continue
            matches = [row for row in workflow.get('runs',[]) if row.get('policy')==policy]
            if len(matches) != 1:
                raise ValueError('Live workflow PASS lacks its specific policy run')
            row = matches[0]
            external = row.get('external_execution',{})
            if (workflow.get('source_unchanged') is not True or row.get('status') != 'complete'
                    or row.get('verification',{}).get('passed') is not True
                    or type(external.get('returncode')) is not int or external['returncode'] != 0
                    or external.get('result',{}).get('output') != {'result':34}
                    or row.get('strong_control',{}).get('accepted') is not True):
                raise ValueError('Live workflow PASS contradicts its retained verification')


def canonical_digest(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode())


def genesis_demo_passed(receipt, content):
    result = receipt.get('experiment', {})
    if result.get('schema') != 'genesis-next-experiment/v1':
        raise ValueError('Unsupported GENESIS experiment schema')
    source = result.get('source', {})
    for key,path in [('baseline_sha256','bridge/workflows.py'), ('checker_sha256','bridge/instruments.py'), ('protocol_sha256','evidence/OMEGA-PROTOCOL.md')]:
        if source.get(key) != digest(content[path]):
            raise ValueError('GENESIS demonstration differs from exact archived source')
    candidate = result.get('artifacts', {}).get('candidate.py')
    if not isinstance(candidate, str) or not candidate or digest(candidate.encode()) != source.get('candidate_sha256'):
        raise ValueError('GENESIS demonstration lacks its actual constructed source bytes')
    if result['artifacts'].get('candidate_sha256') != source['candidate_sha256']:
        raise ValueError('GENESIS candidate artifact identity differs')
    expected = [('original',True), ('unchanged',True), ('changed-source',False), ('changed-input',True),
                ('changed-acceptance',False), ('missing-artifact',False), ('unchanged-again',True)]
    arms = result.get('arms', {})
    if set(arms) != {'baseline','candidate','ordinary'}:
        return False
    for arm in arms.values():
        outcomes = arm.get('outcomes', [])
        if len(outcomes) != len(expected) or any(row.get('case') != name or row.get('accepted') is not accepted for row,(name,accepted) in zip(outcomes,expected)):
            return False
        if type(arm.get('verification_calls')) is not int or arm['verification_calls'] < 0:
            return False
    return (result.get('status') == 'complete' and source.get('evaluation_sources_unchanged') is True
            and result.get('qualification', {}).get('correctness') == 'PASS'
            and result['qualification'].get('production_promotion') is False)


def genesis_successor_passed(freeze_bytes, receipt, content):
    frozen = json.loads(freeze_bytes)
    expected_sources = {label:digest(content[path]) for label,path in GENESIS_SOURCES.items()}
    if (frozen.get('schema') != 'omega-successor-source-freeze/v1' or frozen.get('source_sha256') != expected_sources
            or receipt.get('source_sha256') != expected_sources or receipt.get('freeze_sha256') != digest(freeze_bytes)):
        raise ValueError('GENESIS fresh successor is not bound to the frozen archived source')
    if receipt.get('schema') != 'omega-fresh-successor-qualification/v1':
        raise ValueError('Unsupported GENESIS fresh successor schema')
    if not DIGEST.fullmatch(str(receipt.get('seed_generated_after_source_freeze', ''))):
        raise ValueError('GENESIS successor lacks its post-freeze nonce')
    initial, successor = receipt.get('initial_instances', []), receipt.get('successor_instances', [])
    if len(initial) != 24 or len(successor) != 32 or receipt.get('instances_sha256') != canonical_digest({'initial':initial,'successor':successor}):
        raise ValueError('GENESIS successor raw instance inventory or hash differs')
    if len({row['id'] for row in initial}) != len(initial) or len({row['id'] for row in successor}) != len(successor):
        raise ValueError('GENESIS successor repeats an instance identity')
    arms = receipt.get('arms', [])
    names = {'uncached_baseline','inherited_candidate','strong_ordinary_memoization','inheritance_withdrawn'}
    if len(arms) != 4 or {arm.get('arm') for arm in arms} != names:
        return False
    inherited = {canonical_digest({'spec':row['spec'],'dependencies':row['dependencies']}) for row in initial}
    for arm in arms:
        decisions = arm.get('decisions', [])
        if len(decisions) != len(successor):
            return False
        adjudicated = reused = 0
        for case,decision in zip(successor,decisions):
            if decision.get('id') != case['id']:
                return False
            if decision.get('status') == 'UNKNOWN_BUDGET_EXHAUSTED':
                if decision.get('correct') is not None:
                    return False
                continue
            spec = case['spec']
            actual_acceptance = spec['expected'] == {'result':spec['input']['x'] + spec['input']['offset']}
            if (decision.get('status') != 'ADJUDICATED' or decision.get('accepted') is not actual_acceptance
                    or decision.get('correct') is not True or type(decision.get('reused')) is not bool):
                return False
            adjudicated += 1
            reused += int(decision['reused'])
            if decision['reused'] and canonical_digest({'spec':spec,'dependencies':case['dependencies']}) not in inherited:
                return False
        for key,value in {'adjudicated':adjudicated,'correct_decisions':adjudicated,'errors':0,'reused':reused,
                          'initial_verification_calls':24,'successor_verification_calls':adjudicated-reused,
                          'total_verification_calls':24+adjudicated-reused}.items():
            if type(arm.get(key)) is not int or arm[key] != value:
                return False
        if arm['successor_verification_calls'] != 20:
            return False
        expected_count, expected_reuse = (32,12) if arm['arm'] in {'inherited_candidate','strong_ordinary_memoization'} else (20,0)
        if (adjudicated,reused) != (expected_count,expected_reuse):
            return False
    return (receipt.get('status') == 'PASS' and receipt.get('failures') == []
            and receipt.get('successor_evaluator_allowance') == 20
            and receipt.get('strong_control_advantage') == 'NOT_ESTABLISHED'
            and receipt.get('complete_costs_known') is False)


def reconcile(args):
    if not SHA.fullmatch(args.source_sha) or not SHA.fullmatch(args.source_product_tree) or not DIGEST.fullmatch(args.expected_sha256):
        raise ValueError('Full final source, product tree and archive digest identities are required')
    raw, manifest, content, _modes, archive_hash = archive_snapshot(args.archive, args.source_sha, args.expected_sha256)
    if manifest['source_product_tree'] != args.source_product_tree:
        raise ValueError('Archive product tree differs from the trusted publication identity')
    matrix = json.loads(content['evidence/QUALIFICATION-MATRIX.json'])
    if matrix.get('source_revision') not in (None, args.source_sha):
        raise ValueError('Packaged matrix names a different source')
    rows = {row['id']: copy.deepcopy(row) for row in matrix['criteria']}
    if len(rows) != len(matrix['criteria']):
        raise ValueError('Duplicate criterion ID')
    required_ids = {'A1','A2','B1','B2','B3','B4','B5','C1','C2','D1','E1','E2','F1','F2',
                    'G1','G2','G3','G4','G5','H1','H2','H3','I1','I2','J1',
                    'B6','O1','O2','O3','O4','O5','O6','O7','O8','O9'}
    if not required_ids.issubset(rows):
        raise ValueError('Packaged matrix is missing reconciled criteria')
    changes, inputs = [], []
    def record_input(path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('Evidence must be an ordinary file: ' + str(path))
        inputs.append({'name':path.name, 'sha256':digest(path.read_bytes())})
    def set_row(identifier, status, procedure, evidence, scope):
        row = rows[identifier]
        changes.append({'id':identifier, 'before':row['status'], 'after':status, 'evidence':evidence})
        row.update(status=status, actual_test_or_required_procedure=procedure,
                   evidence_location=evidence, remaining_dependency_or_scope=scope)
    for identifier, row in rows.items():
        if identifier in BLOCKED:
            row['status'] = 'BLOCKED'
        elif identifier in UNRESOLVED_GENESIS_FAILURES:
            row['status'] = 'FAIL'
        elif identifier != 'H3':
            if row['status'] == 'PASS':
                row['historical_status'] = 'PASS'
            row['status'] = 'NOT TESTED'
    record_input(args.operation_receipt)
    receipt, summary = operation_summary(args.operation_receipt, args.source_sha, archive_hash)
    operations = receipt['operations']
    host_platform = receipt.get('host', {}).get('platform')
    if not isinstance(host_platform, str) or not host_platform:
        raise ValueError('Published operation receipt lacks its recorded host')
    completed = summary['status'] == 'PASS'
    operation_dir = Path(args.operation_receipt).parent
    py_index = operation_index(operations, ['-m', 'unittest', 'discover'])
    node_index = operation_index(operations, ['node', '--test'])
    python_log = log_text(operation_dir, py_index, 'stderr') + log_text(operation_dir, py_index, 'stdout')
    python_ok = bool(completed and py_index and summary['operations'][py_index-1].get('reported_python_tests', 0) > 0
                     and has_sequence(operations[py_index-1]['command'], ['-p', 'test_*.py'])
                     and re.search(r'^OK(?: \(skipped=\d+\))?$', python_log, re.MULTILINE))
    node_ok = bool(completed and node_index and summary['operations'][node_index-1].get('reported_node_tests', 0) > 0)
    for index in range(1, len(operations)+1):
        for stream in ('stdout', 'stderr'):
            path = operation_dir / f'operation-{index}.{stream}.txt'
            if path.is_file():
                record_input(path)
    http_index = operation_index(operations, ['node', 'evidence/UI_HTTP_WORKFLOW_REPLAY.cjs'])
    http = {}
    if http_index and completed:
        text = log_text(operation_dir, http_index, 'stdout')
        if text.strip():
            http = json.loads(text)
    http_ok = http.get('status') == 'PASS' and isinstance(http.get('checks'), list)
    launcher = any(any(Path(part.replace('\\','/')).name == 'launch.py' for part in row['command']) and '--help' in row['command'] for row in operations)
    set_row('H1', 'PASS' if completed and python_ok and node_ok else 'FAIL',
            'Verified immutable inventory/hash identity and operated the published customer archive.',
            'PUBLISHED-OPERATION.json; RELEASE-MANIFEST.json',
            'Only the recorded host and commands. Source/product-tree/digest identities were supplied by the trusted publication workflow; authenticated providers and commercial eligibility are separate.')
    set_row('A2', 'PASS' if completed and launcher and http_ok else 'NOT TESTED',
            'Executed packaged launcher help and actual loopback connector/workflow HTTP replay from extracted bytes.',
            'PUBLISHED-OPERATION.json; operation logs',
            'Authored inference fixtures; no live provider connection implied.')
    asset_dir = Path(args.asset_dir)
    browser_path = asset_dir / 'BROWSER-VERIFICATION.json'
    graphical = False
    graphical_failed = False
    if browser_path.is_file():
        record_input(browser_path)
        browser = read_json(browser_path)
        graphical_failed = browser.get('status') == 'FAIL'
        graphical = browser_passed(browser, args.source_sha, asset_dir) and str(browser.get('platform','')).lower() == 'linux'
    for identifier in ('A1', 'I1'):
        set_row(identifier, 'PASS' if graphical and node_ok else ('FAIL' if graphical_failed else 'NOT TESTED'),
                'Actual Linux browser first use, keyboard skip link, French/mobile layout, saved project reload and downloaded JSON reopen in fresh storage.',
                'BROWSER-VERIFICATION.json; matching screenshots; PUBLISHED-OPERATION.json',
                'Recorded Linux Chromium checks only, not general assistive-technology conformance or native installer qualification.')
    for identifier, modules in FIXTURE_MODULES.items():
        passed = python_ok and all(module_passed(python_log, module) for module in modules)
        scope = rows[identifier].get('historical_scope', rows[identifier].get('remaining_dependency_or_scope',''))
        set_row(identifier, 'PASS' if passed else 'NOT TESTED',
                'Executed all recorded tests in ' + ', '.join(modules) + ' from the final extracted archive.',
                'PUBLISHED-OPERATION.json; Python operation log', 'Authored fixture qualification on the recorded host (' + host_platform + '). ' + scope)
    omega_index = operation_index(operations, ['-m','bridge.genesis_next','demo'])
    omega_path = operation_dir/'OMEGA-DEMONSTRATION.json'
    freeze_index = operation_index(operations, ['scripts/qualify_genesis_successor.py','freeze'])
    successor_index = operation_index(operations, ['scripts/qualify_genesis_successor.py','run'])
    freeze_path = operation_dir/'OMEGA-FRESH-SOURCE-FREEZE.json'
    successor_path = operation_dir/'OMEGA-FRESH-SUCCESSOR.json'
    def command_output(index,path):
        if index is None or not path.is_file():
            return False
        command = operations[index-1]['command']
        if '--output' not in command or command.index('--output')+1 >= len(command) or Path(command[command.index('--output')+1]).resolve() != path.resolve():
            raise ValueError('GENESIS receipt is not the recorded extracted command output')
        record_input(path)
        return True
    if completed and command_output(omega_index,omega_path):
        if '--authorize' not in operations[omega_index-1]['command']:
            raise ValueError('GENESIS construction lacks explicit bounded experiment authorization')
        good = genesis_demo_passed(read_json(omega_path),content)
        set_row('O2','PASS' if good else 'FAIL','Executed the actual isolated HARNESS source upgrade; verified candidate bytes and raw baseline/candidate/ordinary acceptance outcomes.',
                'OMEGA-DEMONSTRATION.json; PUBLISHED-OPERATION.json','Authored bounded source recipe, not autonomous discovery or production promotion. The quote example cannot replace this GENESIS experiment.')
    if completed and command_output(freeze_index,freeze_path) and command_output(successor_index,successor_path):
        command = operations[successor_index-1]['command']
        if freeze_index >= successor_index or '--freeze' not in command or command.index('--freeze')+1 >= len(command) or Path(command[command.index('--freeze')+1]).resolve() != freeze_path.resolve():
            raise ValueError('GENESIS successor did not follow its recorded source freeze')
        good = genesis_successor_passed(freeze_path.read_bytes(),read_json(successor_path),content)
        set_row('O3','PASS' if good else 'FAIL','Checked the fresh post-freeze nonce, exact instances, source hashes and all four arms against independent arithmetic and retained-resource identities.',
                'OMEGA-FRESH-SOURCE-FREEZE.json; OMEGA-FRESH-SUCCESSOR.json; PUBLISHED-OPERATION.json','Distinct internal successor task with fresh instance values. Strong ordinary reuse ties; acquisition costs remain included. No new external task-family or complete-cost superiority claim.')
    omega_ui_index = operation_index(operations,['node','evidence/UI_GENESIS_NEXT_REPLAY.cjs'])
    if completed and omega_ui_index:
        text = log_text(operation_dir,omega_ui_index,'stdout')
        omega_ui = json.loads(text) if text.strip() else {}
        ui_ok = omega_ui.get('verdict') == 'PASSED IN SCOPE' and {'bounded experiment consent','conventional tie and unknown costs visible','successor lineage','evidence export','French labels'}.issubset(set(omega_ui.get('checks',[])))
        set_row('O5','PASS' if ui_ok else 'NOT TESTED','Executed the bilingual GENESIS interface replay with explicit authorization, source/evidence export, successor lineage and conventional-tie disclosure.',
                'UI_GENESIS_NEXT_REPLAY command stdout','Authored DOM protocol fixtures. Actual construction and fresh successor proof are separate O2/O3 gates; rendered-browser evidence is separate I1.')
    strategy_rows = http.get('strategies', [])
    strategies_ok = (http_ok and len(strategy_rows) == len(STRATEGIES)
                     and {row.get('strategy') for row in strategy_rows} == STRATEGIES
                     and all(row.get('passed') is True and type(row.get('model_calls')) is int and row['model_calls'] > 0 for row in strategy_rows)
                     and type(http.get('model_calls')) is int and http['model_calls'] >= 2
                     and 'builder critic repair executed with frozen cases' in http['checks']
                     and python_ok and module_passed(python_log, 'test_workflow_strategies')
                     and module_passed(python_log, 'test_independent_strategies'))
    set_row('C2', 'PASS' if strategies_ok else 'NOT TESTED',
            'Seven real connector/workflow strategy paths with authored responses, plus strategy and independent regression modules.',
            'UI_HTTP_WORKFLOW_REPLAY command stdout; Python operation log',
            'Executable policy fixtures only. Parallel/adaptive/adversarial execution is not evidence of live frontier access or a reasoning advantage.')
    paired_path = operation_dir / 'STRATEGY-DEMONSTRATION.json'
    paired_index = operation_index(operations, ['-m', 'bridge.strategy_demo'])
    if paired_path.is_file() and paired_index and completed:
        command = operations[paired_index-1]['command']
        if '--output' not in command or command.index('--output')+1 >= len(command) or Path(command[command.index('--output')+1]).resolve() != paired_path.resolve():
            raise ValueError('Paired receipt is not the recorded extracted command output')
        record_input(paired_path)
        paired = read_json(paired_path)
        paired_ok = paired_passed(paired, content)
        set_row('F2', 'PASS' if paired_ok else 'FAIL',
                'Executed the paired source-access protocol from the published archive; retained both arms, failures, equal budgets and zero-model-call conventional control.',
                'STRATEGY-DEMONSTRATION.json; PUBLISHED-OPERATION.json',
                'Deterministic authored responses and synthetic source transport. Information access and evidence retention only; no live web research, model superiority or complete economic advantage.')
    platform_results = []
    for system, launcher_name in [('Darwin','Launch-HARNESS.command'), ('Windows','Launch-HARNESS.cmd')]:
        path = asset_dir / f'PLATFORM-{system}-VERIFICATION.json'
        status = 'NOT TESTED'
        scope = 'No matching receipt supplied'
        if path.is_file():
            record_input(path)
            platform = read_json(path)
            if platform.get('source_revision') != args.source_sha or platform.get('archive_sha256') != archive_hash:
                raise ValueError('Platform receipt identifies a different source or archive')
            status = platform.get('status')
            if status not in {'PASS','FAIL','BLOCKED','NOT TESTED'}:
                raise ValueError('Unsupported platform status')
            if status == 'PASS':
                ops = platform.get('operations', [])
                if not ops or any(type(row.get('returncode')) is not int or row['returncode'] != 0 or not isinstance(row.get('command'), list) for row in ops):
                    raise ValueError('Platform PASS contradicts its operations')
                native = any(any(Path(str(part).replace('\\','/')).name == launcher_name for part in row['command']) and '--help' in row['command'] for row in ops)
                engine = any(has_sequence(row['command'], ['node','--test']) for row in ops)
                rendered = any(has_sequence(row['command'], ['node','evidence/UI_BROWSER_REPLAY.cjs']) for row in ops)
                expected_browser_os = 'darwin' if system == 'Darwin' else 'win32'
                host = str(platform.get('host', '')).lower()
                actual_os = (host.startswith(('macos-', 'darwin-')) if system == 'Darwin' else host.startswith('windows-'))
                actual_os = actual_os and platform.get('browser_report', {}).get('platform') == expected_browser_os
                if not (actual_os and native and engine and rendered and browser_passed(platform.get('browser_report',{}), args.source_sha, asset_dir, system+'-')):
                    status = 'NOT TESTED'
            scope = platform.get('scope', '')
        platform_results.append({'platform':system, 'status':status, 'scope':scope})
    platform_status = 'PASS' if all(row['status']=='PASS' for row in platform_results) else ('FAIL' if any(row['status']=='FAIL' for row in platform_results) else 'NOT TESTED')
    set_row('I2', platform_status,
            'Same exact archive on actual macOS and Windows: JavaScript, native launcher help, Python startup and headless browser first use.',
            'PLATFORM-Darwin-VERIFICATION.json; PLATFORM-Windows-VERIFICATION.json',
            'No full Python/security suite, authenticated model, signed installer, Safari or Finder/Explorer double-click claim. Repeated tests are per-platform executions. Native Codex isolation is a separate receipt and does not qualify authenticated construction.')
    docs_ok = REQUIRED_FILES.issubset(content) and any(name.startswith('examples/') for name in content)
    listing = content.get('commercial/listing.md', b'').decode('utf-8')
    docs_ok = docs_ok and '## English' in listing and '## Français' in listing
    set_row('H2', 'PASS' if docs_ok and completed else 'NOT TESTED',
            'Checked the exact archive inventory for guides, launchers, examples, notices and bilingual owner materials.',
            'RELEASE-MANIFEST.json; published archive',
            'Inventory and automated tests only; platform execution is separate, merchant decisions and commercial approval remain unresolved.')
    live_summary = {'status':'NOT TESTED', 'scope':'No final-source live receipt supplied'}
    if args.live_receipt:
        if not args.model_evidence_archive:
            raise ValueError('A live receipt requires the complete hash-verified model evidence ZIP')
        record_input(args.model_evidence_archive)
        _model_raw, model_manifest, model_files, model_digest = model_evidence_snapshot(args.model_evidence_archive, args.source_sha, args.source_product_tree)
        record_input(args.live_receipt)
        if Path(args.live_receipt).read_bytes() != model_files['HOSTED-LOCAL-QUALIFICATION.json']:
            raise ValueError('Flat live receipt differs from the model evidence archive manifest')
        live = read_json(args.live_receipt)
        if live.get('schema') != 'alpha-harness/hosted-local-qualification/v1':
            raise ValueError('Unsupported hosted live qualification schema')
        if live.get('source_revision') != args.source_sha or live.get('source_product_tree') != args.source_product_tree:
            raise ValueError('Live receipt is not from the final source and product tree')
        source_hashes_match(live, content)
        qualifications = live.get('qualifications', {})
        if (live.get('status') not in {'PASS','FAIL','RUNNING'} or set(qualifications) != LIVE_KEYS
                or any(value not in {'PASS','FAIL','NOT_TESTED'} for value in qualifications.values())):
            raise ValueError('Malformed live qualification statuses')
        validate_live_provenance(live, model_files, content)
        trusted = live.get('source_unchanged') is True and live['status'] in {'PASS','FAIL'}
        live_summary = {'status':live['status'] if trusted else 'NOT TESTED', 'reported_status':live['status'], 'source_unchanged':live.get('source_unchanged'),
                        'qualifications':qualifications, 'model_evidence_sha256':model_digest,
                        'release_qualification':live.get('release_qualification','NOT RECORDED'),
                        'scope':'Actual final-source hosted local model outcomes; individual failed and untested qualifications remain visible.'}
        def live_status(keys):
            if not trusted:
                return 'NOT TESTED'
            values = [qualifications[key] for key in keys]
            return 'PASS' if all(v=='PASS' for v in values) else ('FAIL' if any(v=='FAIL' for v in values) else 'NOT TESTED')
        set_row('B2', live_status(['local_inference']), 'Actual hosted local-model inference on the recorded final source.',
                Path(args.live_receipt).name, 'Recorded pinned model/server/host only; no remote API, Pro or all-local-runtime claim.')
        set_row('C1', live_status(['single_agent','multi_agent']), 'Actual local single-builder and separate-role multi-agent runs with independently checked artifacts.',
                Path(args.live_receipt).name, 'Same pinned local model; no general reasoning or strategy superiority. Live parallel qualification: '+qualifications['parallel_exploration']+'.')
        set_row('D1', live_status(['single_agent']), 'Actual local model constructed and externally executed a bounded arithmetic artifact.',
                Path(args.live_receipt).name, 'Narrow frozen task. Practical quote construction: '+qualifications['quote_construction']+'; independent quote export: '+qualifications['independent_export']+'; quote successor reuse: '+qualifications['successor_reuse']+'. Conditional authored economics are not empirical economic validation.')
    set_row('J1', 'PASS', 'Generated exact-source machine-readable JSON and readable Markdown from the selected actual receipts.',
            'QUALIFICATION-MATRIX.json; QUALIFICATION-MATRIX.md; RECONCILIATION.json',
            'Owner HTML and its visual receipt are generated separately. No commercial readiness is inferred.')
    matrix.update(source_revision=args.source_sha, source_product_tree=args.source_product_tree,
                  archive_sha256=archive_hash, status='CANDIDATE_NOT_COMMERCIALLY_QUALIFIED',
                  commercially_validated=False, squarespace_execution='EXCLUDED_BY_OWNER',
                  scope='Final-source owner matrix reconciled from supplied exact released-byte receipts. Authored fixtures, actual local-model outcomes, platform first use and unresolved commercial/authenticated gates retain separate scopes.',
                  criteria=list(rows.values()), platform_qualifications=platform_results,
                  live_qualification_summary=live_summary)
    audit = {'schema':'alpha-harness/release-evidence-reconciliation/v1', 'source_revision':args.source_sha,
             'source_product_tree':args.source_product_tree, 'archive_sha256':archive_hash,
             'inputs':inputs, 'decisions':changes, 'commercially_ready':False,
             'publication_trust':'Source/product-tree/archive identities originate in the verified GitHub publication workflow; this helper validates byte and receipt agreement without independently authenticating a remote service.'}
    return matrix, audit


def markdown_report(matrix):
    clean = lambda value: str(value).replace('|', r'\|').replace('\n', ' ')
    lines = ['# Exact-source qualification / Qualification de la source exacte', '',
             '**CANDIDATE — NOT COMMERCIALLY QUALIFIED / VERSION CANDIDATE**', '',
             'Source: '+matrix['source_revision'], 'Product tree: '+matrix['source_product_tree'],
             'Customer archive SHA-256: '+matrix['archive_sha256'], '',
             'Each PASS is limited to its recorded test. Authored responses do not establish live model access. No Squarespace activity was performed.', '',
             '| ID | Requirement | Status | Actual test and evidence | Remaining scope |',
             '|---|---|---|---|---|']
    for row in matrix['criteria']:
        lines.append('| '+' | '.join(map(clean, [row['id'],row['requirement'],row['status'],
            row['actual_test_or_required_procedure']+' Evidence: '+row['evidence_location'],row['remaining_dependency_or_scope']]))+' |')
    lines += ['', '## Français', '',
              'Les résultats sont limités aux essais et aux hôtes explicitement indiqués. Les modèles préparés, les inférences locales réelles, les essais de plateforme et les autorisations commerciales restent distincts. Les blocages ne sont pas effacés par la réussite technique d’une archive. Les comptes, autorisations et décisions marchandes manquants restent à obtenir.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--source-product-tree', required=True)
    parser.add_argument('--operation-receipt', type=Path, required=True)
    parser.add_argument('--asset-dir', type=Path, required=True)
    parser.add_argument('--live-receipt', type=Path)
    parser.add_argument('--model-evidence-archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        matrix, audit = reconcile(args)
        args.output.mkdir(parents=True, exist_ok=False)
        json_write(args.output/'QUALIFICATION-MATRIX.json', matrix)
        (args.output/'QUALIFICATION-MATRIX.md').write_text(markdown_report(matrix), encoding='utf-8')
        json_write(args.output/'RECONCILIATION.json', audit)
        if read_json(args.output/'QUALIFICATION-MATRIX.json') != matrix:
            raise ValueError('Generated matrix readback failed')
        print(json.dumps({'status':'GENERATED_CANDIDATE_MATRIX', 'source_revision':args.source_sha,
                          'archive_sha256':matrix['archive_sha256'], 'output':str(args.output),
                          'commercially_ready':False}, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'status':'REFUSED', 'error':str(error)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
