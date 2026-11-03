"""Read-only unit and capacity sensitivities; never an account or sales forecast."""
from __future__ import annotations

from .commerce import COST_POLICY
from .seller import MICRO, OFFERS


def ceildiv(a, b):
    return (a + b - 1) // b


def economics():
    policy = COST_POLICY
    price = OFFERS['self_hosted']['price_usd'] * MICRO
    fee = ceildiv(price * policy['processing_bps'], 10000) + policy['processing_fixed_microUSD']
    unit = price - fee - policy['acquisition_microUSD']['self_hosted'] - policy['delivery_microUSD']['self_hosted']
    founder_rate = policy['founder_opportunity_microUSD_per_hour']
    exception = founder_rate * policy['exception_minutes'] // 60
    ticket = OFFERS['group_webinar']['price_usd'] * MICRO
    ticket_fee = ceildiv(ticket * policy['event_ticket_bps'], 10000) + policy['event_ticket_fixed_microUSD']
    ticket_unit = ticket - ticket_fee - policy['acquisition_microUSD']['group_webinar'] - policy['delivery_microUSD']['group_webinar']
    group_minutes = sum(policy['webinar_minutes'].values())
    group_cost = founder_rate * group_minutes // 60
    private_price = OFFERS['founder_private']['price_usd'] * MICRO
    private_fee = ceildiv(private_price * policy['processing_bps'], 10000) + policy['processing_fixed_microUSD']
    private_minutes = sum(policy['private_minutes'].values())
    private_unit = private_price - private_fee - policy['acquisition_microUSD']['founder_private'] - policy['delivery_microUSD']['founder_private'] - founder_rate * private_minutes // 60
    target = 3_000_000_000 * MICRO
    required = ceildiv(target, unit)
    founder_annual_minutes = 1600 * 60
    rows = []
    scenarios = [
        ('low_friction_unmeasured', 299, 25, 0, 0, 500),
        ('refund_and_exception_reference', 299, 25, 500, 100, 200),
        ('imitation_and_acquisition_pressure', 149, 75, 1000, 500, 100),
        ('adverse_not_worth_expanding', 99, 150, 2000, 1000, 50)]
    for name, dollars, cac, refunds_bps, exceptions_bps, conversion_bps in scenarios:
        p = dollars * MICRO
        processing = ceildiv(p * policy['processing_bps'], 10000) + policy['processing_fixed_microUSD']
        refund = ceildiv(p * refunds_bps, 10000)
        founder = ceildiv(exception * exceptions_bps, 10000)
        contribution = p - processing - cac * MICRO - policy['delivery_microUSD']['self_hosted'] - refund - founder
        orders = ceildiv(target, contribution) if contribution > 0 else None
        rows.append({'name': name, 'price_usd': dollars, 'acquisition_cost_per_order_usd': cac,
                     'acquisition_basis': 'Assumed CAC per paying buyer, including failed acquisition; not the workflow fixture per-explained-offer cost or an observed funnel.',
                     'refund_rate_bps': refunds_bps, 'founder_exception_rate_bps': exceptions_bps,
                     'assumed_conversion_bps': conversion_bps,
                     'contribution_before_fixed_unknown_costs_microUSD': contribution,
                     'orders_needed_before_fixed_unknown_costs': orders,
                     'qualified_visits_needed_at_assumed_conversion': ceildiv(orders * 10000, conversion_bps) if orders else None,
                     'founder_minutes_needed': ceildiv(orders * exceptions_bps * policy['exception_minutes'], 10000) if orders else None,
                     'empirical_demand': None, 'repeat_purchase_or_referral_assumed': False,
                     'financed_path_executed': False})
    return {'schema': 'omega/conditional-unit-economics/v1',
            'scope': 'READ_ONLY_AUTHORED_USD_SENSITIVITIES_NOT_NATIVE_PROFIT_OR_DEMAND',
            'currency': 'USD; commercial denomination unconfirmed',
            'acquisition_model': 'Per-paying-buyer CAC envelope includes unsuccessful acquisition. Workflow fixtures separately charge per explained offer, including declines. Neither measures demand or conversion.',
            'genesis': {'price_microUSD': price, 'processing_microUSD': fee,
                        'contribution_before_exceptions_fixed_and_unknown_costs_microUSD': unit,
                        'one_exception_cost_microUSD': exception,
                        'contribution_after_one_exception_microUSD': unit - exception},
            'webinar': {'per_seat_contribution_before_shared_founder_microUSD': ticket_unit,
                        'shared_founder_minutes': group_minutes, 'shared_founder_opportunity_microUSD': group_cost,
                        'breakeven_seats_before_unknown_costs': ceildiv(group_cost, ticket_unit),
                        'occupancy_scenarios': [{'seats': n, 'contribution_after_founder_before_unknown_costs_microUSD': n * ticket_unit - group_cost} for n in [25, 100, 151, 500]],
                        'capacity_is_not_demand': True},
            'private': {'total_founder_minutes': private_minutes,
                        'contribution_after_founder_before_unknown_costs_microUSD': private_unit},
            'annual_capacity_sensitivity': {'founder_available_hours_assumed': 1600,
                        'hours_are_unverified_and_alternatives_not_additive': True,
                        'all_time_private_sessions_upper_bound': founder_annual_minutes // private_minutes,
                        'all_time_private_gross_revenue_usd': (founder_annual_minutes // private_minutes) * 20000,
                        'all_time_full_webinars_upper_bound': founder_annual_minutes // group_minutes,
                        'all_time_full_webinars_gross_revenue_usd': (founder_annual_minutes // group_minutes) * 500 * 99,
                        'other_founder_work_budget_minutes': 0,
                        'warning': 'Optimistic capacity ceilings under this availability; no demand and no time left for other work.'},
            'target_arithmetic': {'target_profit_usd': 3_000_000_000,
                        'zero_cost_299_sales_necessary': ceildiv(target, price),
                        'declared_unit_contribution_sales_necessary_before_fixed_costs': required,
                        'maximum_exception_rate_numerator': founder_annual_minutes,
                        'maximum_exception_rate_denominator': required * policy['exception_minutes'],
                        'same_account_365_day_execution': False},
            'favorable_and_adverse_scenarios': rows,
            'buyer_value_before_fees': None, 'buyer_net_benefit_after_adoption_and_operation': None,
            'fully_loaded_seller_profit': None, 'available_reinvestment_cash': None,
            'unknowns': policy['unknown_complete_costs'],
            'cost_treatment': {k: policy[k] for k in ('capex_policy', 'depreciation_policy', 'financing_policy')},
            'no_financial_state_or_primary_account_postings': True}
