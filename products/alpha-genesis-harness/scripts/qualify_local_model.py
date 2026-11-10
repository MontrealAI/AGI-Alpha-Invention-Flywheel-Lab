#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise an already-running LOCAL model; never download or use a remote API."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge.adapters import Runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--kind', choices=['openai', 'responses', 'ollama'], default='openai')
    parser.add_argument('--runtime-description', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    config = {'local_only': True, 'session_budget_usd': 0, 'allow_paid_requests': False,
              'timeout_seconds': 60, 'providers': {'local': {'kind': args.kind,
              'base_url': args.base_url, 'output_limit_field': 'max_tokens', 'models': {
              args.model: {'input_per_million': 0, 'output_per_million': 0, 'streaming': True,
              'tool_calling': False, 'json_mode': False, 'max_output_tokens': 256,
              'input_token_overhead': 4096}}}}}
    runtime = Runtime(config)
    discovery = runtime.discover('local')
    results = []
    for i, stream in enumerate([False, True]):
        started = time.monotonic()
        events = []
        result = runtime.generate({'provider': 'local', 'model': args.model,
          'prompt': 'Write one short sentence explaining what a thermometer measures.',
          'max_output_tokens': 128, 'run_id': f'local-qualification-{i}', 'stream': stream}, events.append)
        results.append({'stream': stream, 'wall_seconds': time.monotonic() - started,
                        'event_count': len(events), 'result': result})
    receipt = {'schema': 'alpha-harness/local-live/v1', 'status': 'PASS',
               'runtime': args.runtime_description, 'platform': platform.platform(),
               'model': args.model, 'discovery': discovery, 'runs': results, 'config': config,
               'scope': 'Actual local model request/response operation only. Not frontier reasoning, tool calling or general agent quality. Runtime description is operator supplied; attach installation identities separately. No cloud API fallback or billed API request.',
               'source_sha256': {str(p.relative_to(PRODUCT)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in [PRODUCT/'bridge/adapters.py', PRODUCT/'bridge/streaming.py', Path(__file__).resolve()]}}
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'status': receipt['status'], 'runs': len(results), 'output': str(args.output)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
