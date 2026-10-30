"""Read-only period reconciliation of conditional scale projections."""
import hashlib
import json

TARGET_CENTS = 300_000_000_000


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _integer(value, name, signed=False):
    if type(value) is not int or (not signed and value < 0):
        raise ValueError('INTEGER_CENTS_OR_COUNT_REQUIRED:' + name)
    return value


def reconcile(run, config, target_cents=TARGET_CENTS):
    _integer(target_cents, 'target')
    if target_cents == 0: raise ValueError('POSITIVE_PROFIT_TARGET_REQUIRED')
    if run.get('scope') != 'CONDITIONAL_SCALE_PROJECTION' or config.get('money_unit') != 'cents' or config.get('currency') != 'USD':
        raise ValueError('EXPLICIT_USD_CENT_PROJECTION_REQUIRED')
    if run.get('config_sha256') != identity(config): raise ValueError('CONFIG_IDENTITY_MISMATCH')
    monthly = run.get('monthly')
    if not isinstance(monthly, list) or run.get('months_completed') != len(monthly):
        raise ValueError('CONTIGUOUS_MONTHS_REQUIRED')
    opening = _integer(config['opening_cash_cents'], 'opening_cash')
    profits, revenues, costs, collections = [0], [0], [0], [0]
    prior = {'recognized': 0, 'cost': 0, 'collected': 0}
    periods, counts = [], []
    for number, row in enumerate(monthly, 1):
        if type(row.get('month')) is not int or row['month'] != number: raise ValueError('CONTIGUOUS_MONTHS_REQUIRED')
        for key in ['cumulative_recognized_revenue_cents', 'cumulative_cost_cents', 'cumulative_collected_revenue_cents',
                    'cash_cents', 'restricted_cash_cents', 'available_cash_cents', 'collected_revenue_cents',
                    'executed_projection_attempts', 'accepted_projection_work_products', 'collected_projection_jobs']:
            _integer(row[key], key)
        p = _integer(row['cumulative_profit_cents'], 'profit', signed=True)
        r, c, k = (row[x] for x in ['cumulative_recognized_revenue_cents', 'cumulative_cost_cents', 'cumulative_collected_revenue_cents'])
        if any(value < prior[name] for name, value in [('recognized', r), ('cost', c), ('collected', k)]):
            raise ValueError('NONMONOTONE_CUMULATIVE_COMPONENT')
        if p != r - c: raise ValueError('PROFIT_COMPONENT_MISMATCH')
        if row['cash_cents'] != opening + k - c: raise ValueError('CASH_CONSERVATION_MISMATCH')
        if row['available_cash_cents'] != row['cash_cents'] - row['restricted_cash_cents']:
            raise ValueError('AVAILABLE_CASH_MISMATCH')
        if row['collected_revenue_cents'] != k - prior['collected']:
            raise ValueError('COLLECTION_PERIOD_MISMATCH')
        if not 0 <= row['collected_projection_jobs'] <= row['accepted_projection_work_products'] <= row['executed_projection_attempts']:
            raise ValueError('PROJECTION_QUALITY_COUNT_MISMATCH')
        profits.append(p); revenues.append(r); costs.append(c); collections.append(k)
        counts.append(row['collected_projection_jobs'])
        if number >= 12:
            delta = p - profits[number - 12]
            component_profit = sum((revenues[i] - revenues[i-1]) - (costs[i] - costs[i-1]) for i in range(number-11, number+1))
            if delta != component_profit: raise ValueError('PERIOD_PROFIT_MISMATCH')
            periods.append({'end_month': number, 'recognized_revenue_cents': r - revenues[number-12],
                'cost_cents': c - costs[number-12], 'accrual_profit_cents': delta,
                'collected_revenue_cents': k - collections[number-12],
                'net_collected_less_expenses_cents': k - collections[number-12] - c + costs[number-12]})
        prior = {'recognized': r, 'cost': c, 'collected': k}
    terminal_cost = _integer(run['cumulative_cost_cents'], 'terminal_cost')
    terminal_collected = _integer(run['cumulative_collected_revenue_cents'], 'terminal_collected')
    terminal_profit = _integer(run['cumulative_profit_cents'], 'terminal_profit', signed=True)
    terminal_cash = _integer(run['ending_cash_cents'], 'terminal_cash')
    receivables = _integer(run['terminal_receivables_cents'], 'receivables')
    reserve = _integer(run['restricted_cash_cents'], 'terminal_reserve')
    if terminal_cash != opening + terminal_collected - terminal_cost: raise ValueError('TERMINAL_CASH_MISMATCH')
    if terminal_profit != terminal_collected + receivables - terminal_cost: raise ValueError('TERMINAL_RECOGNITION_MISMATCH')
    if run['ending_unrestricted_cash_cents'] != terminal_cash - reserve or terminal_cash < reserve:
        raise ValueError('TERMINAL_AVAILABLE_MISMATCH')
    residual = {'cost_cents': terminal_cost - costs[-1], 'collected_cents': terminal_collected - collections[-1],
                'profit_cents': terminal_profit - profits[-1]}
    if run['cash_survival'] and (len(monthly) != config['months'] or any(residual.values())):
        raise ValueError('INCOMPLETE_SURVIVING_TRAJECTORY')
    crossings = [x['end_month'] for x in periods if x['accrual_profit_cents'] >= target_cents]
    delay = 0 if run.get('intervention', {}).get('settlement') == 'same_period' else max(1, config['settlement_months'])
    settled = sum(count for month, count in enumerate(counts, 1) if month + delay <= len(monthly))
    return {'schema': 'agi-alpha/profit-horizon018/v1', 'scope': run['scope'], 'seed': run['seed'],
        'target_profit_cents': target_cents, 'months_completed': len(monthly), 'requested_months': config['months'],
        'cash_survival': run['cash_survival'], 'terminal_reason': run['terminal_reason'],
        'first_trailing_12_profit_crossing_month': min(crossings) if crossings else None,
        'crossing_status': 'REACHED' if crossings else 'HORIZON_NONCROSSING' if run['cash_survival'] else 'FAILED_BEFORE_HORIZON',
        'latest_complete_12_month_period': periods[-1] if periods else None,
        'profit_periods': periods, 'terminal_partial_month_residual': residual,
        'cumulative_profit_cents': terminal_profit, 'cumulative_cost_cents': terminal_cost,
        'cumulative_collected_cents': terminal_collected, 'available_cash_cents': terminal_cash - reserve,
        'restricted_cash_cents': reserve, 'terminal_receivables_cents': receivables,
        'accepted_projection_work_products': sum(r['accepted_projection_work_products'] for r in monthly),
        'invoice_projection_net_paid_jobs': sum(counts), 'settled_projection_jobs_by_recorded_month': settled,
        'payables': None, 'unmodeled_obligations': 'UNKNOWN; projection has no native payable or permanent liability model',
        'monthly_sha256': identity(monthly),
        'accounting_basis': 'Accrual net revenue minus modeled cash expenses; capacity and development outlays expensed immediately. Income taxes, amortization and unmodeled liabilities are not supplied by this model. Not audited native profit.'}


def cost_sensitivity(period, extra_cost_bps, income_tax_bps):
    if any(type(v) is not int or not 0 <= v <= 10000 for v in [extra_cost_bps, income_tax_bps]):
        raise ValueError('BOUNDED_SENSITIVITY_BPS_REQUIRED')
    extra = (period['cost_cents'] * extra_cost_bps + 9999) // 10000
    before_tax = period['accrual_profit_cents'] - extra
    tax = (max(0, before_tax) * income_tax_bps + 9999) // 10000
    return {'extra_cost_bps': extra_cost_bps, 'income_tax_bps': income_tax_bps, 'extra_cost_cents': extra,
            'tax_cents': tax, 'profit_after_sensitivity_cents': before_tax - tax,
            'scope': 'STATIC_ACCOUNTING_SENSITIVITY; growth, financing, choices and tax applicability not reevaluated'}
