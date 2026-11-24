"""Run one registered successor comparison on an explicitly selected loopback model."""

import argparse
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile
from time import perf_counter_ns
from urllib.parse import urlsplit
from uuid import uuid4

from bridge.adapters import BridgeError, strict_json
from formulas import bound_expansion, formula_candidate
from provider import install, read, request_plan

ROOT = Path(__file__).resolve().parent
MAX_FILE = 128 * 1024


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()


def atomic(path, value):
    with NamedTemporaryFile(dir=path.parent, delete=False) as file:
        temp = Path(file.name)
        try:
            file.write(encoded(value))
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            file.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


@contextmanager
def lock(directory):
    # The lock belongs to the open handle and releases when the process exits.
    with (directory / 'lock').open('a+b') as file:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise BridgeError('BUSY', 'A construction run is active in this workspace.') from error
        yield


def replace_bindings(term, bindings, used):
    if isinstance(term, dict) and set(term) == {'field'}:
        name = term['field']
        if name in bindings:
            used.add(name)
            return bindings[name]
    if isinstance(term, dict):
        return {key:replace_bindings(value, bindings, used) for key, value in term.items()}
    if isinstance(term, list):
        return [replace_bindings(value, bindings, used) for value in term]
    return term


def pending(status):
    return {'status':status, 'candidate':None, 'elapsed_ns':None, 'usage':None, 'reason':None, 'bindings_used':[]}


def construct(runtime, provider, plan, arm):
    attempt = pending('PROVIDER_ERROR')
    start = perf_counter_ns()
    try:
        response = runtime.generate({
            'provider':provider.id, 'model':plan['model'], 'prompt':plan['prompts'][arm],
            'max_output_tokens':plan['output_tokens'], 'run_id':uuid4().hex,
        }, expected_provider=provider)
        attempt['usage'] = response['usage']
        reported = response['usage']['output_tokens']
        if reported is not None and reported > plan['output_tokens']:
            raise BridgeError('OUTPUT_LIMIT', 'Reported model usage exceeded the registered output limit.')
        attempt['status'] = 'NO_CANDIDATE'
        draft = formula_candidate(plan['task'], response['text'])
        used = set()
        if arm == 'retained':
            draft = replace_bindings(draft, plan['bindings'], used)
            bound_expansion(draft)
        # Use the same validator as the Pages application before sealing anything.
        checked = subprocess.run(['node', str(ROOT / 'study-seal.mjs')],
                                 input=encoded({'task':plan['task'], 'candidate':draft}), capture_output=True)
        if checked.returncode == 0:
            attempt.update(status='SEALED', candidate=draft, bindings_used=sorted(used))
        else:
            attempt['reason'] = 'SEAL_REJECTED'
    except BridgeError as error:
        attempt['reason'] = error.code
    except (ValueError, RecursionError):
        attempt['reason'] = 'FORMULA_REJECTED'
    finally:
        attempt['elapsed_ns'] = perf_counter_ns() - start
    return attempt


def run(args):
    preview = subprocess.run(['node', str(ROOT / 'study-cli.mjs'), 'plan', str(args.plan)],
                             check=True, capture_output=True)
    plan = strict_json(preview.stdout)
    raw_config = read(args.config, MAX_FILE)
    runtime = install(strict_json(raw_config))
    provider = runtime.provider(args.provider)
    if not runtime.local_only or provider.remote or urlsplit(provider.base).hostname not in {'127.0.0.1','::1'}:
        raise BridgeError('LOCAL_ONLY', 'Successor studies require a selected numeric loopback provider and local_only.')
    for prompt in plan['prompts'].values():
        request_plan(runtime, provider, plan['model'], prompt, plan['output_tokens'], False)
    directory = args.workspace
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock(directory):
        identity = {'study_sha256':plan['study_sha256'], 'provider':provider.id,
                    'config_sha256':sha256(raw_config).hexdigest()}
        stamp = directory / 'plan.json'
        if stamp.exists():
            if strict_json(read(stamp, MAX_FILE)) != identity:
                raise BridgeError('PLAN_CHANGED', 'Use the original plan and provider or a new workspace.')
        else:
            atomic(stamp, identity)
        results = {}
        dispatched = False
        for arm in ('direct','ordinary','retained'):
            marker, output = directory / (arm + '.started'), directory / (arm + '.json')
            if output.exists():
                results[arm] = strict_json(read(output, MAX_FILE))
            elif marker.exists():
                # Dispatch status after a crash is uncertain. Consume its reservation.
                results[arm] = pending('INTERRUPTED')
            elif args.step and dispatched:
                results[arm] = pending('PENDING')
            else:
                with marker.open('xb') as file:
                    file.write(b'Reserved one local request.\n')
                    file.flush()
                    os.fsync(file.fileno())
                print(f'Constructing {arm} with the registered local budget.', file=sys.stderr, flush=True)
                try:
                    attempt = construct(runtime, provider, plan, arm)
                except KeyboardInterrupt:
                    atomic(output, pending('INTERRUPTED'))
                    raise
                atomic(output, attempt)
                results[arm] = attempt
                dispatched = True
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--provider', required=True)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--step', action='store_true', help='At most one new request on this invocation')
    try:
        print(encoded(run(parser.parse_args())).decode(), end='')
    except BridgeError as error:
        print('Study halted (' + error.code + ').', file=sys.stderr)
        sys.exit(2)
    except (OSError, ValueError, subprocess.SubprocessError, RecursionError):
        print('Study halted. Verify the local plan, runtime and workspace files.', file=sys.stderr)
        sys.exit(2)
    except KeyboardInterrupt:
        print('Study paused. The interrupted request will not be sent again.', file=sys.stderr)
        sys.exit(130)
