import copy,json,platform,sqlite3,sys
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
target=root/job['artifact'];original=target.read_bytes();target.write_bytes(original+b'\n')
try:
    try:load_jobs(root,manifest)
    except ValueError as e:results['cached_source_mutation_rejected']=str(e)
    else:raise AssertionError('CACHED_SOURCE_TAMPER_ACCEPTED')
finally:target.write_bytes(original)
results['runtime']={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'cryptography':cryptography.__version__}
Path(sys.argv[1]).write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
