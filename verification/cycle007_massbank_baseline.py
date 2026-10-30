import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import ms_entropy


def verify(data, baseline, output):
    data, baseline, output = [Path(p).resolve() for p in (data, baseline, output)]
    if output.exists():
        raise FileExistsError(output)
    admission = json.loads((data/'ADMISSION.json').read_text())
    observed = json.loads((data/'observations.json').read_text())
    reported = json.loads(baseline.read_text())
    if hashlib.sha256((data/'observations.json').read_bytes()).hexdigest() != reported['input_sha256']:
        raise ValueError('BASELINE_INPUT_IDENTITY')
    ids, energies = admission['identities'], admission['energies']
    lookup = {}
    for record in observed:
        raw = (data/record['record_file']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record['sha256']:
            raise ValueError('SOURCE_RECORD_IDENTITY')
        text = raw.decode('utf-8').split('PK$PEAK:', 1)[1].splitlines()[1:]
        peaks = []
        for line in text:
            if line.startswith('//'):
                break
            fields = line.split()
            if fields:
                peaks.append([float(fields[0]), float(fields[1])])
        key = (record['inchikey'], record['energy'])
        if key in lookup:
            raise ValueError('REPEATED_CELL_NOT_SUPPORTED_BY_THIS_FIXED_COHORT_CHECK')
        lookup[key] = peaks
    results = []
    all_match = True
    for energy, reference in zip(energies, reported['results']):
        matrix = [[float(ms_entropy.calculate_entropy_similarity(lookup[i, energy], lookup[j, energy], ms2_tolerance_in_da=0.02, clean_spectra=True)) for j in ids] for i in ids]
        match = reference['energy'] == energy and all(abs(matrix[i][j]-reference['matrix'][i][j]) <= 1e-10 for i in range(len(ids)) for j in range(len(ids)))
        unique = all(matrix[i][i] > max(matrix[i][j] for j in range(len(ids)) if j != i)+1e-8 for i in range(len(ids)))
        results.append({'energy': energy, 'matrix': matrix, 'reported_matrix_matches': match, 'exact_reference_self_match_unique': unique})
        all_match &= match
    result = {'schema': 'agi-alpha/massbank-baseline-verification007/v1', 'accepted_reproduction': bool(all_match),
              'source_records': len(lookup), 'identities': len(ids), 'energy_settings': len(energies),
              'baseline_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(), 'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'package': {'ms-entropy': importlib.metadata.version('ms-entropy')}, 'results': results,
              'ordinary_single_energy_reference_separation_exists': any(row['exact_reference_self_match_unique'] for row in results),
              'independence': 'Independent raw-record extraction and replay; shared pinned ms-entropy library, source records, host/model family. Not independent algorithm certification.',
              'scope': 'Retrospective exact library-profile geometry. Query equals library record; this is not unknown-sample accuracy, noise robustness, independent replicate confirmation or a new physical measurement experiment. Existing one-energy route removes the noiseless closed-library enabling-gap hypothesis.',
              'statistical_alpha_spent': 0, 'protected_confirmation_qualified': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2);stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('data', 'baseline', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = verify(args.data, args.baseline, args.output)
    print(json.dumps({'accepted_reproduction': result['accepted_reproduction'], 'ordinary_single_energy_reference_separation_exists': result['ordinary_single_energy_reference_separation_exists']}))
    sys.exit(0 if result['accepted_reproduction'] else 1)
