"""Source-bound functional acceptance and explicitly artificial exchange qualification."""
import argparse
import copy
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
PINS = {'vendor/__init__.py':'be8bdfe2c1e80537aa8346db6e39112224381b56a853f94d460c00d29692db54',
        'vendor/alpha_claim/__init__.py':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        'vendor/alpha_claim/contracts.py':'3536b96c4b7ee46f9af7d807e02685aa55e42daae7f7c56b7e9029ca2cde0964',
        'vendor/alpha_claim/protected_exchange.py':'a3bd70ec100f813e64bfaaabef97a6e336c8fd2d86c048c8a3c5e0ec3b664e42'}
LEGACY_ENGINE_SHA256 = '7b72c911d99a9aa12dc1f412d3b66f69ba58f3d4f2f50291310a7fd849df5272'
PINS['vendor/alpha_claim/protected_exchange_legacy.py'] = LEGACY_ENGINE_SHA256
PINS['commercial/terms.py'] = '5ade1ed96b540663ee0826cf66686ce5bf2a571187e273bcf6106963f2a42eb9'
REQUIREMENTS = ['artifact-identity','receipt-identity','verifier-source-identity','frozen-obligations-identity','independent-scoped-acceptance']
COSTS = ['discovery_and_failed_search','inference','data_network_storage','construction_integration','verification_repair','delivery_fees','maintenance_support','refunds_and_terminal_obligations']
SCENARIO = {'currency':'simulated-microUSD','unit_price':2000000,'opening_capital':20000000,'working_capital':1000000,
            'cost_per_admitted_case':{name:10000 for name in COSTS}}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hash_string(value):
    return type(value) is str and len(value)==64 and all(x in '0123456789abcdef' for x in value)


def read_bytes(path,cap=1000000):
    path=Path(path).absolute()
    if path.is_symlink() or not path.is_file() or any(p.is_symlink() for p in path.parents):
        raise ValueError('REGULAR_UNSYMLINKED_FILE_REQUIRED')
    with path.open('rb') as stream:raw=stream.read(cap+1)
    if len(raw)>cap:raise ValueError('INPUT_BYTE_CAP')
    return raw


def read_json(path,cap=1000000):
    raw=read_bytes(path,cap)
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('DUPLICATE_JSON_FIELD')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
    if type(value) is not dict:raise ValueError('OBJECT_REQUIRED')
    canonical(value)
    return value,raw


def source_path(root,item,suffix):
    if type(item) is not dict or set(item)!={'path','sha256'} or not hash_string(item['sha256']):
        raise ValueError('SOURCE_IDENTITY_SCHEMA')
    relative=Path(item['path']) if type(item['path']) is str else Path('/')
    if relative.is_absolute() or '..' in relative.parts or not relative.parts or relative.parts[0]!='verification' or relative.suffix!=suffix:
        raise ValueError('VERIFICATION_SOURCE_SCOPE')
    path=root/relative
    if sha(read_bytes(path,2000000))!=item['sha256']:raise ValueError('VERIFICATION_DEPENDENCY_CHANGED')
    return path


def validate_authority(artifact_path,receipt_path,contract_path,expected_contract_sha256,expected_receipt_sha256,root=None):
    root=ROOT if root is None else Path(root)
    if not hash_string(expected_contract_sha256) or not hash_string(expected_receipt_sha256):raise ValueError('EXTERNAL_FROZEN_AUTHORITY_HASH_REQUIRED')
    contract,contract_raw=read_json(contract_path,64000)
    if sha(contract_raw)!=expected_contract_sha256:raise ValueError('FROZEN_CONTRACT_MISMATCH')
    keys={'schema','scope','requirements','verifier_source','functional_obligations','scenario','commercial_cohort_admitted'}
    if set(contract)!=keys or contract['schema']!='agi-alpha/conditional-functional-contract006/v1':raise ValueError('CONTRACT_SCHEMA')
    if contract['scope']!='source-bound-pilot-report-delivery' or contract['requirements']!=REQUIREMENTS:
        raise ValueError('UNSUPPORTED_FUNCTIONAL_SCOPE_OR_REQUIREMENTS')
    if contract['commercial_cohort_admitted'] is not False:raise ValueError('COMMERCIAL_ADMISSION_NOT_QUALIFIED')
    if contract['scenario']!=SCENARIO:raise ValueError('UNQUALIFIED_SCENARIO_PARAMETERS')
    source_path(root,contract['verifier_source'],'.py')
    obligations_path=source_path(root,contract['functional_obligations'],'.json')
    obligations,_=read_json(obligations_path,64000)
    required={'schema','scope','requires_truthful_all_arms_and_failures','does_not_require_scientific_advantage','buyer_participation_is_fixture_only','commercial_price_is_not_established'}
    if set(obligations)!=required or obligations['schema']!='agi-alpha/functional-obligations006/v1' or obligations['scope']!=contract['scope']:
        raise ValueError('UNSUPPORTED_OBLIGATION_DOCUMENT')
    if any(obligations[key] is not True for key in required-{'schema','scope'}):raise ValueError('UNSUPPORTED_OR_WEAKENED_OBLIGATION')
    artifact,artifact_raw=read_json(artifact_path)
    if len(canonical(artifact))>1000000:raise ValueError('DELIVERY_ARTIFACT_CAP')
    receipt,receipt_raw=read_json(receipt_path,64000)
    if sha(receipt_raw)!=expected_receipt_sha256:raise ValueError('FROZEN_RECEIPT_MISMATCH')
    fields={'schema','artifact_sha256','contract_sha256','functional_obligations_sha256','verifier_source_sha256','accepted','scope'}
    if set(receipt)!=fields or receipt['schema']!='agi-alpha/functional-acceptance006/v1':raise ValueError('ACCEPTANCE_RECEIPT_SCHEMA')
    expected={'artifact_sha256':sha(artifact_raw),'contract_sha256':expected_contract_sha256,
              'functional_obligations_sha256':contract['functional_obligations']['sha256'],
              'verifier_source_sha256':contract['verifier_source']['sha256'],'scope':contract['scope']}
    if any(receipt[key]!=value for key,value in expected.items()):raise ValueError('ACCEPTANCE_RECEIPT_BINDING')
    if receipt['accepted'] is not True:raise ValueError('FUNCTIONAL_ACCEPTANCE_NOT_ESTABLISHED')
    return artifact,contract,receipt,{'artifact_sha256':sha(artifact_raw),'contract_sha256':expected_contract_sha256,
        'receipt_sha256':expected_receipt_sha256,'functional_obligations_sha256':expected['functional_obligations_sha256'],
        'verifier_source_sha256':expected['verifier_source_sha256']}


def engine(root=None, *, version='legacy-permanent-v1'):
    root=ROOT if root is None else Path(root)
    for path,expected in PINS.items():
        if sha(read_bytes(root/path))!=expected:raise ValueError('PINNED_EXCHANGE_SOURCE_MISMATCH '+path)
    if version == 'legacy-permanent-v1':
        from vendor.alpha_claim.protected_exchange_legacy import ProtectedExchange
    elif version == 'prospective-v1':
        from vendor.alpha_claim.protected_exchange import ProtectedExchange
    else:
        raise ValueError('SUPPORTED_EXPLICIT_NATIVE_ENGINE_VERSION_REQUIRED')
    return ProtectedExchange


def run(artifact_path,receipt_path,contract_path,output,*,expected_contract_sha256,expected_receipt_sha256):
    started,cpu=time.monotonic(),time.process_time()
    artifact,contract,receipt,binding=validate_authority(artifact_path,receipt_path,contract_path,expected_contract_sha256,expected_receipt_sha256)
    ProtectedExchange=engine()
    output=Path(output)
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.absolute().parents):raise FileExistsError(output)
    output.mkdir(parents=True,exist_ok=False)
    checks=[];admitted=[];semantic=[]
    base_task={'schema':'agi-alpha/model-delivery006/v1','binding':binding,'artifact_canonical_sha256':sha(canonical(artifact)),
               'scope':contract['scope'],'commercial_admission':False}
    def validate(task):
        if type(task) is not dict or set(task)!=set(base_task)|{'model_accepts'} or any(task[k]!=v for k,v in base_task.items()) or type(task['model_accepts']) is not bool:
            raise ValueError('FROZEN_MODEL_TASK_MISMATCH')
    def check(task,value):
        validate(task)
        current=validate_authority(artifact_path,receipt_path,contract_path,expected_contract_sha256,expected_receipt_sha256)
        accepted=task['model_accepts'] is True and sha(canonical(value))==base_task['artifact_canonical_sha256'] and current[3]==binding
        result={'accepted':accepted,'decisive':True,'scope':'CONDITIONAL_FUNCTIONAL_DELIVERY_QUALIFICATION_ONLY','commercial_acceptance':False,'authority':binding}
        semantic.append(result)
        return result
    def opened(name,opening=SCENARIO['opening_capital'],working=SCENARIO['working_capital']):
        return ProtectedExchange(output/(name+'.sqlite'),key=b'6'*32,contract='conditional006/'+binding['contract_sha256'],validate=validate,check=check,opening=opening,working=working)
    def refuse(name,kinds,call):
        try:call()
        except kinds as error:checks.append({'name':name,'passed':True,'error':type(error).__name__,'detail':str(error)})
        else:raise AssertionError('UNEXPECTED_SUCCESS '+name)
    def offer(ex,ident,*,accepts=True,price=SCENARIO['unit_price'],buyer='model-funded',costed=True):
        task={**base_task,'model_accepts':accepts};ex.offer(ident,buyer,price,'nonrecourse-simulated',task,100)
        row=ex.order(ident);terms={k:row[k] for k in ('id','buyer','price','rail','task_hash','contract','deadline')}
        ex.event(ident,'consent-'+ident,'consent',{'buyer':buyer,'termsHash':sha(canonical(terms))},0)
        admitted.append({'cohort':Path(ex.db.execute('PRAGMA database_list').fetchone()['file']).stem,'scenario_category_costs_charged':costed,'id':ident,'model_accepts':accepts,'price':price,'buyer':buyer,'artifact_sha256':binding['artifact_sha256'],'real_buyer':False})
        if costed:
            for category,amount in SCENARIO['cost_per_admitted_case'].items():ex.cost('scenario-cost-'+ident+'-'+category,amount)
    def fund(ex,ident,*,crash=False):
        return ex.event(ident,'fund-'+ident,'fund',ex.provider.issue(ex.order(ident),'funded'),1,crash=crash)
    def prepare(ex,ident):return ex.event(ident,'prepare-'+ident,'prepare',artifact,2)
    def release(ex,ident,*,crash=False):
        return ex.event(ident,'release-'+ident,'release',ex.provider.issue(ex.order(ident),'cleared'),3,crash=crash)
    def snapshot_rows(ex):
        return {'snapshot':ex.snapshot(),'trades':[dict(r) for r in ex.db.execute('SELECT id,buyer,price,state,custody,refund_due,compensation_due,artifact_hash FROM trades ORDER BY id')],
                'journal':[dict(r) for r in ex.db.execute('SELECT seq,order_id,kind,amount FROM journal ORDER BY seq')],
                'event_count':ex.db.execute('SELECT count(*) FROM events').fetchone()[0],
                'source_receipt_count':ex.db.execute('SELECT count(*) FROM source_receipts').fetchone()[0]}
    ex=opened('same-artifact-cohort')
    snapshots={}
    try:
        ex.wallet('model-funded',100000000);ex.wallet('model-unfunded',0)
        offer(ex,'accepted');fund(ex,'accepted')
        refuse('download-before-acceptance',PermissionError,lambda:ex.download('accepted','model-funded'))
        prepare(ex,'accepted')
        refuse('download-before-payment-clearance',PermissionError,lambda:ex.download('accepted','model-funded'))
        forged=ex.provider.issue(ex.order('accepted'),'cleared');forged['signature']='0'*64
        refuse('forged-clearing-receipt',ValueError,lambda:ex.event('accepted','forged-clear','release',forged,3))
        release(ex,'accepted');before=snapshot_rows(ex);release(ex,'accepted')
        if snapshot_rows(ex)!=before:raise AssertionError('DUPLICATE_SETTLEMENT_CHANGED_LEDGER')
        checks.append({'name':'positive-cleared-settlement-idempotent','passed':True})
        delivered=ex.download('accepted','model-funded')
        if delivered!=canonical(artifact):raise AssertionError('WRONG_DELIVERED_ARTIFACT')
        (output/'DELIVERED.json').write_bytes(delivered)
        refuse('wrong-buyer-download',PermissionError,lambda:ex.download('accepted','other-model'))
        offer(ex,'nonpayment',buyer='model-unfunded')
        refuse('nonpayment',ValueError,lambda:fund(ex,'nonpayment'))
        ex.event('nonpayment','cancel-nonpayment','cancel',{},2)
        offer(ex,'dispute',accepts=False);fund(ex,'dispute')
        refuse('buyer-model-dispute',ValueError,lambda:prepare(ex,'dispute'))
        ex.event('dispute','refund-dispute','refund',{},3)
        before=snapshot_rows(ex);ex.event('dispute','refund-dispute','refund',{},3)
        if snapshot_rows(ex)!=before:raise AssertionError('DUPLICATE_REFUND_CHANGED_LEDGER')
        checks.append({'name':'duplicate-refund-idempotent','passed':True})
        offer(ex,'interrupted');before=snapshot_rows(ex)
        refuse('funding-interrupted-before-commit',InterruptedError,lambda:fund(ex,'interrupted',crash=True))
        if snapshot_rows(ex)!=before:raise AssertionError('FUND_INTERRUPTION_NOT_ATOMIC')
        ex.close();ex=opened('same-artifact-cohort');fund(ex,'interrupted');prepare(ex,'interrupted');before=snapshot_rows(ex)
        refuse('settlement-interrupted-before-commit',InterruptedError,lambda:release(ex,'interrupted',crash=True))
        if snapshot_rows(ex)!=before:raise AssertionError('RELEASE_INTERRUPTION_NOT_ATOMIC')
        ex.close();ex=opened('same-artifact-cohort');release(ex,'interrupted')
        if ex.download('interrupted','model-funded')!=canonical(artifact):raise AssertionError('RESUME_WRONG_ARTIFACT')
        checks.append({'name':'durable-funding-and-release-recovery','passed':True})
        for i in range(3):
            ident='correlated-'+str(i);offer(ex,ident);fund(ex,ident);prepare(ex,ident);release(ex,ident)
        snapshots['primary_conditional_qualification']=snapshot_rows(ex)
        # Every previously released delivery is exposed to the same clustered reversal.
        for ident in ['accepted','interrupted']+['correlated-'+str(i) for i in range(3)]:
            ex.event(ident,'reverse-'+ident,'late_reversal',{},4)
        snapshots['correlated_reversal_stress']=snapshot_rows(ex)
        if ex.snapshot()['revenue']!=0 or ex.snapshot()['collections']!=0 or ex.snapshot()['unrestrictedEarned']!=0:
            raise AssertionError('REFUNDED_REVENUE_OR_EARNINGS_REMAIN')
        checks.append({'name':'correlated-accepted-delivery-refund-cluster','passed':True})
        refuse('breach-stops-investment',ValueError,lambda:ex.reserve_investment('commercial-successor',1,1,intent_hash=binding['artifact_sha256']))
    finally:ex.close()
    liquidity=opened('liquidity-deferral',opening=2100000,working=0)
    try:
        liquidity.wallet('model-funded',10000000);liquidity.cost('illustrative-incurred-cost',100000)
        offer(liquidity,'liquidity-positive',costed=False);fund(liquidity,'liquidity-positive');prepare(liquidity,'liquidity-positive');release(liquidity,'liquidity-positive')
        offer(liquidity,'liquidity-restricted',price=1800000,costed=False);fund(liquidity,'liquidity-restricted')
        snapshots['positive_profit_but_no_unrestricted_cash']=snapshot_rows(liquidity)
        if liquidity.snapshot()['profit']<=0 or liquidity.snapshot()['unrestrictedEarned']!=0 or liquidity.snapshot()['available']!=0:
            raise AssertionError('LIQUIDITY_FALSIFIER_NOT_ESTABLISHED')
        refuse('profit-without-liquidity-defers-investment',ValueError,lambda:liquidity.reserve_investment('liquidity-successor',1,1,intent_hash=binding['artifact_sha256']))
        liquidity.event('liquidity-restricted','refund-restricted','refund',{},4)
        snapshots['refundable_custody_released_not_revenue']=snapshot_rows(liquidity)
        if liquidity.snapshot()['revenue']!=SCENARIO['unit_price']:raise AssertionError('DEPOSIT_COUNTED_AS_REVENUE')
        checks.append({'name':'restricted-deposit-release-not-operating-revenue','passed':True})
    finally:liquidity.close()
    primary=snapshots['primary_conditional_qualification']['snapshot']
    frontier={'units':'simulated-microUSD; scenario prices and cost entries are engineering inputs, not market estimates',
              'illustrative_collections':primary['collections'],'illustrative_costs_charged':primary['expenses'],
              'unpriced_complete_lifecycle_cost_K':None,'conditional_positive_profit_iff':'K < illustrative_collections - illustrative_costs_charged',
              'illustrative_K_upper_threshold':primary['collections']-primary['expenses'],
              'conditional_participation':'Unmeasured. Include zero participation and free qualified conventional self-service. Public core prices are functionally different and do not set this fixture price.',
              'same_cohort_baseline_complete_cost_profit':None,'intervention_complete_cost_profit':None,
              'negative_to_positive_boundary_crossing':'NOT_ESTABLISHED','nonentry_incremental_no_new_commitment_profit':0,'nonentry_complete_profit':None,'best_outside_option_value':None,'AGI_ALPHA_value_capture':'UNKNOWN',
              'commercial_admitted_inputs':0,'accounting_scope':'same-artifact-cohort only; liquidity-deferral is a separate falsifier and is never pooled into this cohort profit','all_fixture_admitted_cases':[x for x in admitted if x['cohort']=='same-artifact-cohort'],
              'cost_categories':{name:{'actual_measured_monetary_cost':None,'scenario_only_per_case_charge':amount} for name,amount in SCENARIO['cost_per_admitted_case'].items()}}
    result={'schema':'agi-alpha/conditional-commerce006/v1','mode':'ENGINEERING_CONDITIONAL_QUALIFICATION_FIXTURE_ONLY',
            'binding':binding,'contract':contract,'source':{'foundation':'MontrealAI/AGI-Alpha-Agent-v0','revision':'a6b2d869a7736e7c414d7d615d86c616c2f82615','pinned_sha256':PINS,'adapter_sha256':sha(read_bytes(__file__))},
            'functional_acceptance':{'accepted':True,'scope':contract['scope'],'receipt':receipt,'not_scientific_advantage':True,'not_buyer_demand':True},
            'all_scenario_cases_including_separate_liquidity_falsifier':admitted,'checks':checks,'all_qualification_checks_passed':all(c['passed'] for c in checks),
            'semantic_checks':semantic,'snapshots':snapshots,'conditional_frontier':frontier,
            'commercial_decision':{'admitted_cohort':None,'actual_receipts':0,'commercially_qualified_simulated_receipts':0,'available_commercial_earned_funds':0,
                'complete_cost_surplus':'UNKNOWN','investment':'DEFER_NO_QUALIFIED_COMMERCIAL_EARNINGS','funded_successor':'NOT_ESTABLISHED','live_commercial_success':'NOT_ESTABLISHED'},
            'resources':{'wall_seconds':time.monotonic()-started,'cpu_seconds':time.process_time()-cpu,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'database_bytes':sum(p.stat().st_size for p in output.glob('*.sqlite')),'external_model_calls':0,'complete_monetary_cost':None},
            'limits':['The external contract and receipt hashes are a trusted caller/independent-verifier boundary; hashes authenticate identity, not factual correctness or external buyer authority.',
                      'Source-hash checks do not turn a forged externally supplied authority hash into a real signature. No actual buyer-authentication or payment provider is integrated.',
                      'The same artifact is functionally accepted/released only inside an explicitly artificial local scenario. Its qualification revenue/profit/cash is NEVER commercial earnings.',
                      'No real provider, customer outreach, spending, security change or transfer. The existing source-pinned Alpha ledger is reused, not replaced.',
                      'All scenarios are fixed before outcome; the stress and liquidity cases are preserved beside the favorable clearing path.',
                      'Historical inference, support and full lifecycle costs remain unknown; no complete-cost commercial profitability or funded compounding follows.']}
    with (output/'COMMERCIAL.json').open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('artifact','receipt','contract','output','expected-contract-sha256','expected-receipt-sha256'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=run(Path(args.artifact),Path(args.receipt),Path(args.contract),Path(args.output),expected_contract_sha256=args.expected_contract_sha256,expected_receipt_sha256=args.expected_receipt_sha256)
    print(json.dumps({'output':args.output,'all_qualification_checks_passed':result['all_qualification_checks_passed'],'commercial_decision':result['commercial_decision']}))

if __name__=='__main__':
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    main()
