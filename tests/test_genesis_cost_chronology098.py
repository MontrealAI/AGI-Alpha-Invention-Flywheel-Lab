"""GENESIS native cost chronology 098 — frozen adversarial protocol.

Registered before adding executable test logic, on an isolated branch based on
PR233 exact source 895166b94410d7157aadb4c2bdac8022383361f2.

Scientific question
-------------------
Does the *canonical* native GENESIS public audit reject a legitimate, HMAC-
replayed BusinessAccount whose acquisition cost was posted at the wrong
source-prescribed hour, despite unchanged cost amount and a still-valid native
ledger? The original source schedules acquisition for first job at hour 24.

Finite fixed cases (no outcome-dependent substitution)
------------------------------------------------------
C0: original registered pilot, every acquisition and maintenance cost posted
at hour 24*(job index+1). Expected: canonical audit and independent witness
both accept.
C1: first acquisition amount unchanged, but date shifted exactly one hour
EARLIER (24->23), injected via BusinessAccount.cost before creating its native
action; all subsequent actions and obligations as originally registered.
Expected: independent source chronology witness rejects; determine from
actual native run whether canonical audit currently rejects or accepts. The
answer is a measured engineering finding, not asserted beforehand.
C2: synthetic key-free copy of genuine exported action rows, with an added
duplicate overhead cost; independent witness rejects, no account is rewritten.
C3: synthetic key-free copy with first acquisition amount +1 microUSD;
independent witness rejects, no account is rewritten.
C4: registered no-purchase case still pays actual fixed acquisition and
maintenance; independent witness accepts and no real revenue is claimed.

No private keys, signer material, actual customers, spending, provider calls or
original P0 accounts. Every operation uses disposable, existing canonical
native simulated accounts and public exports. No platform guard is relaxed.

Only this new test file may be edited on this branch. PR233, PR229, PR232,
current main and all original frozen evidence remain unchanged. A sidecar
witness is NOT an alternative native financial authority or release gate.
Do not merge without the existing owner incorporating any required enforcement
into the canonical audit and qualifying it through the ordinary source gates.

Do not relabel failures, retry until favorable or infer paid commerce.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from genesis_enterprise import native
from genesis_enterprise.policy import canonical

ROOT = Path(__file__).resolve().parents[1]
NATIVE_AVAILABLE = (ROOT / 'commercial/ledger.py').is_file()


def independent_overhead_chronology(protocol, jobs, actions):
    """Read-only registered overhead witness; not a native authority.

    Check exact amount, event hour and cardinality for every completed
    registered job. This does *not* replace audit_journal/HMAC replay, prove
    independent buyer demand, or change any financial receipt.
    """
    expected = {}
    for index, job in enumerate(jobs):
        hour = 24 * (index + 1)
        for kind in ('acquisition', 'maintenance'):
            amount = protocol[kind]
            if amount:
                ident = 'genesis-' + kind + '-' + job['id']
                if ident in expected:
                    raise ValueError('DUPLICATE_REGISTERED_JOB_ID')
                expected[ident] = (hour, amount)
    seen = {}
    for action in actions:
        if action.get('op') != 'cost':
            continue
        ident = action['args']['id']
        if not (ident.startswith('genesis-acquisition-') or
                ident.startswith('genesis-maintenance-')):
            continue
        if ident not in expected:
            raise ValueError('UNREGISTERED_OVERHEAD_COST')
        if ident in seen:
            raise ValueError('DUPLICATE_OVERHEAD_COST')
        if (action['day'], action['args']['amount']) != expected[ident]:
            raise ValueError('REGISTERED_COST_TIMING_OR_AMOUNT_CHANGED')
        seen[ident] = True
    if set(seen) != set(expected):
        raise ValueError('REGISTERED_OVERHEAD_COST_MISSING')
    return {'accepted': True, 'checked_costs': len(seen),
            'scope': 'READ_ONLY_CHRONOLOGY_WITNESS_NOT_A_CANONICAL_AUDIT'}


@unittest.skipUnless(NATIVE_AVAILABLE, 'Canonical native account required; no fake-ledger fallback')
class CostChronology098(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.output = self.root / 'account'
        self.protocol = json.loads(
            (ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json').read_text())

    def tearDown(self):
        self.temp.cleanup()

    def register(self):
        path = self.root / 'registered-protocol.json'
        path.write_bytes(canonical(self.protocol))
        native.register(ROOT, self.output, path)

    def observe(self):
        manifest = json.loads((self.output / 'MANIFEST.json').read_text())
        exported = json.loads((self.output / 'public/native-export.json').read_text())
        return manifest['jobs'], exported['ledger']['actions']

    def test_c0_exact_native_operation_and_witness_accept(self):
        self.register()
        outcome = native.operate(self.output)
        self.assertTrue(outcome['complete'])
        self.assertTrue(outcome['native_audit_accepted'])
        jobs, actions = self.observe()
        receipt = independent_overhead_chronology(self.protocol, jobs, actions)
        self.assertTrue(receipt['accepted'])
        self.assertEqual(receipt['checked_costs'], len(jobs) * 2)
        print('C0_NATIVE_AUDIT_ACCEPTED_AND_REGISTERED_CHRONOLOGY_VALID')

    def test_c1_wrong_first_acquisition_hour_with_canonical_native_history(self):
        from flexibility063.native import BusinessAccount
        self.register()
        original = BusinessAccount.cost
        changed = []
        def wrong_first_acquisition(account, ident, amount, hour):
            if ident.startswith('genesis-acquisition-') and not changed:
                self.assertEqual(hour, 24)
                changed.append((ident, hour, hour - 1))
                return original(account, ident, amount, hour - 1)
            return original(account, ident, amount, hour)
        with patch.object(BusinessAccount, 'cost', wrong_first_acquisition):
            try:
                outcome = native.operate(self.output)
            except ValueError as exc:
                self.assertEqual(len(changed), 1, 'injection must occur before source rejection')
                # A rejection is useful evidence, but do not claim that the
                # chronology witness has observed an exported accepted ledger.
                print('C1_CANONICAL_OPERATION_REJECTED:', type(exc).__name__, str(exc))
                return
        self.assertEqual(len(changed), 1)
        self.assertTrue(outcome['native_audit_accepted'])
        jobs, actions = self.observe()
        shifted = [a for a in actions if a.get('op') == 'cost' and
                   a['args']['id'] == changed[0][0]]
        self.assertEqual(len(shifted), 1)
        self.assertEqual(shifted[0]['day'], 23)
        with self.assertRaisesRegex(ValueError, 'REGISTERED_COST_TIMING_OR_AMOUNT_CHANGED'):
            independent_overhead_chronology(self.protocol, jobs, actions)
        print('C1_CANONICAL_AUDIT_ACCEPTED_WRONG_HOUR; INDEPENDENT_WITNESS_REJECTED')

    def test_c2_duplicate_synthetic_export_rejected(self):
        self.register()
        self.assertTrue(native.operate(self.output)['complete'])
        jobs, actions = self.observe()
        fake = copy.deepcopy(actions)
        overhead = next(a for a in fake if a.get('op') == 'cost' and
                        a['args']['id'].startswith('genesis-acquisition-'))
        fake.append(copy.deepcopy(overhead))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_OVERHEAD_COST'):
            independent_overhead_chronology(self.protocol, jobs, fake)
        print('C2_ONLY_KEYFREE_SYNTHETIC_COPY_MUTATED; WITNESS_REJECTED')

    def test_c3_one_micro_usd_synthetic_under_or_overcharge_rejected(self):
        self.register()
        self.assertTrue(native.operate(self.output)['complete'])
        jobs, actions = self.observe()
        fake = copy.deepcopy(actions)
        overhead = next(a for a in fake if a.get('op') == 'cost' and
                        a['args']['id'].startswith('genesis-acquisition-'))
        overhead['args']['amount'] += 1
        with self.assertRaisesRegex(ValueError, 'REGISTERED_COST_TIMING_OR_AMOUNT_CHANGED'):
            independent_overhead_chronology(self.protocol, jobs, fake)
        print('C3_ONLY_KEYFREE_SYNTHETIC_COPY_MUTATED; WITNESS_REJECTED')

    def test_c4_no_entry_still_accounts_for_registered_acquisition(self):
        self.protocol['offer']['value'] = 0
        self.register()
        outcome = native.operate(self.output)
        self.assertTrue(outcome['complete'])
        self.assertEqual(outcome['accepted_collected_deliveries'], 0)
        jobs, actions = self.observe()
        self.assertTrue(independent_overhead_chronology(self.protocol, jobs, actions)['accepted'])
        self.assertEqual(outcome['actual_revenue'], 0)
        print('C4_NO_ENTRY_STILL_INCURS_COSTS_AND_ZERO_ACTUAL_REVENUE')


if __name__ == '__main__':
    unittest.main()
