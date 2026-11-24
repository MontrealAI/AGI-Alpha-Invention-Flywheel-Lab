"""P0-260 isolated cache regression; synthetic context, no account or keys."""
import copy, hashlib, json, os, sys, tempfile, time, types, resource
from pathlib import Path

SOURCE = Path(__file__).with_name('owner_function.py').read_text()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())

def candidate(source):
    edits = [
        ("    cache_key = digest(", "    context = validated_execution_context(root)\n    cache_key = digest("),
        ("'verifier_files': body['verifier_files']})", "'verifier_files': body['verifier_files'], 'execution_context': context})"),
        ("    if len(_HISTORICAL_AUDITS) >= 128:", "    if validated_execution_context(root) != context:\n        raise ValueError('EXECUTION_CONTEXT_CHANGED_DURING_AUDIT')\n    if len(_HISTORICAL_AUDITS) >= 128:"),
    ]
    for old, new in edits:
        if source.count(old) != 1:
            raise ValueError('NONUNIQUE_PATCH_ANCHOR')
        source = source.replace(old, new, 1)
    return source

class Fixture:
    def __init__(self, root, repaired):
        self.root = root
        self.context = {'closure': 'A', 'launcher': 'isolated', 'store': 'S1'}
        self.expected = copy.deepcopy(self.context)
        self.calls = 0
        self.reject = False
        self.mutate = False
        self.cache = {}
        self.inventory = {'finance.py': 'synthetic'}
        self.ticket = {'historical_root': str(root), 'verifier_files': self.inventory,
                       'from_source': {'sha256': 'synthetic'}, 'prior_record': {}}
        def validate(root):
            if self.context != self.expected:
                raise ValueError('UNAUTHORIZED_EXECUTION_CONTEXT')
            return copy.deepcopy(self.context)
        def run(*args, **kwargs):
            self.calls += 1
            if self.mutate:
                self.context['closure'] = 'MUTATED'
                self.expected = copy.deepcopy(self.context)
            return types.SimpleNamespace(returncode=int(self.reject), stderr='synthetic rejection',
                stdout=json.dumps({'accepted': True, 'child_call': self.calls}))
        g = dict(copy=copy, Path=Path, ticket_body=lambda t: t, source_inventory=lambda root: self.inventory,
                 digest=digest, _HISTORICAL_AUDITS=self.cache, current_store_directory=lambda: self.context['store'],
                 os=os, sys=sys, json=json, subprocess=types.SimpleNamespace(run=run),
                 validated_execution_context=validate)
        exec(compile(candidate(SOURCE) if repaired else SOURCE, '<fixture>', 'exec'), g)
        self.verify = g['verify_historical']
    def audit(self):
        return self.verify(self.ticket, {})

def rejects(f, prefix):
    try:
        f()
    except ValueError as exc:
        return str(exc).startswith(prefix)
    return False

def cases(root):
    def original_same():
        f=Fixture(root,False); a=f.audit(); b=f.audit(); return a==b and f.calls==1
    def original_stale():
        f=Fixture(root,False); a=f.audit(); f.context['closure']='B'; f.reject=True
        return f.audit()==a and f.calls==1
    def candidate_refuse():
        f=Fixture(root,True); f.audit(); f.context['closure']='B'; f.reject=True
        return rejects(f.audit,'UNAUTHORIZED_EXECUTION_CONTEXT') and f.calls==1
    def candidate_same():
        f=Fixture(root,True); a=f.audit(); b=f.audit(); return a==b and f.calls==1
    def candidate_new():
        # Three distinct context dimensions must independently partition reuse.
        for key, value in [('closure','B'),('launcher','new-policy'),('store','S2')]:
            f=Fixture(root,True); f.audit(); f.context[key]=value; f.expected=copy.deepcopy(f.context); f.reject=True
            if not (rejects(f.audit,'PINNED_HISTORICAL_AUDIT_FAILED') and f.calls==2): return False
        return True
    def candidate_midchild():
        f=Fixture(root,True); f.mutate=True
        return rejects(f.audit,'EXECUTION_CONTEXT_CHANGED_DURING_AUDIT') and f.calls==1 and not f.cache
    return [original_same,original_stale,candidate_refuse,candidate_same,candidate_new,candidate_midchild]

def main():
    start=time.perf_counter(); cpu=time.process_time()
    commercial=types.ModuleType('commercial'); ledger=types.ModuleType('commercial.ledger'); ledger.load_jobs=lambda *a: None
    sys.modules['commercial']=commercial; sys.modules['commercial.ledger']=ledger
    results=[]
    with tempfile.TemporaryDirectory() as path:
        for case in cases(Path(path)):
            try: results.append({'case':case.__name__,'pass':bool(case())})
            except Exception as exc: results.append({'case':case.__name__,'pass':False,'error':repr(exc)})
    report={'cases':results,'source_sha256':sha(SOURCE.encode()),'probe_sha256':sha(Path(__file__).read_bytes()),
            'candidate_sha256':sha(candidate(SOURCE).encode()),'cpu_seconds':time.process_time()-cpu,
            'wall_seconds':time.perf_counter()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'scope':'stubbed cache behavior only; no actual signer, account or historical child execution',
            'actual_billing':None}
    print(json.dumps(report,indent=2,sort_keys=True))
    return int(not all(r['pass'] for r in results))

if __name__=='__main__':
    raise SystemExit(main())
