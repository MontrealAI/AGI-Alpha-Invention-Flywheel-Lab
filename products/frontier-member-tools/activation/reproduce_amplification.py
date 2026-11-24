"""Recompute the exact controls and independently replay the recorded comparison."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from calibration_environment import exact as calibrate, validate as calibration_valid
from route_environment import verify


def load(root, name):
    return json.loads((root/name).read_text())


def fingerprint(path):
    return sha256(path.read_bytes()).hexdigest()


def stable(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def expect(condition, reason):
    if not condition:
        raise ValueError(reason)


def native_controls():
    from unittest.mock import patch
    from amplify import assess, proposed_instrument
    from native_experiment import NativeRefused, NativeUnavailable, run

    demonstration = run('def solve(x):\n from fractions import Fraction\n return str(Fraction(*x))', [5,7])
    expect(demonstration.get('result')=='5/7','NATIVE_ARITHMETIC')
    denied = []
    for label, source in {
        'outside_files': 'def solve(x):\n return open("/etc/passwd").read()',
        'host_proc': 'def solve(x):\n return open("/proc/self/status").read()',
        'filesystem_write': 'def solve(x):\n open("/work/new", "w").write("test")',
        'socket': 'def solve(x):\n import socket\n socket.socket()',
        'process': 'def solve(x):\n import os\n os.fork()',
        'exec': 'def solve(x):\n import os\n os.execv("/usr/bin/python3", ["python3", "-V"])',
    }.items():
        answer = run(source, None)
        expect('result' not in answer and answer['error'].startswith(('FileNotFoundError:', 'PermissionError:', 'OSError:')),
               'NATIVE_BOUNDARY:'+label)
        denied.append(label)
    isolated = run('def solve(x):\n import os\n return (dict(os.environ), os.listdir("/work"))', None).get('result')
    # Bubblewrap sets the sandbox working directory. CPython can derive a
    # locale from its own installation. No caller-provided value enters.
    expect(isolated is not None and isolated[1]==[] and isolated[0].pop('PWD', '/work')=='/work'
           and set(isolated[0]) <= {'LC_CTYPE'},'NATIVE_ENVIRONMENT')
    try:
        run('def solve(x):\n while True: pass', None, cpu=1)
    except NativeRefused as error:
        expect(str(error) in ('NATIVE_PROCESS_LIMIT_OR_FAILURE','NATIVE_WALL_LIMIT'), 'NATIVE_TIMEOUT')
    else:
        raise ValueError('NATIVE_TIMEOUT')
    for invalid in ('{"result": NaN}', '{"result": 0, "result": 1}', '{"error": {}}', r'{"result":"\ud800"}',
                    '{"result":'+'['*4000+'0'+']'*4000+'}'):
        source = f'print({invalid!r})\nraise SystemExit(0)'
        try:
            run(source, None)
        except NativeRefused as error:
            expect(str(error)=='NATIVE_OUTPUT','MALFORMED_OUTPUT')
        else:
            raise ValueError('MALFORMED_OUTPUT')
    with patch('amplify.native', side_effect=NativeUnavailable('NATIVE_ISOLATION_REFUSED')):
        for exercise in (lambda: assess('dummy',[{'id':'x','input':0,'expected':0}]),
                         lambda: proposed_instrument({'source':'dummy'},'contract',[],[])):
            try:
                exercise()
            except NativeUnavailable:
                pass
            else:
                raise ValueError('HOST_FAILURE_SCORED_AS_CANDIDATE')
    return {'arithmetic':True,'denied':denied,'environment_empty':True,
            'stopped_nonterminating_program':True,'malformed_outputs_denied':5,'host_failure_refused':True}


def verify_arms(arms, plan, held, native):
    expects = {case['id']:case['expected'] for case in held}
    brief = {}
    for key, arm in arms.items():
        model, method = key.split('/')
        expect(model in plan['comparisons'] and method in plan['comparisons'][model]['arms'],'ARM_NOT_REGISTERED')
        rows = arm['results']
        count = 0
        selected = arm['selected']
        if selected is not None:
            code = arm['candidate']['source']
            expect(sha256(stable(code).encode()).hexdigest()==arm['source_sha256'],'SOURCE_BINDING')
            expect(len(rows)==len(held) and {row['id'] for row in rows}==set(expects),'MISSING_CONFIRMATION')
            exact_rows = ['result' in row and stable(row['result'])==stable(expects[row['id']]) for row in rows]
            expect(exact_rows==[row['accepted'] for row in rows],'OBSERVED_DISPOSITION')
            count = sum(exact_rows)
            if native:
                from amplify import assess
                observed = assess(code,held)
                projection = lambda records: {row['id']:(row['accepted'],'result' in row,stable(row.get('result')))
                                              for row in records}
                expect(projection(observed)==projection(rows),'NATIVE_REPLAY_DRIFT:'+key)
        else:
            expect(not rows and arm['candidate'] is None,'UNSEALED_CANDIDATE')
        expect(count==arm['accepted'],'REPORTED_COUNTS:'+key)
        brief[key] = {'accepted':count,'cases':len(held),'selected':selected}
    return brief


def verify_transfer(root, findings):
    from amplify import bound_instrument

    source = fingerprint(root/'registration.json')
    target = fingerprint(root/'transfer-registration.json')
    envelope = findings['generated']['transfer_instrument']
    candidate = findings['generated']['revised_instrument']
    with TemporaryDirectory() as work:
        path = Path(work)/'transfer.json'
        path.write_text(stable(envelope)+'\n')
        actual, binding, details = bound_instrument(path,target)
        expect(actual==candidate and details['original_registration_sha256']==source,'ORIGINAL_INSTRUMENT')
        actual_trials = [trial for key, trial in findings['transfer']['arms'].items() if key.endswith('/amplified')]
        expect(len(actual_trials)==1 and actual_trials[0]['binding']['transfer']==details
               and actual_trials[0]['binding']['instrument']==binding,'TRANSFER_CHECKPOINT')
        for invalid, scope in (({**envelope,'instrument_utf8':envelope['instrument_utf8']+' '},target), (envelope,source)):
            path.write_text(stable(invalid)+'\n')
            try:
                bound_instrument(path,scope)
            except ValueError:
                pass
            else:
                raise ValueError('TRANSFER_DRIFT_ACCEPTED')
    return details


def replay(root, native=False):
    plan = load(root,'registration.json')
    calibration = load(root,'transfer-registration.json')
    context = load(root,'context-followup.json')
    findings = load(root,'comparisons.json')
    for split in ('development','confirmation'):
        expect(fingerprint(root/(split+'.json'))==plan[split+'_sha256'],'CASE_BINDING:'+split)
        expect(fingerprint(root/('calibration-'+split+'.json'))==calibration[split+'_sha256'],
               'CALIBRATION_BINDING:'+split)
    expect(fingerprint(root/'registration.json')==findings['registration_sha256'],'PLAN_BINDING')
    expected = {f'{name}/{arm}' for name, policy in plan['comparisons'].items() for arm in policy['arms']}
    expect(set(findings['arms'])==expected,'MATCHED_ARMS')
    expected = {f'{context["model"]}/{arm}' for arm in context['arms_in_execution_order']}
    expect(set(findings['revised_arms'])==expected,'REVISED_ARMS')
    expected = {f'{name}/{arm}' for name, policy in calibration['comparisons'].items() for arm in policy['arms']}
    expect(set(findings['transfer']['arms'])==expected,'FRESH_ARMS')
    held = load(root,'confirmation.json')
    exact = verify(held)
    verify(load(root,'development.json'))
    expect([case['input'] for case in held if case['id']=='deployment-05']==[load(root,'trial.json')],'LIVE_WORKLOAD')
    other = load(root,'calibration-confirmation.json')
    expect([case['input'] for case in other if case['id']=='Batch2_R1543-d']==[load(root,'calibration-trial.json')],
           'CALIBRATION_TRIAL_BINDING')
    for case in other+load(root,'calibration-development.json'):
        output = calibrate(case['input'])
        expect(output==case['expected'] and calibration_valid(case['input'],output),'CALIBRATION_CONTROL:'+case['id'])
    return {'exact_controls': len(exact),'cases':len(held),
            'arms':verify_arms(findings['arms'],plan,held,native),
            'revised_arms':verify_arms(findings['revised_arms'],plan,held,native),
            'calibration':{'exact_controls':len(other),'arms':verify_arms(findings['transfer']['arms'],calibration,other,native)},
            'transfer_binding':verify_transfer(root,findings),
            'boundaries':native_controls() if native else None,'native_replay':native}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study',type=Path,default=Path(__file__).parent/'study'/'amplification')
    parser.add_argument('--native',action='store_true',help='Execute isolated Python candidates and denial checks')
    args = parser.parse_args()
    print(json.dumps(replay(args.study,args.native),sort_keys=True))
