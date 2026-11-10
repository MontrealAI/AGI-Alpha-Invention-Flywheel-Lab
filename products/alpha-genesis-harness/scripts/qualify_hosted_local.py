#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded public-runner local inference. New orchestration: qualification occurs only after actual CI execution."""
from __future__ import annotations
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import socket
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from scripts.package_release import safe_file
REPO = PRODUCT.parents[1]
PRODUCT_REL = PRODUCT.relative_to(REPO).as_posix()
BINARY_URL = 'https://github.com/ggml-org/llama.cpp/releases/download/b12242/llama-b12242-bin-ubuntu-x64.tar.gz'
BINARY_ARCHIVE_SHA = '909eef25cd53e6601c8a07c866d8dbb2983e74177088d55182137a8fb8255d62'
BINARY_ARCHIVE_BYTES = 23158635
MODEL_REPO = 'bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF'
MODEL_REVISION = 'ae44f08e1392f39c0e474af10c3ff8355c8b6688'
MODEL_FILE = 'Qwen_Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
MODEL_URL = 'https://huggingface.co/' + MODEL_REPO + '/resolve/' + MODEL_REVISION + '/' + MODEL_FILE
MODEL_SHA = '2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e'
MODEL_BYTES = 2497280736
ORIGINAL_REVISION = 'cdbee75f17c01a7cc42f958dc650907174af0554'
LICENSE_URL = 'https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/resolve/' + ORIGINAL_REVISION + '/LICENSE'
REQUIRED_RELEASE_CHECKS = ('local_inference', 'single_agent', 'multi_agent', 'parallel_exploration')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n')


def read(path):
    return json.loads(path.read_text()) if path.is_file() else None


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def git(*arguments):
    return subprocess.check_output(['git', *arguments], cwd=REPO, text=True).strip()


def source_snapshot():
    paths = git('ls-files', '--', PRODUCT_REL).splitlines()
    return {name[len(PRODUCT_REL)+1:]: sha(REPO/name) for name in paths if (REPO/name).is_file()}


def download(url, path, expected_sha, expected_bytes):
    start = time.monotonic()
    part = path.with_suffix(path.suffix + '.part')
    h = hashlib.sha256()
    count = 0
    with urllib.request.urlopen(url, timeout=120) as response, part.open('wb') as target:
        while block := response.read(4 * 1024 * 1024):
            count += len(block)
            if count > expected_bytes or time.monotonic() - start > 900:
                raise ValueError('Download exceeded its pinned size or 900-second transfer budget.')
            h.update(block)
            target.write(block)
    if count != expected_bytes or h.hexdigest() != expected_sha:
        raise ValueError('Downloaded bytes do not match the pinned upstream identity.')
    part.rename(path)
    return {'url': url, 'bytes': count, 'sha256': h.hexdigest(), 'verified': True,
            'wall_seconds': time.monotonic() - start}


def assert_port_free(port):
    # The hosted job owns a fresh process namespace; refuse an existing listener before launching the pinned binary.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', port))


def sanitized_log(text):
    text = re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[REDACTED_QUERY]', text)
    return re.sub(r'(?i)(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token)\s*[:=]\s*\S+',
                  r'\1=[REDACTED]', text)


def run(command, log_path, timeout, environment):
    start = time.monotonic()
    with log_path.open('w') as log:
        process = subprocess.Popen(command, cwd=PRODUCT, env=environment,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        interrupted = False
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            interrupted = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                returncode = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                returncode = process.wait(timeout=10)
    return {'entrypoint': command[1], 'returncode': returncode, 'timed_out': interrupted,
            'deadline_seconds': timeout, 'wall_seconds': time.monotonic() - start}


def qualified_workflow(item):
    external = item.get('external_execution', {})
    return (item.get('status') == 'complete' and item.get('verification', {}).get('passed') is True
            and external.get('returncode') == 0
            and (external.get('result') or {}).get('output') == {'result': 34}
            and item.get('strong_control', {}).get('accepted') is True)


def release_qualification(record):
    return 'PASS' if (record.get('source_unchanged') is True and not record.get('error')
        and all(record.get('qualifications', {}).get(key) == 'PASS' for key in REQUIRED_RELEASE_CHECKS)) else 'FAIL'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True, help='New private scratch directory outside repository')
    parser.add_argument('--publish', type=Path, required=True, help='New output directory containing only allowlisted public artifacts')
    args = parser.parse_args()
    work, public = args.work.resolve(), args.publish.resolve()
    if work.is_relative_to(REPO) or public.is_relative_to(REPO) or public.is_relative_to(work) or work.is_relative_to(public):
        raise ValueError('Work and publication paths must be separate and outside the repository.')
    if git('status', '--porcelain', '--', PRODUCT_REL):
        raise ValueError('Qualification requires an unchanged committed product tree.')
    work.mkdir(parents=True, exist_ok=False)
    public.mkdir(parents=True, exist_ok=False)
    source = source_snapshot()
    record = {'schema': 'alpha-harness/hosted-local-qualification/v1', 'status': 'RUNNING',
              'release_qualification': 'NOT_TESTED',
              'required_release_qualifications': list(REQUIRED_RELEASE_CHECKS),
              'release_gate': 'Prospectively declared before hosted execution: required core checks are local inference, single-agent, actor/critic multi-agent and parallel exploration. Release qualification additionally requires unchanged sources and no orchestration error. Quote construction, independent quote export and quote successor reuse are additional examples; their original acceptance checks and overall status remain unchanged and any failure remains visible.',
              'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'source_revision': git('rev-parse', 'HEAD'),
              'source_product_tree': git('rev-parse', 'HEAD:' + PRODUCT_REL),
              'source_sha256': {name: digest for name, digest in source.items() if safe_file(name)},
              'source_sha256_scope': 'Archive-eligible tracked product files; source_unchanged separately guards the full tracked snapshot and git status.',
              'source_unchanged': None,
              'ci': {key: os.environ.get(key) for key in ['GITHUB_REPOSITORY', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA']},
              'host': {'platform': sys.platform, 'python': sys.version.split()[0], 'cpu_count_reported': os.cpu_count(),
                       'inference_threads': 2, 'accelerator': 'CPU'},
              'qualifications': {key: 'NOT_TESTED' for key in ['local_inference', 'single_agent', 'multi_agent', 'parallel_exploration', 'quote_construction', 'successor_reuse', 'independent_export']},
              'commands': [], 'downloads': {}, 'api_paid_requests': 0,
              'complete_cost_known': False,
              'cost_scope': 'Local CPU requests only. Hosted runner allowance, electricity, setup, human review, maintenance and all prior failures are not represented as zero full cost.',
              'claims': {'novelty': 'NOT_ESTABLISHED', 'economic_superiority': 'NOT_ESTABLISHED', 'commercial_validation': 'NOT_ESTABLISHED'},
              'qualification_rule': 'Each PASS is derived from actual completed model invocations, frozen-case verification and exported evaluator outcomes. A driver exit code alone is insufficient. Previous workspace trials are separate historical observations.'}
    write(public/'HOSTED-LOCAL-QUALIFICATION.json', record)
    protocol_path = PRODUCT/'evidence/LOCAL-QUOTE-PROTOCOL-003.json'
    protocol = read(protocol_path)
    for name in ['LOCAL-QUOTE-PROTOCOL.json', 'LOCAL-QUOTE-PROTOCOL-002-RECOVERED.json', 'LOCAL-QUOTE-PROTOCOL-003.json', 'LOCAL-QUOTE-OBSERVED-HISTORY.json']:
        path = PRODUCT/'evidence'/name
        if path.is_file():
            shutil.copyfile(path, public/name)
    quote, workflows = None, None
    try:
        archive = work/'llama-b12242.tar.gz'
        weights = work/'qwen3-4b-instruct-2507.gguf'
        record['downloads']['runtime_archive'] = download(BINARY_URL, archive, BINARY_ARCHIVE_SHA, BINARY_ARCHIVE_BYTES)
        runtime_dir = work/'llama'
        runtime_dir.mkdir()
        with tarfile.open(archive) as package:
            package.extractall(runtime_dir, filter='data')
        binaries = [p for p in runtime_dir.rglob('llama-server') if p.is_file()]
        if len(binaries) != 1:
            raise ValueError('Pinned runtime archive did not contain exactly one server binary.')
        binary = binaries[0]
        record['downloads']['runtime_binary_sha256'] = sha(binary)
        record['downloads']['model'] = download(MODEL_URL, weights, MODEL_SHA, MODEL_BYTES)
        with urllib.request.urlopen(LICENSE_URL, timeout=60) as response:
            license_bytes = response.read(100000)
        if b'Apache License' not in license_bytes or b'Version 2.0' not in license_bytes:
            raise ValueError('Pinned original-model license did not identify Apache2.0.')
        model_receipt = dict(record['downloads']['model'], model_license='Apache-2.0',
                             original_model='https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507',
                             original_revision=ORIGINAL_REVISION, quantization_source=MODEL_REPO,
                             quantization_revision=MODEL_REVISION, license_url=LICENSE_URL,
                             license_sha256=hashlib.sha256(license_bytes).hexdigest(),
                             upstream_lfs={'sha256': MODEL_SHA, 'size': MODEL_BYTES},
                             upstream_digest_matches=True)
        write(work/'MODEL-DOWNLOAD.json', model_receipt)
        write(public/'LOCAL-MODEL-DOWNLOAD.json', model_receipt)
        write(public/'LOCAL-RUNTIME-DOWNLOAD.json', record['downloads']['runtime_archive'])
        (public/'QWEN-APACHE-2-LICENSE.txt').write_bytes(license_bytes)
        # No GitHub token, cloud credentials, subscription sessions or arbitrary inherited variables reach inference.
        environment = {key: os.environ[key] for key in ['PATH', 'HOME', 'LANG', 'LC_ALL', 'TMPDIR'] if key in os.environ}
        environment.update(PYTHONUNBUFFERED='1', LD_LIBRARY_PATH=str(binary.parent), NO_PROXY='127.0.0.1,localhost')
        quote_dir = work/'quote003'
        assert_port_free(18767)
        record['commands'].append(run([sys.executable, str(PRODUCT/'scripts/qualify_quote_workflow_003.py'),
            '--binary', str(binary), '--model', str(weights), '--model-receipt', str(work/'MODEL-DOWNLOAD.json'),
            '--output', str(quote_dir)], work/'quote-command.log', 2700, environment))
        quote = read(quote_dir/'RESULT.json')
        if quote is not None:
            shutil.copyfile(quote_dir/'RESULT.json', public/'LOCAL-QUOTE-QUALIFICATION-003.json')
        write(public/'HOSTED-LOCAL-QUALIFICATION.json', record)
        workflow_dir = work/'workflows'
        assert_port_free(18766)
        record['commands'].append(run([sys.executable, str(PRODUCT/'scripts/probe_local_workflows.py'),
            '--server', str(binary), '--model', str(weights), '--alias', 'Qwen3-4B-Instruct-2507-Q4_K_M',
            '--output', str(workflow_dir)], work/'workflow-command.log', 1800, environment))
        workflows = read(workflow_dir/'RESULT.json')
        if workflows is not None:
            # Added envelope provenance is explicit; underlying run fields are preserved.
            workflows['source_revision'] = record['source_revision']
            workflows['source_product_tree'] = record['source_product_tree']
            workflows['provenance_added_by'] = 'qualify_hosted_local.py; actual underlying run fields unchanged'
            write(public/'LOCAL-WORKFLOWS-HOSTED.json', workflows)
        write(public/'HOSTED-LOCAL-QUALIFICATION.json', record)
        strategy_path = work/'STRATEGY-DEMO.json'
        record['commands'].append(run([sys.executable, '-m', 'bridge.strategy_demo',
            '--workspace', str(work/'strategy-workspace'), '--output', str(strategy_path)],
            work/'strategy-command.log', 120, environment))
        if strategy_path.is_file():
            shutil.copyfile(strategy_path, public/'STRATEGY-DEMO-FIXTURE.json')
        record['strategy_fixture_notice'] = 'Authored deterministic fixture; never counted as live inference.'
        valid_quote_source = bool(quote and quote.get('source_unchanged') is True
            and quote.get('source_revision') == record['source_revision']
            and quote.get('product_tree_sha') == record['source_product_tree'])
        qualified_arms = {}
        if quote:
            events = [event for arm in quote.get('arms', []) for event in arm.get('events', [])]
            if any(event.get('kind') == 'model_completed' for event in events):
                record['qualifications']['local_inference'] = 'PASS'
            for arm in quote.get('arms', []):
                arm_id = arm['id']
                required = 7 if arm_id == 'manufacturing_construct' else 4
                checks = [item for item in quote.get('outside_execution', []) if item['arm'] == arm_id]
                boundaries = [item for item in quote.get('numerical_boundary', []) if item['arm'] == arm_id]
                passed = (valid_quote_source and arm.get('status') == 'complete' and arm.get('verification', {}).get('passed') is True
                          and len(checks) == required and all(item.get('passed') is True for item in checks)
                          and len(boundaries) == 1 and boundaries[0].get('refused') is True)
                qualified_arms[arm_id] = passed
                if not passed:
                    continue
                # Only an accepted instrument, its trusted evaluator and protocol-authored inputs can be published.
                source_dir, destination = quote_dir/arm_id, public/'quote'/arm_id
                destination.mkdir(parents=True)
                case_list = protocol['manufacturing_cases'] if arm_id == 'manufacturing_construct' else protocol['lab_cases']
                names = ['quote.json', 'RUN_INSTRUMENT.py'] + [case['name'] + '-input.json' for case in case_list]
                for name in names:
                    shutil.copyfile(source_dir/name, destination/name)
                with (destination/'verified-quotes.csv').open('w', newline='') as stream:
                    columns = ['case'] + protocol['fields'] + ['valid', 'declared_cost_cents', 'within_capacity']
                    writer = csv.DictWriter(stream, fieldnames=columns)
                    writer.writeheader()
                    for case in case_list:
                        actual = next(item['output'] for item in checks if item['case'] == case['name'])
                        writer.writerow(dict({'case': case['name']}, **case['input'], **actual))
                (destination/'README.md').write_text(
                    '# Verified declared-cost example / Exemple de coûts déclarés vérifié\n\n'
                    'This is the actual accepted model-created instrument. The trusted evaluator is exported product code. '
                    'Run: python3 RUN_INSTRUMENT.py quote.json ' + case_list[0]['name'] + '-input.json\n\n'
                    'Outputs passed the frozen cases in a separate Python process. Values are synthetic planning inputs, '
                    'not full business costs, market data or profitability evidence. Negative inputs return invalid/null/false; '
                    'zero quantity retains declared fixed costs. Numerical range and operation limits remain binding.\n\n'
                    'Les entrées sont des exemples de planification. Les coûts complets, la rentabilité et la supériorité '
                    'économique ne sont pas établis. Les tentatives précédentes restent visibles dans les preuves.\n')
            record['qualifications']['quote_construction'] = 'PASS' if qualified_arms.get('manufacturing_construct') else 'FAIL'
            record['qualifications']['independent_export'] = record['qualifications']['quote_construction']
            hashes = {a['id']: a.get('artifact_hashes', {}).get('quote.json', {}).get('sha256') for a in quote.get('arms', [])}
            unchanged_reuse = bool(hashes.get('manufacturing_construct') and hashes.get('manufacturing_construct') == hashes.get('lab_inherit'))
            record['qualifications']['successor_reuse'] = 'PASS' if (qualified_arms.get('manufacturing_construct') and qualified_arms.get('lab_inherit') and unchanged_reuse) else 'FAIL'
            record['successor_reuse_rule'] = 'Both domains accepted and exported, with the exact predecessor quote.json SHA retained. Changed successor artifacts do not count as unchanged reuse.'
        if workflows:
            for entry in workflows.get('runs', []):
                key = {'single-model': 'single_agent', 'actor-critic': 'multi_agent', 'parallel-exploration': 'parallel_exploration'}.get(entry.get('policy'))
                if key:
                    record['qualifications'][key] = 'PASS' if workflows.get('source_unchanged') is True and qualified_workflow(entry) else 'FAIL'
                if any(event.get('kind') == 'model_completed' for event in entry.get('events', [])):
                    record['qualifications']['local_inference'] = 'PASS'
        record['quote_overall_status'] = quote.get('status') if quote else 'NOT_TESTED'
        record['raw_output_notice'] = 'Raw model responses and event transcripts in receipts are untrusted provenance, not accepted claims. Only the separately published quote.json and trusted evaluator passed the stated frozen cases. Extra model-authored project files are not published.'
    except Exception as error:
        record['error'] = {'type': type(error).__name__, 'message': sanitized_log(str(error))[:1000]}
    finally:
        record['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record['source_unchanged'] = source == source_snapshot() and not git('status', '--porcelain', '--', PRODUCT_REL)
        if not record['source_unchanged']:
            for key, value in record['qualifications'].items():
                if value == 'PASS':
                    record['qualifications'][key] = 'FAIL'
            shutil.rmtree(public/'quote', ignore_errors=True)
        record['status'] = 'PASS' if (not record.get('error') and record['source_unchanged']
            and all(value == 'PASS' for value in record['qualifications'].values())
            and record.get('quote_overall_status') == 'PASS') else 'FAIL'
        record['release_qualification'] = release_qualification(record)
        for log_name in ['quote-command.log', 'workflow-command.log', 'strategy-command.log']:
            log_path = work/log_name
            if log_path.is_file():
                with log_path.open('rb') as stream:
                    stream.seek(0, 2)
                    size = stream.tell()
                    stream.seek(max(0, size - 1024 * 1024))
                    content = stream.read().decode('utf-8', errors='replace')
                prefix = '[Earlier log content omitted; last 1MiB retained.]\n' if size > 1024 * 1024 else ''
                (public/log_name).write_text(prefix + sanitized_log(content))
        record['published_logs_notice'] = 'Only three allowlisted command logs, bounded to their final 1MiB and sanitized for credential-shaped fields/URL queries. No private workspace or arbitrary log tree is published.'
        record['published_sha256'] = {path.relative_to(public).as_posix(): sha(path) for path in sorted(public.rglob('*'))
                                      if path.is_file() and path.name != 'HOSTED-LOCAL-QUALIFICATION.json'}
        write(public/'HOSTED-LOCAL-QUALIFICATION.json', record)
        print(json.dumps({'status': record['status'], 'release_qualification': record['release_qualification'],
                          'qualifications': record['qualifications'],
                          'source_revision': record['source_revision'], 'source_product_tree': record['source_product_tree']}), flush=True)
    return 0 if record['release_qualification'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
