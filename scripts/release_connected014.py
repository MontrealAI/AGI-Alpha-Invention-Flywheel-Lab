"""Source-bound immutable release and downloaded-package operating verification."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 256_000_000
PAPERS = ('PAPER.pdf', 'PAPER.tex', 'index.html', 'REPORT.md', 'PUBLICATION.json', 'PDF_QA.json')
REQUIRED_WORKFLOWS = ('campaign.yml', 'consequential007.yml', 'consequential009.yml', 'adaptive012.yml', 'commercial010.yml')
CONDITIONAL_WORKFLOWS = {'measurement009.yml':('.github/workflows/measurement009.yml', 'campaign/next-009/', 'inventions/measurement009/', 'research/next009/', 'verification/next009/', 'docs/next009/', 'evidence/next009/')}
OWN_WORKFLOW = 'connected014-release.yml'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def commit(value):
    if not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('FULL_SOURCE_COMMIT_REQUIRED')
    return value

def tag(value):
    return 'connected014-'+commit(value)

def checked_members(archive):
    members = archive.infolist()
    names = [item.filename for item in members]
    if len(names) != len(set(names)) or sum(item.file_size for item in members) > LIMIT:
        raise ValueError('UNIQUE_BOUNDED_ARCHIVE_REQUIRED')
    for item in members:
        name = PurePosixPath(item.filename)
        if (not item.filename or name.is_absolute() or '..' in name.parts or '\\' in item.filename
                or stat.S_ISLNK(item.external_attr >> 16) or '.git' in name.parts
                or '.sqlite' in item.filename or item.filename.endswith('.adaptive-simulation-key')):
            raise ValueError('UNSAFE_OR_PRIVATE_ARCHIVE_MEMBER')
    if archive.testzip() is not None:
        raise ValueError('ARCHIVE_CRC_FAILURE')
    return names

def archive_manifest(path):
    with zipfile.ZipFile(path) as archive:
        names = checked_members(archive)
        manifest = json.loads(archive.read('SOURCE_MANIFEST.json'))
        if (manifest.get('schema') != 'agi-alpha/connected014-source-distribution/v1'
                or set(names) != set(manifest['files']) | {'SOURCE_MANIFEST.json'}):
            raise ValueError('SOURCE_DISTRIBUTION_MANIFEST_REQUIRED')
        for name, expected in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError('SOURCE_MEMBER_HASH_CHANGED:'+name)
        frozen = manifest['executing_source']
        canonical = json.dumps(frozen['files'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        if hashlib.sha256(canonical).hexdigest() != frozen['sha256']:
            raise ValueError('SOURCE_IDENTITY_DIGEST_CHANGED')
        if any(manifest['files'].get(name) != expected for name, expected in frozen['files'].items()):
            raise ValueError('EXECUTING_SOURCE_CLOSURE_CHANGED')
        return manifest

def asset_names(directory):
    paths = sorted(Path(directory).iterdir())
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError('REGULAR_RELEASE_ASSETS_REQUIRED')
    return {path.name for path in paths}

def seal(directory, manifest):
    directory = Path(directory)
    manifest['files'] = {name: digest(directory/name) for name in sorted(asset_names(directory)-{'RELEASE_MANIFEST.json', 'SHA256SUMS.txt'})}
    write(directory/'RELEASE_MANIFEST.json', manifest)
    names = sorted(asset_names(directory)-{'SHA256SUMS.txt'})
    (directory/'SHA256SUMS.txt').write_text(''.join(digest(directory/name)+'  '+name+'\n' for name in names))

def verify_assets(directory, expected_commit):
    directory = Path(directory)
    manifest = read(directory/'RELEASE_MANIFEST.json')
    if (manifest.get('schema') != 'agi-alpha/connected014-release/v1'
            or manifest.get('source_commit') != commit(expected_commit)
            or manifest.get('tag') != tag(expected_commit)):
        raise ValueError('RELEASE_SOURCE_OR_TAG_CHANGED')
    names = asset_names(directory)
    required = {'connected014-source.zip', 'connected014-keyfree.zip', 'QUALIFICATION.json', 'RELEASE_NOTES.md', *PAPERS}
    if not required <= names:
        raise ValueError('COMPLETE_RELEASE_ASSET_SET_REQUIRED')
    if names != set(manifest['files']) | {'RELEASE_MANIFEST.json', 'SHA256SUMS.txt'}:
        raise ValueError('EXACT_RELEASE_ASSET_SET_REQUIRED')
    for name, expected in manifest['files'].items():
        if Path(name).name != name or digest(directory/name) != expected:
            raise ValueError('RELEASE_ASSET_HASH_CHANGED:'+name)
    checksums = (directory/'SHA256SUMS.txt').read_text().splitlines()
    expected_rows = [digest(directory/name)+'  '+name for name in sorted(names-{'SHA256SUMS.txt'})]
    if checksums != expected_rows:
        raise ValueError('RELEASE_CHECKSUM_SET_CHANGED')
    source = archive_manifest(directory/'connected014-source.zip')
    if source['executing_source']['sha256'] != manifest['source_sha256']:
        raise ValueError('RELEASE_EXECUTING_SOURCE_CHANGED')
    qualification = read(directory/'QUALIFICATION.json')
    if (not qualification.get('accepted') or qualification['source_sha256'] != manifest['source_sha256']
            or qualification['source_archive']['sha256'] != digest(directory/'connected014-source.zip')
            or qualification['public_archive']['sha256'] != digest(directory/'connected014-keyfree.zip')):
        raise ValueError('QUALIFIED_ARCHIVE_BINDING_CHANGED')
    if 'RELEASE_GATE.json' in names:
        gate = read(directory/'RELEASE_GATE.json')
        runs = gate.get('required_workflows', {})
        applicability = gate.get('applicability', {})
        expected_runs = applicable_workflows(applicability.get('changed_paths', []), list(runs),
                                            applicability.get('conservative_all_conditionals', False))
        if (gate.get('source_commit') != expected_commit or gate.get('event') != 'push'
                or gate.get('branch') != 'main' or set(runs) != expected_runs
                or any(row.get('head_sha') != expected_commit or row.get('event') != 'push'
                       or row.get('head_branch') != 'main' or row.get('conclusion') != 'success'
                       or row.get('path') != '.github/workflows/'+name for name, row in runs.items())):
            raise ValueError('SOURCE_BOUND_MAIN_RELEASE_GATE_REQUIRED')
    return manifest

def prepare(qualification, output, source_commit, papers):
    source_commit = commit(source_commit)
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if current != source_commit or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('CLEAN_EXACT_COMMITTED_SOURCE_REQUIRED')
    qualification, output, papers = Path(qualification), Path(output), Path(papers)
    if output.exists():
        raise FileExistsError('NEW_RELEASE_ASSET_DIRECTORY_REQUIRED')
    receipt = read(qualification/'QUALIFICATION.json')
    if not receipt.get('accepted') or not receipt.get('no_git_execution') or not receipt.get('completed_resume_financially_unchanged'):
        raise ValueError('ACCEPTED_CLEAN_OPERATION_AND_RESUME_REQUIRED')
    sys.path.insert(0, str(ROOT))
    from connected_enterprise.runner import identity
    if identity(ROOT)['sha256'] != receipt['source_sha256']:
        raise ValueError('QUALIFICATION_NOT_CURRENT_SOURCE')
    if any(not (papers/name).is_file() or (papers/name).is_symlink() for name in PAPERS):
        raise ValueError('COMPLETE_INSPECTED_RESEARCH_EDITION_REQUIRED')
    publication, qa = read(papers/'PUBLICATION.json'), read(papers/'PDF_QA.json')
    if publication.get('source_sha256') != receipt['source_sha256']:
        raise ValueError('PAPER_EXECUTING_SOURCE_CHANGED')
    for name, expected in publication.get('files', {}).items():
        if Path(name).name != name or digest(papers/name) != expected:
            raise ValueError('PUBLICATION_FILE_HASH_CHANGED')
    if not set(PAPERS[:4]) <= set(publication.get('files', {})):
        raise ValueError('PUBLICATION_CLOSURE_REQUIRED')
    if qa.get('accepted') is not True or qa.get('pdf_sha256') != digest(papers/'PAPER.pdf') or not qa.get('visually_inspected'):
        raise ValueError('HASH_BOUND_VISUAL_PDF_QA_REQUIRED')
    output.mkdir(parents=True)
    for name in ('connected014-source.zip', 'connected014-keyfree.zip', 'QUALIFICATION.json'):
        shutil.copyfile(qualification/name, output/name)
    for name in PAPERS:
        shutil.copyfile(papers/name, output/name)
    notes = ('# Connected 014 released simulated enterprise\n\n'
             'Immutable source commit: `'+source_commit+'`.\n\n'
             'The source package passed clean operation, completed-account resume, independent native/operating audit '
             'and key-free public-package audit. The accompanying research edition states the achieved commercial '
             'and growth evidence and its conditions. Engineering smoke qualification is separate from fresh commercial confirmation. '
             'All customers, payments and earned reinvestment remain simulated. No real spending, outreach or deployment occurred.\n\n'
             'Install the pinned requirements from the source ZIP, then follow docs/connected014/OPERATOR.md. '
             'Source/asset hashes are in RELEASE_MANIFEST.json and SHA256SUMS.txt. '
             'The publication workflow downloads and operates this actual release; its post-publication receipt is retained '
             'as a workflow artifact.\n')
    (output/'RELEASE_NOTES.md').write_text(notes)
    manifest = {'schema':'agi-alpha/connected014-release/v1', 'source_commit':source_commit,
                'source_sha256':receipt['source_sha256'], 'tag':tag(source_commit),
                'scope':'CONDITIONAL_SIMULATION', 'qualification':'CLEAN_ENGINEERING_OPERATION_AND_PUBLIC_AUDIT',
                'downloaded_release_operation':'REQUIRED_IN_PUBLICATION_WORKFLOW_NOT_YET_CLAIMED'}
    seal(output, manifest)
    verify_assets(output, source_commit)
    return manifest

def gh(endpoint, optional=False):
    result = subprocess.run(['gh', 'api', endpoint], capture_output=True, text=True)
    if result.returncode:
        if optional and 'HTTP 404' in result.stderr:
            return None
        raise RuntimeError('GITHUB_API_FAILED:'+endpoint)
    return json.loads(result.stdout)

def qualifying_runs(workflows, source_commit):
    accepted = {}
    for name, runs in workflows.items():
        matches = [row for row in runs if row.get('head_sha') == source_commit and row.get('event') == 'push'
                   and row.get('head_branch') == 'main' and row.get('path') == '.github/workflows/'+name]
        if not matches:
            continue
        latest = max(matches, key=lambda row:(row['run_number'], row.get('run_attempt', 1), row['id']))
        if latest['status'] == 'completed':
            if latest['conclusion'] != 'success':
                raise ValueError('EXACT_MAIN_QUALIFICATION_FAILED:'+name)
            accepted[name] = {key:latest[key] for key in ('id', 'head_sha', 'event', 'head_branch', 'path', 'conclusion', 'html_url')}
    return accepted

def applicable_workflows(changed_paths, observed=(), conservative=False):
    required = set(REQUIRED_WORKFLOWS)
    for name, prefixes in CONDITIONAL_WORKFLOWS.items():
        if conservative or any(path == prefix or (prefix.endswith('/') and path.startswith(prefix)) for path in changed_paths for prefix in prefixes):
            required.add(name)
    for name in observed:
        if name != OWN_WORKFLOW:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.ya?ml', name):
                raise ValueError('WORKFLOW_BASENAME_REQUIRED')
            required.add(name)
    return required

def push_applicability(repository, source_commit):
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    event = read(event_path) if event_path else {}
    before = event.get('before') if event.get('after') == source_commit else None
    if not before or before == '0'*40:
        parents = gh(f'repos/{repository}/commits/{source_commit}').get('parents', [])
        if not parents:
            return {'base_commit':None, 'changed_paths':[], 'conservative_all_conditionals':True}
        before = parents[0]['sha']
    commit(before)
    comparison = gh(f'repos/{repository}/compare/{before}...{source_commit}?per_page=100')
    files = comparison.get('files')
    if not isinstance(files, list):
        raise ValueError('SOURCE_PUSH_PATH_COMPARISON_REQUIRED')
    changed = {item['filename'] for item in files}
    method = 'GITHUB_COMPARE_COMPLETE_FILE_LIST'
    if len(files) >= 300:
        trees = [gh(f'repos/{repository}/git/trees/{value}?recursive=1') for value in (before, source_commit)]
        if any(tree.get('truncated', True) for tree in trees):
            raise ValueError('UNTRUNCATED_PUSH_SOURCE_TREES_REQUIRED')
        old, new = [{row['path']:(row['type'], row.get('mode'), row['sha']) for row in tree['tree'] if row['type'] != 'tree'} for tree in trees]
        changed = {name for name in set(old)|set(new) if old.get(name) != new.get(name)}
        method = 'EXACT_RECURSIVE_GIT_TREE_DIFF_AFTER_COMPARE_FILE_CAP'
    return {'base_commit':before, 'changed_paths':sorted(changed), 'comparison_method':method,
            'conservative_all_conditionals':False}

def publish(directory, source_commit, repository, run_id, timeout):
    directory = Path(directory)
    manifest = verify_assets(directory, source_commit)
    applicability = push_applicability(repository, source_commit)
    deadline = time.monotonic()+timeout
    while True:
        observed = gh(f'repos/{repository}/actions/runs?head_sha={source_commit}&event=push&branch=main&per_page=100')['workflow_runs']
        names = [row['path'].removeprefix('.github/workflows/') for row in observed
                 if row.get('head_sha') == source_commit and row.get('event') == 'push'
                 and row.get('head_branch') == 'main' and row.get('path', '').startswith('.github/workflows/')]
        required = applicable_workflows(applicability['changed_paths'], names, applicability['conservative_all_conditionals'])
        runs = {name:gh(f'repos/{repository}/actions/workflows/{name}/runs?head_sha={source_commit}&event=push&branch=main&per_page=100')['workflow_runs'] for name in required}
        accepted = qualifying_runs(runs, source_commit)
        if set(accepted) == required:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError('EXACT_MAIN_WORKFLOW_GATE_TIMEOUT')
        time.sleep(min(10, max(0, deadline-time.monotonic())))
    if gh(f'repos/{repository}/git/ref/heads/main')['object']['sha'] != source_commit:
        raise ValueError('MAIN_MOVED_BEFORE_PUBLICATION')
    release_tag = tag(source_commit)
    ref = gh(f'repos/{repository}/git/ref/tags/{release_tag}', optional=True)
    existing = gh(f'repos/{repository}/releases/tags/{release_tag}', optional=True)
    if ref is not None and (ref['object']['type'] != 'commit' or ref['object']['sha'] != source_commit):
        raise ValueError('IMMUTABLE_TAG_SOURCE_MISMATCH')
    if existing is not None:
        if ref is None:
            raise ValueError('RELEASE_WITHOUT_SOURCE_TAG')
        previous = directory.parent/'existing-immutable-release'
        if previous.exists():
            raise FileExistsError('NEW_EXISTING_RELEASE_DOWNLOAD_REQUIRED')
        subprocess.run(['gh', 'release', 'download', release_tag, '--repo', repository, '--dir', str(previous)], check=True)
        original = verify_assets(previous, source_commit)
        if original['source_sha256'] != manifest['source_sha256'] or 'RELEASE_GATE.json' not in original['files']:
            raise ValueError('EXISTING_RELEASE_SOURCE_OR_GATE_CHANGED')
        if any(digest(previous/name) != digest(directory/name) for name in ('connected014-source.zip', *PAPERS)):
            raise ValueError('EXISTING_RELEASE_SOURCE_OR_PAPERS_DIFFER')
        remote = {asset['name']:asset.get('digest') for asset in existing['assets']}
        expected = {name:'sha256:'+digest(previous/name) for name in asset_names(previous)}
        if remote != expected:
            raise ValueError('EXISTING_RELEASE_ASSETS_DIFFER; NO_OVERWRITE')
        return original
    gate = {'schema':'agi-alpha/connected014-release-gate/v1', 'source_commit':source_commit,
            'event':'push', 'branch':'main', 'own_run_id':run_id, 'required_workflows':accepted,
            'applicability':applicability}
    write(directory/'RELEASE_GATE.json', gate)
    manifest['downloaded_release_operation'] = 'FOLLOWING_PUBLICATION_JOB_REQUIRED; SEE_WORKFLOW_ARTIFACT'
    seal(directory, manifest)
    manifest = verify_assets(directory, source_commit)
    if ref is None:
        subprocess.run(['gh', 'api', f'repos/{repository}/git/refs', '--method', 'POST', '-f', 'ref=refs/tags/'+release_tag, '-f', 'sha='+source_commit], check=True, stdout=subprocess.DEVNULL)
    ref = gh(f'repos/{repository}/git/ref/tags/{release_tag}')
    if ref['object'].get('sha') != source_commit or ref['object'].get('type') != 'commit':
        raise ValueError('TAG_CHANGED_BEFORE_RELEASE')
    subprocess.run(['gh', 'release', 'create', release_tag, *[str(directory/name) for name in sorted(asset_names(directory))],
                    '--repo', repository, '--verify-tag', '--target', source_commit, '--prerelease',
                    '--title', 'AGI ALPHA connected enterprise 014 — simulated operating release',
                    '--notes-file', str(directory/'RELEASE_NOTES.md')], check=True)
    return manifest

def download(directory, receipt_path, source_commit, repository):
    directory = Path(directory)
    if directory.exists() or Path(receipt_path).exists():
        raise FileExistsError('NEW_RELEASE_DOWNLOAD_AND_RECEIPT_REQUIRED')
    release_tag = tag(source_commit)
    ref = gh(f'repos/{repository}/git/ref/tags/{release_tag}')
    release = gh(f'repos/{repository}/releases/tags/{release_tag}')
    if ref['object'].get('type') != 'commit' or ref['object'].get('sha') != source_commit or release.get('tag_name') != release_tag:
        raise ValueError('PUBLISHED_TAG_SOURCE_CHANGED')
    subprocess.run(['gh', 'release', 'download', release_tag, '--repo', repository, '--dir', str(directory)], check=True)
    manifest = verify_assets(directory, source_commit)
    if 'RELEASE_GATE.json' not in manifest['files']:
        raise ValueError('PUBLISHED_MAIN_GATE_REQUIRED')
    receipt = {'schema':'agi-alpha/connected014-actual-release-download/v1', 'actual_release_download':True,
               'source_commit':source_commit, 'source_sha256':manifest['source_sha256'], 'tag':release_tag,
               'release_url':release['html_url'], 'files':{name:digest(directory/name) for name in sorted(asset_names(directory))}}
    write(receipt_path, receipt)
    return receipt

def operate_download(directory, output, source_commit, timeout, actual_release_download=False):
    directory, output = Path(directory).resolve(), Path(output).resolve()
    manifest = verify_assets(directory, source_commit)
    if output.exists() or any(path.is_symlink() for path in [output, *output.parents]):
        raise ValueError('NEW_UNSYMLINKED_DOWNLOADED_OPERATION_REQUIRED')
    output.mkdir(parents=True)
    source = output/'source'
    with zipfile.ZipFile(directory/'connected014-source.zip') as archive:
        archive.extractall(source)
    if any((parent/'.git').exists() for parent in [source, *source.parents]):
        raise ValueError('DOWNLOADED_OPERATION_MUST_HAVE_NO_GIT_ANCESTRY')
    sys.path.insert(0, str(ROOT))
    from scripts.qualify_connected014 import run_command, native_state
    deadline = time.monotonic()+timeout
    commands = []
    receipt = {'schema':'agi-alpha/connected014-downloaded-release-operation/v1', 'accepted':False,
               'source_commit':source_commit, 'source_sha256':manifest['source_sha256'],
               'tag':manifest['tag'], 'actual_release_download':actual_release_download, 'commands':commands,
               'scope':'SIMULATED_RELEASED_DEFAULT_EXPERIMENT_REPRODUCTION_NOT_UNTOUCHED_CONFIRMATION'}
    try:
        operation = output/'operation'
        base = [sys.executable, '-m', 'connected_enterprise']
        run_command(base+['run', '--output', str(operation)], source, output/'01-run', deadline, commands)
        if read(operation/'FROZEN.json')['source']['sha256'] != manifest['source_sha256']:
            raise ValueError('DOWNLOADED_EXECUTION_SOURCE_CHANGED')
        before = native_state(operation)
        run_command(base+['resume', '--output', str(operation)], source, output/'02-resume', deadline, commands)
        if native_state(operation) != before:
            raise ValueError('DOWNLOADED_RESUME_CHANGED_MONEY_OR_WORK')
        run_command(base+['audit', '--output', str(operation)], source, output/'03-audit', deadline, commands)
        if not read(operation/'PACKAGE_AUDIT.json').get('accepted'):
            raise ValueError('DOWNLOADED_NATIVE_OPERATING_AUDIT_REJECTED')
        public = output/'published-keyfree'
        with zipfile.ZipFile(directory/'connected014-keyfree.zip') as archive:
            checked_members(archive)
            archive.extractall(public)
        run_command(base+['audit', '--output', str(public)], public/'source', output/'04-released-public-audit', deadline, commands)
        if (not read(public/'PACKAGE_AUDIT.json').get('accepted')
                or read(public/'PACKAGE_AUDIT.json').get('source_sha256') != manifest['source_sha256']):
            raise ValueError('RELEASED_PUBLIC_EVIDENCE_SOURCE_CHANGED')
        receipt.update(accepted=True, completed_resume_financially_unchanged=True,
                       native_and_operating_audit=read(operation/'PACKAGE_AUDIT.json'),
                       released_public_audit=read(public/'PACKAGE_AUDIT.json'),
                       operating_report=read(operation/'REPORT.json'))
    except BaseException as error:
        receipt['failure'] = {'type':type(error).__name__, 'message':str(error)}
        raise
    finally:
        write(output/'DOWNLOADED_RELEASE_RUN.json', receipt)
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'publish', 'download', 'operate-download', 'verify'):
        sub = subs.add_parser(name)
        sub.add_argument('--source-commit', required=True)
        sub.add_argument('--assets', required=True)
        if name == 'prepare':
            sub.add_argument('--qualification', required=True)
            sub.add_argument('--papers', required=True)
        elif name == 'publish':
            sub.add_argument('--repository', required=True)
            sub.add_argument('--run-id', required=True, type=int)
            sub.add_argument('--timeout-seconds', type=int, default=900)
        elif name == 'operate-download':
            sub.add_argument('--output', required=True)
            sub.add_argument('--timeout-seconds', type=int, default=900)
            sub.add_argument('--actual-release-download', action='store_true')
        elif name == 'download':
            sub.add_argument('--repository', required=True)
            sub.add_argument('--receipt', required=True)
    args = parser.parse_args()
    if args.command == 'publish' and not 1 <= args.timeout_seconds <= 2400:
        parser.error('publish timeout-seconds must be 1..2400')
    if args.command == 'operate-download' and not 1 <= args.timeout_seconds <= 1200:
        parser.error('operate-download timeout-seconds must be 1..1200')
    if args.command == 'prepare':
        result = prepare(args.qualification, args.assets, args.source_commit, args.papers)
    elif args.command == 'publish':
        result = publish(args.assets, args.source_commit, args.repository, args.run_id, args.timeout_seconds)
    elif args.command == 'operate-download':
        result = operate_download(args.assets, args.output, args.source_commit, args.timeout_seconds, args.actual_release_download)
    elif args.command == 'download':
        result = download(args.assets, args.receipt, args.source_commit, args.repository)
    else:
        result = verify_assets(args.assets, args.source_commit)
    print(json.dumps({'accepted':result.get('accepted', True), 'source_commit':args.source_commit, 'tag':tag(args.source_commit)}, sort_keys=True))

if __name__ == '__main__':
    main()
