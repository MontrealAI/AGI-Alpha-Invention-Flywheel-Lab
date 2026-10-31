"""Check original declared/native/operating clocks without opening any account."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from commercial.ledger import digest
from connected_enterprise.verify import _check_contract_clock, _private_draw

started = time.process_time()
package, output = Path(sys.argv[1]), Path(sys.argv[2])
report_raw = (package / 'REPORT.json').read_bytes()
assert hashlib.sha256(report_raw).hexdigest() == 'c445bf8bebef8c1b5a63baf55ae8fa442e632691b3d47f5a8d164fae6d82db46'
bound = {row['task']['id']: row['result_sha256'] for row in json.loads(report_raw)['worlds_index']}
worlds, examples = [], []
for path in sorted((package / 'worlds').glob('*/RESULT.json')):
    result = json.loads(path.read_text()); world = path.parent.name
    assert digest(result) == bound[world]
    assert result['source']['sha256'] == 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4'
    offers, events = {}, {}
    for action in result['owned_account']['ledger']['actions']:
        if action['op'] == 'offer': offers[action['args']['id']] = action
        if action['op'] == 'event': events.setdefault(action['args']['id'], {})[action['args']['action']] = action
    operating = {(row['order_id'], row['kind']): row for row in result['events'] if 'order_id' in row}
    refunds, quality = 0, 0
    for order in result['orders']:
        ident, cfg = order['id'], result['config']
        _check_contract_clock(ident, offers[ident], events[ident], operating, order['qualified_time'], cfg)
        due = None
        if order['outcome'] == 'QUALITY_REJECTED':
            quality += 1; due = order['production_time'] + cfg['acceptance_hours']
        elif order['outcome'] == 'REFUNDED':
            refunds += 1
            default = _private_draw(result['seed'], [order['customer_id'], order['qualified_time'], order['offer']['service_id']], 'nonpayment') < cfg['nonpayment_bps'] / 10000
            due = order['qualified_time'] + cfg['payment_deadline_hours'] if default else order['acceptance_time'] + cfg['clearing_hours']
            assert order['clearing_due_time'] == due
            forged = order['acceptance_time']
            assert forged != due
            rejection = None
            try:
                _check_contract_clock(ident, offers[ident], {'refund': {'day': forged}},
                                      {(ident, 'REFUND'): {'time': forged}}, order['qualified_time'], cfg, refund_due=due)
            except ValueError as error:
                rejection = str(error)
            assert rejection == 'REFUND_TIME_DIFFERS_FROM_FROZEN_CONTRACT'
            examples.append({'world': world, 'order_id': ident, 'result_sha256': bound[world],
                             'original_native_refund': events[ident]['refund']['day'], 'recomputed_due': due,
                             'forged_native_and_operating_time': forged,
                             'prior_actual_time_equality_predicate': True,
                             'prior_declared_due_equality_predicate': order['clearing_due_time'] == due,
                             'new_forged_clock_rejection': rejection})
        if due is not None:
            _check_contract_clock(ident, offers[ident], events[ident], operating, order['qualified_time'], cfg, refund_due=due)
    worlds.append({'world': world, 'result_sha256': bound[world], 'native_offer_deadlines_checked': len(result['orders']),
                   'default_refunds_checked': refunds, 'quality_refunds_checked': quality})
assert len(worlds) == 8 and examples
receipt = {'schema': 'agi-alpha/completion015-refund-clock-impact/v1',
           'scope': 'READ_ONLY_ORIGINAL_CLOCK_HELPER_INSPECTION_NO_NATIVE_ACCOUNT_AUDIT_OR_COMMERCE_RUN',
           'original_source_sha256': 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4',
           'report_sha256': hashlib.sha256(report_raw).hexdigest(), 'worlds': worlds,
           'original_clock_violations': 0,
           'original_native_offer_deadlines_checked': sum(row['native_offer_deadlines_checked'] for row in worlds),
           'original_default_refunds_checked': sum(row['default_refunds_checked'] for row in worlds),
           'original_quality_refunds_checked': sum(row['quality_refunds_checked'] for row in worlds),
           'counterexample_evidence_level': 'Exact prior refund predicates on copied original records, not a full-audit rerun. Primary review separately reports a full audited one-day counterexample.',
           'prior_verifier_sha256': hashlib.sha256(subprocess.check_output(['git', 'show', '5791ed9:connected_enterprise/verify.py'], cwd=ROOT)).hexdigest(),
           'counterexamples': examples,
           'interpretation': 'Original economics and original failed resource qualification unchanged. QUALITY_REJECTED has no original8 example and is covered by small engineering fixtures, not fabricated historical work.',
           'process_cpu_seconds': time.process_time() - started}
output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
print(json.dumps({key: receipt[key] for key in ['original_native_offer_deadlines_checked', 'original_default_refunds_checked', 'original_quality_refunds_checked', 'original_clock_violations', 'process_cpu_seconds']}))
