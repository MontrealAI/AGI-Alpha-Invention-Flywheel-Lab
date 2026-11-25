"""Compare the retained gate and conventional alternatives on frozen observations."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import resource
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter


HERE = Path(__file__).resolve().parent
REPETITIONS = 9
JQ_ORDINARY = '''
. as $case | [.release.assets[] | select(.name == $case.expected_name)] as $assets |
.origin == "observed_upstream_publisher" and .release.tag == .expected_tag and (.release.draft == false)
and ($assets | length) == 1 and $assets[0].state == "uploaded"
and ($assets[0].digest | strings | test("^sha256:[0-9a-f]{64}$"))
and .archive != null and $assets[0].digest == ("sha256:" + .archive.sha256)
and .archive.sha256 == .archive.ordinary_sha256 and .archive.size == $assets[0].size
'''


def cpu():
    value = resource.getrusage(resource.RUSAGE_CHILDREN)
    return value.ru_utime + value.ru_stime


def invoke(work, script, mode, item):
    job = work / 'case.json'
    job.write_text(json.dumps(item))
    if script == 'jq':
        command = ['jq', '-c', JQ_ORDINARY, str(job)]
    else:
        command = [sys.executable, '-I', '-B', str(HERE / script), mode, str(job)]
    start, child = perf_counter(), cpu()
    result = subprocess.run(command, capture_output=True, check=True, timeout=7)
    value = {'wall_seconds': round(perf_counter() - start, 6), 'cpu_seconds': round(cpu() - child, 6)}
    return json.loads(result.stdout), value


def times(items):
    time_fields = ('wall_seconds', 'cpu_seconds')
    stats = {}
    for field in time_fields:
        values = [x[field] for x in items]
        stats[field] = {'min': min(values), 'median': round(median(values), 6), 'max': max(values)}
    return stats


def matched_pages(work, case):
    records = {'retained.py': [], 'ordinary.py': []}
    accepted = None
    for trial in range(REPETITIONS):
        pair = {}
        scripts = tuple(records) if trial % 2 == 0 else tuple(reversed(records))
        for script in scripts:
            pair[script], timing = invoke(work, script, 'pages', case)
            records[script].append(timing)
        if pair['retained.py'] != pair['ordinary.py']:
            raise AssertionError(pair)
        if accepted is not None and pair['retained.py'] != accepted:
            raise AssertionError('nondeterministic repeated decision')
        accepted = pair['retained.py']
    return {'observed_result': accepted, 'scope': case['study_scope'], 'repetitions_per_arm': REPETITIONS,
            'metrics': {name: times(items) for name, items in records.items()},
            'shared_observation_acquisition': {k: case[k] for k in ('acquisition_wall_seconds', 'acquisition_cpu_seconds')}}


def pages_controls(work, live):
    cases = {}
    for control in ('wrong_commit', 'missing_job', 'failed_verification', 'fixture_origin', 'stale_receipt',
                    'missing_timing', 'duplicate_job'):
        cases[control] = deepcopy(live)
    cases['wrong_commit']['facts']['run']['head_sha'] = '0' * 40
    cases['missing_job']['facts']['jobs'].pop()
    cases['failed_verification']['facts']['jobs'][-1]['conclusion'] = 'failure'
    cases['fixture_origin']['origin'] = 'development_fixture'
    cases['stale_receipt']['facts']['witness']['workflow_run'] = '0'
    cases['missing_timing']['facts']['jobs'][0]['steps'].clear()
    jobs = cases['duplicate_job']['facts']['jobs']
    jobs.append(deepcopy(jobs[0]))
    expected = ('WRONG_RUN', 'INCOMPLETE_JOB_LIST', 'JOB_NOT_SUCCESSFUL', 'INELIGIBLE_OBSERVATION',
                'STALE_OR_MISSING_PUBLICATION', None, 'INCOMPLETE_JOB_LIST')
    report = {}
    for (control, item), wanted in zip(cases.items(), expected, strict=True):
        a, _ = invoke(work, 'retained.py', 'pages', item)
        b, _ = invoke(work, 'ordinary.py', 'pages', item)
        if a != b or a['reason'] != wanted:
            raise AssertionError((control, a, b))
        if control == 'missing_timing' and (a['decision'] != 'GO' or a['longest_observed_wait'] is not None):
            raise AssertionError(a)
        report[control] = a
    return report


def evaluate_transfer(work, actual):
    arms = {'original': ('retained.py', 'pages'), 'withdrawn': ('retained.py', 'withdrawn'),
            'retained': ('retained.py', 'upstream'), 'ordinary_reuse': ('jq', 'upstream'),
            'conventional_integration': ('ordinary.py', 'upstream')}
    sample = {name: [] for name in arms}
    output = {}
    for repeat in range(REPETITIONS):
        methods = tuple(arms) if repeat % 2 == 0 else tuple(reversed(arms))
        for key in methods:
            command, mode = arms[key]
            result, measures = invoke(work, command, mode, actual)
            if key in output and output[key] != result:
                raise AssertionError('nondeterministic transfer result')
            output[key] = result
            sample[key].append(measures)
    retained = output['retained']
    if retained != output['conventional_integration'] or output['ordinary_reuse'] != (retained['decision'] == 'GO'):
        raise AssertionError(output)

    controls = {}
    for name in ('publisher_digest_altered', 'wrong_tag', 'different_local_digest', 'missing_bytes'):
        controls[name] = deepcopy(actual)
    controls['publisher_digest_altered']['release']['assets'][0]['digest'] = 'sha256:' + '0' * 64
    controls['wrong_tag']['release']['tag'] = 'b0'
    controls['different_local_digest']['archive'].update(sha256='1'*64, ordinary_sha256='1'*64)
    controls['missing_bytes']['archive'] = None
    control_results = {}
    for label, item in controls.items():
        r, _ = invoke(work, 'retained.py', 'upstream', item)
        c, _ = invoke(work, 'ordinary.py', 'upstream', item)
        j, _ = invoke(work, 'jq', 'upstream', item)
        if r != c or j is not False or r['decision'] != 'HOLD':
            raise AssertionError((label, r, c, j))
        control_results[label] = r
    return {'repetitions_per_arm': REPETITIONS, 'output': output, 'metrics': {k: times(v) for k, v in sample.items()},
            'controls': control_results, 'inventor_promotion': 'NO-GO',
            'shared_observation_acquisition': {k: actual[k] for k in ('acquisition_wall_seconds', 'acquisition_cpu_seconds')}}


def digest(file):
    return sha256(file.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    primary, followup = (json.loads((HERE / name).read_bytes()) for name in ('OBSERVATIONS.json', 'FOLLOWUP.json'))
    assert primary['registration_sha256'] == digest(HERE / 'REGISTRATION.json')
    assert followup['registration_sha256'] == digest(HERE / 'FOLLOWUP-REGISTRATION.json')
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        cases = primary['pages'] + followup['pages']
        rows = [matched_pages(work, case) for case in cases]
        controls = pages_controls(work, cases[0])
        transfer = evaluate_transfer(work, primary['upstream'])
    if rows[0]['observed_result']['decision'] != 'GO' or rows[1]['observed_result']['reason'] != 'STALE_OR_MISSING_PUBLICATION':
        raise AssertionError(rows[:2])
    identities = ('REGISTRATION.json', 'FOLLOWUP-REGISTRATION.json', 'OBSERVATIONS.json', 'FOLLOWUP.json',
                  'capture.py', 'assess.py', 'retained.py', 'ordinary.py')
    acquisition = primary['observations'] + followup['observations']
    result = {'schema': 'frontier-outcome-driven-productive-assessment-v1', 'files_sha256': {k:digest(HERE/k) for k in identities},
              'pages': rows, 'pages_controls': controls, 'transfer': transfer,
              'cost_scope': {'public_get_requests': len(acquisition), 'response_body_bytes': sum(a['body_bytes'] for a in acquisition),
                             'paid_model_requests': 0, 'real_transactions': 0, 'receipts_usd': None,
                             'included_codex_authoring_cost': None, 'acquisition_host_network_cost': None,
                             'operator_attention_and_recurring_maintenance_cost': None, 'energy_joules': None},
              'completed_at': datetime.now(timezone.utc).isoformat()}
    with args.output.open('x') as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
