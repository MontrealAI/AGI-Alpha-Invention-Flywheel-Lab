"""Source-bound immutable release and downloaded-package operating verification."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import resource
import shutil
import stat
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 256_000_000
HISTORICAL_CPU_REFERENCE_SECONDS = 2400
HOSTED_JOB_LIMIT_SECONDS = 6 * 60 * 60
RECEIPT_SHUTDOWN_RESERVE_SECONDS = 5 * 60
OPERATING_HANG_TIMEOUT_SECONDS = HOSTED_JOB_LIMIT_SECONDS - RECEIPT_SHUTDOWN_RESERVE_SECONDS
PAPERS = ('PAPER.pdf', 'PAPER.tex', 'index.html', 'REPORT.md', 'PUBLICATION.json', 'PDF_QA.json')
REQUIRED_WORKFLOWS = ('campaign.yml', 'consequential007.yml', 'consequential009.yml', 'adaptive012.yml', 'commercial010.yml')
# Terminal measurement009 is manual-only; path changes never renew its expired allocation.
CONDITIONAL_WORKFLOWS = {}
RETIRED_MANUAL_WORKFLOWS = ('measurement009.yml',)
OWN_WORKFLOW = 'connected014-release.yml'

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')

def cpu_usage():
    own, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return {'self_user':own.ru_utime, 'self_system':own.ru_stime,
            'children_user':children.ru_utime, 'children_system':children.ru_stime}

def cpu_delta(before, after):
    keys = ('self_user', 'self_system', 'children_user', 'children_system')
    values = {key:after[key]-before[key] for key in keys}
    if any(not math.isfinite(value) or value < 0 for value in values.values()):
        raise ValueError('MONOTONIC_KERNEL_CPU_COUNTERS_REQUIRED')
    own = values['self_user']+values['self_system']
    children = values['children_user']+values['children_system']
    return {'self_cpu_seconds':own, 'children_cpu_seconds':children,
            'total_measured_cpu_seconds':own+children, 'kernel_cpu_deltas_seconds':values}

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
    publication = read(directory/'PUBLICATION.json')
    if publication.get('source_sha256') != manifest['source_sha256'] and 'COMPOSED_PUBLICATION.json' not in names:
        raise ValueError('COMPOSED_PUBLICATION_REQUIRED')
    if 'COMPOSED_PUBLICATION.json' in names:
        for name, expected in publication.get('files', {}).items():
            if Path(name).name != name or not (directory/name).is_file() or digest(directory/name) != expected:
                raise ValueError('COMPOSED_HISTORICAL_PAPER_ASSET_CHANGED')
        if digest(directory/'PDF_QA.json') != publication.get('pdf_qa_sha256'):
            raise ValueError('COMPOSED_HISTORICAL_PDF_QA_CHANGED')
        verify_composed_binding(read(directory/'COMPOSED_PUBLICATION.json'), source['executing_source']['files'],
                                read(directory/'PUBLICATION.json'), qualification,
                                digest(directory/'QUALIFICATION.json'), directory/'connected014-source.zip')
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
        manual = gate.get('observed_retired_manual_workflows', {})
        if (not isinstance(manual, dict) or any(name not in RETIRED_MANUAL_WORKFLOWS
                or not isinstance(row, dict) or row.get('head_sha') != expected_commit
                or row.get('event') != 'workflow_dispatch' or row.get('head_branch') != 'main'
                or row.get('conclusion') != 'success' or row.get('path') != '.github/workflows/'+name
                for name, row in manual.items())):
            raise ValueError('SOURCE_BOUND_OBSERVED_MANUAL_GATE_REQUIRED')
    return manifest


HISTORICAL_SOURCE = 'b0eae06dabfdf09197a60b60d3680f7f67946936631fafe431dc6be1f9b56983'
HISTORICAL_PUBLICATION = '1db280be4dbae777d12a23dcb1aded270fdcab0563de55319bef8493fa829e66'
COMPOSED_SCOPE = 'CURRENT_ENGINEERING_QUALIFICATION_WITH_UNCHANGED_HISTORICAL_PAPER_NOT_FRESH_ECONOMIC_CONFIRMATION'

def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

HISTORICAL_SNAPSHOTS = 'historical/strategic024-prior-source/'

def historical_source(source, expected_files):
    # Reconstruct historical identity from actual source bytes. Only changed
    # files need plain byte-exact snapshots; unchanged files are not duplicated.
    if len(expected_files) != 149 or canonical_digest(expected_files) != HISTORICAL_SOURCE:
        raise ValueError('HISTORICAL_SOURCE_CHANGED')
    archive = None
    if Path(source).is_dir():
        root = Path(source)
        def get(name):
            p=root/name
            if p.is_symlink() or any(q.is_symlink() for q in p.parents):
                raise ValueError('HISTORICAL_SOURCE_UNSAFE_MEMBER')
            return p.read_bytes() if p.is_file() else None
    else:
        archive=zipfile.ZipFile(source)
        names=set(checked_members(archive))
        def get(name):return archive.read(name) if name in names else None
    try:
        actual={}; total=0
        for name, expected in expected_files.items():
            p=PurePosixPath(name)
            if p.is_absolute() or '..' in p.parts or p.as_posix()!=name:
                raise ValueError('HISTORICAL_SOURCE_UNSAFE_MEMBER')
            raw=get(name)
            if raw is None or hashlib.sha256(raw).hexdigest()!=expected:
                raw=get(HISTORICAL_SNAPSHOTS+name+'.txt')
            if raw is None or hashlib.sha256(raw).hexdigest()!=expected:
                raise ValueError('HISTORICAL_SOURCE_CHANGED '+name)
            total+=len(raw)
            if total>LIMIT:raise ValueError('HISTORICAL_SOURCE_MEMBERS_OR_BOUND')
            actual[name]=hashlib.sha256(raw).hexdigest()
        return actual
    finally:
        if archive is not None:archive.close()

def verify_composed_binding(binding, current_files, publication, qualification, qualification_sha, history_archive):
    if (binding.get('schema') != 'agi-alpha/composed-publication/v1'
            or binding.get('scope') != COMPOSED_SCOPE
            or binding.get('historical_source_sha256') != HISTORICAL_SOURCE
            or publication.get('source_sha256') != HISTORICAL_SOURCE
            or canonical_digest(publication) != HISTORICAL_PUBLICATION
            or binding.get('historical_publication_sha256') != HISTORICAL_PUBLICATION):
        raise ValueError('COMPOSED_HISTORICAL_PUBLICATION_CHANGED')
    prior = historical_source(history_archive, binding['historical_files'])
    changes = {p: {'before_sha256':prior.get(p), 'after_sha256':current_files.get(p)}
               for p in sorted(set(prior) | set(current_files)) if prior.get(p) != current_files.get(p)}
    if (binding.get('current_files') != current_files
            or binding.get('current_source_sha256') != canonical_digest(current_files)
            or binding.get('source_delta') != changes):
        raise ValueError('COMPOSED_SOURCE_DELTA_CHANGED')
    commands = qualification.get('commands', [])
    logs = qualification.get('logs', {})
    expected = ['run', 'resume', 'audit', 'package', 'audit']
    if (qualification.get('schema') != 'agi-alpha/connected014-clean-qualification/v1'
            or len(commands) != len(expected)):
        raise ValueError('COMPOSED_EXECUTED_COMMAND_RECEIPTS_REQUIRED')
    for row, action in zip(commands, expected):
        command = row.get('command', [])
        if (not isinstance(command, list) or len(command) < 4
                or command[1:4] != ['-m', 'connected_enterprise', action]
                or type(row.get('returncode')) is not int or row['returncode'] != 0
                or any(not isinstance(logs.get(row.get(stream)), str)
                       or not re.fullmatch('[0-9a-f]{64}', logs[row[stream]])
                       for stream in ['stdout', 'stderr'])):
            raise ValueError('COMPOSED_EXECUTED_COMMAND_RECEIPTS_REQUIRED')
    for key in ['native_and_operating_audit', 'keyfree_public_audit']:
        audit = qualification.get(key, {})
        if audit.get('accepted') is not True or audit.get('source_sha256') != canonical_digest(current_files):
            raise ValueError('COMPOSED_SOURCE_BOUND_AUDITS_REQUIRED')
    if (qualification.get('accepted') is not True or qualification.get('no_git_execution') is not True
            or qualification.get('completed_resume_financially_unchanged') is not True
            or qualification.get('source_sha256') != canonical_digest(current_files)
            or qualification.get('source_files') != current_files
            or binding.get('qualification_sha256') != qualification_sha
            or binding.get('source_archive_sha256') != qualification['source_archive']['sha256']
            or binding.get('public_archive_sha256') != qualification['public_archive']['sha256']):
        raise ValueError('COMPOSED_ACTUAL_QUALIFICATION_REQUIRED')
    return binding

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
    composed = None
    if publication.get('source_sha256') != receipt['source_sha256']:
        registration = ROOT/'evidence/strategic024-publication/COMPOSED_SOURCE_BINDING.json'
        history_archive = ROOT
        if not registration.is_file() or registration.is_symlink():
            raise ValueError('PAPER_EXECUTING_SOURCE_CHANGED')
        composed = dict(read(registration))
        # Only actual clean qualification supplies acceptance; registration alone grants nothing.
        composed.update(qualification_sha256=digest(qualification/'QUALIFICATION.json'),
                        source_archive_sha256=receipt['source_archive']['sha256'],
                        public_archive_sha256=receipt['public_archive']['sha256'])
        verify_composed_binding(composed, identity(ROOT)['files'], publication, receipt,
                                digest(qualification/'QUALIFICATION.json'), history_archive)
        for row in receipt['commands']:
            for stream in ['stdout', 'stderr']:
                name = row[stream]
                if (Path(name).name != name or not (qualification/name).is_file()
                        or (qualification/name).is_symlink()
                        or digest(qualification/name) != receipt['logs'][name]):
                    raise ValueError('COMPOSED_EXECUTION_LOG_BYTES_CHANGED')
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
    if composed is not None:
        write(output/'COMPOSED_PUBLICATION.json', composed)
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
    if composed is not None:
        notes += ('\nThe unchanged paper describes historical source '+HISTORICAL_SOURCE+
                  ', NOT this composed financial implementation. COMPOSED_PUBLICATION.json separately binds '
                  'actual current-source engineering qualification and the complete declared source delta. '
                  'No fresh economic confirmation or recovered original-account continuity is claimed.\n')
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

def qualifying_runs(workflows, source_commit, *, event='push'):
    accepted = {}
    for name, runs in workflows.items():
        matches = [row for row in runs if row.get('head_sha') == source_commit and row.get('event') == event
                   and row.get('head_branch') == 'main' and row.get('path') == '.github/workflows/'+name]
        if not matches:
            continue
        latest = max(matches, key=lambda row:(row['run_number'], row.get('run_attempt', 1), row['id']))
        if latest['status'] == 'completed':
            if latest['conclusion'] != 'success':
                raise ValueError('EXACT_MAIN_QUALIFICATION_FAILED:'+name)
            accepted[name] = {key:latest[key] for key in ('id', 'head_sha', 'event', 'head_branch', 'path', 'conclusion', 'html_url')}
    return accepted

def observed_retired_manual_runs(workflows, source_commit):
    """No manual run is required; an actually observed same-head run must finish successfully."""
    observed = {name: [row for row in rows if row.get('head_sha') == source_commit
                      and row.get('event') == 'workflow_dispatch' and row.get('head_branch') == 'main'
                      and row.get('path') == '.github/workflows/'+name]
                for name, rows in workflows.items() if name in RETIRED_MANUAL_WORKFLOWS}
    observed = {name:rows for name,rows in observed.items() if rows}
    accepted = qualifying_runs(observed, source_commit, event='workflow_dispatch') if observed else {}
    return observed, accepted

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
        manual_runs = {name:gh(f'repos/{repository}/actions/workflows/{name}/runs?head_sha={source_commit}&event=workflow_dispatch&branch=main&per_page=100')['workflow_runs'] for name in RETIRED_MANUAL_WORKFLOWS}
        manual_observed, manual_accepted = observed_retired_manual_runs(manual_runs, source_commit)
        if set(accepted) == required and set(manual_accepted) == set(manual_observed):
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
            'applicability':applicability, 'observed_retired_manual_workflows':manual_accepted}
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

def failure_checkpoint(operation, output, source_commit, source_sha256):
    """Preserve bounded public diagnostics without auditing or reopening accounts."""
    from connected_enterprise.runner import read_freeze, tasks
    operation, output = Path(operation).absolute(), Path(output).absolute()
    if any(path.is_symlink() for path in [operation, *operation.parents, output, *output.parents]):
        raise ValueError('UNSYMLINKED_FAILURE_CHECKPOINT_REQUIRED')
    captured = {}
    def read_member(name, optional=False):
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or '..' in relative.parts or '\\' in name
                or '.git' in relative.parts or '.sqlite' in name or name.endswith('.adaptive-simulation-key')):
            raise ValueError('UNSAFE_OR_PRIVATE_FAILURE_MEMBER')
        if name in captured:
            return captured[name]
        path = operation.joinpath(*relative.parts)
        if any(part.is_symlink() for part in [path, *path.parents]):
            raise ValueError('UNSYMLINKED_FAILURE_MEMBER_REQUIRED')
        if not path.exists() and optional:
            return None
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 32_000_000:
                raise ValueError('BOUNDED_REGULAR_FAILURE_MEMBER_REQUIRED')
            raw = stream.read(32_000_001)
            after = os.fstat(stream.fileno())
        if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_nlink, before.st_mode)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_nlink, after.st_mode)
                or len(raw) != before.st_size):
            raise ValueError('FAILURE_MEMBER_CHANGED_DURING_CAPTURE')
        captured[name] = raw
        return raw
    frozen_raw = read_member('FROZEN.json')
    frozen = read_freeze(operation)
    if json.loads(frozen_raw) != frozen or frozen['source']['sha256'] != source_sha256:
        raise ValueError('FAILURE_CHECKPOINT_RELEASE_SOURCE_MISMATCH')
    registered = [row['id'] for row in tasks(frozen['protocol'])]
    if (not 1 <= len(registered) <= 1000 or len(registered) != len(set(registered))
            or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,159}', name) for name in registered)):
        raise ValueError('BOUNDED_REGISTERED_FAILURE_WORLDS_REQUIRED')
    archive, candidate = output/'failed-operation-keyfree.zip', output/'.failed-operation-candidate.zip'
    if archive.exists() or candidate.exists():
        raise FileExistsError('NEW_FAILURE_CHECKPOINT_REQUIRED')
    files, missing, total = {}, [], 0
    with zipfile.ZipFile(candidate, 'x', compression=zipfile.ZIP_STORED) as zipped:
        def include(name, expected=None, optional=False):
            nonlocal total
            if name in files:
                if expected is not None and files[name]['sha256'] != expected:
                    raise ValueError('FAILURE_MEMBER_BINDING_COLLISION')
                return
            raw = read_member(name, optional)
            if raw is None:
                missing.append(name)
                return
            if len(files) >= 10000 or total + len(raw) > LIMIT:
                raise ValueError('BOUNDED_REGULAR_FAILURE_MEMBER_REQUIRED')
            actual = hashlib.sha256(raw).hexdigest()
            if expected is not None and actual != expected:
                raise ValueError('FAILURE_MEMBER_HASH_MISMATCH')
            zipped.writestr(name, raw)
            files[name] = {'sha256':actual, 'bytes':len(raw)}
            total += len(raw)
        for name in ('FROZEN.json', 'SERVICES.json', 'PROGRESS.json', 'REPORT.json', 'COMPLETE.json', 'PACKAGE_AUDIT.json'):
            include(name, optional=name not in {'FROZEN.json', 'SERVICES.json'})
        services = json.loads(captured['SERVICES.json'])
        from adaptive_enterprise.instruments import _validate_manifest
        _validate_manifest(operation/'source', services)
        if any(frozen['source']['files'].get(name) != expected for name, expected in services['source_hashes'].items()):
            raise ValueError('FAILURE_SERVICE_SOURCE_BINDING_MISMATCH')
        for name, expected in frozen['source']['files'].items():
            include('source/'+name, expected)
        job_fields = {'id','service_id','accepted','work_keys','input','input_sha256','artifact','artifact_sha256','receipt','receipt_sha256'}
        seen = set()
        for job in services['jobs']:
            if (not isinstance(job, dict) or set(job) != job_fields or not isinstance(job.get('id'), str)
                    or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,159}', job['id']) or job['id'] in seen
                    or type(job.get('accepted')) is not bool):
                raise ValueError('BOUND_FAILURE_SERVICE_JOB_REQUIRED')
            seen.add(job['id'])
            for field, filename in (('input','input.json'), ('artifact','artifact.json'), ('receipt','acceptance.json')):
                if (job[field] != 'service-inputs/'+job['id']+'/'+filename
                        or not isinstance(job[field+'_sha256'], str) or not re.fullmatch('[0-9a-f]{64}', job[field+'_sha256'])):
                    raise ValueError('CANONICAL_FAILURE_SERVICE_PATH_REQUIRED')
                include('source/'+job[field], job[field+'_sha256'])
        for ident in registered:
            for name in ('RESULT.json', 'STATE.json', 'AUDIT.json', 'GROWTH.json'):
                include('worlds/'+ident+'/'+name, optional=True)
        checkpoint = {'schema':'agi-alpha/connected014-failure-checkpoint/v1',
            'scope':'UNQUALIFIED_FAILURE_CHECKPOINT_NOT_RESUME_AUTHORITY', 'source_commit':source_commit,
            'source_sha256':source_sha256, 'frozen_sha256':frozen['sha256'], 'registered_world_ids':registered,
            'consistent_cut':'NOT_ATTESTED; individual file bytes are hash-bound; no financial or operating audit performed.',
            'files':files, 'missing_optional_files':missing}
        zipped.writestr('FAILURE_CHECKPOINT.json', json.dumps(checkpoint, sort_keys=True, separators=(',', ':'), allow_nan=False))
    with zipfile.ZipFile(candidate) as zipped:
        checked_members(zipped)
    candidate.replace(archive)
    return {'path':archive.name, 'sha256':digest(archive), 'bytes':archive.stat().st_size,
            'files':len(files), 'scope':checkpoint['scope'], 'consistent_cut':checkpoint['consistent_cut']}

def operate_download(directory, output, source_commit, timeout, actual_release_download=False):
    directory, output = Path(directory).resolve(), Path(output).resolve()
    manifest = verify_assets(directory, source_commit)
    if output.exists() or any(path.is_symlink() for path in [output, *output.parents]):
        raise ValueError('NEW_UNSYMLINKED_DOWNLOADED_OPERATION_REQUIRED')
    output.mkdir(parents=True)
    cpu_start, wall_start = cpu_usage(), time.monotonic()
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
               'scope':'SIMULATED_RELEASED_DEFAULT_EXPERIMENT_REPRODUCTION_NOT_UNTOUCHED_CONFIRMATION',
               'resource_policy':{'policy_version':'platform-aligned-telemetry-v2',
                   'cpu_limit_seconds':None, 'cpu_acceptance_gate':False,
                   'historical_cpu_reference_seconds':HISTORICAL_CPU_REFERENCE_SECONDS,
                   'hosted_job_limit_seconds':HOSTED_JOB_LIMIT_SECONDS,
                   'receipt_shutdown_reserve_seconds':RECEIPT_SHUTDOWN_RESERVE_SECONDS,
                   'wall_limit_seconds':timeout, 'measurement':'POSIX kernel RUSAGE_SELF plus RUSAGE_CHILDREN deltas; includes waited descendants.',
                   'enforcement':'CPU is measured after each completed subprocess and at final receipt, never an acceptance or spending gate. A finite platform-aligned wall deadline terminates hangs and leaves receipt/shutdown time; no retry or extra experiment is authorized.',
                   'scope':'Run, resume, native/operating audits, key-free packaging, public-copy audit and wrapper work after verified-asset/output-root admission. Initial asset verification and unavailable host/model billing are excluded.'}}
    def measure():
        measured = cpu_delta(cpu_start, cpu_usage())
        measured['wall_seconds'] = time.monotonic()-wall_start
        measured['historical_cpu_reference_exceeded'] = measured['total_measured_cpu_seconds'] > HISTORICAL_CPU_REFERENCE_SECONDS
        measured['coverage'] = 'COMPLETED_WAITED_COMMANDS; ACTIVE_COMMAND_CPU_NOT_YET_REAPED' if receipt.get('active_command') else 'COMPLETED_WAITED_PROCESS_TREE'
        receipt['resources'] = measured
        write(output/'DOWNLOADED_RELEASE_RUN.json', receipt)
        return measured
    def command(arguments, cwd, label):
        receipt['active_command'] = label
        measure()
        run_command(arguments, cwd, output/label, deadline, commands)
        receipt['active_command'] = None
        measure()
    try:
        operation = output/'operation'
        base = [sys.executable, '-m', 'connected_enterprise']
        command(base+['run', '--output', str(operation)], source, '01-run')
        if read(operation/'FROZEN.json')['source']['sha256'] != manifest['source_sha256']:
            raise ValueError('DOWNLOADED_EXECUTION_SOURCE_CHANGED')
        before = native_state(operation)
        command(base+['resume', '--output', str(operation)], source, '02-resume')
        if native_state(operation) != before:
            raise ValueError('DOWNLOADED_RESUME_CHANGED_MONEY_OR_WORK')
        command(base+['audit', '--output', str(operation)], source, '03-audit')
        if not read(operation/'PACKAGE_AUDIT.json').get('accepted'):
            raise ValueError('DOWNLOADED_NATIVE_OPERATING_AUDIT_REJECTED')
        operating_archive = output/'downloaded-operation-keyfree.zip'
        candidate_archive = output/'.downloaded-operation-candidate.zip'
        command(base+['package', '--output', str(operation), '--archive', str(candidate_archive)], source, '04-package-actual-operation')
        operating_public = output/'downloaded-operation-public'
        with zipfile.ZipFile(candidate_archive) as archive:
            checked_members(archive)
            archive.extractall(operating_public)
        command(base+['audit', '--output', str(operating_public)], operating_public/'source', '05-actual-operation-public-audit')
        operating_public_audit = read(operating_public/'PACKAGE_AUDIT.json')
        if not operating_public_audit.get('accepted') or operating_public_audit.get('source_sha256') != manifest['source_sha256']:
            raise ValueError('DOWNLOADED_OPERATION_PUBLIC_AUDIT_REJECTED')
        candidate_archive.replace(operating_archive)
        receipt['downloaded_operation_package'] = {'path':operating_archive.name, 'bytes':operating_archive.stat().st_size,
            'sha256':digest(operating_archive), 'scope':'ACTUAL_DOWNLOADED_IMPLEMENTATION_RUN_KEY_FREE_AUDIT_AND_REPRODUCTION_NOT_ACCOUNT_TAKEOVER'}
        public = output/'published-keyfree'
        with zipfile.ZipFile(directory/'connected014-keyfree.zip') as archive:
            checked_members(archive)
            archive.extractall(public)
        command(base+['audit', '--output', str(public)], public/'source', '06-released-public-audit')
        if (not read(public/'PACKAGE_AUDIT.json').get('accepted')
                or read(public/'PACKAGE_AUDIT.json').get('source_sha256') != manifest['source_sha256']):
            raise ValueError('RELEASED_PUBLIC_EVIDENCE_SOURCE_CHANGED')
        receipt.update(accepted=True, completed_resume_financially_unchanged=True,
                       native_and_operating_audit=read(operation/'PACKAGE_AUDIT.json'),
                       downloaded_operation_public_audit=operating_public_audit,
                       released_public_audit=read(public/'PACKAGE_AUDIT.json'),
                       operating_report=read(operation/'REPORT.json'))
    except BaseException as error:
        receipt['failure'] = {'type':type(error).__name__, 'message':str(error)}
        try:
            receipt['failure_checkpoint'] = failure_checkpoint(output/'operation', output, source_commit, manifest['source_sha256'])
        except BaseException as checkpoint_error:
            receipt['checkpoint_failure'] = {'type':type(checkpoint_error).__name__, 'message':str(checkpoint_error)}
        raise
    finally:
        measure()
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
            sub.add_argument('--timeout-seconds', type=int, default=OPERATING_HANG_TIMEOUT_SECONDS)
            sub.add_argument('--actual-release-download', action='store_true')
        elif name == 'download':
            sub.add_argument('--repository', required=True)
            sub.add_argument('--receipt', required=True)
    args = parser.parse_args()
    if args.command == 'publish' and not 1 <= args.timeout_seconds <= 2400:
        parser.error('publish timeout-seconds must be 1..2400')
    if args.command == 'operate-download' and not 1 <= args.timeout_seconds <= OPERATING_HANG_TIMEOUT_SECONDS:
        parser.error(f'operate-download timeout-seconds must be 1..{OPERATING_HANG_TIMEOUT_SECONDS} (hosted job ceiling minus receipt reserve)')
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
