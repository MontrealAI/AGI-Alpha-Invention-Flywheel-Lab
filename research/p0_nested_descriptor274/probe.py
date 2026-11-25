"""Descriptor-bound fresh native historical replay development instrument; no fixture export."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

BOOTSTRAP = "import os,json,stat,subprocess,sys,importlib.util,hashlib\nfrom pathlib import Path\nimport fcntl\ndef observe(event, **values):\n    row=json.dumps(dict(event=event,**values),sort_keys=True)+'\\n'\n    trace=os.open(os.environ['P0274_TRACE'],os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW)\n    try: os.write(trace,row.encode())\n    finally: os.close(trace)\ndef blob(path):\n    raw=path.read_bytes()\n    return hashlib.sha1((\"blob \"+str(len(raw))+\"\\0\").encode()+raw).hexdigest()\ndef install_bound_replay(fd, route, expected, bootstrap):\n    def ident(d):\n        s=os.fstat(d)\n        if not stat.S_ISDIR(s.st_mode): raise ValueError(\"P0273_DIRECTORY_CAPABILITY_REQUIRED\")\n        return (s.st_dev,s.st_ino)\n    if ident(fd)!=tuple(expected): raise ValueError(\"P0273_CAPABILITY_IDENTITY_CHANGED\")\n    from connected_enterprise import transition_evidence as evidence\n    from connected_enterprise import upgrades\n    def open_bound(path):\n        if str(Path(path).absolute())!=route: raise ValueError(\"P0273_ROUTE_NOT_AUTHORIZED\")\n        if ident(fd)!=tuple(expected): raise ValueError(\"P0273_CAPABILITY_IDENTITY_CHANGED\")\n        # openat(\".\") creates a distinct open-file description, unlike dup().\n        new=os.open(\".\",os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)\n        try:\n            if ident(new)!=tuple(expected): raise ValueError(\"P0273_CAPABILITY_IDENTITY_CHANGED\")\n            return new\n        except BaseException:\n            os.close(new); raise\n    a=open_bound(route); b=open_bound(route)\n    try:\n        fcntl.flock(a,fcntl.LOCK_EX|fcntl.LOCK_NB)\n        try:\n            fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB)\n        except BlockingIOError: contended=True\n        else: contended=False\n        fcntl.flock(a,fcntl.LOCK_UN)\n        fcntl.flock(b,fcntl.LOCK_EX|fcntl.LOCK_NB)\n        observe('bound_process',identity=ident(a)==tuple(expected)==ident(b),independent_lock=contended)\n    finally:\n        os.close(a); os.close(b)\n    if not contended: raise ValueError('P0274_INDEPENDENT_LOCK_REQUIRED')\n    evidence._open_directory=open_bound\n    real_run=subprocess.run\n    native=upgrades.verify_historical\n    def fresh(*a,**kw):\n        upgrades._HISTORICAL_AUDITS.clear()\n        return native(*a,**kw)\n    upgrades.verify_historical=fresh\n    def launch(args,*a,**kw):\n        if (isinstance(args,list) and len(args)==3 and args[1]==\"-c\"\n            and \"from connected_enterprise.finance import audit_journal\" in args[2]):\n            p=json.loads(kw[\"input\"])\n            if p.get(\"evidence_dir\")!=route: raise ValueError(\"P0273_NESTED_ROUTE_CHANGED\")\n            child=Path(kw[\"cwd\"])\n            # Only the known evidence-capable owner closure can receive the adapter.\n            module=child/\"connected_enterprise/transition_evidence.py\"\n            verifier=child/\"connected_enterprise/upgrades.py\"\n            if module.is_file() and verifier.is_file():\n                if (blob(module)!=EVIDENCE_SHA\n                    or blob(verifier)!=UPGRADES_SHA):\n                    raise ValueError(\"P0273_UNSUPPORTED_HISTORICAL_RUNTIME\")\n                args=[*args[:2], prefix(fd,route,expected,bootstrap)+args[2]]\n                if kw.get(\"pass_fds\"): raise ValueError(\"P0273_UNEXPECTED_DESCRIPTOR_SET\")\n                kw[\"pass_fds\"]=(fd,)\n                # Inject a test-only recovery alias AFTER direct child entry.\n                ref=os.environ['P0274_ALIAS_REF']; alias='.pending-'+ref\n                os.link(ref,alias,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)\n                observe('nested_compatible_launch')\n                result=real_run(args,*a,**kw)\n                try: os.stat(alias,dir_fd=fd,follow_symlinks=False)\n                except FileNotFoundError: removed=True\n                else: removed=False\n                observe('nested_compatible_return',accepted=result.returncode==0,recovered=removed)\n                if result.returncode==0 and not removed: raise ValueError('P0274_NESTED_RECOVERY_MISSING')\n                return result\n            elif p[\"record\"].get(\"source_transitions\") or p[\"record\"].get(\"connected_journal\",{}).get(\"source_history\"):\n                raise ValueError(\"P0273_UNSUPPORTED_HISTORICAL_RUNTIME\")\n            # Legacy leaf without transition records: original verifier, no CAS capability.\n            observe('nested_legacy_leaf')\n        return real_run(args,*a,**kw)\n    subprocess.run=launch\ndef prefix(fd,route,expected,bootstrap):\n    return (\"BOOTSTRAP=\"+repr(bootstrap)+\"\\nEVIDENCE_SHA=\"+repr(EVIDENCE_SHA)+\n            \"\\nUPGRADES_SHA=\"+repr(UPGRADES_SHA)+\"\\n\"+bootstrap+\n            \"\\ninstall_bound_replay(\"+repr(fd)+\",\"+repr(route)+\",\"+repr(tuple(expected))+\",BOOTSTRAP)\\n\")\n"
EVIDENCE_SHA = "2397091ef8e1960ad13950693d5b3cd04e2ff7c5"
UPGRADES_SHA = "9866d004c412fc05c9f6292cf898307f177359df"
exec(BOOTSTRAP)
OWNER = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    owner, out = map(lambda p: Path(p).resolve(), sys.argv[1:3])
    start = time.monotonic()
    self0 = resource.getrusage(resource.RUSAGE_SELF)
    child0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {'owner_commit': OWNER, 'probe_sha256': sha(Path(__file__).read_bytes()),
               'stage': 'source', 'arms': {}, 'diagnostic_accepted': False,
               'descriptor_equivalent': None, 'original_account_accessed': False,
               'actual_commerce': False, 'second_transition_committed': False, 'third_transition_committed': False,
               'actual_billing_usd': None}
    fixture = None
    case = None
    try:
        if subprocess.check_output(['git','-C',str(owner),'rev-parse','HEAD'],text=True).strip()!=OWNER:
            raise ValueError('PINNED_OWNER_REQUIRED')
        os.chdir(owner)
        sys.path.insert(0,str(owner))
        from tests.test_connected_operating_upgrade import OperatingUpgradeTests
        from commercial.ledger import digest
        from connected_enterprise.engine import run_world
        from connected_enterprise.operations import _copy_source, _copy_inputs
        from connected_enterprise.runner import identity
        from connected_enterprise.transition_evidence import business_evidence, ticket_body
        import connected_enterprise.upgrades as u
        fixture = OperatingUpgradeTests
        receipt['stage'] = 'fixture'
        fixture.setUpClass()
        case = fixture()
        case.setUp()
        receipt['stage'] = 'legacy'
        case.legacy()
        receipt['stage'] = 'first_migration'
        first = case.migrate()
        if not first.get('accepted'):
            raise ValueError('FIRST_MIGRATION_NOT_ACCEPTED')
        receipt['stage'] = 'one_event'
        result = run_world(case.new,case.manifest,case.cfg,2610312202,'growth',
                           case.world,source=case.source,stop_after_events=1)
        checkpoint = json.loads((case.world/'STATE.json').read_text())
        state = checkpoint['body']['state']
        if not state['queue'] or len(result['owned_account']['connected_journal']['source_history'])!=1:
            raise ValueError('NONEMPTY_ONE_TRANSITION_REQUIRED')
        future=case.case/'forward-source'
        _copy_source(case.new,future)
        _copy_inputs(case.new,future,case.manifest)
        engine=future/'connected_enterprise/engine.py'
        engine.write_bytes(engine.read_bytes()+b'\n# P0-274 second authorized disposable target.\n')
        # Native second migration on the isolated, stable route. No patches or changed timeout.
        from connected_enterprise.migration import upgrade_world
        receipt['stage']='second_migration'
        initial_source=case.new
        second=upgrade_world(future,case.new,case.manifest,case.world,policy=case.policy,
                    expected_checkpoint_sha256=digest(checkpoint),ident='p0-274-second')
        if not second.get('accepted'):raise ValueError('SECOND_MIGRATION_REJECTED')
        receipt['second_transition_committed']=True
        after=json.loads((case.world/'STATE.json').read_text())['body']['state']
        receipt['second_queue_preserved']=all(after[k]==state[k] for k in ['queue','current','orders','buyers','events','investments','used_jobs','processed_events','last_time'])
        if not receipt['second_queue_preserved'] or case.key.stat().st_ino!=case.key_inode:raise ValueError('SECOND_PRESERVATION_FAILED')
        case.new=future;case.source=identity(future)
        receipt['stage']='second_event'
        result=run_world(case.new,case.manifest,case.cfg,2610312202,'growth',case.world,source=case.source,stop_after_events=1)
        checkpoint=json.loads((case.world/'STATE.json').read_text());state=checkpoint['body']['state']
        if not state['queue'] or len(result['owned_account']['connected_journal']['source_history'])!=2:raise ValueError('TWO_TRANSITIONS_AND_QUEUE_REQUIRED')
        future=case.case/'third-source';_copy_source(case.new,future);_copy_inputs(case.new,future,case.manifest)
        engine=future/'connected_enterprise/engine.py'
        engine.write_bytes(engine.read_bytes()+b'\n# P0-274 third authorized uncommitted target.\n')
        config=state['config']
        origin=state.get('origin_source',state['source'])
        contract='connected014/'+digest({'config':config,'seed':state['seed'],'arm':state['arm'],
                                         'source':origin,'manifest':case.manifest})
        day=max(state['last_time'],state['current']['event']['time'] if state['current'] else state['last_time'])
        operating={'schema':'agi-alpha/connected-operating-transition/v1',
                   'prior_checkpoint':checkpoint,'from_runtime':state['source'],
                   'to_runtime':identity(future),'policy':case.policy}
        store=case.world/'transition-evidence'
        receipt['stage']='third_authorization'
        ticket=u.authorize_upgrade(historical_root=case.new,target_root=future,manifest=case.manifest,
                 path=case.world/'account.sqlite',opening=config['opening'],working=config['working'],
                 contract=contract,expected_state_digest=None,ident='p0-274-third-not-committed',
                 day=day,operating=operating,evidence_dir=store)
        receipt['stage']='authorization_validation'
        with business_evidence(case.world):
            body=u.validate_ticket(ticket,root=future,path=case.world/'account.sqlite')
            if body['counter']!=3 or len(body['prior_record']['connected_journal']['source_history'])!=2:
                raise ValueError('NATIVE_THIRD_AUTHORIZATION_REQUIRED')
        receipt['native_third_authorization']=True
        ref=ticket['body']['evidence']['prior_record']['sha256']
        published=store/ref
        original=published.read_bytes()
        if sha(original)!=ref:
            raise ValueError('ACTUAL_REFERENCED_BLOB_REQUIRED')
        ledger_files=[case.world/'STATE.json',case.world/'account.sqlite.actions.jsonl',
                      case.world/'account.sqlite.connected-journal.json']
        before=[p.read_bytes() for p in ledger_files]
        inventory=[u.source_inventory(p) for p in (initial_source,case.new,future)]
        trace=case.case/'nested-trace.jsonl';trace.touch(mode=0o600)
        os.environ['P0274_TRACE']=str(trace);os.environ['P0274_ALIAS_REF']=ref
        baseline=None
        def route_identity(path):
            s=path.stat()
            return (s.st_dev,s.st_ino)
        import connected_enterprise.transition_evidence as evidence
        real_run=subprocess.run
        def invoke(name, expected_route, *, bound=False):
            nonlocal baseline
            receipt['stage']=name
            trace.write_text('')
            u._HISTORICAL_AUDITS.clear()
            row={'route_matches_parent':route_identity(store)==expected_route}
            value=None
            fd=evidence._store.get().fd
            def launch(args,*a,**kw):
                if bound:
                    if not (isinstance(args,list) and len(args)==3 and args[1]=='-c'
                            and 'from connected_enterprise.finance import audit_journal' in args[2]):
                        raise ValueError('P0273_UNEXPECTED_LAUNCH')
                    if json.loads(kw['input']).get('evidence_dir')!=str(store):
                        raise ValueError('P0273_UNEXPECTED_ROUTE')
                    if blob(Path(kw['cwd'])/'connected_enterprise/transition_evidence.py')!=EVIDENCE_SHA or blob(Path(kw['cwd'])/'connected_enterprise/upgrades.py')!=UPGRADES_SHA:
                        raise ValueError('P0273_UNSUPPORTED_HISTORICAL_RUNTIME')
                    args=[*args[:2],prefix(fd,str(store),expected_route,BOOTSTRAP)+args[2]]
                    kw['pass_fds']=(fd,)
                return real_run(args,*a,**kw)
            with patch.object(u.subprocess,'run',side_effect=launch) as observe:
                try:
                    value=u.verify_historical(ticket,case.manifest,root=future)
                    row['accepted']=bool(value.get('accepted'))
                except Exception as exc:
                    row['accepted']=False
                    row['exception_type']=type(exc).__name__
                    row['historical_rejected']=str(exc).startswith('PINNED_HISTORICAL_AUDIT_FAILED:')
                    row['timeout']=isinstance(exc,subprocess.TimeoutExpired)
                row['direct_launches']=observe.call_count
            if name=='fresh_baseline' and row['accepted']:baseline=value
            row['receipt_equal']=baseline is not None and baseline==value
            events=[json.loads(x) for x in trace.read_text().splitlines()]
            processes=[x for x in events if x['event']=='bound_process']
            starts=[x for x in events if x['event']=='nested_compatible_launch']
            ends=[x for x in events if x['event']=='nested_compatible_return']
            row.update(bound_processes=len(processes),all_process_identity_and_lock=all(x['identity'] and x['independent_lock'] for x in processes),
                       nested_compatible_launches=len(starts),nested_compatible_returns=len(ends),
                       nested_recovery_all=all(x['accepted'] and x['recovered'] for x in ends),
                       nested_legacy_leaves=sum(x['event']=='nested_legacy_leaf' for x in events))
            receipt['arms'][name]=row
            return row
        def relocated(name, expected_route, *, empty=False, invalid=False):
            saved=store.with_name('p0274-original-directory')
            store.rename(saved)
            try:
                if empty:store.mkdir(mode=0o700)
                else:shutil.copytree(saved,store)
                old_alias=saved/('.pending-'+ref)
                new_alias=store/('.pending-'+ref)
                if invalid:
                    badname=sha(b'expected different development bytes')
                    bad=saved/badname
                    bad.write_bytes(b'invalid development evidence')
                    old_alias=saved/('.pending-'+badname)
                    os.link(bad,old_alias)
                else:os.link(saved/ref,old_alias)
                if not empty:os.link(store/ref,new_alias)
                try:
                    row=invoke(name,expected_route,bound=True)
                    row['original_alias_removed']=not old_alias.exists()
                    row['replacement_alias_retained']=new_alias.exists() if not empty else None
                    return row
                finally:
                    old_alias.unlink(missing_ok=True)
                    if invalid:bad.unlink(missing_ok=True)
            finally:
                if store.exists():shutil.rmtree(store)
                saved.rename(store)
        with business_evidence(case.world):
            original_route=route_identity(store)
            fd=evidence._store.get().fd
            # Distinct open descriptions must contend rather than inherit the parent's lock.
            lock_probe="""import os,fcntl,sys
fd=int(sys.argv[1]);new=os.open('.',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
try:
 try:fcntl.flock(new,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('contended')
 else:print('acquired')
finally:os.close(new)
"""
            fcntl.flock(fd,fcntl.LOCK_EX)
            try:
                lock1=real_run([sys.executable,'-c',lock_probe,str(fd)],pass_fds=(fd,),capture_output=True,text=True,timeout=10)
            finally:fcntl.flock(fd,fcntl.LOCK_UN)
            lock2=real_run([sys.executable,'-c',lock_probe,str(fd)],pass_fds=(fd,),capture_output=True,text=True,timeout=10)
            receipt['independent_lock']=lock1.returncode==lock2.returncode==0 and lock1.stdout.strip()=='contended' and lock2.stdout.strip()=='acquired'
            a=invoke('fresh_baseline',original_route)
            b=relocated('bound_identical_replacement',original_route)
            c=relocated('bound_empty_replacement',original_route,empty=True)
            d=relocated('bound_invalid_original_valid_replacement',original_route,invalid=True)
            alias=store/('.pending-'+ref)
            os.link(published,alias)
            try:
                e=invoke('restored_bound',original_route,bound=True)
                e['alias_removed']=not alias.exists()
            finally:alias.unlink(missing_ok=True)
        receipt['stage']='invariants'
        invariants={'state_and_native_history_unchanged':before==[p.read_bytes() for p in ledger_files],
                    'source_inventory_unchanged':inventory==[u.source_inventory(p) for p in (initial_source,case.new,future)],
                    'signer_inode_unchanged':case.key.stat().st_ino==case.key_inode,
                    'referenced_blob_unchanged':published.read_bytes()==original,
                    'directory_identity_restored':route_identity(store)==original_route}
        receipt['invariants']=invariants
        receipt['diagnostic_accepted']=bool(all(invariants.values()) and receipt['independent_lock']
            and a['accepted'] and a['direct_launches']==1 and a['route_matches_parent']
            and b['accepted'] and b['receipt_equal'] and b['direct_launches']==1
            and b['nested_compatible_launches']>=1 and b['nested_compatible_launches']==b['nested_compatible_returns']
            and b['bound_processes']>=2 and b['all_process_identity_and_lock'] and b['nested_recovery_all'] and b['nested_legacy_leaves']>=1
            and not b['route_matches_parent'] and b['original_alias_removed'] and b['replacement_alias_retained']
            and c['accepted'] and c['receipt_equal'] and c['original_alias_removed']
            and c['direct_launches']==1 and not c['route_matches_parent']
            and not d['accepted'] and d.get('historical_rejected') and d['direct_launches']==1
            and not d['original_alias_removed'] and d['replacement_alias_retained']
            and e['accepted'] and e['receipt_equal'] and e['alias_removed'] and e['direct_launches']==1
            and not any(x.get('timeout',False) for x in receipt['arms'].values()))
        receipt['descriptor_equivalent']=receipt['diagnostic_accepted']
        receipt['stage']='complete'
    except Exception as exc:
        receipt['failure_type']=type(exc).__name__
        receipt['timeout']=isinstance(exc,subprocess.TimeoutExpired)
    finally:
        try:
            if case is not None:case.tearDown()
            if fixture is not None:fixture.tearDownClass()
        except Exception as exc:
            receipt['cleanup_failure_type']=type(exc).__name__
            receipt['diagnostic_accepted']=False
        self1=resource.getrusage(resource.RUSAGE_SELF)
        child1=resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['self_cpu_seconds']=self1.ru_utime+self1.ru_stime-self0.ru_utime-self0.ru_stime
        receipt['waited_child_cpu_seconds']=child1.ru_utime+child1.ru_stime-child0.ru_utime-child0.ru_stime
        receipt['wall_seconds']=time.monotonic()-start
        out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return 0 if receipt['diagnostic_accepted'] else 1

if __name__=='__main__':
    raise SystemExit(main())
