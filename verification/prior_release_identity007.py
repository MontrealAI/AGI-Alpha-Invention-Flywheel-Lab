"""Read-only identity closure for the previously published cycle006 release."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import resource
import time
import zipfile


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(spec_path, downloads, output):
    started, cpu = time.monotonic(), time.process_time()
    spec_raw = spec_path.read_bytes()
    spec = json.loads(spec_raw)
    if spec['schema'] != 'agi-alpha/prior-release-identity-spec007/v1' or spec['tag_name'] != 'perturbation-construction-20261029-r1' or spec['target_commitish'] != 'cd90c81ab757a7042bf4d0384e8e1a7e6c2a9557':
        raise ValueError('PUBLISHED_RELEASE_SCOPE')
    output.mkdir(parents=True, exist_ok=False)
    assets = {item['name']: item for item in spec['assets']}
    if len(assets) != len(spec['assets']):
        raise ValueError('DUPLICATE_ASSET_NAME')
    checked = {}
    for name, item in assets.items():
        if Path(name).name != name:
            raise ValueError('ASSET_PATH_SCOPE')
        path = downloads / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != item['bytes']:
            raise ValueError('ASSET_SIZE_OR_SCOPE ' + name)
        digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
        if digest != item['sha256']:
            raise ValueError('ASSET_IDENTITY ' + name)
        checked[name] = {'bytes': item['bytes'], 'sha256': digest}
    sums = (downloads / 'SHA256SUMS.txt').read_text().splitlines()
    listed = {}
    for line in sums:
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        if name in listed or name not in assets or digest != assets[name]['sha256']:
            raise ValueError('PUBLISHED_CHECKSUM_LIST')
        listed[name] = digest
    if set(listed) != set(assets) - {'SHA256SUMS.txt'}:
        raise ValueError('PUBLISHED_CHECKSUM_SET')
    root = Path(__file__).resolve().parents[1]
    helper = root / 'verification/cycle006_archive_check.py'
    if helper.is_symlink() or sha(helper.read_bytes()) != spec['checker_sha256']:
        raise ValueError('TRUSTED_OLD_CHECKER_IDENTITY')
    module_spec = importlib.util.spec_from_file_location('pinned_cycle006_archive_checker', helper)
    checker = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(checker)
    source_name = 'AGI_ALPHA_Perturbation_Construction_006_source_evidence.zip'
    data, manifest, _ = checker.payloads(downloads / source_name, assets[source_name]['sha256'])
    freeze_path = 'campaign/cycle-006/REPRODUCTION_FREEZE.json'
    if sha(data[freeze_path]) != spec['reproduction_freeze_sha256'] or sha(data['campaign/cycle-006/CANDIDATE_FREEZE.json']) != spec['candidate_freeze_sha256']:
        raise ValueError('PRIOR_FREEZE_IDENTITY')
    freeze = json.loads(data[freeze_path])
    if any(sha(data[name]) != identity for name, identity in freeze['sources'].items()):
        raise ValueError('FROZEN_SOURCE_CLOSURE')
    qualification_raw = (downloads / 'ARCHIVE_QUALIFICATION.json').read_bytes()
    qualification = json.loads(qualification_raw)
    if qualification['archive_sha256'] != assets[source_name]['sha256'] or qualification['runtime_qualified'] is not True or qualification['identity_only'] is not False or qualification['verifier_sha256'] != spec['checker_sha256']:
        raise ValueError('PRESERVED_CI_QUALIFICATION_SCOPE')
    for row in qualification['checks'].values():
        if not (row['returncode'] == 0 if isinstance(row, dict) else row is True):
            raise ValueError('PRESERVED_CI_QUALIFICATION_FAILED')
    reports = {}
    with zipfile.ZipFile(downloads / 'CLEAN_ARCHIVE_RUNTIME_EVIDENCE.zip') as archive:
        for mode in ('ordinary', 'validated'):
            names = [name for name in archive.namelist() if name.endswith(mode + '-runtime/REPORT.json')]
            if len(names) != 1:
                raise ValueError('CI_RUNTIME_REPORT_NOT_UNIQUE')
            raw = archive.read(names[0])
            report = json.loads(raw)
            if report['source_freeze_sha256'] != spec['reproduction_freeze_sha256'] or report['all_predictions_reconstructed'] is not True or any(report['scientific_pilot_threshold_met'].values()) or not all(report['conditional_settlement_checks_passed'].values()) or report['actual_receipts'] != 0 or report['available_commercial_earned_funds'] != 0 or report['funded_successor'] is not False:
                raise ValueError('PRESERVED_CI_REPORT_SCOPE')
            reports[mode] = sha(raw)
    paper = {}
    for suffix in ('md', 'tex', 'pdf', 'html', 'build.json', 'inputs.json'):
        name = 'cycle-006.' + suffix
        if sha(data['docs/research/' + name]) != assets[name]['sha256']:
            raise ValueError('RELEASE_PAPER_SOURCE_MISMATCH')
        paper[name] = assets[name]['sha256']
    report = {'schema': 'agi-alpha/prior-release-identity007/v1', 'passed': True,
        'release_url': spec['release_url'], 'release_id': spec['release_id'], 'source_ref': spec['target_commitish'],
        'spec_sha256': sha(spec_raw), 'verifier_sha256': sha(Path(__file__).read_bytes()),
        'old_archive_parser_sha256': spec['checker_sha256'], 'assets_checked': checked,
        'downloaded_bytes': sum(item['bytes'] for item in assets.values()),
        'payload_files': len(data), 'manifest_sha256': sha(manifest),
        'reproduction_sources_checked': len(freeze['sources']),
        'reproduction_freeze_sha256': spec['reproduction_freeze_sha256'],
        'candidate_freeze_sha256': spec['candidate_freeze_sha256'],
        'preserved_CI_runtime_reports': reports, 'paper_identities': paper,
        'identity_qualified_now': True, 'new_runtime_execution': False,
        'original_failed_local_receipt_status': 'OVERRUN_NOT_QUALIFIED_UNCHANGED',
        'wall_seconds': time.monotonic()-started, 'process_cpu_seconds': time.process_time()-cpu,
        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'scope': 'Actual public release downloads match independently obtained GitHub asset digests, checksum list, full archive manifest and frozen source closure. Previously published CI runtime receipts are inspected, not reexecuted. This new identity-only receipt does not retroactively qualify the old overrun, establish scientific success or supply commercial earnings.'}
    with (output / 'IDENTITY.json').open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps({'passed': True, 'payload_files': len(data), 'reproduction_sources_checked': len(freeze['sources']), 'assets_checked': len(assets)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--downloads', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.spec, args.downloads, args.output)
