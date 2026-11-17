"""Run ordinary production tools on the two frozen public example contracts."""
import base64
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
# The measured comparator is this complete route: a name-set comparison plus
# GNU SHA-256, since checking listed files alone cannot detect extra files.
SAFE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\Z')
JQ = r'''
  def migrate:
    if (type == "object" and keys == ["id", "name", "status"] and all(.[]; type == "string")) then
      {record_id: .id, area: (.id | split("-")[0]), headline: .name, decision: .status}
    else error("invalid_value") end;
  if type == "object" and keys == ["rows"] and (.rows | type) == "array" then
    {rows: [.rows[] | migrate]}
  else error("invalid_value") end
'''


def conventional_audit(payload, manifest, executable):
    observed = {}
    for name, encoded in payload['files'].items():
        if not SAFE_NAME.fullmatch(name):
            return {'error': 'invalid_path'}
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            return {'error': 'invalid_value'}
        # Names are treated as data. No archive extraction or path opens.
        result = subprocess.run([executable], input=content, capture_output=True, check=True)
        observed[name] = result.stdout.decode('ascii').split()[0]
    common = observed.keys() & manifest.keys()
    changed = sorted(k for k in common if observed[k] != manifest[k])
    missing = sorted(manifest.keys() - observed.keys())
    unexpected = sorted(observed.keys() - manifest.keys())
    return {'ok': not (changed or missing or unexpected), 'changed': changed, 'missing': missing,
            'unexpected': unexpected, 'matched': sorted(common.difference(changed))}


def conventional_migrate(payload, executable):
    result = subprocess.run([executable, '-ce', JQ], input=json.dumps(payload), capture_output=True, text=True)
    if result.returncode:
        if 'invalid_value' in result.stderr:
            return {'error': 'invalid_value'}
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def main():
    out = {'report': 'conventional-example-comparison-v1', 'arms': [], 'complete_delivery_cost': 'unmeasured',
           'cost_scope': 'Wall time includes each comparator process, input preparation inside the case and output parsing. Engineering, model time, evaluation development, operator review, integration and customer acceptance are outside these timings.'}
    all_pass = True
    for fixture, executable_name in [('integrity', 'sha256sum'), ('migration', 'jq')]:
        path = ROOT / f'{fixture}.json'
        executable = shutil.which(executable_name)
        if executable is None:
            raise SystemExit(f'The conventional comparison requires {executable_name} on PATH.')
        version = subprocess.check_output([executable, '--version'], text=True).splitlines()[0]
        specification = json.loads(path.read_bytes())['mission']['construction_spec']
        arm = {'id': fixture, 'tool': version, 'fixture_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'cases': []}
        for test in specification['cases']:
            start = time.perf_counter_ns()
            if fixture == 'migration':
                result = conventional_migrate(test['input'], executable)
            else:
                result = conventional_audit(test['input'], specification['definition']['manifest'], executable)
            elapsed = time.perf_counter_ns() - start
            expected = test['expected'] if 'expected' in test else {'error': test['error']}
            passed = result == expected
            all_pass &= passed
            arm['cases'].append({'case': test['name'], 'matched_frozen_expectation': passed,
                                 'elapsed_ns': elapsed, 'observed': result})
        out['arms'].append(arm)
    out['all_matched'] = bool(all_pass)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
