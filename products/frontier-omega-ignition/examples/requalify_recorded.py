"""Re-evaluate the published, previously constructed programs against this checkout."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from ignition import construction, delivery, evaluation
from ignition.portable import MEMBERS
from ignition.store import digest, runtime_source, strict_json


EVIDENCE = PRODUCT / 'evidence'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run_recipient(bundle, directory):
    directory.mkdir()
    # Only trusted, locally generated bundle bytes can reach this function.
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        require(set(archive.namelist()) == set(MEMBERS) | {'SHA256SUMS.json'},
                'Unexpected generated recipient members')
        archive.extractall(directory)
    def run(args, input_bytes=None):
        result = subprocess.run([sys.executable, '-I', 'run.py', *args], cwd=directory,
                                capture_output=True, input=input_bytes, check=True)
        return strict_json(result.stdout)
    return {'verify': run(['verify']), 'example': run(['run'], (directory / 'example-input.json').read_bytes())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='new directory for a replay receipt and two current-code bundles')
    args = parser.parse_args()
    historical = strict_json((EVIDENCE / 'assisted-runtime.json').read_bytes())
    require(digest(historical['files_sha256']) == historical['runtime_sha256'], 'Historical runtime mapping mismatch')
    original = strict_json((EVIDENCE / 'recipient-checks.json').read_bytes())
    source = runtime_source()
    report = {'format': 'ignition/recorded-artifact-requalification-v1',
              'mode': 'replay with fresh evaluation and recipient execution',
              'model_calls': 0, 'research_repeated': False,
              'historical_runtime_sha256': historical['runtime_sha256'], 'current_runtime_sha256': source,
              'replay_script_sha256': sha(Path(__file__).read_bytes()),
              'python': sys.version.split()[0], 'created_at': datetime.now(timezone.utc).isoformat(),
              'cases': []}
    require(original['snapshot'] == historical['runtime_sha256'], 'Inconsistent historical runtime references')
    require([row['mission'] for row in original['cases']] == ['integrity', 'migration', 'unsupported'],
            'Expected exactly the three public reference cases')
    bundles = {}
    with tempfile.TemporaryDirectory(prefix='ignition-public-replay-') as temp:
        for case in original['cases']:
            name = case['mission']
            raw = (EVIDENCE / f'{name}-run.json').read_bytes()
            require(sha(raw) == case['run_evidence_sha256'], f'{name}: run record hash mismatch')
            saved = strict_json(raw)
            require(saved['id'] == case['id'] and saved['runtime'] == historical['runtime_sha256'],
                    f'{name}: run identity mismatch')
            require(digest([saved['mission'], saved['sources']]) == saved['input_sha256'],
                    f'{name}: mission/source binding mismatch')
            base = {'mission': name, 'original_run': saved['id'], 'original_run_sha256': sha(raw)}
            if name == 'unsupported':
                require(saved['status'] == 'deferred' and saved['artifact'] is None, 'Negative control changed')
                report['cases'].append({**base, 'scope': 'historical deferral checked; no executable artifact'})
                continue
            old_zip = (EVIDENCE / f'{name}-artifact.zip').read_bytes()
            require(sha(old_zip) == case['bundle_sha256'], f'{name}: original bundle identity differs')
            with zipfile.ZipFile(io.BytesIO(old_zip)) as archive:
                for member, field in [('contract.json', 'contract'), ('artifact.json', 'artifact'), ('receipt.json', 'evaluation')]:
                    require(strict_json(archive.read(member)) == saved[field], f'{name}: archived {field} differs')
            contract, artifact = saved['contract'], saved['artifact']
            require(construction.freeze_contract(saved['mission']['construction_spec']) == contract,
                    f'{name}: construction contract differs from stated mission')
            fresh = evaluation.evaluate(contract, artifact)
            require(fresh['status'] == 'pass', f'{name}: current evaluator rejected the original program')
            context = {'execution_mode': 'recorded program replay; zero model calls', 'original_run_id': saved['id'],
                       'original_runtime_sha256': saved['runtime'], 'current_runtime_sha256': source}
            bundle = delivery.export_bundle(contract, artifact, fresh, context)
            recipient = run_recipient(bundle, Path(temp) / name)
            require(recipient['verify']['status'] == 'pass' and recipient['example'] == case['portable_example'],
                    f'{name}: current recipient failed to reproduce the example outcome')
            bundles[name] = bundle
            report['cases'].append({**base, 'original_bundle_sha256': sha(old_zip),
                                    'new_replay_bundle_sha256': sha(bundle), 'fresh_implementation_sha256': fresh['implementation_sha256'],
                                    'recipient': recipient, 'comparison': fresh['comparison']})
    require(runtime_source() == source, 'Runtime changed during replay')
    raw_report = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        # Do not replace previous evidence, even on retry.
        args.output.mkdir(exist_ok=False)
        for name, bundle in bundles.items():
            (args.output / (name + '-replay.zip')).write_bytes(bundle)
        (args.output / 'replay-receipt.json').write_text(raw_report, encoding='utf-8')
    print(raw_report, end='')


if __name__ == '__main__':
    main()
