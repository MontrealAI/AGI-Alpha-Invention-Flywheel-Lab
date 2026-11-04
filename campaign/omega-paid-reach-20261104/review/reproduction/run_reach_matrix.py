"""Register and operate only the ten preregistered source-qualified native accounts."""
import argparse, concurrent.futures, hashlib, json, os, pathlib, subprocess, sys, time

P = pathlib.Path
ARMS = ('organic', 'pilot')
SCENARIOS = ('central', 'weak', 'copycat', 'no_demand', 'failed_activation')
PROTOCOL = '2b6eef4a9535f6f626e2ca88fcc432c672f1b9cc45ec5bef868e3378d38f5277'
def hx(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, obj):
    t = p.with_suffix('.part')
    t.write_text(json.dumps(obj, sort_keys=True, indent=2)+'\n')
    t.replace(p)
def main():
    a=argparse.ArgumentParser()
    for name in ('source','output','gate'): a.add_argument('--'+name, type=P, required=True)
    o=a.parse_args(); source=o.source.resolve(); out=o.output.resolve(); gate=json.loads(o.gate.read_text())
    if not gate.get('accepted') or gate.get('errors')!=0 or gate.get('failures')!=0 or gate.get('skipped')!=0:
        raise SystemExit('FROZEN_PASSING_GATE_REQUIRED')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
    if sha!=gate['source_commit'] or hx(source/'campaign/omega-paid-reach-20261104/PROTOCOL.md')!=PROTOCOL:
        raise SystemExit('FROZEN_SOURCE_OR_PROTOCOL_MISMATCH')
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=source,text=True).strip():
        raise SystemExit('TRACKED_SOURCE_CHANGED')
    out.mkdir(parents=True,exist_ok=True); logs=out/'_qualification'; logs.mkdir(exist_ok=True)
    reg={'source_commit':sha,'gate_sha256':hx(o.gate),'protocol_sha256':PROTOCOL,'arms':ARMS,'scenarios':SCENARIOS}
    regpath=logs/'REGISTRATION.json'
    if regpath.exists() and json.loads(regpath.read_text())!=json.loads(json.dumps(reg)): raise SystemExit('MATRIX_BINDING_CHANGED')
    if not regpath.exists(): write(regpath,reg)
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    def case(cell):
        scenario,arm=cell; acct=out/scenario/arm; acct.parent.mkdir(exist_ok=True)
        label=scenario+'-'+arm; stage=logs/label; stage.mkdir(exist_ok=True)
        prior=stage/'RESULT.json'
        # Preserve completed cases. A separate repeat must pass audit/live resume on the same authority.
        attempt=len(list(stage.glob('attempt-*')))+1; d=stage/f'attempt-{attempt}'; d.mkdir()
        existed=acct.exists(); rows=[]
        sides=('.actions.jsonl','.adaptive-simulation-key','.connected-journal.json','.adaptive-account.json','.adaptive-proofs.json','.adaptive-resolutions.json')
        def authority():
            return {s:hx(acct/('account.sqlite'+s)) if (acct/('account.sqlite'+s)).is_file() else None for s in sides}
        def command(op):
            cmd=[sys.executable,'-m','mechanism_harness.reach_native',op,str(acct),'--arm',arm,'--scenario',scenario]
            log=d/f'{len(rows)+1}-{op}.log'; started=time.monotonic()
            with log.open('xb') as f: result=subprocess.run(cmd,cwd=source,env=env,stdout=f,stderr=subprocess.STDOUT)
            row={'stage':op,'returncode':result.returncode,'elapsed_seconds':time.monotonic()-started,'log_sha256':hx(log)}
            rows.append(row); write(d/'PROGRESS.json',{'source_commit':sha,'rows':rows})
            if result.returncode: raise RuntimeError('NONZERO_'+op)
        start=time.monotonic(); rec={'source_commit':sha,'arm':arm,'scenario':scenario,'started_existing':existed,'attempt':attempt,'accepted':False}
        try:
            command('resume' if existed else 'run')
            before=hx(acct/'NATIVE_EXPORT.json'); auth=authority()
            if not all(auth[s] for s in sides[:4]): raise RuntimeError('MISSING_AUTHORITY')
            command('audit'); command('resume')
            if hx(acct/'NATIVE_EXPORT.json')!=before or authority()!=auth: raise RuntimeError('LIVE_RECOVERY_CHANGED_AUTHORITY_OR_EXPORT')
            report=json.loads((acct/'REPORT.json').read_text())
            if report.get('actual_revenue_usd')!=0 or report.get('opening_microUSD')!=100000000000: raise RuntimeError('INVALID_FINANCIAL_SCOPE')
            rec.update(accepted=True,native_export_sha256=before,report_sha256=hx(acct/'REPORT.json'),resume_unchanged=True)
        except BaseException as e: rec['error']=f'{type(e).__name__}: {e}'
        rec['commands']=rows;rec['elapsed_seconds']=time.monotonic()-start
        write(d/'RESULT.json',rec);write(prior,rec)
        print(json.dumps({k:rec.get(k) for k in ('scenario','arm','accepted','attempt','elapsed_seconds','error')}),flush=True)
        return rec
    cells=[(s,a) for s in SCENARIOS for a in ARMS]
    # Four separate, single-threaded accounts on the eight-core worker. This is
    # execution concurrency only; it changes no buyer, contract or account.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: results=list(ex.map(case,cells))
    clean=not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=source,text=True).strip()
    record={'source_commit':sha,'independent_accounts':len(results),'accepted':all(r['accepted'] for r in results) and clean,'source_unchanged':clean,'cases':results}
    write(logs/'MATRIX.json',record)
    return 0 if record['accepted'] else 1
if __name__=='__main__': sys.exit(main())
