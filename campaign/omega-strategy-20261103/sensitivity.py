"""Reproduce development sensitivities without opening or funding an account.

The protocol was fixed before these supplementary calculations. This is a
read-only planner comparison, not the registered native commercial experiment.
"""
from collections import Counter
from dataclasses import replace
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import resource
import time

from omega import market


def run(protocol):
    start, cpu = time.monotonic(), time.process_time()
    rows = []
    for variation in protocol['variants']:
        values = dict(variation)
        ident = values.pop('id')
        rates = replace(market.Rates(), **values)
        for mode in market.POLICIES:
            plans = [market.simulate(case, mode, rates=rates)
                     for case in market.registered_cases(development=True)]
            prof = [x['economic_profit_cents'] for x in plans]
            actions = Counter(s['action']['kind'] for x in plans for s in x['trace'])
            rows.append({
                'variant': ident, 'policy': mode, 'case_count': len(plans),
                'min_plan_economic_profit_cents': min(prof),
                'max_plan_economic_profit_cents': max(prof),
                'positive_plan_cases': sum(v > 0 for v in prof),
                'selected_actions': dict(actions),
                'selected_process_packages': sum(s['action']['construct_process']
                                                 for x in plans for s in x['trace']),
                'plan_hashes': [market.digest(x) for x in plans],
                'native_postings': 0,
            })
    bounds = []
    for channel in ('community', 'partner'):
        cost = sum(market.variable_costs('self_hosted', 29900, channel).values())
        after_tax = Decimal(29900 - cost) * Decimal('0.75') / 100
        n = int((Decimal(3_000_000_000) / after_tax).to_integral_value(rounding=ROUND_CEILING))
        bounds.append({
            'channel': channel, 'price_USD': 299, 'variable_cost_USD': cost / 100,
            'after_tax_unit_margin_USD': str(after_tax),
            'minimum_successful_nonrefunded_software_sales_in_same365days': n,
            'assumptions': '25% annual tax; omits acquisition, fixed costs, failures, remedies beyond envelope and owner time. Necessary optimistic bound, not sufficient funded scale or demand.',
        })
    return {
        'schema': 'omega/supplementary-cost-sensitivity-result/v1',
        'protocol_sha256': market.digest(protocol),
        'source_commit': protocol['source_commit'], 'scope': protocol['role'],
        'source_policy_changed': False, 'native_accounts_created': 0,
        'native_postings': 0, 'rows': rows,
        'software_necessary_volume_bounds': bounds,
        'telemetry': {'wall_seconds': time.monotonic() - start,
                      'cpu_seconds': time.process_time() - cpu,
                      'maximum_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      'not_business_billing_or_human_labor': True},
    }


if __name__ == '__main__':
    protocol = json.loads(Path(__file__).with_name('SENSITIVITY_PROTOCOL.json').read_text())
    print(json.dumps(run(protocol), indent=2, sort_keys=True))
