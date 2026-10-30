import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

PIN = 'd4cccb5b6756bb14d52568c82720dde1dd3d42e1'
PREFIX = 'https://github.com/MassBank/MassBank-data/blob/' + PIN + '/'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def parse(raw):
    lines = raw.decode('utf-8').splitlines()
    data = {}
    peaks = []
    in_peaks = False
    for line in lines:
        if line.startswith('PK$PEAK:'):
            in_peaks = True
            continue
        if in_peaks:
            if line.startswith('//'):
                break
            fields = line.split()
            if fields:
                peaks.append([float(fields[0]), float(fields[1])])
        elif ': ' in line:
            key, value = line.split(': ', 1)
            data.setdefault(key, []).append(value)
    return data, peaks


def verify(dataset, admission, source_repo, expected_dataset_sha256, expected_admission_sha256, output):
    dataset, admission, source_repo, output = [Path(p).resolve() for p in (dataset, admission, source_repo, output)]
    if output.exists():
        raise FileExistsError(output)
    raw_data, raw_admission = dataset.read_bytes(), admission.read_bytes()
    if sha(raw_data) != expected_dataset_sha256 or sha(raw_admission) != expected_admission_sha256:
        raise ValueError('EXTERNAL_DATASET_OR_ADMISSION_IDENTITY')
    records, cohort = json.loads(raw_data), json.loads(raw_admission)
    if cohort['type'] != 'RETROSPECTIVE_DEVELOPMENT_ONLY' or cohort['source_commit'] != PIN:
        raise ValueError('UNQUALIFIED_ADMISSION_SCOPE')
    head = subprocess.check_output(['git', '-C', str(source_repo), 'rev-parse', 'HEAD'], text=True).strip()
    if head != PIN:
        raise ValueError('SOURCE_REPOSITORY_REVISION')
    checks = []
    cells = {}
    for record in records:
        url = record['source_url']
        if not url.startswith(PREFIX):
            raise ValueError('SOURCE_URL_SCOPE')
        path = url[len(PREFIX):]
        if Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('SOURCE_PATH_SCOPE')
        canonical = subprocess.check_output(['git', '-C', str(source_repo), 'show', PIN+':'+path])
        local = dataset.parent / record['record_file']
        if sha(canonical) != record['sha256'] or local.read_bytes() != canonical:
            raise ValueError('PUBLISHED_RECORD_IDENTITY')
        fields, peaks = parse(canonical)
        focused = fields.get('MS$FOCUSED_ION', [])
        ms = fields.get('AC$MASS_SPECTROMETRY', [])
        def one(prefix, values):
            matches = [value[len(prefix):] for value in values if value.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError('METADATA_FIELD_MULTIPLICITY')
            return matches[0]
        identity = one('INCHIKEY ', fields.get('CH$LINK', []))
        energy = one('COLLISION_ENERGY ', ms)
        exact = (record['peaks'] == peaks and record['inchikey'] == identity and record['formula'] == fields['CH$FORMULA'][0] and
                 record['energy'] == energy and record['mode'] == one('ION_MODE ', ms) and
                 record['adduct'] == one('PRECURSOR_TYPE ', focused) and record['precursor'] == one('PRECURSOR_M/Z ', focused) and
                 record['instrument'] == fields['AC$INSTRUMENT'] and record['fragmentation_mode'] == one('FRAGMENTATION_MODE ', ms))
        admitted = (record['formula'] == cohort['selected_formula'] and record['mode'] == cohort['mode'] and record['adduct'] == cohort['adduct'] and
                    record['instrument'] == cohort['exact_instrument'] and record['fragmentation_mode'] == cohort['fragmentation_mode_field'] and
                    record['inchikey'] in cohort['identities'] and energy in cohort['energies'] and bool(re.fullmatch(r'\d+(?:\.\d+)? % \(nominal\)', energy)))
        identity_claim = any(value.strip() in ('CONFIDENCE 1', 'CONFIDENCE standard compound') for value in fields.get('COMMENT', []))
        attribution = fields.get('LICENSE') == record['license'] and fields.get('AUTHORS') == record['authors']
        if not exact or not admitted or not identity_claim or not attribution:
            raise ValueError('METADATA_PEAKS_OR_ADMISSION_MISMATCH')
        cells.setdefault((identity, energy), []).append(record['sha256'])
        checks.append({'record_sha256': record['sha256'], 'source_url': url, 'source_git_bytes_match': True, 'metadata_and_full_peak_values_match': True,
                       'confidence': fields.get('COMMENT'), 'attribution_preserved': True, 'raw_record_bytes': len(canonical)})
    expected_cells = {(identity, energy) for identity in cohort['identities'] for energy in cohort['energies']}
    if set(cells) != expected_cells or len(records) != cohort['record_count']:
        raise ValueError('COMPLETE_ADMITTED_COHORT_COVERAGE')
    output.mkdir(parents=True)
    report = {'schema': 'agi-alpha/massbank-source-verification007/v1', 'accepted_source_development': True,
              'source_commit': PIN, 'dataset_sha256': sha(raw_data), 'admission_sha256': sha(raw_admission),
              'verifier_sha256': sha(Path(__file__).read_bytes()), 'records_verified': len(records), 'identities': len(cohort['identities']),
              'energies': len(cohort['energies']), 'cells': len(cells), 'repeated_cells': sum(len(rows)>1 for rows in cells.values()), 'checks': checks,
              'independent_replicates_established': False, 'protected_confirmation_qualified': False, 'statistical_alpha_spent': 0,
              'limits': 'Verifies published record identity, data extraction and metadata contract only. Source-reported standard/confidence is not new independent chemical authentication. No independent repeat measurement or physical acquisition experiment; all records exposed development. No scientific superiority or consequential enabling claim.'}
    with (output/'REPORT.json').open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2);stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('dataset', 'admission', 'source-repo', 'expected-dataset-sha256', 'expected-admission-sha256', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = verify(args.dataset, args.admission, args.source_repo, args.expected_dataset_sha256, args.expected_admission_sha256, args.output)
    print(json.dumps({key: result[key] for key in ('accepted_source_development', 'records_verified', 'identities', 'energies', 'repeated_cells')}))
