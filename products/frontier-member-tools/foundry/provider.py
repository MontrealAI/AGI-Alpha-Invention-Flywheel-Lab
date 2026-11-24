"""Explicit one-request local HARNESS provider companion. Never invoke it from Pages."""

import argparse
from decimal import Decimal
from hashlib import sha256
import json
import sys
from time import perf_counter_ns
from urllib.parse import urlsplit
from uuid import uuid4
from pathlib import Path

from bridge.adapters import BridgeError, Runtime, strict_json


def read(path, limit):
    with Path(path).open('rb') as file:
        data = file.read(limit + 1)
    if not data or len(data) > limit:
        raise BridgeError('FILE', 'File is empty or exceeds the stated byte bound.')
    return data


def install(config):
    if not isinstance(config, dict):
        raise BridgeError('CONFIG', 'Use a local HARNESS configuration object.')
    # One explicit authorization covers one dispatch, even after a provider error.
    return Runtime({**config, 'local_only': config.get('local_only', True), 'max_attempts': 1})


def request_plan(runtime, provider, model, prompt, limit, stream):
    m = provider.models.get(model)
    if not m or not provider.ready or not 0 < limit <= m.max_output_tokens or (stream and not m.streaming):
        raise BridgeError('MODEL', 'Choose a ready configured model and supported settings.')
    size = len(prompt.encode('utf-8')) + m.input_token_overhead
    if m.context_window is not None and size + limit > m.context_window:
        raise BridgeError('CONTEXT', 'The declared context window is too small for these bounds.')
    reserved = (Decimal(size) * m.input_price + Decimal(limit) * m.output_price) / 1_000_000
    if provider.remote and (not runtime.allow_paid or reserved > runtime.budget.limit):
        raise BridgeError('BUDGET', 'Remote inference requires declared applicable prices and an explicit sufficient USD budget.')
    plan = {'provider': provider.id, 'kind': provider.kind, 'model': model, 'endpoint': provider.base,
            'remote': provider.remote, 'prompt_sha256': sha256(prompt.encode()).hexdigest(),
            'max_output_tokens': limit, 'input_token_bound': size, 'stream': stream,
            'user_rates_usd_per_million': {'input': str(m.input_price), 'output': str(m.output_price)},
            'accounting_ceiling_usd': str(reserved) if provider.remote else None,
            'authorized_session_budget_usd': str(runtime.budget.limit) if provider.remote else None,
            'accounted_cost_is_vendor_cap': False, 'complete_cost_known': False, 'max_requests': 1}
    plan['approval_sha256'] = sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('command', choices=['status','discover','plan','generate'])
    parser.add_argument('--provider')
    parser.add_argument('--model')
    parser.add_argument('--prompt')
    parser.add_argument('--formula-mission', help='Compile scalar assignments against this local mission file')
    parser.add_argument('--candidate-file', type=Path, help='Write the returned instrument to a new local JSON file')
    parser.add_argument('--tokens', type=int, default=512)
    parser.add_argument('--stream', action='store_true')
    parser.add_argument('--catalog-consent', help='Exact configured remote hostname to query')
    parser.add_argument('--approve', help='Exact hash of a reviewed remote request plan')
    params = parser.parse_args()
    runtime = install(strict_json(read(params.config, 128 * 1024)))
    if params.command == 'status':
        return runtime.status()
    p = runtime.provider(params.provider)
    host = urlsplit(p.base).hostname
    if not p.remote and host not in {'127.0.0.1', '::1'}:
        raise BridgeError('LOCAL_HOST', 'Use a numeric loopback address for local connections.')
    if params.command == 'discover':
        if p.remote and params.catalog_consent != host:
            raise BridgeError('CONSENT', 'Review the configured host and explicitly approve remote discovery.')
        return runtime.discover(p.id)
    if params.candidate_file and params.candidate_file.exists():
        raise BridgeError('FILE_EXISTS', 'Choose a new candidate file.')
    if not params.prompt:
        raise BridgeError('INPUT', 'Generate and review a prompt file before dispatch.')
    prompt = read(params.prompt, 24 * 1024).decode('utf-8')
    formula_task = None
    if params.formula_mission:
        if not params.candidate_file:
            raise BridgeError('INPUT', 'A formula mission requires a separate candidate output file.')
        formula_task = strict_json(read(params.formula_mission, 128 * 1024))
        if not isinstance(formula_task, dict) or formula_task.get('schema') != 'frontier/foundry-mission-v1':
            raise BridgeError('MISSION', 'Use a valid local mission file.')
    plan = request_plan(runtime, p, params.model, prompt, params.tokens, params.stream)
    if params.command == 'plan':
        return plan
    if p.remote and params.approve != plan['approval_sha256']:
        raise BridgeError('CONSENT', 'The request differs from the approved remote plan. Preview and approve this exact plan.')
    once = False
    def progress(_):
        nonlocal once
        if not once:
            print('Provider response received; waiting for final usage.', file=sys.stderr, flush=True)
            once = True
    start = perf_counter_ns()
    print('Dispatching one request to the selected provider.', file=sys.stderr, flush=True)
    try:
        result = runtime.generate({'provider': p.id, 'model': params.model, 'prompt': prompt,
                                   'max_output_tokens': params.tokens, 'run_id': uuid4().hex,
                                   'stream': params.stream},
                                  on_event=progress if params.stream else None, expected_provider=p)
    except BridgeError as error:
        # A dispatched request may have been billed before a transport or validation failure.
        print(json.dumps({'status':'FAILED', 'code':error.code, 'elapsed_ns':perf_counter_ns()-start,
                          'local_budget':runtime.budget.view()}), file=sys.stderr)
        raise
    receipt = {**result, 'elapsed_ns':perf_counter_ns()-start, 'plan_sha256':plan['approval_sha256'],
               'charged_amount_usd':None}
    if params.candidate_file:
        raw = receipt.pop('text').strip()
        if raw.startswith('```json') and raw.endswith('```'):
            raw = raw[7:-3].strip()
        try:
            if formula_task:
                from formulas import formula_candidate
                draft = formula_candidate(formula_task, raw)
            else:
                draft = strict_json(raw)
            if not isinstance(draft, dict) or set(draft) != {'name','inputs','outputs'}:
                raise BridgeError('CANDIDATE', 'Return a bounded HARNESS instrument in JSON.')
            data = json.dumps(draft, ensure_ascii=False, allow_nan=False) + '\n'
            with params.candidate_file.open('x', encoding='utf-8') as handle:
                handle.write(data)
        except (BridgeError, OSError, ValueError, RecursionError) as error:
            receipt['candidate_file_status'] = 'INVALID_OR_NOT_WRITTEN'
            print(json.dumps(receipt, ensure_ascii=False), file=sys.stderr)
            raise BridgeError('CANDIDATE_FILE', 'Inspect the provider usage. The reply was not written.') from error
        receipt['candidate_file_status'] = 'UNVERIFIED'
    return receipt


if __name__ == '__main__':
    try:
        print(json.dumps(main(), ensure_ascii=False, allow_nan=False))
    except BridgeError as error:
        print('HARNESS request blocked or stopped (' + error.code + ').', file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print('Cancelled locally. Already dispatched provider work can continue and incur usage.', file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        print('Invalid local configuration or file. Consult the offline guide.', file=sys.stderr)
        sys.exit(2)
