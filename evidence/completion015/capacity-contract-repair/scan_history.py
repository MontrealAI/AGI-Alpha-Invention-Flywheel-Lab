"""Read-only source-bound capacity-term checks, without opening native accounts."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from commercial.ledger import digest
from connected_enterprise.verify import _check_investments

started = time.process_time()
package, output = Path(sys.argv[1]), Path(sys.argv[2])
report_raw = (package / 'REPORT.json').read_bytes()
assert hashlib.sha256(report_raw).hexdigest() == 'c445bf8bebef8c1b5a63baf55ae8fa442e632691b3d47f5a8d164fae6d82db46'
bound = {row['task']['id']: row['result_sha256'] for row in json.loads(report_raw)['worlds_index']}
rows = []
for path in sorted((package / 'worlds').glob('*/RESULT.json')):
    result = json.loads(path.read_text()); world = path.parent.name
    assert digest(result) == bound[world]
    assert result['source']['sha256'] == 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4'
    checked = _check_investments(result, result['owned_account']['ledger'], {row['id']: row for row in result['orders']})
    capacity = [row for row in result['investments'] if row['kind'] == 'capacity']
    uses = sum(row.get('capacity_source_plan_id') is not None for row in result['orders'])
    forged = copy.deepcopy(result)
    for row in forged['investments']:
        if row['kind'] == 'capacity':
            row['activation_time'] = row['purchased_time']; row['expiry_time'] += 100000
    rejection = None
    if capacity:
        try:
            _check_investments(forged, forged['owned_account']['ledger'], {row['id']: row for row in forged['orders']})
        except ValueError as error:
            rejection = str(error)
        assert rejection == 'CAPACITY_LIFETIME_DIFFERS_FROM_FINANCED_CONTRACT'
    rows.append({'world': world, 'result_sha256': bound[world], 'original_helper_accepted': True,
                 'capacity_investments': len(capacity), 'actual_capacity_uses': uses,
                 'forged_timing_rejection': rejection, 'helper_receipt': checked})
assert len(rows) == 8
receipt = {'schema': 'agi-alpha/completion015-capacity-contract-impact/v1',
           'scope': 'READ_ONLY_ORIGINAL_RECORDS_HELPER_CHECK_ONLY_NO_NATIVE_ACCOUNT_AUDIT_OR_COMMERCE_RUN',
           'original_source_sha256': 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4',
           'report_sha256': hashlib.sha256(report_raw).hexdigest(), 'worlds': rows,
           'capacity_investments': sum(row['capacity_investments'] for row in rows),
           'actual_capacity_uses': sum(row['actual_capacity_uses'] for row in rows),
           'original_timing_term_violations': 0,
           'interpretation': 'Original eight-world finances, productive uses and CPU qualification failure retain their original source identity. No repaired-source commercial qualification is claimed.',
           'process_cpu_seconds': time.process_time() - started}
output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
print(json.dumps({key: receipt[key] for key in ['capacity_investments', 'actual_capacity_uses', 'original_timing_term_violations', 'process_cpu_seconds']}))
