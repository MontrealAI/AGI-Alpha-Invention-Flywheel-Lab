import argparse, copy, hashlib, json, os, resource, signal, sys, tempfile, time, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from commercial.ledger import digest
from commercial.terms import prospective_terms
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, source_identity
from adaptive_enterprise.account import audit_account
from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICE_SOURCES, prepare_services, execute_job
from experiments.commerce006 import PINS
from test_ordinary_portable_upgrade import tree_cpu

MICRO = 1_000_000
HERE = Path(__file__).resolve().parent

def run_authorized():
    import shutil
    protocol = json.loads((HERE / 'maturity_successor_protocol.json').read_text())
    started = time.monotonic()
    initial = resource.getrusage(resource.RUSAGE_SELF)
    host_pid = int(Path('/proc/self/stat').read_text().split(' ', 1)[0])
    def stop(signum, frame):
        if tree_cpu(host_pid) > 35 or time.monotonic() - started > 115:
            raise RuntimeError('PROSPECTIVE_40_CPU_120_WALL_PROOF_BOUND_APPROACHING')
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, .2, .2)
    receipt = {'schema': 'agi-alpha/native020-maturity-successor-proof/v1', 'accepted': False,
               'protocol_sha256': hashlib.sha256((HERE / 'maturity_successor_protocol.json').read_bytes()).hexdigest(),
               'scope': 'Fixed authored capital-mechanism engineering case; no market, frontier-model, external-commerce or annual-profit qualification.',
               'test_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    last_record = None
    try:
        assert source_identity(ROOT)['sha256'] == protocol['financial_source_sha256'], 'REGISTERED_FINANCIAL_SOURCE_CHANGED'
        with tempfile.TemporaryDirectory(prefix='maturity-successor-proof-') as temp:
            root = Path(temp) / 'source'
            for name in set(SOURCE_PATHS) | set(SERVICE_SOURCES) | set(PINS):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            assert source_identity(root) == source_identity(ROOT)
            manifest = prepare_services(root, 'services', cohort_seed=2610312001)
            jobs = sorted((j for j in manifest['jobs'] if j['service_id'] == 'reconciliation' and j['accepted']), key=lambda j: j['id'])
            assert len(jobs) >= 6
            account_path = Path(temp) / 'same-account.sqlite'
            with JournalAccount(root, manifest, account_path, opening=500 * MICRO, working=100 * MICRO,
                                contract='native020/maturity-funds-successor-fixed-mechanism') as a:
                key_path = account_path.with_name(account_path.name + '.adaptive-simulation-key')
                key_inode = key_path.stat().st_ino
                service_receipts = []
                def produce(ident, buyer, job, arrival, settled, maturity, price, cost, allow_seed):
                    terms = prospective_terms(ident, price, maturity, settled, premium=0, fee=0)
                    a.execute('register_terms', {'id': 'terms-' + ident, 'terms': terms}, arrival)
                    work = {'job_id': job['id'], 'artifact_sha256': job['artifact_sha256'], 'terms_sha256': digest(terms),
                            'resource_contract': 'Fixed authored prepaid complete synthetic production/checking/delivery/support invoice'}
                    funding = a.spend('production-' + ident, 'production_contract', cost, arrival, work,
                                      expected_net=price - cost, allow_seed=allow_seed)
                    assert funding is not None
                    a.execute('wallet', {'buyer': buyer, 'amount': price}, arrival)
                    a.execute('offer', {'id': ident, 'buyer': buyer, 'price': price,
                                       'job_id': job['id'], 'deadline': settled, 'terms_id': 'terms-' + ident}, arrival)
                    for action in ['consent', 'fund']:
                        a.execute('event', {'id': ident, 'event_id': ident + '-' + action, 'action': action}, arrival)
                    execution = execute_job(root, job)
                    assert execution['accepted'] is True and execution['artifact_sha256'] == job['artifact_sha256']
                    a.execute('event', {'id': ident, 'event_id': ident + '-prepare', 'action': 'prepare'}, arrival)
                    a.execute('event', {'id': ident, 'event_id': ident + '-release', 'action': 'release'}, settled)
                    service_receipts.append({'order_id': ident, 'job_id': job['id'], 'execution': execution,
                                             'funding': funding, 'price_microUSD': price, 'cost_microUSD': cost,
                                             'complete_modeled_profit_microUSD': price - cost})
                    return funding
                for i in range(5):
                    produce('prior-' + str(i), 'buyer-' + str(i), jobs[i], 2 * i, 2 * i + 1, 20 + 2 * i,
                            100 * MICRO, 50 * MICRO, True)
                    last_record = a.export()
                before = copy.deepcopy(a.export())
                state = before['ledger']['summary']
                assert (state['profit'], state['cash'], state['tailReserve'], state['available']) == (250 * MICRO, 750 * MICRO, 501 * MICRO, 149 * MICRO)
                planned_terms = prospective_terms('successor', 200 * MICRO, 35, 30, premium=0, fee=0)
                planned_work = {'job_id': jobs[5]['id'], 'artifact_sha256': jobs[5]['artifact_sha256'],
                                'terms_sha256': digest(planned_terms),
                                'resource_contract': 'Fixed authored prepaid complete synthetic production/checking/delivery/support invoice'}
                deferred = a.spend('production-successor', 'production_contract', 150 * MICRO, 11, planned_work,
                                   expected_net=50 * MICRO, allow_seed=False)
                assert deferred is None
                assert a.export()['ledger'] == before['ledger']
                after_deferral = copy.deepcopy(a.snapshot())
                a.advance_financial(29)
                after_release = copy.deepcopy(a.export())
                released = after_release['ledger']['summary']
                assert released['cash'] == state['cash'] and released['profit'] == state['profit']
                assert state['tailReserve'] - released['tailReserve'] == 501 * MICRO
                assert released['tailReserve'] == 0 and released['available'] == 650 * MICRO
                prior_prefix = copy.deepcopy(after_release['ledger']['actions'])
                funding = produce('successor', 'successor-buyer', jobs[5], 29, 30, 35, 200 * MICRO, 150 * MICRO, False)
                assert funding['funding'] == 'EARNED'
                record = a.export()
                reserve = next(e for e in record['ledger']['actions'] if e['op'] == 'reserve' and e['args']['id'] == funding['plan_id'])
                maturity_events = [e for e in record['ledger']['actions'] if e['op'] == 'mature']
                assert len(maturity_events) == 5 and all(e['seq'] < reserve['seq'] for e in maturity_events)
                assert reserve['args']['amount'] == 150 * MICRO and reserve['before']['unrestrictedEarned'] >= 150 * MICRO
                assert record['ledger']['actions'][:len(prior_prefix)] == prior_prefix
                final = record['ledger']['summary']
                assert (final['profit'], final['cash'], final['tailReserve']) == (300 * MICRO, 800 * MICRO, 200_200_000)
                assert final['payables'] == 0 and key_path.stat().st_ino == key_inode
                assert a.audit()['accepted'] and audit_account(record, root=root, manifest=manifest)['accepted']
                last_record = record
                receipt.update(accepted=True, before_release=state, denied_funding_at_hour=11,
                               after_deferral=after_deferral, after_release=released, final_summary=final,
                               release_without_income_microUSD=501 * MICRO, successor_contribution_microUSD=50 * MICRO,
                               successor_protection_tail_microUSD=200_200_000, funding_lineage={'reservation': reserve,
                               'prior_maturity_sequences': [e['seq'] for e in maturity_events]},
                               distinct_service_job_ids=[r['job_id'] for r in service_receipts],
                               service_receipts=service_receipts, same_private_key_inode=True)
    except BaseException:
        receipt['error'] = traceback.format_exc()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        own, children = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['cpu_seconds_including_waited_children'] = own.ru_utime + own.ru_stime - initial.ru_utime - initial.ru_stime + children.ru_utime + children.ru_stime
        receipt['wall_seconds'] = time.monotonic() - started
        if last_record is not None:
            path = HERE / 'maturity_successor_public_record.json'
            path.write_text(json.dumps(last_record, indent=2) + '\n')
            receipt['public_record_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        if receipt['cpu_seconds_including_waited_children'] > 40 or receipt['wall_seconds'] > 120:
            receipt.update(accepted=False, resource_failure='REGISTERED_INDEPENDENT_PROOF_BOUND_EXCEEDED')
        (HERE / 'maturity_successor_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['accepted'] else 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute-authorized', action='store_true')
    args = parser.parse_args()
    if not args.execute_authorized:
        print(json.dumps({'status': 'UNEXECUTED_REQUIRES_NEW_ALLOCATION', 'no_fixture_or_account_created': True}))
        raise SystemExit(0)
    raise SystemExit(run_authorized())
