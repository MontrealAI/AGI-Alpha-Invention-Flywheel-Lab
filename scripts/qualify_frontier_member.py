"""Exercise the distributed bundles in temporary independent installations."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from zipfile import ZipFile

import frontier_member_value as member


def require(ok, message):
    if not ok:
        raise ValueError(message)


def install(path, destination, expected):
    require(member.digest(path.read_bytes()) == expected['sha256'], 'Published package digest mismatch')
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        require(set(archive.namelist()) == {'manifest.json', *manifest['file_sha256']}
                and len(archive.namelist()) == len(manifest['file_sha256']) + 1, 'Unexpected package member')
        for name, fingerprint in manifest['file_sha256'].items():
            binding = PurePosixPath(name)
            require(not binding.is_absolute() and '..' not in binding.parts, 'Unsafe package path')
            data = archive.read(name)
            require(member.digest(data) == fingerprint, 'Package file digest mismatch')
            target = destination.joinpath(*binding.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return manifest


def call(directory, *command, expected=0):
    start = perf_counter_ns()
    result = subprocess.run(command, cwd=directory, capture_output=True, check=False)
    elapsed = perf_counter_ns() - start
    require(result.returncode == expected, f'{command[0]} {command[1]} exit {result.returncode}: {result.stderr[:500].decode(errors="replace")}')
    return (json.loads(result.stdout) if result.stdout.strip() else None), elapsed


def qualify_endpoint(package, root, expected, reference):
    install(package, root, expected)
    sample = json.loads((root / 'sample.json').read_bytes())
    require(member.digest(member.stable(sample)) == reference['input_sha256'], 'Public benchmark fixture changed')
    strict = {**sample, 'maximum_p90_ttft_ms': '100'}
    floor = {**sample, 'minimum_tokens_per_s': '500'}
    altered = deepcopy(sample)
    altered['rows'][3]['published'] = '2026-11-24'
    altered['rows'][2]['p90_ttft_ms'] = None
    altered['rows'][1]['published'] = None
    measured = []
    for name, batch, wanted in (('registered', sample, 140), ('new-ceiling', strict, 35),
                                 ('infeasible', floor, None), ('withheld', altered, 17)):
        path = root / 'run.json'
        path.write_bytes(member.stable(batch))
        candidate, js_ns = call(root, 'node', 'endpoint-cli.mjs', path)
        independent, sql_ns = call(root, sys.executable, 'endpoint-sqlite.py', path)
        require(candidate == independent and candidate['highest_tested_load'] == wanted, 'Exact SQLite comparison failed')
        require(candidate['operating_adoption'] == 'ABSTAIN', 'Benchmark promoted to operating authority')
        if name == 'registered':
            require(member.digest(member.stable(independent)) == reference['result_sha256'], 'Independent result digest mismatch')
        measured.append({'case': name, 'documented_load': wanted, 'node_wall_ns': js_ns, 'sqlite_wall_ns': sql_ns})
    broken = deepcopy(sample)
    broken['rows'][3]['load'] = broken['rows'][2]['load']
    path.write_bytes(member.stable(broken))
    call(root, 'node', 'endpoint-cli.mjs', path, expected=2)
    broken['rows'][3]['load'] = sample['rows'][3]['load']
    broken['minimum_tokens_per_s'] = '1e2'
    path.write_bytes(member.stable(broken))
    call(root, 'node', 'endpoint-cli.mjs', path, expected=2)
    return {'comparisons': measured, 'denied_inputs': 2, 'full_cost': None, 'test_case': 'controlled-public'}


def qualify_archive(package, root, expected, live):
    install(package, root, expected)
    audit, wall = call(root, sys.executable, 'archive-verify.py')
    require(audit['signature_verified'] and audit['registered_cases'] == 6
            and audit['direct_origin_budget_cases'] == 6, 'Signed archive reference was not recovered')
    original = root / member.ARCHIVE_PATH / 'evidence/standalone-query.json'
    known, _ = call(root, sys.executable, 'archive-verify.py', original)
    require(known['state'] == 'MATCHED_SIGNED_REFERENCE', 'Prior real query fails separate verification')
    sample = json.loads(original.read_bytes())
    sample['field']['temperature_k'] += 1
    changed = root / 'changed.json'
    changed.write_bytes(member.stable(sample))
    failed, _ = call(root, sys.executable, 'archive-verify.py', changed, expected=2)
    require(failed['state'] == 'REJECTED', 'Tampered measurement was accepted')
    sample['case']['latitude'] = 46.76
    changed.write_bytes(member.stable(sample))
    missing, _ = call(root, sys.executable, 'archive-verify.py', changed, expected=2)
    require(missing['state'] == 'ABSTAIN', 'Unknown case was accepted')
    actual = []
    if live:
        for day, cycle, lat, lon in (('2024-01-18', '00', '46.75', '-71.25'),
                                     ('2025-06-06', '12', '43.75', '-79.5')):
            point, elapsed = call(root, sys.executable, 'archive-query.py', '--day', day,
                                  '--cycle', cycle, '--latitude', lat, '--longitude', lon)
            output = root / 'point.json'
            output.write_bytes(member.stable(point))
            result, _ = call(root, sys.executable, 'archive-verify.py', output)
            require(result['state'] == 'MATCHED_SIGNED_REFERENCE', 'New public query did not match reference')
            actual.append({'day': day, 'cycle': cycle, 'latitude': lat, 'longitude': lon, 'wall_ns': elapsed,
                           'temperature_k': point['field']['temperature_k'], 'body_bytes': point['body_bytes']})
    return {'offline_audit_wall_ns': wall, 'signed_case_count': audit['registered_cases'], 'denied_inputs': 2,
            'live_queries': actual, 'full_cost': None, 'test_case': 'controlled-public'}


def qualify_foundry(directory, root, release):
    expected = release['foundry_sha256'][member.FOUNDRY_ZIP]
    install(directory / member.FOUNDRY_ZIP, root, {'sha256': expected})
    example = json.loads((root / 'example.json').read_bytes())
    demo, wall_ns = call(root, 'node', 'foundry-cli.mjs', 'demo')
    require(demo['summary']['matched'] == demo['summary']['total'] == 6
            and demo['result'] == {'bytes':327680,'ordered':True}, 'Public archive replay changed')
    retained, _ = call(root, 'node', 'foundry-cli.mjs', 'recheck', 'retained/noaa-window.json', 'retained/noaa-cases.json')
    reused, _ = call(root, 'node', 'foundry-cli.mjs', 'run', 'retained/noaa-window.json', 'retained/noaa-cases.json',
                     'retained/noaa-reuse-input.json')
    require(retained['summary']['matched'] == 14 and reused == {'bytes':32,'ordered':True},
            'The packaged reference model candidate failed reproducible verification')
    subprocess.run([sys.executable,'-c', "import json; from formulas import formula_candidate; "
                    "a=json.load(open('example.json')); "
                    "d=formula_candidate(a['task'],'bytes = end - start + 1; ordered = start <= end'); "
                    "assert d['outputs'] == a['candidate']['outputs']"], cwd=root, check=True)
    subprocess.run([sys.executable,'-c',
                    "from formulas import bound_expansion\n"
                    "tree={'field':'x'}\n"
                    "for _ in range(11): tree={'op':'eq','args':[tree,tree]}\n"
                    "try: bound_expansion(tree)\n"
                    "except ValueError: pass\n"
                    "else: raise AssertionError('Expansion bound was not applied')"], cwd=root, check=True)
    for name, value in (('task', 'task'), ('draft','candidate'), ('cases','suite'), ('input','sample')):
        (root / f'{name}.json').write_bytes(member.stable(example[value]))
    sealed, _ = call(root, 'node', 'foundry-cli.mjs', 'retain', 'task.json', 'draft.json', 'cases.json')
    (root / 'asset.json').write_bytes(member.stable(sealed))
    original, _ = call(root, 'node', 'foundry-cli.mjs', 'recheck', 'asset.json', 'cases.json')
    recalc, reuse_ns = call(root, 'node', 'foundry-cli.mjs', 'run', 'asset.json', 'cases.json', 'input.json')
    require(original['summary']['matched'] == 6 and recalc == demo['result'], 'Retained instrument could not be reused')
    modified = deepcopy(sealed)
    modified['asset']['candidate']['outputs']['bytes'] = 1
    (root / 'altered.json').write_bytes(member.stable(modified))
    call(root, 'node', 'foundry-cli.mjs', 'recheck', 'altered.json', 'cases.json', expected=2)
    modified['asset']['candidate_sha256'] = member.digest(member.stable(modified['asset']['candidate']))
    modified['sha256'] = member.digest(member.stable(modified['asset']))
    (root / 'altered.json').write_bytes(member.stable(modified))
    call(root, 'node', 'foundry-cli.mjs', 'recheck', 'altered.json', 'cases.json', expected=2)
    wrong = deepcopy(example['suite'])
    wrong['cases'][0]['expected']['bytes'] = 17
    (root / 'other-cases.json').write_bytes(member.stable(wrong))
    call(root, 'node', 'foundry-cli.mjs', 'recheck', 'asset.json', 'other-cases.json', expected=2)
    (root / 'input.json').write_bytes(b'{"start":1,"end":2000000001}')
    call(root, 'node', 'foundry-cli.mjs', 'run', 'asset.json', 'cases.json', 'input.json', expected=2)
    (root / 'draft.json').write_bytes(b'{"name":"refuse","inputs":["start","end"],"outputs":{"bytes":{"op":"exec","args":["rejected"]},"ordered":true}}')
    call(root, 'node', 'foundry-cli.mjs', 'seal', 'task.json', 'draft.json', expected=2)
    cfg = json.loads((root / 'local.example.json').read_bytes())
    state, _ = call(root, sys.executable, 'provider.py', '--config', 'local.example.json', 'status')
    require(state['local_only'] is True and state['providers'][0]['local'], 'Offline provider default cannot be reproduced')
    cfg['providers']['localhost-inference']['base_url'] = 'https://example.invalid/v1'
    (root / 'held.json').write_bytes(member.stable(cfg))
    call(root, sys.executable, 'provider.py', '--config', 'held.json', 'status', expected=2)
    cfg['local_only'], cfg['allow_paid_requests'], cfg['session_budget_usd'] = False,True,1
    provider = cfg['providers']['localhost-inference']
    provider['key_env'] = 'FOUNDRY_TEST_ONLY'
    provider['models']['replace-with-your-model-id']['input_per_million'] = 1
    (root / 'held.json').write_bytes(member.stable(cfg))
    (root / 'prompt.txt').write_text('This is a denial fixture. No request may be sent.')
    attempt = subprocess.run([sys.executable,'provider.py','--config','held.json','generate',
                              '--provider','localhost-inference','--model','replace-with-your-model-id',
                              '--prompt','prompt.txt'], capture_output=True, cwd=root,
                             env={**os.environ,'FOUNDRY_TEST_ONLY':'fixture-never-a-real-credential'})
    require(attempt.returncode == 2 and b'CONSENT' in attempt.stderr and b'Dispatching' not in attempt.stderr
            and b'fixture-never-a-real-credential' not in attempt.stderr, 'Unapproved remote dispatch was not refused')
    return {'archive_sample_matches':6,'reference_model_candidate_matches':14,'offline_reuse':True,'demo_wall_ns':wall_ns,'reuse_wall_ns':reuse_ns,
            'package_sha256':expected,'negative_controls':8,'real_member_trial':None}


def qualify_successors(directory, root, release):
    expected = release['foundry_sha256'][member.STUDY_ZIP]
    manifest = install(directory / member.STUDY_ZIP, root, {'sha256':expected})
    require(manifest['version'] == '1.1.0', 'Wrong study companion version')
    outcomes = {}
    for trial in ('successor-study','successor-followup'):
        report_path, cases_path = f'{trial}/report.json', f'{trial}/cases.json'
        envelope = json.loads((root / report_path).read_bytes())
        result, elapsed = call(root, 'node', 'study-cli.mjs', 'replay', report_path, cases_path)
        require(result == envelope['report'], 'Study replay did not reproduce the recorded comparison')
        comparison = result['comparison']
        require(comparison['reference']['matched'] == comparison['reference']['total'] == 49 and
                comparison['decision'] == 'KEEP_INCUMBENT', 'Incumbent outcome changed')
        outcomes[trial] = {'sha256':envelope['sha256'], 'replay_wall_ns':elapsed,
                           'matched':{name:arm['comparison']['matched'] if arm['comparison'] else None
                                      for name, arm in comparison['outcomes'].items()}}
    require(set(outcomes['successor-study']['matched'].values()) == {43}, 'Failed boundary cases were lost')
    require(set(outcomes['successor-followup']['matched'].values()) == {49}, 'Clarified cohort did not reproduce')

    clarified = json.loads((root / 'successor-followup/report.json').read_bytes())['report']
    (root / 'mission.json').write_bytes(member.stable(clarified['plan']['study']['task']))
    (root / 'candidate.json').write_bytes(member.stable(clarified['attempts']['direct']['candidate']))
    asset, _ = call(root, 'node', 'foundry-cli.mjs', 'retain', 'mission.json', 'candidate.json',
                    'successor-followup/cases.json')
    (root / 'capability.json').write_bytes(member.stable(asset))
    valid = {'previous_end':7,'start':8,'end':9,'object_bytes':10,'body_bytes':2,'same_version':True}
    for item, expected_result in ((valid, True), ({**valid,'end':10,'body_bytes':3}, False)):
        (root / 'fresh.json').write_bytes(member.stable(item))
        reuse, _ = call(root, 'node', 'foundry-cli.mjs', 'run', 'capability.json', 'successor-followup/cases.json', 'fresh.json')
        require(reuse == {'appendable':expected_result}, 'Retained candidate failed a fresh boundary case')

    report = json.loads((root / 'successor-study/report.json').read_bytes())
    tampered = deepcopy(report)
    tampered['report']['comparison']['retained_vs_ordinary'] = 'HIGHER'
    tampered['sha256'] = member.digest(member.stable(tampered['report']))
    (root / 'tampered.json').write_bytes(member.stable(tampered))
    call(root, 'node', 'study-cli.mjs', 'replay', 'tampered.json', 'successor-study/cases.json', expected=2)
    cases = json.loads((root / 'successor-study/cases.json').read_bytes())
    cases['cases'][0]['expected']['appendable'] ^= True
    (root / 'different-cases.json').write_bytes(member.stable(cases))
    call(root, 'node', 'study-cli.mjs', 'replay', 'successor-study/report.json', 'different-cases.json', expected=2)

    plan = report['report']['plan']
    (root / 'plan.json').write_bytes(member.stable(plan))
    config = json.loads((root / 'local.example.json').read_bytes())
    provider = config['providers']['localhost-inference']
    options = provider['models'].pop('replace-with-your-model-id')
    provider['models'][plan['study']['model']] = options
    cfg = root / 'study-local.json'
    invocation = (sys.executable, 'study.py', '--config', cfg.name, '--provider', 'localhost-inference',
                  '--plan', 'plan.json', '--workspace', 'interrupted')
    cfg.write_bytes(member.stable({**config,'local_only':False}))
    call(root, *invocation, expected=2)
    workspace = root / 'interrupted'
    require(not workspace.exists(), 'Non-local configuration reached construction')
    cfg.write_bytes(member.stable(config))
    workspace.mkdir()
    (workspace / 'plan.json').write_bytes(member.stable({'study_sha256':plan['sha256'],
        'provider':'localhost-inference','config_sha256':member.digest(cfg.read_bytes())}))
    for arm in ('direct','ordinary','retained'):
        (workspace / f'{arm}.started').touch()
    resumed, _ = call(root, *invocation)
    require(set(attempt['status'] for attempt in resumed.values()) == {'INTERRUPTED'},
            'An interrupted arm was dispatched again')
    return {'package_sha256':expected, 'replayed':outcomes, 'retained_fresh_cases':2, 'denied_controls':4}


def qualify_inventor(directory, root, release):
    expected = release['foundry_sha256'][member.INVENTOR_ZIP]
    manifest = install(directory / member.INVENTOR_ZIP, root, {'sha256':expected})
    require(manifest['id'] == 'frontier-inventor', 'Wrong invention companion')
    report, elapsed = call(root, sys.executable, 'reproduce.py')
    diagnostic, _ = call(root, sys.executable, 'reproduce.py', '--diagnostic')
    larger, _ = call(root, sys.executable, 'reproduce.py', '--larger')
    comparison = report['comparisons']
    require(set(comparison) >= {f'{name}-conventional' for name in ('editions','endpoint','impact')} and
            all(row['matched'] == row['total'] == 9 for name,row in comparison.items() if name.endswith('-conventional')),
            'Independent conventional comparison did not reproduce')
    denial = '''from relational import QueryRefused, evaluate
schema = {'source':{'id':'TEXT'}}
data = {'source':[{'id':'caption'}]}
assert evaluate(schema,data,'SELECT id FROM source') == [['caption']]
for sql in ('ATTACH DATABASE ":memory:" AS external', 'SELECT name FROM sqlite_schema',
            "SELECT load_extension('permission-test')", 'WITH x AS (SELECT 1) DELETE FROM source',
            'WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT SUM(n) FROM x'):
    try:
        evaluate(schema,data,sql)
    except QueryRefused:
        continue
    raise AssertionError('A forbidden or unbounded query completed')
'''
    subprocess.run([sys.executable, '-c', denial], cwd=root, check=True)
    recovery = '''from pathlib import Path
from types import SimpleNamespace
from inventor import Run
model = SimpleNamespace(name='recovery-fixture', config_sha256='test-only')
path = Path('interrupted.json')
run = Run(path,model,256,{'kind':'construction'})
run.state['pending'] = {'reserved_output':256,'prompt_sha256':'a'*64}
run.save()
resumed = Run(path,model,256,{'kind':'construction'})
assert resumed.remaining == 0 and resumed.state['pending'] is None
assert resumed.state['events'][0]['status'] == 'INTERRUPTED'
assert Run(path,model,256,{'kind':'construction'}).state == resumed.state
'''
    subprocess.run([sys.executable, '-c', recovery], cwd=root, check=True)

    for prefix, options, cohort in (('',(),report), ('diagnostic-',('--diagnostic',),diagnostic),
                                    ('larger-',('--larger',),larger)):
        first = next((label for label,value in cohort['comparisons'].items() if value['verdict'] == 'MATCHED' and
                      not label.endswith('-conventional')), None)
        if first:
            break
    else:
        prefix, options, first = '', (), 'impact-conventional'
    study = json.loads((root/'study'/f'{prefix}reproduction.json').read_bytes())
    evidence = json.loads((root/'study'/f'{prefix}evidence.json').read_bytes())
    scope = evidence['assessments'][first]['assessment']['mission']
    item = study['missions'][scope]['confirmation'][0]
    (root/'reuse.json').write_bytes(member.stable(item['input']))
    result, _ = call(root, sys.executable, 'reproduce.py', *options, '--apply', first, 'reuse.json')
    require(sorted(result['result']) == sorted(item['expected']), 'Reopened query did not reproduce the held case')
    fresh = {'node':[{'name':name} for name in ('input-refresh','evidence-check','publish','unaffected')],
             'edge':[{'input':'input-refresh','downstream':'evidence-check'},
                     {'input':'evidence-check','downstream':'publish'},
                     {'input':'evidence-check','downstream':'unknown'},
                     {'input':'unknown','downstream':'unaffected'}],
             'changed':[{'name':'input-refresh'}]}
    (root/'fresh.json').write_bytes(member.stable(fresh))
    fresh_result, _ = call(root, sys.executable, 'reproduce.py', '--apply', 'impact-conventional', 'fresh.json')
    require(sorted(fresh_result['result']) == [['evidence-check'],['input-refresh'],['publish']],
            'Reopened reference missed transitive impact on fresh input')
    return {'package_sha256':expected,'evidence_sha256':report['evidence_sha256'],
            'compared':comparison,'diagnostic':diagnostic['comparisons'],'larger':larger['comparisons'],'offline_wall_ns':elapsed,
            'reopened':first,'fresh_impact':fresh_result['result'],'denied_controls':5,'interruption_recovery':True}


def qualify_learning(directory, root, release):
    expected = release['foundry_sha256'][member.LEARNING_ZIP]
    manifest = install(directory/member.LEARNING_ZIP,root,{'sha256':expected})
    require(manifest['id']=='frontier-learning','Wrong learning companion')
    model, wall = call(root,sys.executable,'reproduce.py','--full')
    require(model['case_count']>=16 and model['parameters_changed']>0,'Missing fitted parameters or confirmation')
    boundaries,_ = call(root,sys.executable,'self_test.py')
    require(boundaries['wasm_denials']==4 and all(boundaries['workspace'].values()),'Learning boundary failed')
    return {'package_sha256':expected,'replay_wall_ns':wall,'trained_model':model,'boundaries':boundaries}


def qualify_activation(directory,root,release):
    expected=release['foundry_sha256'][member.ACTIVATION_ZIP]
    manifest=install(directory/member.ACTIVATION_ZIP,root,{'sha256':expected})
    require(manifest['id']=='frontier-activation','Wrong activation companion')
    evidence,elapsed=call(root,sys.executable,'reproduce_activation.py')
    require(evidence['controls']['row_loop'] and evidence['controls']['denied']==6 and
            evidence['controls']['unstructured_action_rejected'] and
            evidence['historical_phases']['future_excluded'],'Research isolation or phase qualification failed')
    return {'package_sha256':expected,'replayed_ns':elapsed,**evidence}


def qualify_amplification(directory,root,release):
    expected=release['foundry_sha256'][member.AMPLIFICATION_ZIP]
    manifest=install(directory/member.AMPLIFICATION_ZIP,root,{'sha256':expected})
    require(manifest['id']=='frontier-activation' and manifest['version']=='1.1.0' and
            manifest['source']==member.commit_url(member.AMPLIFICATION_PIN),'Wrong amplification companion')
    evidence,elapsed=call(root,sys.executable,'reproduce_amplification.py')
    require(evidence['exact_controls']==evidence['cases']==12 and evidence['calibration']['exact_controls']==6,
            'Amplification control failed')
    result,_=call(root,sys.executable,'route_environment.py','study/amplification/trial.json')
    require(result=={'load':256,'witnesses':['e045','e072'],'operational_adoption':'ABSTAIN'},
            'Distinct-system witness failed')
    calibration,_=call(root,sys.executable,'calibration_environment.py','study/amplification/calibration-trial.json')
    require(calibration=={'slack':[154525728350382,1892645562643243],'witness':['row-07','row-02']},
            'Exact calibration witness failed')
    return {'package_sha256':expected,'replayed_ns':elapsed,'worked_contract':result,
            'calibration_witness':calibration,**evidence}


def qualify_substrate(directory, root, release):
    expected = release['foundry_sha256'][member.SUBSTRATE_ZIP]
    manifest = install(directory/member.SUBSTRATE_ZIP, root, {'sha256': expected})
    require(manifest['id']=='frontier-activation' and manifest['version']=='1.2.0' and
            manifest['source']==member.commit_url(member.SUBSTRATE_PIN), 'Wrong substrate companion')
    evidence, elapsed = call(root, sys.executable, 'verify_substrate.py')
    require(evidence['checked_cases']==32 and evidence['sample']['decision']=='COVARIANCE_SENSITIVE'
            and evidence['endpoint']['load']==256, 'Scientific workbench replay failed')
    return {'package_sha256': expected, 'replayed_ns': elapsed, **evidence}


def qualify_liberation(directory, root, release):
    expected=release['foundry_sha256'][member.LIBERATION_ZIP]
    manifest=install(directory/member.LIBERATION_ZIP,root,{'sha256':expected})
    require(manifest['id']=='frontier-activation' and manifest['version']=='1.3.0' and
            manifest['source']==member.commit_url(member.LIBERATION_PIN),'Wrong research workbench source')
    evidence,elapsed=call(root,sys.executable,'verify_liberation.py')
    require(evidence['construction_held_accepted']['manual']==42 and evidence['covariance_confirmed']==106
            and evidence['hydrology']['days']==28,'Invention and scientific workbench replay failed')
    return {'package_sha256':expected,'replayed_ns':elapsed,**evidence}


def qualify_cascade(directory, root, release):
    expected = release['foundry_sha256'][member.CASCADE_ZIP]
    manifest = install(directory/member.CASCADE_ZIP,root,{'sha256':expected})
    require(manifest['id']=='frontier-activation' and manifest['version']=='1.4.0'
            and manifest['source']==member.commit_url(member.CASCADE_PIN),'Wrong cascade workbench source')
    for name, filename in member.CASCADE_STUDIES.items():
        require((directory/name).read_bytes()==(root/'study/cascade'/filename).read_bytes(),
                'Cascade public data and portable evidence differ')
    evidence, elapsed = call(root, sys.executable, 'verify_cascade.py')
    require(evidence['tess']['held']==11 and evidence['historical_oni_seasons']==900
            and evidence['composition']['jobs']==13 and evidence['observing_decision']=='ABSTAIN',
            'Cascade evidence is incomplete')
    return {'package_sha256':expected, 'replayed_ns':elapsed, **evidence}


def qualify_factory(directory, root, release):
    expected=release['foundry_sha256'][member.FACTORY_ZIP]
    manifest=install(directory/member.FACTORY_ZIP,root,{'sha256':expected})
    require(manifest['id']=='frontier-activation' and manifest['version']=='1.5.0'
            and manifest['source']==member.commit_url(release['source_commit']),'Wrong factory workbench source')
    require((directory/member.FACTORY_RESULTS).read_bytes()==(root/'study/factory/FACTORY.json').read_bytes(),
            'Factory public and portable evidence differ')
    evidence,elapsed=call(root,sys.executable,'verify_factory.py')
    require(evidence['industry_cases']==9 and evidence['independent_sql_agreement']==9
            and evidence['measurement_cases']>=8 and evidence['transit']['forecast_verdict']=='ABSTAIN',
            'Factory evidence is incomplete')
    return {'package_sha256':expected,'replayed_ns':elapsed,**evidence}


def qualify(directory, live=False):
    manifest = json.loads((directory / member.MEMBER_JSON).read_bytes())
    tools = manifest['capabilities']
    with TemporaryDirectory() as work:
        root = Path(work)
        results = {
            'endpoint': qualify_endpoint(directory / member.ENDPOINT_ZIP, root / 'endpoint',
                                         tools['endpoint'], manifest['endpoint_reference']),
            'archive': qualify_archive(directory / member.ARCHIVE_ZIP, root / 'archive',
                                       tools['archive'], live),
            'measured_productivity': None,
        }
        if (directory / 'atlas-release.json').is_file():
            release = json.loads((directory / 'atlas-release.json').read_bytes())
            if 'foundry_sha256' in release:
                results['foundry'] = qualify_foundry(directory, root / 'foundry', release)
                if member.STUDY_ZIP in release['foundry_sha256']:
                    results['successors'] = qualify_successors(directory, root / 'successors', release)
                if member.INVENTOR_ZIP in release['foundry_sha256']:
                    results['inventor'] = qualify_inventor(directory, root / 'inventor', release)
                if member.LEARNING_ZIP in release['foundry_sha256']:
                    results['learning'] = qualify_learning(directory,root/'learning',release)
                if member.ACTIVATION_ZIP in release['foundry_sha256']:
                    results['activation'] = qualify_activation(directory,root/'activation',release)
                if member.AMPLIFICATION_ZIP in release['foundry_sha256']:
                    results['amplification'] = qualify_amplification(directory,root/'amplification',release)
                if member.SUBSTRATE_ZIP in release['foundry_sha256']:
                    results['substrate'] = qualify_substrate(directory, root/'substrate', release)
                if member.LIBERATION_ZIP in release['foundry_sha256']:
                    results['liberation'] = qualify_liberation(directory, root/'liberation', release)
                if member.CASCADE_ZIP in release['foundry_sha256']:
                    results['cascade'] = qualify_cascade(directory, root/'cascade', release)
                if member.FACTORY_ZIP in release['foundry_sha256']:
                    results['factory'] = qualify_factory(directory, root/'factory', release)
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--live-archive', action='store_true')
    options = parser.parse_args()
    print(json.dumps(qualify(options.directory.resolve(), options.live_archive), sort_keys=True))
