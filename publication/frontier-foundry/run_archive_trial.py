"""Replay the registered construction and transfer with an explicit local llama.cpp server.

Start the pinned server with the options in REPORT.md. Use the extracted release companion.
Only the construction prompt is sent to the model. Historical cases are gathered after the
candidate is sealed. The direct inference control legitimately receives the task inputs.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[2]
PIN = '6a635b77012fb45b4d96c404a33fa04327c19674'
PATH = 'products/frontier-omega-alpha/research/archive_point/evidence/'
MODEL = 'qwen2.5-0.5b-q4_k_m'
REGISTRATION = 'ada2b9f9a12997d8968df53cc316ce81f730fc3b'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def artifact(data):
    return sha256(data).hexdigest()


def git_read(name, digest):
    raw = subprocess.check_output(['git','show',f'{PIN}:{PATH}{name}'], cwd=ROOT)
    if artifact(raw) != digest:
        raise ValueError('Archive receipt digest mismatch')
    return json.loads(raw)


def cases():
    first = git_read('confirmation.json', '5f2e47bb0f08b7efcfdf934683c1b9215d45c5b4e5c9f7795ea324ac250d5add')
    second = git_read('standalone-query.json', 'f4cf18462ebc49466f64c90fc7332186f7c1bf6bf9705663e5a066833daa4b0e')
    sources = [item[route]['source'] for item in first['receipt']['cases'] for route in ('candidate','reference')]
    sources.append(second['field']['source'])
    items = []
    for source in sources:
        start, end, length = map(int, re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', source['content_range']).groups())
        body = source['body_bytes']
        if source['http_status'] != 206 or not 0 <= start <= end < length or len(range(start,end + 1)) != body:
            raise ValueError('The arithmetic oracle disagrees with an observed historical response.')
        items.append({'start':start,'end':end,'length':length,'body':body})
    return items[:-1], items[-1]


def execute(directory, *args):
    start = perf_counter_ns()
    output = subprocess.run(['node',str(directory/'foundry-cli.mjs'),*map(str,args)],
                            check=False, capture_output=True)
    return {'returncode':output.returncode, 'output':output.stdout.decode(),
            'error':output.stderr.decode(), 'wall_ns':perf_counter_ns()-start}


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('companion', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--port', type=int, default=18479)
    ap.add_argument('--runtime-setup-ns', type=int)
    return ap


def main(args):
    directory = args.companion.resolve()
    sys.path.insert(0, str(directory))
    from bridge.adapters import BridgeError, Runtime, strict_json, transport

    def sender(url, headers, body=None, timeout=60):
        if body is not None:
            # Use the same deterministic decoding parameters for every research arm.
            body = {**body, 'temperature':0, 'seed':283, 'cache_prompt':False}
        return transport(url, headers, body, timeout)

    runtime = Runtime({'local_only':True,'max_attempts':1,'timeout_seconds':90,'providers':{
        'llama':{'kind':'openai','base_url':f'http://127.0.0.1:{args.port}/v1',
                 'output_limit_field':'max_tokens','models':{
                     MODEL:{'input_per_million':0,'output_per_million':0,'max_output_tokens':512,
                            'input_token_overhead':128,'context_window':4096}
                 }}
    }}, sender=sender)
    receipt = {
        'schema':'frontier/registered-foundry-trial-v1','registration':REGISTRATION,
        'classic_comparator':'Python integer arithmetic with counts bound to public NOAA receipts',
        's1_reference_source': PIN, 'seed':283,'temperature':0,'output_token_limit':512,
        'model':MODEL,'model_sha256':'74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db',
        'runtime':'llama.cpp b12242 CPU-only, four threads, 4096 context, parallel=1, prompt cache disabled',
        'runtime_setup_ns':args.runtime_setup_ns,
        'host':platform.platform(),'node':subprocess.check_output(['node','--version'], text=True).strip(),
        'discovery':runtime.discover('llama'),'beneficiary_acceptance':None,'complete_cost':None,
        'realized_economic_value':None,'comparative_advantage':'INSUFFICIENT EVIDENCE',
        'construction_attempts':{},
    }

    def request(label, prompt):
        started = perf_counter_ns()
        result = {}
        try:
            result = runtime.generate({'provider':'llama','model':MODEL,'prompt':prompt,
                                       'max_output_tokens':512,'run_id':label})
        except BridgeError as error:
            result = {'failure':error.code}
        finally:
            result['elapsed_ns'] = perf_counter_ns() - started
        result['prompt_sha256'] = artifact(prompt.encode())
        result['prompt'] = prompt
        receipt['construction_attempts'][label] = result
        return result

    example = json.loads((directory/'example.json').read_bytes())
    task = example['task']
    with TemporaryDirectory() as work:
        p = Path(work)

        def save(name, value):
            path = p/name
            path.write_bytes(encoded(value))
            return path

        def seal(label, contract, record):
            draft = p/(label + '-candidate.json')
            draft.write_text(record.get('text', ''), encoding='utf-8')
            result = execute(directory, 'seal', contract, draft)
            record['candidate_file_sha256'] = artifact(draft.read_bytes())
            record['seal'] = result
            return draft if not result['returncode'] else None

        def sheet(name, contract, rows):
            return save(name, {'schema':'frontier/foundry-cases-v1',
                               'mission_sha256':artifact(encoded(contract)),
                               'reference':'RFC 9110 and the public NOAA archive receipts '+PIN,'cases':rows})

        def compare(task_file, candidate_file, suite):
            result = execute(directory, 'check', task_file, candidate_file, suite)
            if result['output']:
                result['evidence'] = json.loads(result.pop('output'))
            return result

        s1_task = save('s1-mission.json', task)
        prompt = execute(directory, 'prompt', s1_task)['output']
        first = request('s1', prompt)
        s1 = seal('s1', s1_task, first)
        if not s1 and first.get('text'):
            repair = request('s1-syntax-repair', prompt + '\nOnly repair the output JSON structure. Previous reply:\n' + first['text'])
            s1 = seal('s1-syntax-repair', s1_task, repair)
        elif not s1:
            receipt['repair_unavailable'] = 'The provider returned no usable text to repair.'

        # Deliberate process boundary: the model cannot access these source records
        # during construction. Their contents are public and were not secretly held.
        historical, reference_reuse = cases()
        s1_rows = [{'input':{k:row[k] for k in ('start','end')},
                    'expected':{'bytes':row['body'],'ordered':True}} for row in historical]
        s1_rows += [{'input':{'start':7,'end':7},'expected':{'bytes':1,'ordered':True}},
                    {'input':{'start':8,'end':4},'expected':{'bytes':-3,'ordered':False}}]
        receipt['control_predecessor'] = {
            'historical_case_count':len(historical),
            'invalid_input_controls':['missing','out-of-domain','fraction'],
            'standalone_input_already_in_historical_suite':reference_reuse in historical,
        }
        start = perf_counter_ns()
        incumbent = [{'bytes':row['input']['end']-row['input']['start']+1,
                      'ordered':row['input']['start'] <= row['input']['end']} for row in s1_rows]
        receipt['python_s1'] = {'matched':sum(a == b['expected'] for a,b in zip(incumbent,s1_rows)),
                                'total':len(s1_rows),'kernel_ns':perf_counter_ns()-start,
                                'includes_setup_review_maintenance':False}
        qualification = sheet('s1-cases.json',task,s1_rows)
        retained = None
        if s1:
            receipt['s1_grade'] = compare(s1_task,s1,qualification)
            if receipt['s1_grade']['returncode'] == 0:
                reuse = [{'input':{k:reference_reuse[k] for k in ('start','end')},
                          'expected':{'bytes':reference_reuse['body'],'ordered':True}}]
                receipt['s1_replay_reuse'] = compare(s1_task,s1,sheet('s1-standalone.json',task,reuse))
                retained = execute(directory,'retain',s1_task,s1,qualification)
                receipt['s1_retained'] = json.loads(retained['output'])
                for name, data in [('missing',{'start':0}),('out-of-domain',{'start':0,'end':2_000_000_001}),
                                   ('fraction',{'start':0.5,'end':1})]:
                    result = execute(directory,'run',save('asset.json',receipt['s1_retained']),qualification,save('negative.json',data))
                    receipt['control_predecessor'].setdefault('candidate_invalid_input_results',{})[name] = result['returncode']
        else:
            receipt['s1_grade'] = {'status':'NO_VALID_CANDIDATE'}

        direct = request('direct-s1', 'For each start/end pair in order, output JSON only. Return an array of objects containing bytes (end - start + 1) and ordered (start <= end). Inputs: '
                         + json.dumps([row['input'] for row in s1_rows],separators=(',',':')))
        try:
            rows = strict_json(direct.get('text', ''))
            if not isinstance(rows,list):
                raise ValueError('expected array')
            receipt['direct_grade'] = {'matched':sum(type(a) is dict and a == b['expected'] for a,b in zip(rows,s1_rows)),
                                       'expected':len(s1_rows),'rows_returned':len(rows)}
        except (BridgeError, ValueError):
            receipt['direct_grade'] = {'status':'INVALID_OUTPUT','expected':len(s1_rows)}

        contract = {**task,'objective':'Check that the archived response length agrees with the partial byte window.',
                    'rule':'Return matches = start <= end and end < length and body == end - start + 1.',
                    'inputs':{k:task['inputs']['start'] for k in ('start','end','length','body')},
                    'outputs':{'matches':'boolean'},
                    'acceptance':'Every original and malformed byte window agrees with the Python/RFC reference.'}
        s2_task = save('s2-mission.json',contract)
        prompt = execute(directory,'prompt',s2_task)['output']
        arms = [('s2-ordinary-reuse', 'S1 knowledge: inputs start, end. bytes = end - start + 1. ordered = start <= end. Outputs bytes (integer) and ordered (boolean). Example: start 5 end 7 gives bytes 3 and ordered true.')]
        if retained:
            arms.append(('s2-retained', 'S1 format and executable: ' + encoded(receipt['s1_retained']['asset']['candidate']).decode() +
                         '. Example: start 5 end 7 gives bytes 3 and ordered true.'))
        else:
            receipt['s2-retained'] = {'status':'NO_QUALIFIED_S1'}
        second_candidates = [(name, seal(name,s2_task,request(name,prompt + '\n' + knowledge))) for name,knowledge in arms]
        negatives = [{**row,'body':row['body']-1} for row in historical]
        invalid = [{'start':2,'end':5,'length':5,'body':4},{'start':3,'end':2,'length':4,'body':0}]
        start = perf_counter_ns()
        s2_rows = [{'input':row,'expected':{'matches':row['start'] <= row['end'] < row['length'] and
                             len(range(row['start'],row['end']+1)) == row['body']}} for row in historical + negatives + invalid]
        receipt['python_s2'] = {'total':len(s2_rows),'kernel_ns':perf_counter_ns()-start}
        second_cases = sheet('s2-cases.json',contract,s2_rows)
        for name, draft in second_candidates:
            receipt[name] = compare(s2_task,draft,second_cases) if draft else {'status':'NO_VALID_CANDIDATE'}
    args.output.write_bytes(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True).encode()+b'\n')


if __name__ == '__main__':
    main(parser().parse_args())
