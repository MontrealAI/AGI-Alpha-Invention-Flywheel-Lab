"""Read-only diagnosis of exposed PR176 operating evidence, not an auditor.

Use after full native and corrected operating replay. This does not grant
investment authority, estimate counterfactual profit or manufacture buyer intent.
"""
import argparse
import json
from pathlib import Path


def inspect(account, state):
    skipped = [e for e in state['events']
               if e.get('decision') == 'CAPACITY_UNAVAILABLE_NO_CONTACT_OR_ORDER']
    # A response field on a purportedly uncontacted row is contradictory input.
    if any('buyer_response' in e for e in skipped):
        raise ValueError('UNCONTACTED_ROW_HAS_BUYER_RESPONSE')
    leases = []
    for row in account['connected_journal']['entries']:
        r = row['request']
        if r.get('operation') != 'spend' or r.get('kind') != 'capacity-lease':
            continue
        if row['status'] != 'COMPLETE':
            raise ValueError('CAPACITY_SPEND_NOT_COMPLETE')
        receipt = row['receipt']
        if receipt['amount'] != r['amount'] or receipt['id'] != r['id']:
            raise ValueError('CAPACITY_RECEIPT_MISMATCH')
        commands = [c['args'] for e in state['events'] for c in e['commands']
                    if c['op'] == 'spend' and c['args'].get('ident') == r['id']]
        if len(commands) != 1:
            raise ValueError('UNIQUE_CAPACITY_COMMAND_REQUIRED')
        command = dict(commands[0]); command['id'] = command.pop('ident')
        if command != {k:v for k,v in r.items() if k != 'operation'}:
            raise ValueError('CAPACITY_COMMAND_MISMATCH')
        leases.append({'id':r['id'], 'hour':r['day'], 'paid_microUSD':r['amount'],
                       'funding':receipt['funding'],
                       'declared_expected_net_microUSD':r['expected_net'],
                       'expected_net_equals_spend':r['expected_net'] == r['amount']})
    return {'capacity_skipped_without_buyer_response':len(skipped),
            'qualified_demand_from_skipped_rows':0, 'leases':leases,
            'capacity_paid_microUSD':sum(x['paid_microUSD'] for x in leases),
            'future_demand':None, 'counterfactual_profit':None,
            'decision':'Do not use capacity skips or spend-sized expected_net as demand/return estimates.',
            'scope':'exposed evidence diagnosis after full replay; no financial mutation'}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('case',type=Path);a=p.parse_args()
    print(json.dumps(inspect(json.loads((a.case/'account.json').read_text()),
                             json.loads((a.case/'operating.json').read_text())),sort_keys=True))
