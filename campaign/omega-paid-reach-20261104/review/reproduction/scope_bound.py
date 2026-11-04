"""Optimistic gross-collections bound from public type supports; no private draw."""
import sys
from pathlib import Path
import json

# The reproduction tools live four directories below the repository root.
root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(root))
from mechanism_harness.cart_campaign import CASES
from mechanism_harness.market_cases import market
from mechanism_harness.reach_policy import PROSPECTS, ORGANIC_ROSTER
from connected_enterprise.channels import default_contracts


def max_payment(t):
    # Voluntary selection requires strictly positive net utility above outside.
    return max(0, min(t['budget_cents'], max(t['values'][1:]) - t['outside_utility'] - 1))


def bound():
    markets = [market(seed, family) for seed, family in CASES]
    warm = sum(max_payment(t) for m in markets for t in m['types'])
    support = markets[0]['types']
    owned = default_contracts()['pilot']['owned_audience_count']
    assert set(sorted(PROSPECTS)[:owned]) <= set(ORGANIC_ROSTER)
    one_contact = owned * max(map(max_payment, support))
    other_lifetimes = (len(PROSPECTS) - owned) * 2 * max(t['budget_cents'] for t in support)
    return {'units': 'US cents', 'warm': warm, 'four_organic_only': one_contact,
            'other_twenty_lifetime_wallets': other_lifetimes,
            'max_collections_before_any_expense': warm + one_contact + other_lifetimes}


if __name__ == '__main__':
    print(json.dumps(bound(), sort_keys=True))
