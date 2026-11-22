"""Read-only complete-offer comparison, never spending or predicted demand."""
COSTS = ('construction', 'acquisition', 'onboarding', 'production', 'verification',
         'correction', 'distribution', 'capacity', 'support', 'refund_loss',
         'liability_tail', 'tax', 'financing', 'shutdown', 'host_model')


def compare(*, costs, price, buyer_value, buyer_budget, outside_surplus,
            available, earned, consent, acceptance):
    """All amounts are integer microUSD; costs are a whole-delivery downside.

    Acquisition/construction are included even if sunk; no future collection
    funds the commitment. A result is a conditional authored quote, not a
    calibrated expected_net or authority to change an immutable native catalog.
    Unknown cost remains unknown. No capacity inference from uncontacted leads.
    """
    if set(costs) != set(COSTS):
        raise ValueError('COMPLETE_COST_CATEGORIES_REQUIRED')
    amounts = [price, buyer_value, buyer_budget, outside_surplus, available, earned]
    if any(type(n) is not int or n < 0 for n in amounts):
        raise ValueError('NONNEGATIVE_EXACT_MONEY_REQUIRED')
    if any(v is not None and (type(v) is not int or v < 0) for v in costs.values()):
        raise ValueError('NONNEGATIVE_EXACT_COST_OR_UNKNOWN_REQUIRED')
    if type(consent) is not bool or type(acceptance) is not bool:
        raise ValueError('EXPLICIT_CONSENT_AND_ACCEPTANCE_REQUIRED')
    reasons = []
    unknown = [k for k in COSTS if costs[k] is None]
    total = None if unknown else sum(costs.values())
    net = None if total is None else price-total
    if unknown: reasons.append('UNKNOWN_COMPLETE_COST')
    if not consent: reasons.append('NO_VOLUNTARY_CONSENT')
    if buyer_budget < price or buyer_value-price <= outside_surplus:
        reasons.append('BUYER_OUTSIDE_OPTION_WINS_OR_TIES')
    if not acceptance: reasons.append('NO_ACCEPTED_TYPED_OUTPUT')
    if net is not None and net <= 0: reasons.append('NO_POSITIVE_COMPLETE_SURPLUS')
    if total is not None and min(available, earned) < total:
        reasons.append('WHOLE_DELIVERY_NOT_EARNED_FUNDED')
    # There is intentionally no flag to assert this dependency away.
    reasons.append('NATIVE_CATALOG_TRANSITION_UNQUALIFIED')
    return {'admitted': False, 'reasons': reasons, 'unknown_costs': unknown,
            'whole_delivery_microUSD': total, 'conditional_surplus_microUSD': net,
            'economic_conditions_met': len(reasons) == 1,
            'forecast_expected_net': None, 'native_mutations': 0,
            'scope': 'finite authored offer comparison, not market calibration'}
