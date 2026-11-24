"""Exact native recovery-effect discriminator; publish no fixture records."""
import hashlib
import json
import os
from pathlib import Path
import resource
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
               'reuse_equivalent': None, 'original_account_accessed': False,
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
        engine.write_bytes(engine.read_bytes()+b'\n# P0-271 disposable authorized target.\n')
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
                 contract=contract,expected_state_digest=None,ident='p0-271-prepared-not-committed',
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
        def invoke(name,cold,alias=None):
            nonlocal baseline
            receipt['stage']=name
            if cold:
                u._HISTORICAL_AUDITS.clear()
            row={'cold':cold}
            value=None
            with patch.object(u.subprocess,'run',wraps=subprocess.run) as observe:
                try:
                    value=u.verify_historical(ticket,case.manifest,root=future)
                    row['accepted']=bool(value.get('accepted'))
                except Exception as exc:
                    row['accepted']=False
                    row['exception_type']=type(exc).__name__
                    row['historical_audit_rejected']=str(exc).startswith('PINNED_HISTORICAL_AUDIT_FAILED:')
                    row['timeout']=isinstance(exc,subprocess.TimeoutExpired)
                row['direct_launches']=observe.call_count
            if name=='cold_baseline' and row['accepted']:
                baseline=value
            row['receipt_equal']=baseline is not None and value==baseline
            row['published_unchanged']=published.read_bytes()==original
            if alias is not None:
                row['alias_removed']=not alias.exists()
            receipt['arms'][name]=row
            return row
        def valid(name,cold):
            alias=store/('.pending-'+ref)
            if alias.exists():
                raise ValueError('UNEXPECTED_PREEXISTING_ALIAS')
            os.link(published,alias)
            try:
                return invoke(name,cold,alias)
            finally:
                alias.unlink(missing_ok=True)
        def invalid(name,cold):
            badname=sha(b'P0-271 intentionally unreferenced expected bytes')
            bad=store/badname
            alias=store/('.pending-'+badname)
            if bad.exists() or alias.exists():
                raise ValueError('UNEXPECTED_COLLISION')
            bad.write_bytes(b'P0-271 intentionally incorrect bytes')
            os.link(bad,alias)
            try:
                return invoke(name,cold,alias)
            finally:
                alias.unlink(missing_ok=True)
                bad.unlink(missing_ok=True)
        with business_evidence(case.world):
            a=invoke('cold_baseline',True)
            b=invoke('warm_clean',False)
            c=valid('warm_valid',False)
            d=valid('cold_valid',True)
            e=invalid('warm_invalid',False)
            f=invalid('cold_invalid',True)
            g=invoke('restored_cold',True)
        receipt['stage']='invariants'
        invariants={'state_and_native_history_unchanged':before==[p.read_bytes() for p in ledger_files],
                    'source_inventory_unchanged':inventory==u.source_inventory(case.new),
                    'signer_inode_unchanged':case.key.stat().st_ino==case.key_inode,
                    'all_referenced_blob_checks':all(x['published_unchanged'] for x in receipt['arms'].values())}
        receipt['invariants']=invariants
        receipt['diagnostic_accepted']=bool(all(invariants.values()) and a['accepted'] and a['direct_launches']==1
            and b['accepted'] and b['receipt_equal'] and b['direct_launches']==0
            and d['accepted'] and d['receipt_equal'] and d['alias_removed'] and d['direct_launches']==1
            and not f['accepted'] and f['historical_audit_rejected'] and not f['alias_removed'] and f['direct_launches']==1
            and g['accepted'] and g['receipt_equal'] and g['direct_launches']==1
            and not any(x.get('timeout',False) for x in receipt['arms'].values()))
        if receipt['diagnostic_accepted']:
            receipt['reuse_equivalent']=all(x[k]==y[k] for x,y in [(c,d),(e,f)]
                    for k in ('accepted','receipt_equal','alias_removed','published_unchanged'))
        receipt['stage']='complete'
    except Exception as exc:
        receipt['failure_type']=type(exc).__name__
        receipt['timeout']=isinstance(exc,subprocess.TimeoutExpired)
        # Never print exceptions: they can contain private paths or native records.
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
