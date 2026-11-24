"""P0-268: diagnostic only; no new caching, no original account access."""
import ast
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

PROBE_BLOB = 'd1dfcf29fd7f602480ed0d273f241f9c5b631229'
METHOD = 'test_forward_engine_only_upgrade_preserves_prior_transition_and_same_business'
TRACE = r'''
import contextlib as _t_context, hashlib as _t_hash, hmac as _t_hmac
import json as _t_json, os as _t_os, time as _t_time
from pathlib import Path as _t_Path

def _t_emit(row):
    path = _t_os.environ.get('P0262_TRACE')
    if not path:
        return
    raw = (_t_json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode()
    fd = _t_os.open(path+'.spans',_t_os.O_WRONLY|_t_os.O_CREAT|_t_os.O_APPEND,0o600)
    try:
        if _t_os.write(fd,raw)!=len(raw):
            raise OSError('P0268_SHORT_TRACE_WRITE')
    finally:
        _t_os.close(fd)

@_t_context.contextmanager
def _t_span(phase, payload=None):
    trace = _t_os.environ.get('P0262_TRACE')
    if not trace:
        yield
        return
    salt = _t_Path(trace+'.salt').read_bytes()
    def token(raw):
        return _t_hmac.new(salt,raw,_t_hash.sha256).hexdigest()
    proc=token(('proc:'+str(_t_os.getpid())).encode())
    parent=token(('proc:'+str(_t_os.getppid())).encode())
    start=_t_time.monotonic_ns()
    ident=token(('span:'+proc+':'+str(start)+':'+phase).encode())
    common={'id':ident,'proc':proc,'parent':parent,'phase':phase}
    if payload is not None:
        common['request']=token(b'audit-input:'+payload.encode())
    _t_emit(dict(common,event='start',ns=start))
    ok=False
    try:
        yield
        ok=True
    finally:
        _t_emit(dict(common,event='end',ns=_t_time.monotonic_ns(),returned=ok))
'''

# AST wrapping keeps code-string literals byte-identical; do not indent
# multi-line string source mechanically or alter historical audit programs.
TOP = {'source_inventory':'source_inventory','_p0262_inventory':'inventory',
       '_p0262_launch':'launch_total','_p0263_context':'leaf_context',
       'verify_historical':'verify_historical','authorize_upgrade':'authorize',
       'verify_original':'post_launch_source_check'}
BOOT = {'_g_inventory':'inventory','_g_run':'descendant_total',
        'verify':'descendant_closure_check'}

def span(phase, body, payload=None):
    args=[ast.Constant(phase)]
    if payload is not None:
        args.append(ast.parse(payload,mode='eval').body)
    return ast.With(items=[ast.withitem(context_expr=ast.Call(
        func=ast.Name(id='_t_span',ctx=ast.Load()),args=args,keywords=[]))],
        body=body)

class Instrument(ast.NodeTransformer):
    def __init__(self, phases):
        self.phases=phases
        self.stack=[]
        self.counts=Counter()

    def visit_FunctionDef(self,node):
        self.stack.append(node.name)
        node=self.generic_visit(node)
        self.stack.pop()
        if node.name in self.phases:
            offset=int(bool(node.body and isinstance(node.body[0],ast.Expr)
                and isinstance(node.body[0].value,ast.Constant)
                and isinstance(node.body[0].value.value,str)))
            phase=self.phases[node.name]
            node.body=node.body[:offset]+[span(phase,node.body[offset:])]
            self.counts[phase]+=1
        return node

    def statement(self,node):
        node=self.generic_visit(node)
        if not self.stack:
            return node
        name=self.stack[-1]
        value=getattr(node,'value',None)
        if not isinstance(value,ast.Call):
            return node
        f=value.func
        phase=None; payload=None
        if (name=='_p0262_launch' and isinstance(f,ast.Attribute)
                and isinstance(f.value,ast.Name) and f.value.id=='subprocess' and f.attr=='run'):
            phase='child_wait'
            payload="json.dumps(payload) if kind=='audit' else None"
        if name=='_g_run' and isinstance(f,ast.Name) and f.id=='_g_real_run':
            phase='child_wait'
            payload="kw.get('input') if name=='verify_historical' or caller.f_locals.get('kind')=='audit' else None"
        if name=='verify_historical' and isinstance(f,ast.Name) and f.id in {'load_jobs','ticket_body'}:
            phase=f.id
        if phase:
            self.counts[phase]+=1
            return span(phase,[node],payload)
        return node

    visit_Assign=statement
    visit_Expr=statement
    visit_Return=statement

def transform(source, phases):
    tree=ast.parse(source)
    worker=Instrument(phases)
    tree=worker.visit(tree)
    # Keep module docstring and future imports at the beginning.
    offset=int(bool(tree.body and isinstance(tree.body[0],ast.Expr)
        and isinstance(tree.body[0].value,ast.Constant)
        and isinstance(tree.body[0].value.value,str)))
    while offset<len(tree.body) and isinstance(tree.body[offset],ast.ImportFrom) and tree.body[offset].module=='__future__':
        offset+=1
    tree.body[offset:offset]=ast.parse(TRACE).body
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)+'\n',dict(worker.counts)

def instrument(patch):
    tree=ast.parse(patch)
    candidates=[n for n in tree.body if isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Name) and t.id=='_P0267_BOOT' for t in n.targets)]
    if len(candidates)!=1:
        raise ValueError('P0268_BOOT_ANCHOR')
    node=candidates[0]
    boot=ast.literal_eval(node.value)
    child,boot_counts=transform(boot,BOOT)
    child+="\nwith _t_span('boot_observed'):\n    pass\n"
    node.value=ast.Constant(child)
    ast.fix_missing_locations(tree)
    patched,counts=transform(ast.unparse(tree),TOP)
    if counts.get('child_wait')!=1 or boot_counts.get('child_wait')!=2:
        raise ValueError('P0268_WAIT_ANCHOR')
    if counts.get('ticket_body')!=1 or counts.get('load_jobs')!=2:
        raise ValueError('P0268_VERIFY_ANCHOR')
    if not all(counts.get(p)==1 for p in TOP.values()) or not all(boot_counts.get(p)==1 for p in BOOT.values()):
        raise ValueError('P0268_PHASE_ANCHOR')
    compile(patched,'<instrumented>','exec')
    compile(child,'<instrumented-boot>','exec')
    return patched.encode(),counts,boot_counts

def summarize(path):
    start={}; end={}; malformed=0
    if not path.exists():
        return {'usable':False,'reason':'NO_TRACE'}
    for line in path.read_bytes().splitlines():
        try:
            row=json.loads(line)
            target=start if row['event']=='start' else end if row['event']=='end' else None
            if target is None or row['id'] in target:
                raise ValueError()
            target[row['id']]=row
        except (ValueError,KeyError,TypeError):
            malformed+=1
    completed=[]; invalid=0
    for ident,a in start.items():
        b=end.get(ident)
        if b is None:
            continue
        if b['ns']<a['ns'] or any(a.get(k)!=b.get(k) for k in ('proc','parent','phase','request')):
            invalid+=1
            continue
        completed.append((a,b))
    phases=defaultdict(lambda: {'count':0,'returned':0,'inclusive_ns':0})
    for a,b in completed:
        p=phases[a['phase']]
        p['count']+=1; p['returned']+=int(b['returned']);p['inclusive_ns']+=b['ns']-a['ns']
    waits=[(a,b) for a,b in completed if a['phase']=='child_wait']
    request_counts=Counter(a['request'] for a in start.values()
        if a['phase']=='child_wait' and 'request' in a)
    boots=[a for a in start.values() if a['phase']=='boot_observed']
    # Patched descendant mediation calls _g_real_run from inside _p0262_launch.
    # Nested same-process wait spans can refer to the same physical child.
    # Retain ambiguity explicitly, rather than manufacturing a physical edge.
    all_waits=[(a,end.get(a['id'])) for a in start.values() if a['phase']=='child_wait']
    edges=0; ambiguous=0; missing=0; innermost_requests=Counter()
    for boot in boots:
        candidates=[(a,b) for a,b in all_waits if a['proc']==boot['parent']
                    and a['ns']<=boot['ns'] and (b is None or boot['ns']<=b['ns'])]
        if len(candidates)==1:
            edges+=1
        elif len(candidates)>1:
            ambiguous+=1
        else:
            missing+=1
        if candidates:
            # One observed boot is one process observation, not every nested span.
            nearest=max(candidates,key=lambda pair:pair[0]['ns'])[0]
            if 'request' in nearest:
                innermost_requests[nearest['request']]+=1
    return {'usable':bool(waits and boots and not malformed and not invalid and not (set(end)-set(start))),
        'spans_started':len(start),'spans_completed':len(completed),
        'unclosed_spans':len(set(start)-set(end)),'orphan_end':len(set(end)-set(start)),
        'malformed_rows':malformed,'invalid_pairs':invalid,
        'phase_totals':dict(phases),'distinct_exact_audit_input_digests':len(request_counts),
        'audit_input_wait_spans':sum(request_counts.values()),
        'repeated_exact_input_wait_spans':sum(n-1 for n in request_counts.values()),
        'observed_boots_with_correlated_audit_input':sum(innermost_requests.values()),
        'distinct_correlated_boot_input_digests':len(innermost_requests),
        'repeated_correlated_boot_inputs':sum(n-1 for n in innermost_requests.values()),
        'isolated_boot_spans':len(boots),'single_parent_wait_matches':edges,
        'ambiguous_parent_wait_matches':ambiguous,'missing_parent_wait_matches':missing,
        'interpretation':'Inclusive timings overlap across phases and processes; duplicate spans are not distinct physical launches. Exact input repetition is not cache eligibility. Unclosed spans are censored, not zero time.'}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    owner,prior,deps,probe_path,out=map(lambda x:Path(x).resolve(),sys.argv[1:6])
    t=time.monotonic();cpu0=resource.getrusage(resource.RUSAGE_CHILDREN)
    result={'native_accepted':False,'diagnostic_usable':False,'actual_commerce':False,
        'original_account_accessed':False,'whole_episode_billing_usd':None,
        'method':METHOD,'probe_sha256':sha(Path(__file__).read_bytes())}
    try:
        data=probe_path.read_bytes()
        blob=hashlib.sha1(('blob '+str(len(data))+'\0').encode()+data).hexdigest()
        if blob!=PROBE_BLOB:
            raise ValueError('P0268_PRIOR_PROBE_CHANGED')
        spec=importlib.util.spec_from_file_location('p0267',probe_path)
        prior_probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior_probe)
        if prior_probe.head(owner)!=prior_probe.OWNER or prior_probe.head(prior)!=prior_probe.PRIOR:
            raise ValueError('P0268_PINNED_HEAD_CHANGED')
        test=owner/'tests/test_connected_operating_upgrade.py'
        original_test=sha(test.read_bytes())
        baseline,gates=prior_probe.build(owner,prior)
        checks=prior_probe.context_checks(baseline)
        if not all(checks.values()) or not all(x['accepted'] for x in gates):
            raise ValueError('P0268_BASELINE_STATIC_GATE')
        patch,counts,boot_counts=instrument(baseline)
        result.update(owner_commit=prior_probe.OWNER,prior_commit=prior_probe.PRIOR,
            baseline_patch_sha256=sha(baseline),instrumented_patch_sha256=sha(patch),
            owner_test_sha256=original_test,baseline_static_gates=gates,baseline_context_checks=checks,
            instrumented_anchors=counts,descendant_anchors=boot_counts)
        target=owner/'connected_enterprise/upgrades.py'
        target.write_bytes(patch)
        private=out.parent/'p0268-private';private.mkdir(mode=0o700)
        case=private/'case';case.mkdir(mode=0o700)
        trace=case/'launches.txt'
        salt=Path(str(trace)+'.salt')
        fd=os.open(salt,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(os.urandom(32))
        dm=private/'deps.json'
        dm.write_text(json.dumps(prior_probe.inventory(deps),sort_keys=True,separators=(',',':')))
        result['dependency_manifest_sha256']=sha(dm.read_bytes())
        env={'PATH':os.defpath,'HOME':str(private),'TMPDIR':str(case),'PYTHONDONTWRITEBYTECODE':'1',
            'PYTHONPATH':str(owner),'P0262_DEPS':str(deps),'P0262_DEP_MANIFEST':str(dm),
            'P0262_DEP_MANIFEST_SHA':result['dependency_manifest_sha256'],'P0262_TRACE':str(trace)}
        log=case/'private.log'
        with log.open('wb') as stream:
            done=subprocess.run([sys.executable,'-B','-m','unittest','-v',
                'tests.test_connected_operating_upgrade.OperatingUpgradeTests.'+METHOD],
                cwd=owner,env=env,stdout=stream,stderr=subprocess.STDOUT)
        result['native_exit']=done.returncode
        raw=log.read_bytes()
        result['private_log_sha256']=sha(raw)
        result['diagnostic_markers']=[m for m in ['TimeoutExpired','AssertionError','P0268_',
            'P0267_','P0263_','P0262_','NameError','ImportError','FileNotFoundError'] if m.encode() in raw]
        result['owner_test_unchanged']=sha(test.read_bytes())==original_test
        result['instrumented_source_unchanged']=target.read_bytes()==patch
        result['native_accepted']=bool(done.returncode==0 and result['owner_test_unchanged']
            and result['instrumented_source_unchanged'])
        result['trace']=summarize(Path(str(trace)+'.spans'))
        result['diagnostic_usable']=bool(result['trace']['usable'] and result['owner_test_unchanged']
            and result['instrumented_source_unchanged'])
        result['legacy_launch_counts']=dict(Counter(trace.read_text().splitlines())) if trace.exists() else {}
        # Trace keys, raw spans, account data and log contents never enter the receipt.
    except Exception as e:
        result['failure_type']=type(e).__name__
        result['failure_code']=str(e) if str(e).startswith('P0268_') else 'PRIVATE_DIAGNOSTIC'
    finally:
        cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
        result['waited_child_cpu_seconds']=cpu.ru_utime+cpu.ru_stime-cpu0.ru_utime-cpu0.ru_stime
        result['wall_seconds']=time.monotonic()-t
        out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    # Keep the native failure visible even when diagnostic telemetry is usable.
    return 0 if result['native_accepted'] and result['diagnostic_usable'] else 1

if __name__=='__main__':
    raise SystemExit(main())
