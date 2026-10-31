#!/usr/bin/env python3
"""Optional reuse of a successful main-branch cohort; never a fresh result."""
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import sysconfig
import urllib.error
import urllib.parse
import urllib.request
import zipfile

SCHEMA = 'agi-alpha/adaptive-cohort-reuse036/v1'
WORKFLOW = '.github/workflows/adaptive012.yml'
# These exact paths are not read by adaptive_enterprise.runner's frozen cohort.
# Do not generalize this list to *.md: many manifests and policies ARE inputs.
EXCLUDED = {'AGENTS.md', 'docs/harness/DEVELOPER_GUIDE.md',
            'evidence/strategic024-publication/COMPOSED_SOURCE_BINDING.json'}
ARTIFACT = 'adaptive-cohort036-receipt'
MAX_BYTES = 512 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


def fingerprint(root):
    if git(root, 'status', '--porcelain', '--untracked-files=no').strip():
        raise ValueError('TRACKED_CHECKOUT_NOT_CLEAN')
    untracked = git(root, 'ls-files', '--others', '-z').split(b'\0')
    if any(p and not ('__pycache__' in Path(p.decode()).parts and p.endswith(b'.pyc')) for p in untracked):
        raise ValueError('UNTRACKED_INPUT_PRESENT')
    if os.environ.get('PYTHONPATH') or os.environ.get('PYTHONHOME'):
        raise ValueError('EXTERNAL_PYTHON_PATH_UNSUPPORTED')
    entries = []
    for row in git(root, 'ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not row:
            continue
        mode_type_hash, raw_name = row.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        mode, kind, blob = mode_type_hash.decode().split()
        if mode not in {'100644', '100755'} or kind != 'blob':
            raise ValueError('NONREGULAR_TRACKED_INPUT')
        if name not in EXCLUDED:
            entries.append([name, mode, blob])
    # Hash actual installed distribution files, not just mutable version labels.
    packages = []
    for dist in importlib.metadata.distributions():
        files = []
        for entry in dist.files or ():
            path = Path(dist.locate_file(entry))
            if path.suffix == '.pyc':
                continue
            if not path.is_file():
                raise ValueError('INSTALLED_DISTRIBUTION_FILE_MISSING')
            files.append([str(entry), sha(path.read_bytes())])
        if not files:
            raise ValueError('UNIDENTIFIED_INSTALLED_DISTRIBUTION')
        packages.append([dist.metadata['Name'], dist.version, sorted(files)])
    stdlib_root = Path(sysconfig.get_path('stdlib'))
    stdlib = []
    for directory, dirs, names in os.walk(stdlib_root):
        dirs[:] = sorted(d for d in dirs if d not in {'site-packages', 'dist-packages', '__pycache__'})
        for name in sorted(names):
            path = Path(directory)/name
            if path.suffix != '.pyc':
                stdlib.append([str(path.relative_to(stdlib_root)), sha(path.read_bytes())])
    if not stdlib:
        raise ValueError('PYTHON_STDLIB_IDENTITY_UNAVAILABLE')
    image = {key: os.environ.get(key) for key in ('ImageOS', 'ImageVersion')}
    if not all(image.values()):
        raise ValueError('RUNNER_IMAGE_IDENTITY_UNAVAILABLE')
    payload = {'schema': SCHEMA, 'tracked_entries': sorted(entries),
               'excluded_nonexecuted_paths': sorted(EXCLUDED),
               'python': sys.version, 'python_executable_sha256': sha(Path(sys.executable).read_bytes()),
               'stdlib_sha256': sha(canonical(stdlib)),
               'platform': [platform.system(), platform.machine()], 'sqlite': sqlite3.sqlite_version,
               'execution_environment': {k: os.environ.get(k) for k in ('LANG', 'LC_ALL', 'TZ', 'PYTHONHASHSEED', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS')},
               'runner_image': image, 'installed_content_sha256': sha(canonical(sorted(packages)))}
    return sha(canonical(payload))


def trusted_run(run, repo, head, ancestor):
    return (run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('event') == 'push' and run.get('head_branch') == 'main'
            and run.get('path') == WORKFLOW and run.get('head_sha') != head
            and run.get('repository', {}).get('full_name') == repo
            and run.get('head_repository', {}).get('full_name') == repo
            and ancestor(run.get('head_sha', '')))


def valid_receipt(receipt, run, key, repo):
    return (receipt.get('schema') == SCHEMA and receipt.get('kind') == 'EXECUTED_COHORT'
            and receipt.get('repository') == repo and receipt.get('run_id') == run['id']
            and receipt.get('run_attempt') == run.get('run_attempt') and isinstance(receipt.get('run_attempt'), int)
            and receipt.get('source_commit') == run['head_sha'] and receipt.get('input_key') == key
            and receipt.get('audit_accepted') is True and receipt.get('worlds') == 160
            and receipt.get('qualification_scope') == 'NATIVE_FINANCIAL_ONLY'
            and all(isinstance(receipt.get(k), str) and re.fullmatch(r'[0-9a-f]{64}', receipt[k])
                    for k in ('report_sha256', 'frozen_sha256', 'index_sha256', 'native_source_sha256')))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api(path):
    url = 'https://api.github.com/' + path
    request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                                      'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('API_RESPONSE_BOUND')
    return json.loads(raw)


def archive(repo, artifact):
    if artifact.get('expired') or artifact.get('size_in_bytes', MAX_BYTES + 1) > MAX_BYTES:
        raise ValueError('ARTIFACT_UNAVAILABLE')
    req = urllib.request.Request('https://api.github.com/repos/' + repo + '/actions/artifacts/' + str(artifact['id']) + '/zip',
                                 headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN']})
    try:
        urllib.request.build_opener(NoRedirect).open(req, timeout=20)
        raise ValueError('SIGNED_ARTIFACT_REDIRECT_REQUIRED')
    except urllib.error.HTTPError as error:
        if error.code != 302:
            raise
        target = error.headers['Location']
    parsed = urllib.parse.urlsplit(target)
    if parsed.scheme != 'https' or parsed.username or parsed.password:
        raise ValueError('ARTIFACT_REDIRECT_SCOPE')
    # The GitHub token is NEVER forwarded to the signed artifact host.
    with urllib.request.urlopen(target, timeout=20) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES or artifact.get('digest') != 'sha256:' + sha(raw):
        raise ValueError('ARTIFACT_DIGEST_MISMATCH')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.namelist() != ['COHORT_RECEIPT.json'] or z.infolist()[0].file_size > MAX_BYTES:
            raise ValueError('EXACT_RECEIPT_ARCHIVE_REQUIRED')
        return json.loads(z.read('COHORT_RECEIPT.json'))


def lookup(root, key, repo, head):
    def ancestor(commit):
        if not isinstance(commit, str) or len(commit) != 40:
            return False
        return subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', commit, head],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    # A bounded opportunistic lookup; absent proof always means execute normally.
    runs = api('repos/' + repo + '/actions/workflows/adaptive012.yml/runs?branch=main&event=push&status=success&per_page=20')['workflow_runs']
    for run in runs:
        if not trusted_run(run, repo, head, ancestor):
            continue
        artifacts = api('repos/' + repo + '/actions/runs/' + str(run['id']) + '/artifacts?per_page=100')['artifacts']
        for item in artifacts:
            if item.get('name') != ARTIFACT:
                continue
            try:
                receipt = archive(repo, item)
            except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                continue
            if valid_receipt(receipt, run, key, repo):
                return {'run_id': run['id'], 'source_commit': run['head_sha'],
                        'run_url': run['html_url'], 'artifact_id': item['id'],
                        'artifact_sha256': item['digest'], 'original_receipt': receipt}
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['lookup', 'record'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cohort', type=Path)
    args = parser.parse_args(); root = Path.cwd(); args.output.mkdir(parents=True, exist_ok=True)
    if args.mode == 'lookup':
        result = {'schema': SCHEMA, 'reuse': False, 'scope': 'Fresh qualification; optional cohort evidence reuse only.', 'current_run_url': 'https://github.com/' + os.environ.get('GITHUB_REPOSITORY', '') + '/actions/runs/' + os.environ.get('GITHUB_RUN_ID', '')}
        try:
            head = git(root, 'rev-parse', 'HEAD').decode().strip()
            key = fingerprint(root); result.update(input_key=key, source_commit=head, current_run_url='https://github.com/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID'])
            found = lookup(root, key, os.environ['GITHUB_REPOSITORY'], head)
            if found:
                result.update(reuse=True, original=found, scope='REUSED_PRIOR_COHORT_NOT_FRESH_CONFIRMATION; current tests/package/smoke remain mandatory.')
        except Exception as error:  # Any unverifiable optimization falls back to real execution.
            result['fallback_reason'] = type(error).__name__
        (args.output/'REUSE.json').write_bytes(canonical(result)+b'\n')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write('reuse=' + str(result['reuse']).lower() + '\n')
        print(json.dumps(result))
    else:
        lookup_result = json.loads((args.output/'REUSE.json').read_bytes())
        if lookup_result.get('reuse') or not lookup_result.get('input_key'):
            return
        if fingerprint(root) != lookup_result['input_key']:
            raise ValueError('QUALIFIED_INPUT_CHANGED')
        p = args.cohort
        complete = json.loads((p/'COMPLETE.json').read_bytes()); audit = json.loads((p/'FINANCIAL_AUDIT.json').read_bytes())
        if not audit.get('accepted') or audit.get('native_worlds_replayed') != 160 or audit.get('qualification_scope') != 'NATIVE_FINANCIAL_ONLY':
            raise ValueError('COMPLETE_NATIVE_COHORT_AUDIT_REQUIRED')
        if complete['report_sha256'] != sha((p/'REPORT.json').read_bytes()) or complete['source_sha256'] != audit['source_sha256']:
            raise ValueError('COHORT_RECEIPT_BINDING')
        receipt = {'schema': SCHEMA, 'kind': 'EXECUTED_COHORT', 'repository': os.environ['GITHUB_REPOSITORY'],
                   'run_id': int(os.environ['GITHUB_RUN_ID']), 'run_attempt': int(os.environ['GITHUB_RUN_ATTEMPT']), 'source_commit': lookup_result['source_commit'],
                   'input_key': lookup_result['input_key'], 'audit_accepted': True, 'worlds': 160, 'qualification_scope': 'NATIVE_FINANCIAL_ONLY',
                   'native_source_sha256': complete['source_sha256'], 'report_sha256': complete['report_sha256'],
                   'frozen_sha256': sha((p/'FROZEN012.json').read_bytes()), 'index_sha256': sha((p/'INDEX.json').read_bytes())}
        (args.output/'COHORT_RECEIPT.json').write_bytes(canonical(receipt)+b'\n')

if __name__ == '__main__':
    main()
