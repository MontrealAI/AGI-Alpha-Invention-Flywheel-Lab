import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile


root = Path(__file__).resolve().parent
arm = sys.argv[1]
assert arm in {'baseline', 'candidate'}
sys.path.insert(0, str(root / ('workshop-' + arm)))
from bridge import workshop
from bridge.workflows import WorkflowService


class LocalProtocolFixture:
    def __init__(self, formulas):
        self.formulas = iter(formulas)
        self.prompts = []

    def status(self):
        return {'providers': [{'id': 'fixture', 'ready': True, 'models': ['author'], 'local': True}]}

    def generate(self, request):
        self.prompts.append(request['prompt'])
        candidate = {'inputs': ['x'], 'bindings': {}, 'outputs': {'result': next(self.formulas)},
                     'summary': 'Deterministically authored response for the transport-independent regression.'}
        return {'text': json.dumps(candidate), 'model': 'author', 'reported_model': 'author',
                'qualification': 'AUTHORED_FIXTURE'}

    def redact(self, text):
        return text


def request(mark, values, labels, context, prior=None):
    data = {'request_id': mark * 32, 'family': 'custom', 'objective': 'Qualify a shipping arithmetic instrument',
            'provider': 'fixture', 'model': 'author', 'consent': 'local', 'context': context,
            'cases': [{'input': {'x': x}, 'expected': {'result': y}} for x, y in zip(values, labels)]}
    if prior:
        data.update(inherit=prior, loop='successor')
    return data


def trial(formula, labels, context):
    hidden_input = 99971
    values = [14, 16, hidden_input]
    runtime = LocalProtocolFixture(['2 * x', formula])
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        service = WorkflowService(runtime, folder / 'workspace')
        try:
            first = workshop.register(service, request('1', [1, 2, 3], [2, 4, 6], 'Return result = 2 times x.'))
            predecessor = service.step(first['id'])
            assert predecessor['status'] == 'complete'
            sha = predecessor['artifacts']['instrument.json']['sha256']
            second = workshop.register(service, request('2', values, labels, context, first['id']))
            successor = service.step(second['id'])
            assert len(runtime.prompts) == 2 and str(hidden_input) not in runtime.prompts[1]
            assert str(labels[-1]) not in runtime.prompts[1]
            events = successor['events']
            check_stages = [item['detail']['stage'] for item in events if item['kind'] == 'verification']
            assert check_stages[-1] == 'final'
            assert sum(item['kind'] == 'model_completed' for item in events) == 1
            replay = None
            if successor['status'] == 'complete':
                snap = workshop.operate(service, 'get', {'run_id': second['id']})
                zip_bytes = workshop.bundle(service, {'run_id': second['id'], 'revision': snap['revision']})
                portable = folder / 'isolated-export'
                with ZipFile(io.BytesIO(zip_bytes)) as bundle:
                    instrument = bundle.read('instrument.json')
                    bundle.extractall(portable)
                assert hashlib.sha256(instrument).hexdigest() == successor['artifacts']['instrument.json']['sha256']
                replay = subprocess.run([sys.executable, '-B', 'RUN_WORKSHOP.py', 'check'],
                                        cwd=portable, capture_output=True, check=True).returncode
            return {'status': successor['status'], 'same_predecessor_bytes': successor['artifacts']['instrument.json']['sha256'] == sha,
                    'rewrite_refused': any(item['kind'] == 'inherited_rewrite_refused' for item in events),
                    'fixture_model_completions': 1, 'final_frozen_checks': check_stages[-1] == 'final',
                    'hidden_input_or_expected_in_model_prompt': False, 'portable_exit': replay}
        finally:
            service.close()


results = {
    'redundant_rewrite': trial('x + x', [28, 32, 199942], 'Return result = 2 times x.'),
    'necessary_adaptation': trial('3 * x', [42, 48, 299913], 'Return result = 3 times x.'),
    'initial_pass_held_failure': trial('choose(x < 1000, 2 * x, 3 * x)', [28, 32, 299913],
                                       'Return result = 2 times x.'),
    'changed_contract_initial_tie': trial('choose(x < 1000, 2 * x, 3 * x)', [28, 32, 299913],
                                       'Return result = 2 times x below 1000 and 3 times x at or above 1000.'),
}
assert results['necessary_adaptation']['status'] == 'complete' and not results['necessary_adaptation']['same_predecessor_bytes']
assert results['redundant_rewrite']['status'] == 'complete'
assert results['redundant_rewrite']['same_predecessor_bytes'] == (arm == 'candidate')
assert results['redundant_rewrite']['rewrite_refused'] == (arm == 'candidate')
assert results['initial_pass_held_failure']['status'] == ('needs_review' if arm == 'candidate' else 'complete')
assert results['changed_contract_initial_tie']['status'] == 'complete'
assert not results['changed_contract_initial_tie']['same_predecessor_bytes']
path = root / ('WORKSHOP-REUSE-' + arm.upper() + '.json')
path.write_text(json.dumps({'fixture_scope': 'Independent synthetic custom cases with scripted model responses',
                           'cases': results}, indent=2, sort_keys=True) + '\n')
print(path.name, hashlib.sha256(path.read_bytes()).hexdigest())
