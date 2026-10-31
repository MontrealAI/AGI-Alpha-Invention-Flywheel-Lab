"""Development benchmark equivalence; product source/financial audits remain strict."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

started = time.process_time(); root = Path(sys.argv[1]); names = sys.argv[2:]
def sha(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def funding(value):
    value=copy.deepcopy(value)
    for key in ['source_sha256','native_actions_sha256','obligation_receipt_sha256']:value.pop(key,None)
    if 'native_receipt' in value:
        for key in ['state_digest','actions_sha256']:value['native_receipt'].pop(key,None)
    return value

def project(result):
    result=copy.deepcopy(result); owned=result.pop('owned_account');result.pop('source');result.pop('resource_receipt')
    for row in result['costs']:row['funding_receipt']=funding(row['funding_receipt'])
    for row in result['orders']:
        row['funding_receipt']=funding(row['funding_receipt'])
        row['service_receipt'].pop('process_cpu_seconds',None)
    for row in result['investments']:row['funding_receipt']=funding(row['funding_receipt'])
    tape=copy.deepcopy(owned['ledger']);tape.pop('actions_sha256')
    tape['config']['manifest_sha256']='CURRENT_SOURCE_COHORT_IDENTITY'
    tape['config']['contract']='CURRENT_SOURCE_ACCOUNT_CONTRACT'
    seed_ids={entry['receipt']['native_event_sequence']:entry['request']['id']
              for entry in owned['connected_journal']['entries']
              if entry['request']['operation']=='spend' and entry['funding']=='SEED'}
    for row in tape['actions']:
        if row['op']=='reserve':row['args']['intent_sha256']='CURRENT_SOURCE_AUTHORIZED_INTENT'
        if row['op']=='finish':row['args']['artifact_sha256']='CURRENT_SOURCE_WORK_AND_OBLIGATION_COMMITMENT'
        if row['seq'] in seed_ids:
            assert row['op']=='cost';row['args']['id']='SEED_RESOURCE:'+seed_ids[row['seq']]
    for row in tape['investment_witnesses']:
        witness=json.loads(row['witness'])
        for key in ['intentHash','artifactHash']:
            if key in witness:witness[key]='CURRENT_SOURCE_NATIVE_COMMITMENT'
        row['witness']=witness
    result['native_ledger_semantics']=tape
    # Every reservation amount, worst-case liability and resource execution term
    # remains compared; only current-source authorization/HMAC commitments differ.
    contracts={}
    for ident,proof in owned['action_proofs'].items():
        body=copy.deepcopy(proof['body']);body.pop('expected_state_digest');body.pop('authorized_digest')
        body['plan'].pop('source_hashes')
        for option in body['plan'].get('selected_options',[]):option.get('execution',{}).pop('source_sha256',None)
        contracts[ident]=body
    result['authorized_resource_contract_semantics']=contracts
    obligations=copy.deepcopy(owned['obligation_resolutions'])
    for receipt in obligations.values():
        receipt.pop('native_actions_sha256')
        for row in receipt['growth']:row.pop('execution_sha256')
    result['obligation_resolution_semantics']=obligations
    return result

def differences(a,b,path=''):
    if type(a)!=type(b):return[path]
    if isinstance(a,dict):return [p for key in sorted(set(a)|set(b)) for p in ([path+'.'+key] if key not in a or key not in b else differences(a[key],b[key],path+'.'+key))]
    if isinstance(a,list):return [path] if len(a)!=len(b) else [p for i,(x,y) in enumerate(zip(a,b)) for p in differences(x,y,path+'['+str(i)+']')]
    return [] if a==b else[path]

baseline=json.loads((root/'before-unprofiled/RESULT.json').read_text());expected=project(baseline);worlds=[]
for name in names:
    path=root/name/'RESULT.json';result=json.loads(path.read_text());actual=project(result);diff=differences(expected,actual)
    assert not diff,(name,diff[:30])
    assert sha(result['source']['files'])==result['source']['sha256']
    worlds.append({'candidate':name,'result_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                   'authentic_world_source_sha256':result['source']['sha256'],
                   'financial_source_files':{key:result['source']['files'][key] for key in ['commercial/ledger.py','adaptive_enterprise/account.py','connected_enterprise/finance.py']},
                   'semantic_projection_sha256':sha(actual),'semantic_differences':[],
                   'paid_jobs':result['paid_jobs'],'accepted_jobs':result['accepted_jobs'],
                   'native_actions':len(result['owned_account']['ledger']['actions']),
                   'native_reservations':len(result['owned_account']['action_proofs']),
                   'summary':result['summary']})
receipt={'schema':'agi-alpha/performance016-development-equivalence/v1',
         'scope':'Fixed exposed14003/12day baseline engineering; no full-default release or new commercial confirmation.',
         'baseline_commit':'10bdb2c5787f95158642b068756ba30b58140562',
         'baseline_result_file_sha256':hashlib.sha256((root/'before-unprofiled/RESULT.json').read_bytes()).hexdigest(),
         'baseline_semantic_projection_sha256':sha(expected),'candidates':worlds,
         'compared':'Every frozen config, buyer/budget/choice/market/channel/event/cost/offer/order/time/useful work artifact/price/output/counter; every native action op/day/amount/before/after and all native financial tables/witness money; every resource contract/liability and obligation amount/unused reserve.',
         'excluded_provenance':'Top source/resource timing; service CPU; funding source/native-prefix/obligation digests and receipt state digest; native source-bound contract/manifest IDs, action/intent/finish hashes, source-derived seed resource IDs (mapped through original journal), witness intent/artifact hashes; plan source hashes and state/authorization/HMAC commitments; obligation native-prefix and execution commitments. Product audits still enforce all of these unchanged.',
         'not_claimed':'Bitwise cryptographic equality across different source/manifests/private simulation keys; native capacity expansion in this baseline fixture; end-to-end resource-qualified release success.',
         'process_cpu_seconds':time.process_time()-started}
(root/'SEMANTIC_EQUIVALENCE.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({'candidates':[row['candidate'] for row in worlds],'projection_sha256':sha(expected),'process_cpu_seconds':receipt['process_cpu_seconds']}))
