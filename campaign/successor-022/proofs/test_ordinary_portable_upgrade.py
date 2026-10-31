import copy, datetime, hashlib, json, os, resource, shutil, signal, sys, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_native_source_upgrade import NativeSourceUpgradeTests as T
from commercial.terms import prospective_terms
from connected_enterprise.finance import source_identity

def tree_cpu(pid):
    total, pending, seen = 0.0, [pid], set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        path = Path('/proc') / str(current) / 'stat'
        try:
            raw = path.read_text()
            fields = raw[raw.rfind(')') + 2:].split()
            total += sum(int(fields[i]) for i in [11, 12, 13, 14]) / os.sysconf('SC_CLK_TCK')
            pending.extend(map(int, (path.parent / 'task' / str(current) / 'children').read_text().split()))
        except (OSError, ValueError, IndexError):
            pass
    return total

def main():
    started, start_cpu = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF)
    raw = Path('/proc/self/stat').read_text()
    host_pid = int(raw.split(' ', 1)[0])
    def enforce(signum, frame):
        if tree_cpu(host_pid) > 28:
            raise RuntimeError('INDEPENDENT_30_CPU_ENVELOPE_APPROACHING')
    signal.signal(signal.SIGALRM, enforce)
    signal.setitimer(signal.ITIMER_REAL, .2, .2)
    result = {'schema': 'agi-alpha/native020-independent-upgrade/v1', 'accepted': False,
              'source_sha256': source_identity(ROOT)['sha256'],
              'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'historical_commit': '10bdb2c5787f95158642b068756ba30b58140562',
              'scope': 'Financial Account/Journal source transition only; no legacy engine queue or STATE migration.',
              'independence': 'Different same-session reviewing agent and independently composed sequence; shared model, host, tools and source fixture.',
              'cpu_limit_seconds': 30, 'early_stop_seconds': 28}
    t, initialized = None, False
    try:
        T.setUpClass()
        initialized = True
        t = T('test_pristine_old_verifier_transition_preserves_account_money_and_obligations')
        t.setUp()
        ticket = t.authorize()
        untouched = copy.deepcopy(ticket)
        key_path = t.path.with_name(t.path.name + '.adaptive-simulation-key')
        key_identity = key_path.stat().st_ino
        t.a = t.upgrade(ticket)
        fallback = t.new / 'historical-source-versions' / ticket['body']['from_source']['sha256']
        fallback.parent.mkdir()
        shutil.move(str(t.old), str(fallback))
        t.old.mkdir()
        assert list(t.old.iterdir()) == []
        assert t.a.audit()['accepted']
        t.a.close()
        t.a = t.reopen()
        a = t.a
        assert key_path.stat().st_ino == key_identity
        job = next(j for j in t.manifest['jobs'] if j['service_id'] == 'reconciliation' and j['accepted'])
        terms = prospective_terms('new-prospective', 1_000_000, 10, 5)
        a.execute('register_terms', {'id': 'new-terms', 'terms': terms}, 4)
        a.execute('wallet', {'buyer': 'new-buyer', 'amount': 1_000_000}, 4)
        a.execute('offer', {'id': 'new-prospective', 'buyer': 'new-buyer', 'price': 1_000_000,
                           'job_id': job['id'], 'deadline': 8, 'terms_id': 'new-terms'}, 4)
        for action, day in [('consent', 4), ('fund', 4), ('prepare', 5), ('release', 5)]:
            a.execute('event', {'id': 'new-prospective', 'action': action, 'event_id': 'new-' + action}, day)
        assert a.snapshot()['summary']['tailReserve'] == 101_400_000
        a.execute('mature', {'id': 'new-prospective', 'event_id': 'new-maturity'}, 11)
        record = a.export()
        assert record['ledger']['summary']['tailReserve'] == 100_200_000
        assert record['source_transitions']['upgrade-1'] == untouched
        assert record['ledger']['actions'][:len(t.original['ledger']['actions'])] == t.original['ledger']['actions']
        assert a.audit()['accepted']
        assert source_identity(ROOT)['sha256'] == result['source_sha256']
        result.update(accepted=True, ordinary_legacy_account_preserved=True, private_key_inode_unchanged=True,
                      invalid_empty_original_source_skipped=True, inventory_bound_fallback_audited=True,
                      new_prospective_order_accepted_and_collected=True, original_permanent_tail_microUSD=100_200_000,
                      signed_ticket_unchanged=True, prior_native_actions_unchanged=True,
                      final_summary=record['ledger']['summary'])
        output = Path(__file__).parent / 'ordinary_portable_upgrade_public_record.json'
        output.write_text(json.dumps(record, indent=2) + '\n')
        result['public_record_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    except BaseException:
        result['error'] = traceback.format_exc()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if t is not None:
            t.tearDown()
        if initialized:
            T.tearDownClass()
        self_cpu, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        result['cpu_seconds_including_waited_children'] = self_cpu.ru_utime + self_cpu.ru_stime - start_cpu.ru_utime - start_cpu.ru_stime + children.ru_utime + children.ru_stime
        result['wall_seconds'] = time.monotonic() - started
        result['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if result['cpu_seconds_including_waited_children'] > 30:
            result.update(accepted=False, resource_failure='INDEPENDENT_30_CPU_LIMIT_EXCEEDED')
        receipt = Path(__file__).parent / 'ordinary_portable_upgrade_receipt.json'
        receipt.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, sort_keys=True))
    return 0 if result['accepted'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
