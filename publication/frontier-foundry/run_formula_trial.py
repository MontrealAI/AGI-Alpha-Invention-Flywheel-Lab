"""Registered compact-formula candidate construction, compile, verify and replay."""

import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from uuid import uuid4

from run_archive_trial import ROOT, PIN, MODEL, artifact, encoded, execute, parser, cases

REGISTRATION = '60f3e42f09e4cd28752a779968dd736c12dd8958'
FRESH = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20240120/00/atmos/gfs.t00z.pgrb2.0p25.f024'


def acquire(work):
    """Read one new 32-byte response, preserving identity and refusal evidence."""
    headers, data = work/'fresh.headers', work/'fresh.body'
    start = perf_counter_ns()
    attempt = subprocess.run(['curl','--fail','--silent','--show-error','--max-time','30','--max-filesize','32',
        '--range','0-31','--dump-header',str(headers),'--output',str(data),FRESH], capture_output=True)
    result = {'url':FRESH,'requested_range':'bytes=0-31','curl_exit':attempt.returncode,
              'wall_ns':perf_counter_ns()-start,'status':'ABSTAIN'}
    header = headers.read_text(errors='replace').splitlines() if headers.exists() else []
    statuses = [line for line in header if line.startswith('HTTP/')]
    fields = {key.lower():value.strip() for line in header if ':' in line for key,value in [line.split(':',1)]}
    raw = data.read_bytes() if data.exists() else b''
    result.update({'http':statuses[-1] if statuses else None,'range':fields.get('content-range'),
                   'etag':fields.get('etag'),'body_bytes':len(raw),'body_sha256':artifact(raw)})
    match = re.fullmatch(r'bytes 0-31/(\d+)',fields.get('content-range',''))
    if not attempt.returncode and statuses and statuses[-1].split()[1] == '206' and match and int(match[1]) > 31 and len(raw) == 32:
        result['status'] = 'OBSERVED'
    return result


def run(args):
    sys.path.insert(0, str(args.companion.resolve()))
    sys.path.insert(0, str(ROOT/'products/alpha-genesis-harness'))
    from bridge.adapters import BridgeError, Runtime, transport
    from bridge.instruments import compile_formula

    def sender(url, headers, body=None, timeout=60):
        if body is not None:
            body = {**body,'temperature':0,'seed':283,'cache_prompt':False}
        return transport(url,headers,body,timeout)

    model, weights, registration = (
        ('qwen3-4b-instruct-2507-q4_k_m', '2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e',
         '353f4842483425c27389a652d0d1388d5683462c')
        if args.reference_model else (MODEL, '74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db', REGISTRATION)
    )
    runtime = Runtime({'local_only':True,'timeout_seconds':90,'max_attempts':1,'providers':{
        'llama':{'kind':'openai','base_url':f'http://127.0.0.1:{args.port}/v1','output_limit_field':'max_tokens',
                 'models':{model:{'input_per_million':0,'output_per_million':0,'max_output_tokens':512,
                                  'input_token_overhead':128,'context_window':4096}}}
    }},sender=sender)
    evidence = {
        'schema':'frontier/foundry-formula-trial-v1','registration':registration,
        'baseline_registration':'ada2b9f9a12997d8968df53cc316ce81f730fc3b',
        'receipt_source':PIN,'seed':283,'temperature':0,'model':model,
        'weights_sha256':weights,
        'runtime_setup_ns':args.runtime_setup_ns,
        'compiler_sha256':artifact((ROOT/'products/alpha-genesis-harness/bridge/instruments.py').read_bytes()),
        'complete_cost':None,'beneficiary_acceptance':None,'commercial_evidence':None,'attempts':{}
    }

    def construct(label, task, prompt, token_limit):
        receipt = evidence['attempts'][label] = {'prompt':prompt,'prompt_sha256':artifact(prompt.encode()),'max_output_tokens':token_limit}
        start = perf_counter_ns()
        try:
            receipt.update(runtime.generate({'provider':'llama','model':model,'prompt':prompt,
                                             'max_output_tokens':token_limit,'run_id':uuid4().hex}))
        except BridgeError as error:
            receipt['failure'] = error.code
        receipt['model_wall_ns'] = perf_counter_ns()-start
        start = perf_counter_ns()
        try:
            raw = receipt.get('text','').strip()
            # Accept ordinary text or a single code fence. Every surviving line must be an assignment.
            raw = re.sub(r'^\x60{3}(?:python|text)?\n([\s\S]*?)\n\x60{3}$',r'\1',raw)
            parts = [re.fullmatch(r'([a-z]+)\s*=\s*(.+)',line.strip()) for line in raw.splitlines() if line.strip()]
            if any(part is None for part in parts) or len(parts) != len(task['outputs']):
                raise ValueError('FORMULA_FORMAT')
            formulas = {m[1]:m[2] for m in parts}
            if set(formulas) != set(task['outputs']):
                raise ValueError('FORMULA_FIELDS')
            candidate = {'name':label,'inputs':list(task['inputs']),
                         'outputs':{name:compile_formula(formula,{}) for name,formula in formulas.items()}}
            receipt.update({'formulas':formulas,'candidate':candidate,'candidate_sha256':artifact(encoded(candidate))})
            return candidate
        except (ValueError,RecursionError) as error:
            receipt['construction_failure'] = str(error)
            return None
        finally:
            receipt['compilation_ns'] = perf_counter_ns()-start

    directory = args.companion.resolve()
    task = json.loads((directory/'example.json').read_bytes())['task']
    with TemporaryDirectory() as work:
        p = Path(work)
        def save(name, value):
            target = p/name
            target.write_bytes(encoded(value))
            return target
        def cli(*parts):
            result = execute(directory,*parts)
            if result['output'].lstrip().startswith('{'):
                result['output'] = json.loads(result['output'])
            return result
        def trial(label, task, candidate, rows):
            paths = (save(label+'-mission.json',task),save(label+'-candidate.json',candidate))
            sealed = cli('seal',*paths)
            evidence[label+'_seal'] = sealed
            if sealed['returncode']:
                return None
            if callable(rows):
                rows = rows()
            suite = save(label+'-suite.json',{'schema':'frontier/foundry-cases-v1',
                'mission_sha256':artifact(encoded(task)), 'reference':'RFC 9110 and observed NOAA ranges at '+PIN,
                'cases':rows})
            result = evidence[label+'_grade'] = cli('check',*paths,suite)
            return (paths,suite) if result['returncode'] == 0 else None

        s1_prompt = ('Complete two formulas using start and end (integers). The range includes both endpoints. '
                     'For start=5 and end=7, bytes is 3 and ordered is True. '
                     'Return only these two assignments, replacing each blank with a Python expression:\n'
                     'bytes = ___\nordered = ___\nThe second assignment tests whether the first offset is at or before the last.')
        s1 = construct('s1-formulas',task,s1_prompt,256)
        def s1_cases():
            historic,_ = cases()
            return [{'input':{k:item[k] for k in ('start','end')},'expected':{'bytes':item['body'],'ordered':True}}
                    for item in historic] + [{'input':{'start':7,'end':7},'expected':{'bytes':1,'ordered':True}},
                                             {'input':{'start':8,'end':4},'expected':{'bytes':-3,'ordered':False}}]
        retained = trial('s1',task,s1,s1_cases) if s1 else None
        if retained:
            paths,suite = retained
            asset = evidence['asset'] = cli('retain',*paths,suite)
            if asset['returncode']:
                raise ValueError('Sealed asset could not be retained')
            retained_path = save('asset.json',asset['output'])
            evidence['invalid_inputs'] = {name:cli('run',retained_path,suite,save('negative.json',item))
                for name,item in [('missing',{'start':0}),('excess',{'start':0,'end':2_000_000_001}),
                                  ('fraction',{'start':0.5,'end':1})]}
            response = evidence['fresh_observation'] = acquire(p)
            if response['status'] == 'OBSERVED':
                evidence['fresh_run'] = cli('run',retained_path,suite,save('fresh.json',{'start':0,'end':31}))
                evidence['fresh_run_matches_observation'] = evidence['fresh_run']['output'] == {
                    'bytes':response['body_bytes'],'ordered':True}

        successor = {**task,'objective':'Validate normalized byte-window length and observed response-body size.',
                     'rule':'Require an ordered window within the object and a matching inclusive byte count.',
                     'inputs':{name:task['inputs']['start'] for name in ('start','end','length','body')},
                     'outputs':{'matches':'boolean'}}
        common = ('Return only one Python assignment: matches = ___. The scalar inputs are start, end, length and body. '
                  'Return True if all three tests pass: start is at most end; end is strictly less than length; '
                  'the number of bytes in the inclusive window equals body. Use and, comparisons and arithmetic.\n')
        prose = 'S1 assignments: bytes = end - start + 1; ordered = start <= end.'
        arms = [('s2_ordinary',prose)]
        if retained:
            arms.append(('s2_executable','S1 executable expressions: '+encoded(s1['outputs']).decode()))
        def s2_cases():
            historic,_ = cases()
            negatives = [{**row,'body':row['body']-1} for row in historic]
            invalid = [{'start':2,'end':5,'length':5,'body':4},{'start':3,'end':2,'length':4,'body':0}]
            return [{'input':row,'expected':{'matches':row['start'] <= row['end'] < row['length']
                     and len(range(row['start'],row['end']+1)) == row['body']}}
                    for row in historic + negatives + invalid]
        candidates = [(label,construct(label,successor,common + prior +
                       ' Example: start=5, end=7 gives bytes=3 and ordered=True.',256)) for label,prior in arms]
        for label, instrument in candidates:
            if instrument:
                trial(label,successor,instrument,s2_cases)
    args.output.write_text(json.dumps(evidence,ensure_ascii=False,sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    ap = parser()
    ap.add_argument('--reference-model', action='store_true')
    run(ap.parse_args())
