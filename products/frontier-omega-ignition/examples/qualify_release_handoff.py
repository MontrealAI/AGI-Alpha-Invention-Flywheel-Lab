"""Build a pinned public edition, deliver a fresh receiver, and test real received directories."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
sys.path.insert(0, str(PRODUCT))
from ignition.construction import build, freeze_contract
from ignition.delivery import export_bundle
from ignition.evaluation import evaluate
from ignition.portable import MEMBERS
from ignition.store import digest, runtime_source, strict_json


PIN = '09e611c6df506ab24fba494b1ec41716e3721049'
SOURCE_ID = 'd19a7d9e0217e3d741e4b6e23705315c54c64209390fe862dc2e4421d062db49'
ASSEMBLY_ID = 'ddabff0bec7715860ee894d77607ff9570e836076a3626a9ab5de33a0b5d0f39'
BASE = 'docs/research/frontier-omega-world-lab.html'
EDITION = 'docs/frontier-omega-ignition/research-edition'
FRAGMENTS = ('assemble.py', 'construction-core.js', 'studio-ui.js', 'ignition-ui.js',
             'studio.html', 'studio.css', 'ignition.html', 'ignition.css', 'independent_check.py',
             'README.md', 'DEMO_SCRIPT.md', 'tests/test_construction.cjs', 'tests/test_browser.py',
             'tests/test_ignition.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def assemble(work, reference_tree):
    source = work / 'source'
    hashes = {}
    for path in [BASE] + [EDITION + '/' + name for name in FRAGMENTS]:
        if reference_tree:
            blob = (reference_tree / path).read_bytes()
        else:
            blob = subprocess.check_output(['git', 'cat-file', 'blob', PIN + ':' + path], cwd=REPO)
        hashes[path] = sha(blob)
        destination = source / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(blob)
    check(digest(hashes) == SOURCE_ID, 'Pinned source bytes differ; refusing to run that assembler')
    clean = work / 'sender'
    subprocess.run([sys.executable, '-I', str(source / EDITION / 'assemble.py'), '--base', str(source / BASE),
                    '--output', str(clean)], check=True, capture_output=True)
    manifest_bytes = (clean / 'ASSEMBLY.json').read_bytes()
    check(sha(manifest_bytes) == ASSEMBLY_ID, 'Assembled manifest differs from pinned clean reference')
    expected = strict_json(manifest_bytes)['files'] | {'ASSEMBLY.json': ASSEMBLY_ID}
    return clean, expected


def expected_result(manifest, changed=(), missing=(), unexpected=()):
    return {'ok': not (changed or missing or unexpected),
            'matched': sorted(set(manifest).difference(changed, missing)), 'changed': sorted(changed),
            'missing': sorted(missing), 'unexpected': sorted(unexpected)}


def gnu_audit(folder, manifest, executable):
    # Match the complete workload. Plain sha256sum --check misses unlisted files.
    # These temporary directories are our own public, regular-file fixtures.
    names = sorted(str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file())
    output = subprocess.check_output([executable, '--zero', '--', *names], cwd=folder)
    observed = {}
    for record in output.split(b'\0')[:-1]:
        observed[record[66:].decode('utf-8')] = record[:64].decode('ascii')
    changed = [name for name in observed.keys() & manifest.keys() if observed[name] != manifest[name]]
    return expected_result(manifest, changed, manifest.keys() - observed.keys(), observed.keys() - manifest.keys())


def make_receiver(manifest, clean):
    # Freeze the clean output from the trusted sender. Directory cases below exercise the standalone receiver.
    content = {name: base64.b64encode((clean / name).read_bytes()).decode('ascii') for name in sorted(manifest)}
    spec = {'kind': 'manifest_audit', 'purpose': 'Audit the whole public research edition against pinned sender bytes.',
            'definition': {'manifest': manifest}, 'cases': [
                {'name': 'Complete public edition', 'input': {'files': content}, 'expected': expected_result(manifest)},
                {'name': 'Nothing received', 'input': {'files': {}}, 'expected': expected_result(manifest, missing=manifest)}]}
    contract = freeze_contract(spec)
    artifact = build(contract, {'kind': 'manifest_audit', 'program': {'manifest': manifest}})
    receipt = evaluate(contract, artifact)
    check(receipt['status'] == 'pass', 'New receipt checker did not pass its frozen contract')
    bundle = export_bundle(contract, artifact, receipt, {'source_revision': PIN, 'model_calls': 0,
                           'mode': 'direct deterministic compilation of a public, trusted delivery manifest'})
    return bundle, contract['sha256'], artifact['sha256']


def challenge_copy(clean, destination, scenario):
    shutil.copytree(clean, destination)
    changes, missing, extra = [], [], []
    if scenario == 'changed_missing_extra':
        with (destination / 'index.html').open('ab') as html:
            html.write(b'\n')
        (destination / 'tests/test_browser.py').unlink()
        (destination / 'unlisted.css').write_bytes(b'/* extra */\n')
        changes, missing, extra = ['index.html'], ['tests/test_browser.py'], ['unlisted.css']
    if scenario == 'rewritten_received_reference':
        (destination / 'README.md').write_bytes(b'Received replacement edition\n')
        path = destination / 'ASSEMBLY.json'
        copied = strict_json(path.read_bytes())
        copied['files']['README.md'] = sha((destination / 'README.md').read_bytes())
        path.write_text(json.dumps(copied, indent=2) + '\n', encoding='utf-8')
        changes = ['ASSEMBLY.json', 'README.md']
    return changes, missing, extra


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-tree', type=Path, help='existing checkout of the pinned public edition')
    parser.add_argument('--output', type=Path, help='new directory for the portable receiver ZIP and JSON receipt')
    args = parser.parse_args()
    executable = shutil.which('sha256sum')
    check(executable, 'GNU sha256sum is required for the independent conventional comparison')
    version = subprocess.check_output([executable, '--version'], text=True).splitlines()[0]
    source = runtime_source()
    begin = time.perf_counter_ns()
    report = {'format': 'ignition/public-release-handoff/v1', 'created_at': datetime.now(timezone.utc).isoformat(),
              'source_url': 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/' + PIN,
              'revision': PIN, 'assembler_inputs_sha256': SOURCE_ID, 'pinned_assembly_sha256': ASSEMBLY_ID,
              'current_runtime_sha256': source, 'qualification_script_sha256': sha(Path(__file__).read_bytes()),
              'python': sys.version.split()[0], 'conventional': version + ' plus complete file-set comparison',
              'execution': 'New deterministic sender and recipient execution on public bytes; deliberately modified receiver copies.',
              'trust': 'The expected inventory and the digest of ASSEMBLY.json are fixed outside the received directories.',
              'model_calls': 0, 'complete_cost': 'unmeasured', 'cases': []}
    with tempfile.TemporaryDirectory(prefix='ignition-public-edition-') as temp:
        work = Path(temp)
        clean, manifest = assemble(work, args.reference_tree)
        bundle, contract, artifact = make_receiver(manifest, clean)
        runner = work / 'receiver'
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            check(set(archive.namelist()) == set(MEMBERS) | {'SHA256SUMS.json'}, 'Unexpected new package member')
            archive.extractall(runner)
        base = [sys.executable, '-I', 'run.py']
        confirmation = strict_json(subprocess.check_output([*base, 'verify'], cwd=runner))
        check(confirmation['status'] == 'pass', 'Standalone receiver verification failed')
        report.update(artifact_sha256=artifact, contract_sha256=contract, package_sha256=sha(bundle),
                      public_files=len(manifest), public_bytes=sum((clean / k).stat().st_size for k in manifest),
                      receiver_verification=confirmation)
        for scenario in ['clean', 'changed_missing_extra', 'rewritten_received_reference']:
            received = work / scenario
            defects = challenge_copy(clean, received, scenario)
            expected = expected_result(manifest, *defects)
            t0 = time.perf_counter_ns()
            result = subprocess.run([*base, 'audit-directory', str(received)], cwd=runner, capture_output=True)
            elapsed_candidate = time.perf_counter_ns() - t0
            check(result.returncode == (0 if expected['ok'] else 1), f'{scenario}: unexpected receiver exit {result.returncode}: {result.stderr[:300]}')
            received_result = strict_json(result.stdout)
            t0 = time.perf_counter_ns()
            ordinary = gnu_audit(received, manifest, executable)
            elapsed_ordinary = time.perf_counter_ns() - t0
            check(received_result == ordinary == expected, f'{scenario}: verdict or file classification differs')
            report['cases'].append({'scenario': scenario, 'result': received_result, 'matched_ordinary': True,
                                    'receiver_exit': result.returncode, 'receiver_wall_ns': elapsed_candidate,
                                    'ordinary_wall_ns': elapsed_ordinary})
        check(runtime_source() == source, 'Runtime changed during qualification')
        report['total_wall_ns'] = time.perf_counter_ns() - begin
        report['economics'] = 'Both routes met all three frozen file-level outcomes. Single local timings cover process and data handling only. Buyer demand, installation, review, engineering and support costs were not measured.'
        data = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.mkdir(exist_ok=False)
            (args.output / 'research-edition-receiver.zip').write_bytes(bundle)
            (args.output / 'release-handoff.json').write_text(data, encoding='utf-8')
        print(data, end='')


if __name__ == '__main__':
    main()
