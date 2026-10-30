import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time

PROBE = '''import copy,json,platform,sqlite3,sys
from pathlib import Path
import cryptography
from commercial.market import run_world
from commercial.ledger import audit,load_jobs
root=Path.cwd()
freeze=json.loads((root/'campaign/commercial-010/SOURCE_FREEZE.json').read_text())
manifest=json.loads((root/freeze['manifest']).read_text())
policy=json.loads((root/freeze['policy']).read_text())
arm=next(a for a in policy['arms'] if a['id']=='strategic_autonomous_onboarding')
results={}
for label,world_id in [('positive','qualified_differentiation'),('negative','zero_demand')]:
    world=next(w for w in policy['worlds'] if w['id']==world_id)
    result=run_world(root=root,manifest=manifest,policy=policy,world=world,seed=1,multiplier=9500,arm=arm,directory=root/('probe-'+label))
    checked=audit(result['ledger'],root=root,manifest=manifest,expected_actions_sha256=result['ledger']['actions_sha256'])
    agents=[a for a in result['ledger']['actions'] if a['op']=='cost' and a['args']['id'].endswith('-agent-onboarding')]
    ids=[a['args']['id'] for a in agents]
    if len(ids)!=len(set(ids)):raise AssertionError('ONBOARDING_CHARGED_TWICE')
    seen=set()
    for cycle in result['cycles']:
        for d in cycle['decisions']:
            if d['buyer'] in seen and any(d['onboarding'][k] for k in ['agent_expense','external_fee','customer_friction_usd']):raise AssertionError('REPEAT_ONBOARDING_CHARGE')
            if d['participates']:seen.add(d['buyer'])
    if len(agents)!=len(seen):raise AssertionError('ONBOARDING_JOB_EVENT_MISMATCH')
    if label=='positive' and not result['conditional_simulated_go']:raise AssertionError('POSITIVE_REPLAY_FAILED')
    if label=='negative' and (result['conditional_simulated_go'] or result['paid_jobs'] or checked['summary']['unrestrictedEarned']):raise AssertionError('ZERO_DEMAND_FALSE_SUCCESS')
    summary=checked['summary']
    results[label]={'world':world_id,'seed':1,'price_policy':9500,'arm':arm['id'],'scope':'SIMULATED','conditional_simulated_go':result['conditional_simulated_go'],'paid_jobs':result['paid_jobs'],'earned_funded_cycles':result['earned_funded_cycles'],'repeat_buyers':result['repeat_buyers'],'summary':summary,'ledger_actions_sha256':result['ledger']['actions_sha256'],'ledger_replay_accepted':checked['accepted'],'onboarding_once_verified':True,'agent_onboarding_events':len(agents),'agent_onboarding_cost':sum(a['args']['amount'] for a in agents),'actual_collections':0,'actual_profit':None}
    if label=='positive':
        mutated=copy.deepcopy(result['ledger']);mutated['summary']['profit']+=1
        try:audit(mutated,root=root,manifest=manifest)
        except ValueError as e:results[label]['summary_mutation_rejected']=str(e)
        else:raise AssertionError('FORGED_SUMMARY_ACCEPTED')
job=next(j for j in manifest['jobs'] if j['accepted'])
target=root/job['artifact'];original=target.read_bytes();target.write_bytes(original+b'\\n')
try:
    try:load_jobs(root,manifest)
    except ValueError as e:results['cached_source_mutation_rejected']=str(e)
    else:raise AssertionError('CACHED_SOURCE_TAMPER_ACCEPTED')
finally:target.write_bytes(original)
results['runtime']={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'cryptography':cryptography.__version__}
Path(sys.argv[1]).write_text(json.dumps(results,indent=2,allow_nan=False)+'\\n')
'''


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--freeze-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    cpu = resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    children_cpu = child.ru_utime + child.ru_stime
    freeze_path = Path('campaign/commercial-010/SOURCE_FREEZE.json')
    freeze_raw = (args.root / freeze_path).read_bytes()
    if sha(freeze_raw) != args.freeze_sha256:
        raise ValueError('EXTERNAL_FREEZE_IDENTITY_MISMATCH')
    freeze = json.loads(freeze_raw)
    copied = {}
    commands = []
    with tempfile.TemporaryDirectory(prefix='commercial010-no-git-') as tmp:
        clean = Path(tmp)
        files = set(freeze['sources']) | {str(freeze_path)}
        for directory in [Path(freeze['manifest']).parent, Path('campaign/commercial-010/onboarding/executed-001')]:
            files.update(str(p.relative_to(args.root)) for p in (args.root / directory).rglob('*') if p.is_file())
        for name in sorted(files):
            source = args.root / name
            if source.is_symlink():
                raise ValueError('SYMLINK_COPY_REFUSED')
            raw = source.read_bytes()
            if name in freeze['sources'] and sha(raw) != freeze['sources'][name]:
                raise ValueError('FROZEN_SOURCE_CHANGED ' + name)
            target = clean / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            copied[name] = sha(raw)
        if list(clean.rglob('.git')):
            raise AssertionError('GIT_HISTORY_PRESENT')
        env = dict(os.environ, PYTHONPATH=str(clean), PYTHONDONTWRITEBYTECODE='1')
        def run(argv, label, expected_success=True):
            command = [sys.executable] + argv
            result = subprocess.run(command, cwd=clean, env=env, capture_output=True, text=True, timeout=90)
            (args.output / (label + '.stdout.log')).write_text(result.stdout)
            (args.output / (label + '.stderr.log')).write_text(result.stderr)
            commands.append({'argv': command, 'cwd': '<clean-no-git-root>', 'returncode': result.returncode})
            if expected_success and result.returncode:
                raise RuntimeError('CLEAN_COMMAND_FAILED ' + label + ' ' + result.stderr[-1000:])
            return result
        run(['run_commercial010.py', '--freeze-sha256', args.freeze_sha256, '--check-inputs', '--output', 'inputs.json'], 'frozen-inputs')
        (clean / 'probe.py').write_text(PROBE)
        run(['probe.py', str(args.output.absolute() / 'REPLAY_RESULTS.json')], 'positive-negative-replay')
        policy_path = clean / freeze['policy']
        original = policy_path.read_bytes()
        policy_path.write_bytes(original + b'\n')
        rejected = run(['run_commercial010.py', '--freeze-sha256', args.freeze_sha256, '--check-inputs', '--output', 'forged-inputs.json'], 'frozen-mutation', expected_success=False)
        if rejected.returncode == 0 or 'FROZEN_SOURCE_CHANGED ' + freeze['policy'] not in rejected.stderr:
            raise AssertionError('WRONG_FROZEN_INPUT_REFUSAL')
        policy_path.write_bytes(original)
        shutil.copy2(clean / 'probe.py', args.output / 'probe.py')
        shutil.copy2(clean / 'inputs.json', args.output / 'INPUT_CHECK.json')
    for name, expected in freeze['sources'].items():
        if sha((args.root / name).read_bytes()) != expected:
            raise ValueError('ORIGINAL_SOURCE_CHANGED_DURING_AUDIT ' + name)
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'schema': 'agi-alpha/commercial010-clean-audit/v1', 'source_freeze_sha256': args.freeze_sha256,
               'scope': 'SIMULATED_ENGINEERING_REPLAY', 'accepted': True, 'git_history_present': False,
               'network_operations': 'No network commands or network clients used; installed host dependencies reused.',
               'copied_sources_and_inputs_sha256': copied, 'commands': commands,
               'frozen_input_mutation_rejected': True, 'original_frozen_sources_unchanged': True,
               'resources': {'wall_seconds': time.monotonic() - started,
                             'cpu_seconds': own.ru_utime + own.ru_stime - cpu + child.ru_utime + child.ru_stime - children_cpu,
                             'child_peak_rss_kib': child.ru_maxrss},
               'limits': 'Independent checker role and clean directory; same host, Python, dependency installation and model family. Exposed seed1 only; not fresh scientific or actual commercial confirmation.'}
    with (args.output / 'RECEIPT.json').open('x') as stream:
        json.dump(receipt, stream, indent=2, allow_nan=False)
        stream.write('\n')


if __name__ == '__main__':
    main()
