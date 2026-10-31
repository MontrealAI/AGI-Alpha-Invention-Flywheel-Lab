import argparse
import collections
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from commercial.ledger import canonical,digest


def read(path):
    return json.loads(Path(path).read_text())


def write(path,value):
    Path(path).write_bytes(canonical(value)+b'\n')


def call(output,name,args,*,cwd=ROOT):
    original=name;attempt=1
    while (output/(name+'.stdout')).exists() or (output/(name+'.stderr')).exists():
        attempt+=1;name=original+'-attempt-'+str(attempt)
    done=subprocess.run([sys.executable,'-m','connected_enterprise',*args],cwd=cwd,
                        text=True,capture_output=True,timeout=650)
    (output/(name+'.stdout')).write_text(done.stdout);(output/(name+'.stderr')).write_text(done.stderr)
    if done.returncode:raise RuntimeError(name+' failed: '+done.stderr[-3000:])
    return json.loads(done.stdout.strip().splitlines()[-1])


def active_source(output,registration):
    continuation=output/'CONTINUATION.json'
    return read(continuation)['source_sha256'] if continuation.exists() else registration['source_sha256']


def repair(output,intermediate):
    from connected_enterprise.runner import identity
    from connected_enterprise.finance import source_identity
    registration=read(output/'REGISTRATION.json');business=output/'business'
    if (output/'CONTINUATION.json').exists():raise ValueError('EXPLICIT_CONTINUATION_ALREADY_REGISTERED')
    intermediate=Path(intermediate).absolute()
    if (identity(intermediate)['sha256']!='dc22e409ee8375b3bab2535737c1403313aa365cb4afe2a1144f2f8e6f586aab'
            or source_identity(intermediate)['sha256']!='25c01bec5889a56aa1c0172f17a3bd27ba0d32c7c387e29f93a60a0ff9d4d7d0'):
        raise ValueError('EXACT_ALREADY_AUTHORIZED_INTERMEDIATE_SOURCE_REQUIRED')
    checkpoint=read(business/'STATE.json');before=checkpoint['body']['state']
    initial_checkpoint_sha=digest(checkpoint)
    prior_actions=[json.loads(line) for line in (business/'account.sqlite.actions.jsonl').read_text().splitlines()][1:]
    def recover(root,label):
        intent=business/'account.sqlite.operating-checkpoint-intent.json'
        if intent.exists():
            current=read(business/'STATE.json')
            return call(output,'compatible-recovery-'+label,['recover-checkpoint','--output',str(business),
                '--historical-source',str(root),'--manifest',str(output/'SERVICES.json'),
                '--expected-checkpoint',digest(current),'--id','verified-retirement-'+label])
    receipts=[];journal=read(business/'account.sqlite.connected-journal.json')['body']
    if journal['source']['sha256']!=checkpoint['body']['source_sha256']:
        d=read(business/'OPERATOR.json');request=d['upgrade_request'];pending_root=business/d['source_dir']
        recover(pending_root,'pending-stage-2')
        receipts.append(call(output,'complete-authorized-stage-2',['upgrade','--output',str(business),
            '--historical-source',request['historical_root'],'--manifest',str(output/'SERVICES.json'),
            '--policy',str(output/'POLICY.json'),'--expected-checkpoint',request['expected_checkpoint_sha256'],
            '--id',request['id']],cwd=pending_root))
    checkpoint=read(business/'STATE.json')
    if checkpoint['body']['source_sha256']=='e7c9707a3449797609c91b33b11aaca4ccbe7f072db9abbea5820ed83281f6be':
        historical=business/'source-022';recover(historical,'before-stage-2')
        receipts.append(call(output,'matched-intermediate-stage-2',['upgrade','--output',str(business),
            '--historical-source',str(historical),'--manifest',str(output/'SERVICES.json'),
            '--policy',str(output/'POLICY.json'),'--expected-checkpoint',digest(checkpoint),
            '--id','qualification-'+registration['arm']+'-repair-2'],cwd=intermediate))
    d=read(business/'OPERATOR.json');historical=business/d['source_dir'];recover(historical,'before-final-stage-3')
    checkpoint=read(business/'STATE.json')
    receipt=call(output,'final-forward-repair-stage-3',['upgrade','--output',str(business),
        '--historical-source',str(historical),'--manifest',str(output/'SERVICES.json'),
        '--policy',str(output/'POLICY.json'),'--expected-checkpoint',digest(checkpoint),
        '--id','qualification-'+registration['arm']+'-repair-final-3'])
    receipts.append(receipt)
    recoveries=[read(p) for p in sorted((business/'CHECKPOINT_RECOVERY').glob('*.receipt.json'))]
    after=read(business/'STATE.json')['body']['state']
    for field in ['queue','current','orders','buyers','events','decisions','investments','used_jobs','processed_events','last_time']:
        if after[field]!=before[field]:raise ValueError('FORWARD_REPAIR_LOST_OPERATING_STATE:'+field)
    if (business/'account.sqlite.adaptive-simulation-key').stat().st_ino!=registration['key_inode']:
        raise ValueError('FORWARD_REPAIR_CHANGED_KEY_IDENTITY')
    continuation={'schema':'agi-alpha/successor022-forward-repair-continuation/v1',
        'failed_candidate_commit':'9c74bc5a8de61167a9c157c9cd2532c4a9b7577d',
        'original_registration_sha256':digest(registration),'previous_source_sha256':registration['source_sha256'],
        'source_sha256':read(business/'OPERATOR.json')['source']['sha256'],
        'prior_checkpoint_sha256':initial_checkpoint_sha,'prior_native_actions_sha256':digest(prior_actions),
        'prior_native_actions':len(prior_actions),'prior_processed_events':before['processed_events'],
        'preserved_compatible_recovery_receipts':recoveries,'migration_stages':receipts,
        'continuation_protocol':read(ROOT/'campaign/successor-022/CONTINUATION_PROTOCOL.json'),
        'scope':'Same account, original seed/config/horizon/policy, three total $1 upgrade invoices per arm; interrupted engineering continuation, not fresh confirmation. Original frozen candidate failed restart qualification.'}
    write(output/'CONTINUATION.json',continuation);print(json.dumps(continuation))


def setup(output,arm):
    from tests.connected_legacy_fixture import materialize
    from adaptive_enterprise.instruments import prepare_services
    from connected_enterprise.runner import identity
    if output.exists():raise FileExistsError('NEW_QUALIFICATION_BUSINESS_REQUIRED')
    output.mkdir(parents=True);protocol=read(ROOT/'campaign/successor-022/QUALIFICATION_PROTOCOL.json')
    cfg=read(ROOT/protocol['config']);policy=read(ROOT/protocol['policies'][arm]);old=output/'legacy-source'
    materialize(ROOT,protocol['legacy_commit'],old)
    manifest=prepare_services(old,'service-inputs',cohort_seed=protocol['service_cohort_seed'])
    write(output/'SERVICES.json',manifest);write(output/'CONFIG.json',cfg);write(output/'POLICY.json',policy)
    payload={'root':str(old),'manifest':manifest,'config':cfg,'seed':protocol['world_seed'],'arm':'growth',
             'output':str(output/'business'),'source':identity(old),'stop_after_events':250}
    code='''import json,sys
from pathlib import Path
from connected_enterprise.engine import run_world
p=json.load(sys.stdin)
def stop(where,state,account):
 checkpoint=json.loads((Path(p['output'])/'STATE.json').read_text())
 kinds={e['kind'] for e in checkpoint['body']['state']['queue']}
 if {'produce','accept','clear'}<=kinds and account.snapshot()['summary']['tailReserve']>0:
  (Path(p['output']).parent/'LEGACY_RECORD.json').write_text(json.dumps(account.export()))
  raise InterruptedError('registered nonempty prepared legacy checkpoint')
try:run_world(**p,failpoint=stop)
except InterruptedError:pass
else:raise ValueError('REGISTERED_LEGACY_COVERAGE_NOT_REACHED')
'''
    done=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),cwd=old,
                        env={**os.environ,'PYTHONPATH':str(old)},text=True,capture_output=True,timeout=300)
    (output/'legacy.stdout').write_text(done.stdout);(output/'legacy.stderr').write_text(done.stderr)
    if done.returncode:raise RuntimeError(done.stderr)
    business=output/'business';checkpoint=read(business/'STATE.json');write(output/'ORIGINAL_CHECKPOINT.json',checkpoint)
    key=business/'account.sqlite.adaptive-simulation-key';inode=key.stat().st_ino
    receipt=call(output,'upgrade',['upgrade','--output',str(business),'--historical-source',str(old),
                 '--manifest',str(output/'SERVICES.json'),'--policy',str(output/'POLICY.json'),
                 '--expected-checkpoint',digest(checkpoint),'--id','qualification-'+arm+'-1'])
    after=read(business/'STATE.json')['body']['state'];before=checkpoint['body']['state']
    for field in ['queue','current','orders','buyers','events','decisions','investments','used_jobs','processed_events','last_time']:
        if after[field]!=before[field]:raise ValueError('UPGRADE_LOST_OPERATING_STATE:'+field)
    if after['costs'][:len(before['costs'])]!=before['costs'] or key.stat().st_ino!=inode:
        raise ValueError('UPGRADE_LOST_COST_HISTORY_OR_KEY_IDENTITY')
    d=read(business/'OPERATOR.json')
    registration={'schema':'agi-alpha/successor022-business-registration/v1','arm':arm,'protocol':protocol,
                  'protocol_sha256':digest(protocol),'config_sha256':digest(cfg),'policy_sha256':digest(policy),
                  'manifest_sha256':digest(manifest),'source_sha256':d['source']['sha256'],
                  'original_native_actions_sha256':read(output/'LEGACY_RECORD.json')['ledger']['actions_sha256'],
                  'original_checkpoint_sha256':digest(checkpoint),'key_inode':inode,'migration':receipt}
    write(output/'REGISTRATION.json',registration)
    print(json.dumps({'registered':True,'arm':arm,'source_sha256':registration['source_sha256'],'legacy_queue_kinds':sorted({e['kind'] for e in before['queue']})}))


def step(output):
    registration=read(output/'REGISTRATION.json');business=output/'business';before=read(business/'STATE.json')['body']['state']
    if not before['queue']:raise ValueError('REGISTERED_BUSINESS_ALREADY_COMPLETE')
    number=len(list(output.glob('quantum-*.json')))+1
    result=call(output,'quantum-'+str(number),['operate','--output',str(business),'--max-events',str(registration['protocol']['quantum_event_limit'])])
    after=read(business/'STATE.json')['body']['state']
    if after['processed_events']<=before['processed_events']:raise ValueError('QUANTUM_MADE_NO_PROGRESS')
    if (business/'account.sqlite.adaptive-simulation-key').stat().st_ino!=registration['key_inode']:
        raise ValueError('CONTINUING_ACCOUNT_KEY_CHANGED')
    receipt={'schema':'agi-alpha/successor022-quantum/v1','number':number,'before_events':before['processed_events'],
             'after_events':after['processed_events'],'remaining_events':len(after['queue']),'complete':result['complete'],
             'source_sha256':active_source(output,registration),'summary':result['summary']}
    write(output/('quantum-'+str(number)+'.json'),receipt);print(json.dumps(receipt))


def finish(output):
    registration=read(output/'REGISTRATION.json');business=output/'business';before=read(business/'RESULT.json')
    if not before['complete']:raise ValueError('ALL_REGISTERED_EVENTS_MUST_COMPLETE')
    call(output,'resume-complete',['resume','--output',str(business)])
    result=read(business/'RESULT.json')
    if result['owned_account']['ledger']!=before['owned_account']['ledger']:
        raise ValueError('COMPLETE_RESUME_CHANGED_NATIVE_LEDGER')
    checked=call(output,'audit',['audit','--output',str(business)])
    score=call(output,'scoreboard',['scoreboard','--output',str(business)])
    prior=read(output/'LEGACY_RECORD.json')['ledger'];actions=result['owned_account']['ledger']['actions']
    if actions[:len(prior['actions'])]!=prior['actions'] or result['source']['sha256']!=active_source(output,registration):
        raise ValueError('CONTINUING_NATIVE_HISTORY_OR_SOURCE_CHANGED')
    old_state=read(output/'ORIGINAL_CHECKPOINT.json')['body']['state'];old_orders=list(old_state['orders'])
    if old_state['current']:old_orders+=old_state['current'].get('orders',[])
    protected=sum(o['price']+200000 for o in result['orders'] if o['id'] in {r['id'] for r in old_orders} and o['outcome']=='SETTLED')
    if result['summary']['tailReserve']<protected:raise ValueError('LEGACY_PERMANENT_TAIL_WAS_ERASED')
    verdict=score['profitable_settlements_funded_after_maturity']>=2 and score['summary']['profit']>0 and checked['accepted']
    receipt={'schema':'agi-alpha/successor022-business-verdict/v1','arm':registration['arm'],'audit_accepted':checked['accepted'],
             'complete_resume_unchanged':True,'same_key_inode':(business/'account.sqlite.adaptive-simulation-key').stat().st_ino==registration['key_inode'],
             'source_sha256':active_source(output,registration),'summary':result['summary'],'paid_jobs':result['paid_jobs'],
             'forward_repair_continuation':(output/'CONTINUATION.json').exists(),
             'service_counts':dict(collections.Counter(o['offer']['service_id'] for o in result['orders'] if o['outcome']=='SETTLED')),
             'maturities':score['maturities'],'profitable_settlements_funded_after_maturity':score['profitable_settlements_funded_after_maturity'],
             'prospective_positive_region_criterion':verdict if registration['arm']=='prospective' else None,
             'scope':'CONDITIONAL_AUTHORED_SYNTHETIC_ENGINEERING_NOT_EXTERNAL_OR_ANNUAL_PROFIT'}
    write(output/'VERDICT.json',receipt);print(json.dumps(receipt))


def export(output):
    verdict=read(output/'VERDICT.json');business=output/'business';d=read(business/'OPERATOR.json')
    public=output/'public'
    if public.exists():raise FileExistsError('NEW_PUBLIC_EXPORT_REQUIRED')
    public.mkdir();shutil.copytree(business/d['source_dir'],public/'source')
    record=read(business/'RESULT.json')['owned_account'];historical_roots=[]
    for ticket in record['source_transitions'].values():
        old=Path(ticket['body']['historical_root']);historical_roots.append(old)
        fallback=public/'source'/'historical-source-versions'/ticket['body']['from_source']['sha256']
        if not fallback.exists():shutil.copytree(old,fallback)
    for name,path in [('RESULT.json',business/'RESULT.json'),('STATE.json',business/'STATE.json'),('SERVICES.json',output/'SERVICES.json'),
                      ('SCOREBOARD.json',business/'SCOREBOARD.json'),('VERDICT.json',output/'VERDICT.json'),('REGISTRATION.json',output/'REGISTRATION.json')]:
        shutil.copyfile(path,public/name)
    if (output/'CONTINUATION.json').exists():shutil.copyfile(output/'CONTINUATION.json',public/'CONTINUATION.json')
    hidden_roots=[]
    try:
        for old in dict.fromkeys(historical_roots):
            hidden=old.with_name(old.name+'-portability-offline');old.rename(hidden);hidden_roots.append((old,hidden))
        code='import json,sys;from pathlib import Path;from connected_enterprise.verify import audit;p=Path(sys.argv[1]);print(json.dumps(audit(p/"source",json.load(open(p/"SERVICES.json")),json.load(open(p/"RESULT.json"))),sort_keys=True))'
        done=subprocess.run([sys.executable,'-c',code,str(public)],cwd=public/'source',text=True,capture_output=True,timeout=300)
        (output/'portable-audit.stdout').write_text(done.stdout);(output/'portable-audit.stderr').write_text(done.stderr)
        if done.returncode:raise RuntimeError(done.stderr)
        checked=json.loads(done.stdout)
    finally:
        for old,hidden in reversed(hidden_roots):hidden.rename(old)
    if not checked['accepted']:raise ValueError('EXPORTED_PORTABLE_AUDIT_FAILED')
    receipt={'accepted':True,'scope':'CLEAN_KEY_FREE_SOURCE_COPY_REPRODUCTION_NOT_A_PUBLISHED_RELEASE_DOWNLOAD',
             'historical_absolute_source_unavailable_during_audit':True,'private_account_or_keys_exported':False,
             'audit':checked}
    write(output/'PORTABLE_EXPORT.json',receipt);print(json.dumps({'accepted':True,'public':str(public)}))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','repair','step','finish','export']);parser.add_argument('--output',required=True)
    parser.add_argument('--arm',choices=['prospective','permanent_control']);parser.add_argument('--intermediate-source')
    args=parser.parse_args();output=Path(args.output).absolute()
    if args.action=='setup':
        if args.arm is None:parser.error('--arm required for setup')
        setup(output,args.arm)
    elif args.action=='repair':
        if args.intermediate_source is None:parser.error('--intermediate-source required for repair')
        repair(output,args.intermediate_source)
    else:globals()[args.action](output)


if __name__=='__main__':main()
