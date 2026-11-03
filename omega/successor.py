"""Actual portable batch capability and finite causal controls; no novel-method claim."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
from mechanism_harness.core import digest
from omega.product import BUNDLE_PATHS
from omega.verify import exhaustive_optimum, verify as verify_plan

SCHEMA = 'omega/qualified-successor/v1'
DEFAULT_COST_COMPONENTS = {
    'packaging_execution': 1_000_000,
    'qualification_execution': 1_000_000,
    'temporary_storage': 100_000,
}
LAUNCHER = '''import json, sys
from omega.runner import buyer
from omega.help import diagnose

items=json.load(sys.stdin)
if type(items) is not list or not 1 <= len(items) <= 16:
    raise ValueError('FINITE_BATCH_OF_ONE_TO_SIXTEEN_CASES_REQUIRED')
rows=[]
for item in items:
    if type(item) is not dict or set(item)!={'id','request'} or type(item['id']) is not str:
        raise ValueError('EXACT_BATCH_ITEM_FIELDS_REQUIRED')
    row={'id':item['id'],'result':None,'error':None,'help':None}
    try: row['result']=buyer(item['request'])
    except (ValueError,TypeError,KeyError,RuntimeError) as error:
        row['error']=str(error)
        row['help']=diagnose(str(error))
    rows.append(row)
json.dump(rows,sys.stdout,sort_keys=True)
sys.stdout.write('\\n')
'''
CONVENTIONAL_LAUNCHER = '''import json, sys
from omega.water import validate, conventional_milp
from omega.verify import verify
from omega.help import diagnose
from mechanism_harness.core import digest

rows=[]
for item in json.load(sys.stdin):
    row={'id':item['id'],'result':None,'error':None,'help':None}
    try:
        request=item['request'];validate(request)
        if request['model_route']=='buyer_owned_account_external':
            raise ValueError('EXTERNAL_PROPOSAL_FILE_REQUIRED_NO_ACCOUNT_WILL_BE_CALLED')
        if sum(s['capacity'] for s in request['sources'] if s['consent'])+request['freshwater_cap'] < sum(k['demand'] for k in request['sinks']):
            proposal={'status':'MODEL_INFEASIBLE','request_sha256':digest(request),'allocation':None,'freshwater':None,'objective':None}
        else: proposal=conventional_milp(request)
        certificate=verify(request,proposal) if proposal['status']=='MODEL_PLAN' else None
        row['result']={'model_api_calls':0,'plan':proposal,'certificate':certificate}
    except (ValueError,TypeError,KeyError,RuntimeError) as error:
        row['error']=str(error);row['help']=diagnose(str(error))
    rows.append(row)
json.dump(rows,sys.stdout,sort_keys=True)
sys.stdout.write('\\n')
'''


def plan(root, cost_components_microUSD=None):
    root = Path(root)
    costs = dict(DEFAULT_COST_COMPONENTS if cost_components_microUSD is None else cost_components_microUSD)
    if set(costs) != set(DEFAULT_COST_COMPONENTS) or any(type(v) is not int or v < 0 for v in costs.values()):
        raise ValueError('COMPLETE_ACTION_COST_QUOTE_REQUIRED')
    paths = sorted(set(BUNDLE_PATHS) | {'omega/help.py'})
    sources = {}
    for relative in paths:
        path = root/relative
        if path.is_symlink() or not path.is_file():
            raise ValueError('REGULAR_KIT_SOURCE_REQUIRED')
        sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    files = {**sources, 'omega_batch.py':hashlib.sha256(LAUNCHER.encode()).hexdigest()}
    return {
        'schema':SCHEMA, 'artifact_sha256':digest(files), 'file_sha256':files,
        'source_hashes':sources, 'cost_components_microUSD':costs,
        'quoted_construction_max_microUSD':sum(costs.values()),
        'cost_basis':'AUTHORED_ACTION_ONLY_ENVELOPE_NOT_MEASURED_BILL; construction, qualification and temporary storage prepaid; no actual model/development total established',
        'actual_development_model_bill_microUSD':None,
        'capability':'Portable local batch of independent mathematical results and documentation-backed diagnostics',
        'rights':'HYPOTHETICAL_LOCAL_RESEARCH_COPY; repository redistribution rights unresolved',
        'scope':'FINITE_DEVELOPER_AUTHORED_WORKFLOW_NOT_AUTONOMOUS_INVENTION_OR_PHYSICAL_QUALIFICATION',
    }


def construct(root, output, *, specification=None):
    root, output = Path(root), Path(output)
    specification = plan(root) if specification is None else specification
    if specification != plan(root, specification.get('cost_components_microUSD')):
        raise ValueError('CONSTRUCTION_SPECIFICATION_CHANGED')
    output.mkdir(parents=True, exist_ok=False)
    for relative in specification['source_hashes']:
        destination = output/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root/relative, destination)
    (output/'omega_batch.py').write_text(LAUNCHER, encoding='utf-8')
    (output/'manifest.json').write_text(json.dumps(specification,sort_keys=True,indent=2)+'\n', encoding='utf-8')
    return specification


def fixtures(root):
    original = json.loads((Path(root)/'omega/request.json').read_text())
    changed = copy.deepcopy(original)
    changed['name'] = 'Changed successor source quality'
    changed['sources'][1]['upper_quality'][0] = 9
    refused = copy.deepcopy(original)
    refused['name'] = 'Changed successor participation'
    refused['sources'][0]['consent'] = False
    external = copy.deepcopy(original)
    external['model_route'] = 'buyer_owned_account_external'
    malformed = copy.deepcopy(original)
    malformed['freshwater_cap'] = -1
    oversized = copy.deepcopy(original)
    oversized['sources'][0]['capacity'] = 10**100
    oversized['sinks'][0]['demand'] = 10**100 + 10
    return [
        {'id':'primary', 'request':original}, {'id':'quality-successor', 'request':changed},
        {'id':'withdrawal', 'request':refused}, {'id':'external-unavailable', 'request':external},
        {'id':'invalid-input', 'request':malformed}, {'id':'resource-refusal', 'request':oversized},
    ]


def _execute(directory, items, launcher='omega_batch.py'):
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    process = subprocess.run([sys.executable,'-E','-s','-B',str(Path(directory).resolve()/launcher)],
        input=json.dumps(items),text=True,capture_output=True,cwd=directory,env={},timeout=30)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if process.returncode:
        raise ValueError('PORTABLE_KIT_EXECUTION_FAILED:'+str(process.returncode))
    return json.loads(process.stdout), {
        'wall_seconds':time.perf_counter()-start,
        'child_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        'telemetry_is_not_a_human_time_or_billing_measure':True,
    }


def _accept(root, items, rows):
    if type(rows) is not list or len(rows) != len(items):
        raise ValueError('COMPLETE_INDEPENDENT_BATCH_REQUIRED')
    expected_errors = {
        'external-unavailable':('EXTERNAL_PROPOSAL_FILE_REQUIRED_NO_ACCOUNT_WILL_BE_CALLED','External proposal handoff'),
        'invalid-input':('NONNEGATIVE_INTEGER_REQUIRED:freshwater_cap','Invalid requests or rejected plans'),
        'resource-refusal':('RESOURCE_CHECKPOINT_NOT_INFEASIBILITY','Resource checkpoints'),
    }
    documentation = (Path(root)/'omega/README.md').read_text()
    doc_hash = hashlib.sha256(documentation.encode()).hexdigest()
    accepted = []
    for item, row in zip(items, rows):
        if type(row) is not dict or set(row) != {'id','result','error','help'} or row['id'] != item['id']:
            raise ValueError('BATCH_RESPONSE_BINDING_CHANGED')
        if item['id'] in expected_errors:
            error, section = expected_errors[item['id']]
            if item['id'] == 'resource-refusal' and row['error'] is None and isinstance(row['result'],dict):
                request = item['request']
                total_supply = sum(s['capacity'] for s in request['sources'] if s['consent'])+request['freshwater_cap']
                total_demand = sum(k['demand'] for k in request['sinks'])
                proposal = row['result'].get('plan',{})
                if total_supply >= total_demand or proposal.get('status') != 'MODEL_INFEASIBLE' or proposal.get('request_sha256') != digest(request) or row['result'].get('certificate') is not None:
                    raise ValueError('EXACT_SUPPLY_BOUND_NOT_ESTABLISHED')
                accepted.append({'id':item['id'],'accepted':True,'outcome':'EXACT_TOTAL_SUPPLY_INFEASIBILITY'})
                continue
            help_row = row['help']
            if row['error'] != error or row['result'] is not None or type(help_row) is not dict:
                raise ValueError('EXPECTED_REFUSAL_NOT_ESTABLISHED')
            if help_row.get('status') != 'DOCUMENTED' or help_row.get('documentation_sha256') != doc_hash or help_row.get('network_calls') != 0:
                raise ValueError('LOCAL_DOCUMENTATION_BINDING_CHANGED')
            citations = help_row.get('citations')
            if type(citations) is not list or len(citations) != 1:
                raise ValueError('EXACT_DOCUMENT_CITATION_REQUIRED')
            citation = citations[0]
            if citation.get('file') != 'omega/README.md' or citation.get('section') != section or not citation.get('excerpt') or citation['excerpt'] not in documentation:
                raise ValueError('DOCUMENTATION_CITATION_CHANGED')
            accepted.append({'id':item['id'],'accepted':True,'outcome':'SAFE_REFUSAL_WITH_CURRENT_DOCUMENTATION'})
        else:
            result = row['result']
            if row['error'] is not None or row['help'] is not None or type(result) is not dict or result.get('model_api_calls') != 0:
                raise ValueError('EXPECTED_MATHEMATICAL_RESULT_MISSING')
            optimum = exhaustive_optimum(item['request'])['objective']
            if optimum is None:
                if result.get('plan',{}).get('status') != 'MODEL_INFEASIBLE' or result.get('certificate') is not None:
                    raise ValueError('INFEASIBILITY_NOT_INDEPENDENTLY_ESTABLISHED')
                outcome = 'EXHAUSTIVELY_CHECKED_MODEL_INFEASIBLE'
            else:
                certificate = verify_plan(item['request'],result['plan'])
                if result.get('certificate') != certificate or result['plan']['objective'] != optimum:
                    raise ValueError('INDEPENDENT_CERTIFICATE_OR_OPTIMUM_MISMATCH')
                outcome = 'INDEPENDENTLY_ACCEPTED_MATHEMATICAL_RESULT'
            accepted.append({'id':item['id'],'accepted':True,'outcome':outcome,'optimum':optimum})
    return accepted


def _checked_manifest(root, output):
    root, output = Path(root), Path(output)
    manifest_path = output/'manifest.json'
    if manifest_path.is_symlink():
        raise ValueError('REGULAR_KIT_MANIFEST_REQUIRED')
    manifest = json.loads(manifest_path.read_text())
    expected = plan(root,manifest.get('cost_components_microUSD'))
    if manifest != expected:
        raise ValueError('QUALIFICATION_MANIFEST_CHANGED')
    observed = set()
    for path in output.rglob('*'):
        if path.is_symlink():
            raise ValueError('QUALIFICATION_ARTIFACT_CHANGED')
        if path.is_file():
            observed.add(str(path.relative_to(output)))
    if observed != set(manifest['file_sha256']) | {'manifest.json'}:
        raise ValueError('QUALIFICATION_FILE_SET_CHANGED')
    for relative, expected_hash in manifest['file_sha256'].items():
        path = output/relative
        if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError('QUALIFICATION_ARTIFACT_CHANGED')
    return manifest


def verify(root, output):
    manifest = _checked_manifest(root,output)
    items = fixtures(root)
    rows, telemetry = _execute(output,items)
    acceptance = _accept(root,items,rows)
    return {
        'accepted':True,'activation_allowed':True,'artifact_sha256':manifest['artifact_sha256'],
        'qualification_sha256':digest({'artifact':manifest['artifact_sha256'],'cases':items,'results':acceptance}),
        'case_count':len(items),'accepted_case_count':len(acceptance),'cases':acceptance,
        'quoted_construction_max_microUSD':manifest['quoted_construction_max_microUSD'],
        'cost_basis':manifest['cost_basis'],'execution':telemetry,
        'scope':'FINITE_LOCAL_KIT_QUALIFICATION; activation requires a separate native funded construction receipt',
    }


def operate_tasks(root, output, task_ids=('quality-successor','withdrawal','external-unavailable')):
    manifest = _checked_manifest(root,output)
    indexed = {item['id']:item for item in fixtures(root) if item['id']!='primary'}
    if not isinstance(task_ids,(list,tuple)) or not task_ids or len(task_ids)>16 or any(type(t) is not str or t not in indexed for t in task_ids) or len(set(task_ids))!=len(task_ids):
        raise ValueError('DISTINCT_REGISTERED_SUCCESSOR_TASKS_REQUIRED')
    rows = []
    for ident in task_ids:
        item = indexed[ident]
        actual, telemetry = _execute(output,[item])
        accepted = _accept(root,[item],actual)[0]
        rows.append({'task_id':ident,'request_sha256':digest(item['request']),
            'result_sha256':digest(actual[0]),'result':actual[0],'acceptance':accepted,'execution':telemetry})
    charge = manifest['cost_components_microUSD']['qualification_execution']
    return {'schema':'omega/operated-successor-tasks/v1','artifact_sha256':manifest['artifact_sha256'],
        'task_ids':list(task_ids),'case_count':len(rows),'accepted_case_count':len(rows),'tasks':rows,
        'task_cost_each_microUSD':charge,'total_task_cost_microUSD':len(rows)*charge,
        'scope':'Actual local task executions under an authored action-cost envelope; native funding and permission are separate',
        'no_special_method_advantage':'An ordinary retained copy performs the identical work; fresh reconstruction each time is a limited discard-and-rebuild baseline'}


def comparison(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True,exist_ok=False)
    specification = plan(root)
    retained = output/'retained'
    construct(root,retained,specification=specification)
    predecessor = verify(root,retained)
    items = fixtures(root)[1:]
    rows = []
    for arm in ('retained_capability','no_predecessor','cash_only','equal_content_ordinary_reuse','conventional_construction'):
        directory = retained if arm == 'retained_capability' else output/arm
        if arm == 'equal_content_ordinary_reuse':
            shutil.copytree(retained,directory)
        elif arm != 'retained_capability':
            # No prior receipt or launcher is required: ordinary construction gets
            # the same public source/docs and may rebuild the same useful wrapper.
            construct(root,directory,specification=specification)
        if arm == 'conventional_construction':
            (directory/'ordinary_batch.py').write_text(CONVENTIONAL_LAUNCHER,encoding='utf-8')
        result, telemetry = _execute(directory,items,'ordinary_batch.py' if arm == 'conventional_construction' else 'omega_batch.py')
        acceptance = _accept(root,items,result)
        rows.append({'arm':arm,'accepted_cases':len(acceptance),'cases':acceptance,
            'result_sha256':digest(result),'execution':telemetry,
            'uses_predecessor_executable':arm in {'retained_capability','equal_content_ordinary_reuse'},
            'cash_creates_information_or_software':False,
            'producer':'Independent conventional MILP and ordinary wrapper' if arm=='conventional_construction' else 'Existing deterministic buyer constructor and public batch wrapper',
            'new_wrapper_construction':arm in {'no_predecessor','cash_only','conventional_construction'},
            'modeled_new_action_cost_microUSD':specification['cost_components_microUSD']['qualification_execution'] if arm in {'retained_capability','equal_content_ordinary_reuse'} else specification['quoted_construction_max_microUSD']})
    equal = len({digest(r['cases']) for r in rows}) == 1
    return {
        'schema':'omega/causal-successor-comparison/v1','predecessor':predecessor,'arms':rows,
        'predecessor_acquisition_cost_microUSD':specification['quoted_construction_max_microUSD'],
        'acquisition_cost_treatment':'Charge once for acquired predecessor and charge the qualification envelope again on changed tasks. All direct/rebuild controls may acquire the same available public capability at the same quote and retain it thereafter. Reuse and validation are not free across the complete sequence.',
        'same_information_and_case_budget':True,'all_arms_same_results':equal,
        'result_comparison':'Independent accepted outcomes and objectives; harmless report-layout differences are not advantages',
        'cash_only_scope':'This capability comparison holds adequate construction funding fixed; native earned-funding eligibility is separately checked by the seller account, not inferred here',
        'retained_method_advantage':False,
        'ordinary_equal_content_reuse_ties':rows[0]['cases']==rows[3]['cases'],
        'conventional_additional_resolved_case':any(c['outcome']=='EXACT_TOTAL_SUPPLY_INFEASIBILITY' for c in rows[-1]['cases']),
        'stronger_successor_capability_established':False,
        'super_alpha_established':False,
        'learning':'Portable accepted workflow handles changed inputs, refusals and diagnostics. Equal-content ordinary reuse ties. The conventional MILP wrapper also uses an exact total-supply bound and resolves the oversized infeasible case where the candidate safely checkpoints. Cash alone does not create capability, but can fund the same available construction.',
        'limitations':['Authored visible fixtures, not hidden customer holdouts','Construction is developer-authored, not discovered autonomously','Runtime telemetry is not human labor or complete resource billing','Modeled action cost is an explicit sensitivity, not measured invoice','No new scientific mechanism, physical capability or buyer willingness to pay established'],
    }


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    result=comparison(Path(__file__).resolve().parents[1],Path(args.output))
    print(json.dumps(result,indent=2,sort_keys=True))
