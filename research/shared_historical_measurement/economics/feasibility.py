"""Conditional funding bounds, not prices, a financial ledger, or observed demand.

All monetary inputs must use one caller-declared currency/unit and one bounded
service horizon. None are estimated here. Numeric tests are mathematical fixtures.
"""
from dataclasses import dataclass
import math

COST_COMPONENTS = (
    'acquisition', 'setup', 'calibration', 'feature_execution',
    'model_work', 'verification', 'delivery', 'coordination', 'maintenance',
)


def nonnegative(x, name):
    if not math.isfinite(x) or x < 0:
        raise ValueError(f'{name} must be finite and nonnegative')
    return x


@dataclass(frozen=True)
class Requester:
    """Utility v-p; outside_net_utility includes best available alternative.

    A zero-cost leaked equivalent gives outside_net_utility == value. An
    equivalent rival at price r gives max(0, value-r). These are input scenarios,
    not assertions that either option exists. Budget limits payable transfer.
    """
    identity: str
    value: float | None
    budget: float | None
    outside_net_utility: float | None

    def cap(self):
        xs = (self.value, self.budget, self.outside_net_utility)
        for name, x in zip(('value', 'budget', 'outside_net_utility'), xs):
            if x is not None:
                nonnegative(x, name)
        if any(x is None for x in xs):
            return None
        return max(0.0, min(self.budget, self.value - self.outside_net_utility))


def complete_cost(components):
    """Missing/unknown expenses remain unknown, never silently become zero."""
    extra = set(components) - set(COST_COMPONENTS)
    if extra:
        raise ValueError(f'Unknown cost components: {sorted(extra)}')
    for key, value in components.items():
        if value is not None:
            nonnegative(value, key)
    missing = [k for k in COST_COMPONENTS if components.get(k) is None]
    return (None if missing else sum(components.values())), missing


def funding_region(requesters, components, enforceable_exclusion=False):
    """Fixed full allocation; transferable utility; nonstrategic known values.

    sum caps >= complete cost is necessary and sufficient for an individually
    rational, budget-respecting cost-covering transfer vector under these
    assumptions. This is NOT a truthful/coalition-proof commissioning mechanism.
    """
    ids = [r.identity for r in requesters]
    if any(not i for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('Nonempty, unique fixed requester identities required')
    caps = {r.identity: r.cap() for r in requesters}
    cost, missing = complete_cost(components)
    total = None if any(v is None for v in caps.values()) else sum(caps.values())
    rejects_full_allocation = [r.identity for r in requesters
                               if r.value is not None and r.outside_net_utility is not None
                               and r.value < r.outside_net_utility]
    status = 'unknown'
    if total is not None and cost is not None:
        status = 'conditionally_feasible' if total >= cost else 'infeasible'
    if rejects_full_allocation:
        status = 'infeasible'
    return {
        'status': status, 'payment_caps': caps, 'funding_cap': total,
        'requesters_rejecting_even_free_full_allocation': rejects_full_allocation,
        'complete_cost': cost, 'unpriced_cost_components': missing,
        'exclusion_assumption_satisfied': enforceable_exclusion,
        'implementable_transaction_established': False,
        'transfer_bound_only': True,
        'warning': ('No observed requester valuations or enforceable commitments are '
                    'established by this computation. If access is not excludable, '
                    'recompute outside utilities for leakage and strategic waiting.'),
    }


def comparative_region(separate_cost, ordinary_shared_cost, commissioning_cost, funding_cap):
    for name, x in locals().copy().items():
        if x is not None:
            nonnegative(x, name)
    if any(x is None for x in (separate_cost, ordinary_shared_cost, commissioning_cost, funding_cap)):
        return {'status': 'unknown'}
    return {
        'status': 'conditional_only',
        'separate_cost_recoverable': funding_cap >= separate_cost,
        'ordinary_shared_cost_recoverable': funding_cap >= ordinary_shared_cost,
        'commissioning_cost_recoverable': funding_cap >= commissioning_cost,
        'sharing_opens_region_vs_separate': ordinary_shared_cost <= funding_cap < separate_cost,
        'commissioning_opens_region_vs_ordinary_shared': commissioning_cost <= funding_cap < ordinary_shared_cost,
        'commissioning_overhead': commissioning_cost - ordinary_shared_cost,
    }
