"""Capture bounded public release facts and measure an existing approved archive."""

import argparse
from datetime import datetime, timezone
from hashlib import file_digest, sha256
import json
from pathlib import Path
import subprocess
import tarfile
from time import perf_counter, process_time
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


HERE = Path(__file__).resolve().parent
REPO = 'https://api.github.com/repos/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
PAGE = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/atlas-release.json'
LLAMA = 'https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/b12242'
HOSTS = {'api.github.com', 'montrealai.github.io', 'raw.githubusercontent.com'}
HISTORICAL = ('https://raw.githubusercontent.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/'
              'd4527cb28e5bed6a0ff15a0d1fc2effa9de76a4a/publication/evidence-bound/production/LIVE-RELEASE.json')
MAX_METADATA_BYTES = 2 << 20
RUN_FIELDS = ('id', 'path', 'run_attempt', 'event', 'head_branch', 'head_sha', 'status', 'conclusion', 'created_at')
JOB_FIELDS = ('id', 'name', 'run_id', 'run_attempt', 'head_sha', 'status', 'conclusion', 'created_at', 'completed_at')
STEP_FIELDS = ('number', 'name', 'started_at')
ASSET_FIELDS = ('id', 'name', 'state', 'size', 'digest')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def projection(document, fields):
    return {key: document.get(key) for key in fields}


def capture(url, transform, history):
    parts = urlparse(url)
    if parts.scheme != 'https' or parts.netloc not in HOSTS:
        raise ValueError('public source is outside the compiled allowlist')
    request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'montreal-ai-public-evidence-capture'})
    started = perf_counter()
    with build_opener(NoRedirect).open(request, timeout=12) as response:
        if response.status != 200 or response.url != url:
            raise ValueError('unexpected public response')
        data = response.read(MAX_METADATA_BYTES + 1)
    if len(data) > MAX_METADATA_BYTES:
        raise ValueError('public metadata size exceeds the capture limit')
    decoded = json.loads(data)
    result = transform(decoded)
    history.append({'url': url, 'raw_sha256': sha256(data).hexdigest(), 'body_bytes': len(data),
                    'captured_at': datetime.now(timezone.utc).isoformat(),
                    'elapsed_seconds': round(perf_counter() - started, 6)})
    return result


def jobs_document(document):
    jobs = document['jobs']
    if document['total_count'] != len(jobs):
        raise ValueError('workflow job list is incomplete')
    return [dict(projection(job, JOB_FIELDS), steps=[projection(step, STEP_FIELDS) for step in job['steps']])
            for job in jobs]


def earliest_push(document, commit):
    matching = [row['id'] for row in document['workflow_runs'] if row['head_sha'] == commit
                and row['event'] == 'push' and row['head_branch'] == 'main' and isinstance(row['id'], int)
                and row['id'] > 0]
    if not matching:
        raise ValueError('exact main push run unavailable')
    if document['total_count'] != len(document['workflow_runs']):
        raise ValueError('run selection list is incomplete')
    return min(matching)


def pages_cases(registration, history):
    rows = []
    for spec in registration['o1']['cases']:
        start, cpu = perf_counter(), process_time()
        row = {'id': spec['id'], 'expected_commit': spec['commit']}
        if 'workflow_run' in spec:
            row['expected_run'] = spec['workflow_run']
            witness_source = HISTORICAL
            row['study_scope'] = 'historical'
        else:
            url = f'{REPO}/actions/workflows/research-pages.yml/runs?head_sha={spec["commit"]}&event=push&per_page=100'
            row['expected_run'] = capture(url, lambda value: earliest_push(value, spec['commit']), history)
            witness_source = PAGE
            row['study_scope'] = 'current_at_capture'
        run = capture(f'{REPO}/actions/runs/{row["expected_run"]}', lambda value: projection(value, RUN_FIELDS), history)
        jobs = capture(f'{REPO}/actions/runs/{row["expected_run"]}/attempts/{run["run_attempt"]}/jobs?per_page=100',
                       jobs_document, history)
        witness = capture(witness_source, lambda value: projection(value, ('source_commit', 'workflow_run')), history)
        row['facts'] = {'run': run, 'jobs': jobs, 'witness': witness}
        row['witness_source'] = witness_source
        row['origin'] = 'observed_public' if row['study_scope'] == 'current_at_capture' else 'observed_pinned_transcript'
        row['acquisition_wall_seconds'] = round(perf_counter() - start, 6)
        row['acquisition_cpu_seconds'] = round(process_time() - cpu, 6)
        rows.append(row)
    return rows


def local_archive(path):
    if not path.is_file():
        return None
    exact_size = path.stat().st_size
    if not 0 < exact_size <= 50 * (1 << 20):
        raise ValueError('approved archive exceeds the read scope')
    with path.open('rb') as source:
        exact_digest = file_digest(source, 'sha256').hexdigest()
    ordinary = subprocess.check_output(['sha256sum', '--', str(path)], text=True).split()[0]
    if ordinary != exact_digest:
        raise ValueError('file digest observations disagree')
    with tarfile.open(path, 'r|gz') as tar:
        server_path = [item.name for item in tar if Path(item.name).name == 'llama-server' and item.isfile()]
    return {'sha256': exact_digest, 'size': exact_size, 'ordinary_sha256': ordinary, 'server_members': server_path}


def upstream_case(registration, history, asset_path):
    start, cpu = perf_counter(), process_time()
    target = registration['o2']['artifact']
    release = capture(LLAMA, lambda value: {'tag': value['tag_name'], 'id': value['id'],
                      'draft': value['draft'], 'prerelease': value['prerelease'],
                      'assets': [projection(row, ASSET_FIELDS) for row in value['assets'] if row['name'] == target]}, history)
    result = {'origin': 'observed_upstream_publisher', 'expected_tag': 'b12242', 'expected_name': target,
              'release': release, 'archive': local_archive(asset_path)}
    result['acquisition_wall_seconds'] = round(perf_counter() - start, 6)
    result['acquisition_cpu_seconds'] = round(process_time() - cpu, 6)
    return result


def scheduled_case(path):
    registration_bytes = (HERE / 'FOLLOWUP-REGISTRATION.json').read_bytes()
    spec = json.loads(registration_bytes)
    history = []
    started, cpu = perf_counter(), process_time()
    run = capture(f'{REPO}/actions/runs/{spec["expected_run"]}', lambda value: projection(value, RUN_FIELDS), history)
    jobs = capture(f'{REPO}/actions/runs/{spec["expected_run"]}/attempts/{run["run_attempt"]}/jobs?per_page=100',
                   jobs_document, history)
    witness = capture(PAGE, lambda value: projection(value, ('source_commit', 'workflow_run')), history)
    case = {'id': spec['id'], 'expected_commit': spec['commit'], 'expected_run': spec['expected_run'],
            'expected_event': spec['expected_event'], 'study_scope': 'current_at_capture', 'origin': 'observed_public',
            'facts': {'run': run, 'jobs': jobs, 'witness': witness}, 'witness_source': PAGE,
            'acquisition_wall_seconds': round(perf_counter() - started, 6),
            'acquisition_cpu_seconds': round(process_time() - cpu, 6)}
    save(path, {'registration_sha256': sha256(registration_bytes).hexdigest(), 'pages': [case], 'observations': history})


def save(path, observations):
    with path.open('x') as output:
        json.dump(observations, output, sort_keys=True, indent=2)
        output.write('\n')


def main():
    parser = argparse.ArgumentParser()
    operations = parser.add_subparsers(dest='operation', required=True)
    first = operations.add_parser('start')
    first.add_argument('approved_archive', type=Path)
    first.add_argument('output', type=Path)
    followup = operations.add_parser('followup')
    followup.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.operation == 'followup':
        scheduled_case(args.output)
        return
    registration_bytes = (HERE / 'REGISTRATION.json').read_bytes()
    registration = json.loads(registration_bytes)
    history = []
    observations = {'registration_sha256': sha256(registration_bytes).hexdigest(),
                    'pages': pages_cases(registration, history), 'upstream': upstream_case(registration, history, args.approved_archive),
                    'observations': history}
    save(args.output, observations)


if __name__ == '__main__':
    main()
