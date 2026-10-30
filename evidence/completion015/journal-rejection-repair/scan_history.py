"""Read original public records only; never open retired native accounts."""
import hashlib
import json
from pathlib import Path
import sys
import time

started = time.process_time()
package = Path(sys.argv[1])
output = Path(sys.argv[2])


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


report_raw = (package / 'REPORT.json').read_bytes()
assert hashlib.sha256(report_raw).hexdigest() == 'c445bf8bebef8c1b5a63baf55ae8fa442e632691b3d47f5a8d164fae6d82db46'
report = json.loads(report_raw)
bound = {row['task']['id']: row['result_sha256'] for row in report['worlds_index']}
worlds = []
for path in sorted((package / 'worlds').glob('*/RESULT.json')):
    result = json.loads(path.read_text())
    world = path.parent.name
    assert digest(result) == bound[world]
    assert result['source']['sha256'] == 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4'
    account = result['owned_account']; journal = account['connected_journal']; tape = account['ledger']
    assert digest(journal) == account['connected_journal_sha256']
    covered, keys, statuses = [], set(), {}
    for entry in journal['entries']:
        assert entry['key'] not in keys
        keys.add(entry['key']); statuses[entry['status']] = statuses.get(entry['status'], 0) + 1
        assert entry['status'] == 'COMPLETE'
        request, receipt = entry['request'], entry['receipt']
        if request['operation'] == 'execute':
            sequence = receipt['sequence'] - 1
            native = tape['actions'][sequence]
            assert (native['op'], native['args'], native['day']) == (request['op'], request['args'], request['day'])
            assert receipt['actions_sha256'] == digest(tape['actions'][:sequence + 1])
        else:
            assert request['operation'] == 'spend'
            sequence = receipt['native_event_sequence']
            native = tape['actions'][sequence]
            assert receipt['native_actions_sha256'] == digest(tape['actions'][:sequence + 1])
            if entry['funding'] == 'EARNED':
                plan = entry['plan']
                reservations = [row for row in tape['actions'] if row['op'] == 'reserve' and row['args']['id'] == plan['plan_id']]
                assert len(reservations) == 1 and native['op'] == 'finish' and native['args']['id'] == plan['plan_id']
                covered.append(reservations[0]['seq'])
            else:
                assert entry['funding'] == 'SEED' and native['op'] == 'cost'
        covered.append(sequence)
    assert covered == list(range(len(tape['actions'])))
    worlds.append({'world': world, 'result_sha256': digest(result), 'journal_sha256': digest(journal),
                   'statuses': statuses, 'native_actions': len(covered), 'coverage_gaps': 0})
assert len(worlds) == 8
receipt = {'schema': 'agi-alpha/completion015-journal-rejection-impact/v1',
           'scope': 'READ_ONLY_ORIGINAL_RECORD_INSPECTION_NO_ACCOUNT_REOPEN_OR_SIMULATION',
           'original_source_sha256': 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4',
           'report_sha256': hashlib.sha256(report_raw).hexdigest(),
           'public_archive_sha256': 'dd50eb744faac1d9cbd2a3295d9dea49fa26f0799dcefa85f97b58e649cf6d75',
           'worlds': worlds, 'total_complete_entries': sum(row['statuses']['COMPLETE'] for row in worlds),
           'total_native_actions': sum(row['native_actions'] for row in worlds),
           'pending_or_rejected_entries': 0, 'coverage_gaps': 0,
           'interpretation': 'No published original eight-world journal contains this rejection path. Original economics and failed resource qualification retain original identity; no repaired-source result is asserted.',
           'process_cpu_seconds': time.process_time() - started}
output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
print(json.dumps({key: receipt[key] for key in ['total_complete_entries', 'total_native_actions', 'pending_or_rejected_entries', 'coverage_gaps', 'process_cpu_seconds']}))
