"""Native historical evidence route discriminator; publish no fixture records."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

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
               'route_equivalent': None, 'original_account_accessed': False,
               'actual_commerce': False, 'second_transition_committed': False,
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
        engine.write_bytes(engine.read_bytes()+b'\n# P0-272 disposable authorized target.\n')
        config=state['config']
        origin=state.get('origin_source',state['source'])
        contract='connected014/'+digest({'config':config,'seed':state['seed'],'arm':state['arm'],
                                         'source':origin,'manifest':case.manifest})
        day=max(state['last_time'],state['current']['event']['time'] if state['current'] else state['last_time'])
        operating={'schema':'agi-alpha/connected-operating-transition/v1',
                   'prior_checkpoint':checkpoint,'from_runtime':state['source'],
                   'to_runtime':identity(future),'policy':case.policy}
        store=case.world/'transition-evidence'
        receipt['stage']='second_authorization'
        ticket=u.authorize_upgrade(historical_root=case.new,target_root=future,manifest=case.manifest,
                 path=case.world/'account.sqlite',opening=config['opening'],working=config['working'],
                 contract=contract,expected_state_digest=None,ident='p0-272-prepared-not-committed',
                 day=day,operating=operating,evidence_dir=store)
        receipt['stage']='authorization_validation'
        with business_evidence(case.world):
            body=u.validate_ticket(ticket,root=future,path=case.world/'account.sqlite')
            if body['counter']!=2 or len(body['prior_record']['connected_journal']['source_history'])!=1:
                raise ValueError('NATIVE_SECOND_AUTHORIZATION_REQUIRED')
        receipt['native_second_authorization']=True
        ref=ticket['body']['evidence']['prior_record']['sha256']
        published=store/ref
        original=published.read_bytes()
        if sha(original)!=ref:
            raise ValueError('ACTUAL_REFERENCED_BLOB_REQUIRED')
        ledger_files=[case.world/'STATE.json',case.world/'account.sqlite.actions.jsonl',
                      case.world/'account.sqlite.connected-journal.json']
        before=[p.read_bytes() for p in ledger_files]
        inventory=u.source_inventory(case.new)
        baseline=None
        def route_identity(path):
            s=path.stat()
            return (s.st_dev,s.st_ino)
        def invoke(name, expected_route, *, guarded=False):
            nonlocal baseline
            receipt['stage']=name
            u._HISTORICAL_AUDITS.clear()
            row={'route_matches_parent':route_identity(store)==expected_route}
            value=None
            with patch.object(u.subprocess,'run',wraps=subprocess.run) as observe:
                try:
                    if guarded and not row['route_matches_parent']:
                        raise ValueError('P0_272_ROUTE_IDENTITY_CHANGED')
                    value=u.verify_historical(ticket,case.manifest,root=future)
                    row['accepted']=bool(value.get('accepted'))
                except Exception as exc:
                    row['accepted']=False
                    row['exception_type']=type(exc).__name__
                    row['route_rejected']=str(exc)=='P0_272_ROUTE_IDENTITY_CHANGED'
                    row['historical_rejected']=str(exc).startswith('PINNED_HISTORICAL_AUDIT_FAILED:')
                    row['timeout']=isinstance(exc,subprocess.TimeoutExpired)
                row['direct_launches']=observe.call_count
            if name=='fresh_baseline' and row['accepted']:
                baseline=value
            row['receipt_equal']=baseline is not None and baseline==value
            receipt['arms'][name]=row
            return row
        def relocated(name, expected_route, *, empty=False, guarded=False):
            saved=store.with_name('p0272-original-directory')
            if saved.exists():
                raise ValueError('UNEXPECTED_ROUTE_COLLISION')
            store.rename(saved)
            try:
                if empty:
                    store.mkdir(mode=0o700)
                else:
                    shutil.copytree(saved,store)
                old_alias=saved/('.pending-'+ref)
                new_alias=store/('.pending-'+ref)
                os.link(saved/ref,old_alias)
                if not empty:
                    os.link(store/ref,new_alias)
                try:
                    row=invoke(name,expected_route,guarded=guarded)
                    row['original_alias_retained']=old_alias.exists()
                    row['replacement_alias_removed']=not new_alias.exists() if not empty else None
                    row['original_blob_unchanged']=(saved/ref).read_bytes()==original
                    return row
                finally:
                    old_alias.unlink(missing_ok=True)
            finally:
                if store.exists():shutil.rmtree(store)
                saved.rename(store)
        with business_evidence(case.world):
            original_route=route_identity(store)
            a=invoke('fresh_baseline',original_route)
            b=relocated('fresh_identical_replacement',original_route)
            c=relocated('fresh_empty_replacement',original_route,empty=True)
            d=relocated('guarded_identical_replacement',original_route,guarded=True)
            alias=store/('.pending-'+ref)
            os.link(published,alias)
            try:
                e=invoke('restored_fresh',original_route)
                e['alias_removed']=not alias.exists()
            finally:
                alias.unlink(missing_ok=True)
        receipt['stage']='invariants'
        invariants={'state_and_native_history_unchanged':before==[p.read_bytes() for p in ledger_files],
                    'source_inventory_unchanged':inventory==u.source_inventory(case.new),
                    'signer_inode_unchanged':case.key.stat().st_ino==case.key_inode,
                    'referenced_blob_unchanged':published.read_bytes()==original,
                    'directory_identity_restored':route_identity(store)==original_route}
        receipt['invariants']=invariants
        receipt['diagnostic_accepted']=bool(all(invariants.values())
            and a['accepted'] and a['direct_launches']==1 and a['route_matches_parent']
            and b['accepted'] and b['receipt_equal'] and b['direct_launches']==1
            and not b['route_matches_parent'] and b['original_alias_retained']
            and b['replacement_alias_removed'] and b['original_blob_unchanged']
            and not c['accepted'] and c.get('historical_rejected') and c['direct_launches']==1
            and not d['accepted'] and d.get('route_rejected') and d['direct_launches']==0
            and d['original_alias_retained'] and not d['replacement_alias_removed']
            and e['accepted'] and e['receipt_equal'] and e['alias_removed']
            and e['direct_launches']==1 and e['route_matches_parent']
            and not any(x.get('timeout',False) for x in receipt['arms'].values()))
        if receipt['diagnostic_accepted']:
            receipt['route_equivalent']=False
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
