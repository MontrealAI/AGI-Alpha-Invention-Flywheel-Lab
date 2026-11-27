"""Test-only call-order witness, not a native account or full audit bypass."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
from unittest.mock import patch

# Exact function extracted from pinned public runner blob 02aebd24b9c1dc1e2d4bea40f387acbf1312829e.
SOURCE = "def comparison(output,control=None,candidate=None):\n    output=Path(output).resolve();f=read_freeze(output)\n    control=control or f['protocol']['control_arm'];candidate=candidate or f['protocol']['candidate_arm']\n    if control==candidate or control not in f['protocol']['arms'] or candidate not in f['protocol']['arms']:\n        raise ValueError('DISTINCT_REGISTERED_COMPARISON_ARMS_REQUIRED')\n    checked=audit_output(output)\n    if not checked['accepted']:raise ValueError('ACCEPTED_NATIVE_AND_OPERATING_AUDIT_REQUIRED')\n    from .scale import compare\n    results=[json.loads((output/'worlds'/task['id']/'RESULT.json').read_text()) for task in tasks(f['protocol']) if task['arm'] in {control,candidate}]\n    result=compare(results,baseline=control,candidate=candidate)\n    result.update(source_sha256=f['source']['sha256'],frozen_sha256=f['sha256'],audit=checked,\n                  evidence_role=f['protocol'].get('evidence_role','reproduction'),funding_authority=False)\n    return result\n"

def reference(output, control=None, candidate=None):
    f = read_freeze(output)
    control = control or f['protocol']['control_arm']
    candidate = candidate or f['protocol']['candidate_arm']
    checked, results = audit_snapshot(output)
    if not checked['accepted']:
        raise ValueError('ACCEPTED_NATIVE_AND_OPERATING_AUDIT_REQUIRED')
    from .scale import compare
    result = compare([row for row in results if row['arm'] in {control, candidate}],
                     baseline=control, candidate=candidate)
    result.update(audit=checked, funding_authority=False)
    return result

def run(route, case):
    calls = []
    names = ['baseline', 'growth']
    task_rows = [{'id': n, 'arm': n} for n in names]
    f = {'protocol': {'control_arm': 'baseline', 'candidate_arm': 'growth',
                      'arms': names}, 'source': {'sha256': 'synthetic'}, 'sha256': 'synthetic'}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for n in names:
            p = root / 'worlds' / n / 'RESULT.json'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'arm': n, 'marker': 1}))
        def snapshot(output):
            rows = [json.loads((output/'worlds'/n/'RESULT.json').read_text()) for n in names]
            if case == 'changed_after_audit':
                (output/'worlds'/'growth'/'RESULT.json').write_text(json.dumps({'arm':'growth','marker':2}))
            return {'accepted': case != 'refused'}, rows
        def compare(rows, **kwargs):
            calls.append(copy.deepcopy(rows))
            return {'marker': next(x['marker'] for x in rows if x['arm']=='growth')}
        scale = types.ModuleType('connected_enterprise.scale')
        scale.compare = compare
        pkg = types.ModuleType('connected_enterprise')
        pkg.__path__ = []
        namespace = dict(globals(), __package__='connected_enterprise',
                         read_freeze=lambda _: f, tasks=lambda _: task_rows,
                         audit_output=lambda p: snapshot(p)[0], audit_snapshot=snapshot)
        exec(compile(SOURCE if route=='pinned' else
                     __import__('inspect').getsource(reference), '<review>', 'exec'), namespace)
        with patch.dict(sys.modules, {'connected_enterprise':pkg,'connected_enterprise.scale':scale}):
            try:
                result = namespace['comparison' if route=='pinned' else 'reference'](root)
                row = {'route':route,'case':case,'marker':result['marker'],
                       'accepted':result['audit']['accepted'],'calls':len(calls)}
            except ValueError as e:
                row = {'route':route,'case':case,'error':str(e),'calls':len(calls)}
        if case == 'refused':
            assert row['error']=='ACCEPTED_NATIVE_AND_OPERATING_AUDIT_REQUIRED' and row['calls']==0
        else:
            expected = 2 if route=='pinned' and case=='changed_after_audit' else 1
            assert row['marker']==expected and row['accepted'] is True and row['calls']==1
        return row

if __name__ == '__main__':
    start, cpu = time.perf_counter(), time.process_time()
    rows = [run(route, case) for route in ('pinned','reference')
            for case in ('unchanged','refused','changed_after_audit')]
    print(json.dumps({'source_function_sha256': hashlib.sha256(SOURCE.encode()).hexdigest(),
                      'rows':rows,'local_cpu_seconds':time.process_time()-cpu,
                      'local_wall_seconds':time.perf_counter()-start},sort_keys=True,indent=2))
