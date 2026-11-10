#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run prospective hosted quote trial 004; no remote inference or arbitrary model code."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import urllib.request

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge.adapters import Runtime
from bridge.workflows import WorkflowService


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def ordinary(values):
    valid = all(value >= 0 for value in values.values())
    return {'valid': valid, 'declared_cost_cents': (values['quantity'] * values['unit_cost_cents'] + values['setup_cents'] + values['verification_cents'] + values['maintenance_cents']) if valid else None,
            'within_capacity': valid and values['quantity'] <= values['capacity']}


def source_hashes():
    return {str(path.relative_to(PRODUCT)): sha(path) for path in
            [PRODUCT/'bridge/adapters.py', PRODUCT/'bridge/streaming.py', PRODUCT/'bridge/workflows.py', PRODUCT/'bridge/services.py', PRODUCT/'bridge/workflow_strategies.py', PRODUCT/'bridge/instruments.py', Path(__file__).resolve()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; refuses existing path')
    parser.add_argument('--model-receipt', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    protocol_path = PRODUCT/'evidence/LOCAL-QUOTE-PROTOCOL-004.json'
    protocol = read(protocol_path)
    before = source_hashes()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=PRODUCT, text=True).strip()
    product_tree = subprocess.check_output(['git', 'rev-parse', 'HEAD:products/alpha-genesis-harness'], cwd=PRODUCT, text=True).strip()
    version = subprocess.run([str(args.binary), '--version'], capture_output=True, text=True, timeout=10)
    result = {'schema': 'alpha-harness/live-quote-qualification/v4', 'trial_id': 'quote-trial-004',
              'structured_output': protocol['structured_output'], 'source_revision': revision, 'product_tree_sha': product_tree, 'protocol_sha256': sha(protocol_path),
              'source_sha256': before, 'runtime_binary_sha256': sha(args.binary),
              'runtime_version': (version.stdout + version.stderr).strip(),
              'model_download': read(args.model_receipt), 'model_sha256_matches_receipt': sha(args.model) == read(args.model_receipt)['sha256'],
              'arms': [], 'outside_execution': [], 'numerical_boundary': [], 'status': 'RUNNING',
              'claims': {'live_local_inference': False, 'useful_artifact_constructed': False, 'successor_reuse_accepted': False,
                         'economic_superiority': 'NOT_ESTABLISHED', 'novelty': 'NOT_ESTABLISHED', 'commercial_validation': 'NOT_ESTABLISHED'},
              'full_cost_boundaries': protocol['full_cost_boundaries']}
    if not result['model_sha256_matches_receipt']:
        raise ValueError('Model identity differs from verified download receipt')
    for case in protocol['manufacturing_cases'] + protocol['lab_cases']:
        if ordinary(case['input']) != case['expected']:
            raise ValueError('Preregistered expectation differs from independent ordinary formula')
    result['ordinary_control'] = {'status': 'PASS', 'model_calls': 0, 'cases': len(protocol['manufacturing_cases']) + len(protocol['lab_cases']),
       'method': 'Direct conventional scalar arithmetic and sign/capacity comparisons, same contract and inputs.',
       'cost_scope': 'No inference requests. Human implementation, review and operating cost are unmeasured, not zero.'}
    write(args.output/'RESULT.json', result)
    model_id = 'Qwen3-4B-Instruct-2507-Q4_K_M'
    config = {'local_only': True, 'session_budget_usd': 0, 'allow_paid_requests': False, 'timeout_seconds': 600,
              'max_attempts': 1, 'providers': {'local': {'kind': 'openai', 'base_url': 'http://127.0.0.1:18767/v1',
              'output_limit_field': 'max_tokens', 'models': {model_id: {'input_per_million': 0, 'output_per_million': 0,
              'max_output_tokens': 4096, 'input_token_overhead': 4096, 'json_mode': True}}}}}
    base_runtime = Runtime(config)
    observations = []
    class ObservedRuntime:
        def __getattr__(self, name):
            return getattr(base_runtime, name)
        def generate(self, data, on_event=None):
            start = time.monotonic()
            observation = {'run_id': data['run_id'], 'prompt_sha256': hashlib.sha256(data['prompt'].encode()).hexdigest()}
            try:
                response = base_runtime.generate(data, on_event=on_event)
                observation['response'] = response
                return response
            except Exception as error:
                observation['error_code'] = getattr(error, 'code', type(error).__name__)
                raise
            finally:
                observation['wall_seconds'] = time.monotonic() - start
                observations.append(observation)
    runtime = ObservedRuntime()
    command = [str(args.binary), '-m', str(args.model), '--host', '127.0.0.1', '--port', '18767', '-c', '16384',
               '-t', '2', '--parallel', '1', '--n-gpu-layers', '0', '--no-webui', '--reasoning-budget', '0',
               '--chat-template-kwargs', '{"enable_thinking":false}', '--alias', model_id]
    objective = ('Construct quote.json, a declared-cost and capacity planning calculator. Inputs: quantity, unit_cost_cents, setup_cents, verification_cents, maintenance_cents, capacity. '
       'valid is true only when all six numeric inputs are nonnegative. If valid, declared_cost_cents = quantity*unit_cost_cents + setup_cents + verification_cents + maintenance_cents; within_capacity = quantity<=capacity. '
       'If invalid return valid=false, declared_cost_cents=null, within_capacity=false. Quantity zero still includes fixed costs. '
       'This is an illustrative planning estimate, not a full-cost business or profitability claim; unknown costs remain unknown. Return only supported JSON actions. '
       'Instrument expressions cannot refer to other output fields: repeat the required conditions within each output. Use the exact output names and input field names. Do not substitute Python code. ' + protocol['construction_format_instruction'])
    roles = {role: {'provider': 'local', 'model': model_id} for role in ['builder', 'critic']}
    service = None
    with (args.output/'runtime.log').open('w') as log:
        server = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            for attempt in range(120):
                if server.poll() is not None:
                    raise RuntimeError('Local model server exited before readiness')
                try:
                    urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:18767/health', timeout=1).read()
                    break
                except Exception:
                    time.sleep(.25)
            else:
                raise TimeoutError('Local model did not become ready within declared startup probe')
            discovery = runtime.discover('local')
            result['discovery'] = discovery
            workspace = args.output/'private-projects'
            service = WorkflowService(runtime, workspace)
            initial_id = None
            for arm in protocol['arms']:
                if arm['id'] == 'ordinary_direct_formula':
                    continue
                cases = protocol['manufacturing_cases'] if arm['id'] == 'manufacturing_construct' else protocol['lab_cases']
                if arm['id'] == 'lab_inherit' and initial_id is None:
                    result['arms'].append({'id': arm['id'], 'status': 'BLOCKED', 'reason': 'Original construction did not pass; no verified capability to inherit.'})
                    continue
                if arm['id'] == 'lab_inherit':
                    # A genuine close/reopen validates persistence before successor use.
                    service.close()
                    service = WorkflowService(runtime, workspace)
                spec = {'objective': objective, 'context': ('Manufacturing quote planning.' if arm['id'] == 'manufacturing_construct' else
                    'Distinct successor application: batch laboratory service pricing/capacity. quantity=samples, unit cost=consumables per sample, setup=assay setup, verification=QC, maintenance=allocated instrument maintenance, capacity=available batch slots. All numbers are authored examples, not measured market data. Same additive mechanism; current acceptance must be rechecked.'),
                    'roles': roles, 'strategy': 'actor-critic', 'acceptance': [{'kind': 'instrument', 'artifact': 'quote.json', 'input': c['input'], 'expected': c['expected']} for c in cases],
                    'max_iterations': 2, 'max_actions': 8, 'max_output_tokens': 4096, 'local_only': True,
                    'tool_permissions': ['construct_instrument', 'run_instrument', 'read_artifact', 'write_document', 'write_dataset']}
                if arm['id'] == 'lab_inherit':
                    spec['inherited_capability'] = initial_id
                    spec['objective'] = spec['objective'].replace(protocol['construction_format_instruction'], protocol['inheritance_format_instruction'])
                started = time.monotonic()
                observation_start = len(observations)
                state = service.create(spec)
                while state['status'] == 'ready':
                    state = service.step(state['id'])
                    print(json.dumps({'arm': arm['id'], 'status': state['status'], 'phase': state['phase'], 'iteration': state['iteration'], 'actions': state['actions']}), flush=True)
                archive = service.export(state['id'])
                write(args.output/(arm['id'] + '-project.json'), archive)
                arm_result = {'id': arm['id'], 'status': state['status'], 'wall_seconds': time.monotonic() - started,
                     'model_calls': state['model_calls'], 'actions': state['actions'], 'verification': state['verification'], 'state_id': state['id'],
                     'events': state['events'], 'observations': observations[observation_start:], 'artifact_hashes': state['artifacts'],
                     'archive_sha256': sha(args.output/(arm['id'] + '-project.json'))}
                result['arms'].append(arm_result)
                result['claims']['live_local_inference'] |= bool(arm_result['observations'])
                write(args.output/'RESULT.json', result)
                if state['status'] != 'complete':
                    continue
                if arm['id'] == 'manufacturing_construct':
                    initial_id = state['id']
                    result['claims']['useful_artifact_constructed'] = True
                if arm['id'] == 'lab_inherit':
                    result['claims']['successor_reuse_accepted'] = True
                export_dir = args.output/arm['id']
                export_dir.mkdir()
                for name, content in archive['files'].items():
                    # Export filenames have already passed the service's narrow filename contract.
                    (export_dir/name).write_text(content)
                for case in cases:
                    input_file = export_dir/(case['name'] + '-input.json')
                    write(input_file, case['input'])
                    proc = subprocess.run([sys.executable, str(export_dir/'RUN_INSTRUMENT.py'), str(export_dir/'quote.json'), str(input_file)],
                                           cwd=export_dir, capture_output=True, text=True, timeout=20)
                    output = json.loads(proc.stdout)['output'] if proc.returncode == 0 else None
                    passed = proc.returncode == 0 and output == case['expected'] and output == ordinary(case['input'])
                    result['outside_execution'].append({'arm': arm['id'], 'case': case['name'], 'exit_code': proc.returncode, 'output': output,
                        'expected': case['expected'], 'ordinary_control': ordinary(case['input']), 'passed': passed})
                overflow = dict(cases[0]['input'], quantity=2**53)
                input_file = export_dir/'outside-range-input.json'
                write(input_file, overflow)
                proc = subprocess.run([sys.executable, str(export_dir/'RUN_INSTRUMENT.py'), str(export_dir/'quote.json'), str(input_file)],
                    cwd=export_dir, capture_output=True, text=True, timeout=20)
                result['numerical_boundary'].append({'arm': arm['id'], 'input_quantity': 2**53, 'refused': proc.returncode != 0,
                    'reason': 'Input integer exceeds the documented exact portable range; no accepted result claimed.'})
                write(args.output/'RESULT.json', result)
        except Exception as error:
            result['status'] = 'FAIL'
            result['execution_error'] = {'type': type(error).__name__, 'message': str(error)[:1000]}
            result['final_source_sha256'] = source_hashes()
            result['source_unchanged'] = before == result['final_source_sha256']
            write(args.output/'RESULT.json', result)
            raise
        finally:
            if service is not None:
                service.close()
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
    after = source_hashes()
    result['source_unchanged'] = before == after
    result['final_source_sha256'] = after
    result['resource'] = {'child_cpu_seconds': resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
                          'api_paid_requests': 0, 'local_compute_full_cost': None}
    result['status'] = 'PASS' if (all(a['status'] == 'complete' for a in result['arms']) and all(v['passed'] for v in result['outside_execution'])
                                and all(v['refused'] for v in result['numerical_boundary']) and result['source_unchanged']) else 'FAIL'
    result['comparison_verdict'] = 'Conventional direct arithmetic accepts every fixed case with zero inference. Inheritance can reuse a verified artifact, but no superior outcome or complete-cost advantage over that capable control is established. Initial construction and all failed attempts remain charged/visible.'
    write(args.output/'RESULT.json', result)
    print(json.dumps({'status': result['status'], 'output': str(args.output/'RESULT.json')}), flush=True)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
