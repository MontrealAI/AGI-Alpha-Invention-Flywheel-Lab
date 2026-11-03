"""Independent, key-free contractual expense completeness witness for Omega PR201.

Additive research verifier. Uses the ORIGINAL JournalAccount journal and immutable
native export; it never creates, edits, signs, or replays accounts. Finance replay
is still necessary but insufficient by itself to establish omitted obligations.
"""
from pathlib import Path

from connected_enterprise.finance import audit_journal
from . import inventor_native as owner


class CostWitnessError(ValueError):
    pass


def _require(condition, code):
    if not condition:
        raise CostWitnessError(code)


def verify(output, result, indexes=None):
    """Prove that declared fee, maintenance and tax expenses appear exactly once.

    Requires a separately validated complete owner `audit_operation` for buyer
    and service semantics. This witness does not substitute a new ledger or
    permit funding. Native signed exports are read-only.
    """
    output = Path(output)
    indexes = tuple(owner.INDEXES if indexes is None else indexes)
    _require(len(indexes) == len(set(indexes)), 'UNIQUE_REGISTERED_INDEXES_REQUIRED')
    manifest = owner.read(output / 'MANIFEST.json')
    exported = owner.read(output / 'NATIVE_EXPORT.json')
    independently_audited = audit_journal(exported, root=output / 'runtime', manifest=manifest)
    _require(independently_audited == result['native_audit'],
             'INDEPENDENT_NATIVE_AUDIT_MISMATCH')
    _require(exported['ledger']['summary'] == result['native_summary'],
             'NATIVE_SUMMARY_MISMATCH')
    _require(result['contract'] == owner.CONTRACT and result['tariff'] == owner.TARIFF,
             'FROZEN_CONTRACT_OR_TARIFF_MISMATCH')
    acts = exported['ledger']['actions']
    costs = {}
    for sequence, action in enumerate(acts):
        if action['op'] == 'cost':
            ident = action['args']['id']
            costs.setdefault(ident, []).append((sequence, action))
    def one_cost(ident, amount, day):
        matches = costs.get(ident, [])
        _require(len(matches) == 1, 'REQUIRED_COST_NOT_EXACTLY_ONCE:' + ident)
        seq, action = matches[0]
        _require(action['args']['amount'] == amount and action['day'] == day,
                 'CONTRACTUAL_COST_AMOUNT_OR_DAY_CHANGED:' + ident)
        return seq, action

    expected_fees = set()
    fee_sequences = []
    for ordinal, index in enumerate(indexes):
        record = owner.read(output / ('order-%03d.json' % index))
        expected_day = 1 + 20 * ordinal
        _require(record['index'] == index and record['day'] == expected_day,
                 'REGISTERED_ORDER_SCHEDULE_CHANGED')
        if record['status'] != 'SETTLED':
            _require(record['complete'] is False, 'REFUSAL_COMPLETENESS_CHANGED')
            continue
        _require(record['complete'] is True, 'SETTLED_COMPLETENESS_CHANGED')
        _require(type(record['price']) is int and record['price'] > 0,
                 'SETTLED_PRICE_REQUIRED')
        expected_fee = (record['price'] * owner.TARIFF['payment_bps'] + 9999) // 10000
        _require(record['fee'] == expected_fee, 'CONTRACTUAL_FEE_REPORT_CHANGED')
        ident = 'fee-' + str(index)
        fee_seq, _ = one_cost(ident, expected_fee, expected_day)
        expected_fees.add(ident)
        fee_sequences.append(fee_seq)
        trade_id = 'omega-trade-' + str(index)
        release_sequences = [
            seq for seq, action in enumerate(acts)
            if action['op'] == 'event' and action['args'].get('id') == trade_id
            and action['args'].get('action') == 'release'
        ]
        _require(len(release_sequences) == 1 and fee_seq < release_sequences[0],
                 'FEE_REQUIRED_BEFORE_SETTLEMENT:' + ident)
    actual_fees = {ident for ident in costs if ident.startswith('fee-')}
    _require(actual_fees == expected_fees, 'UNDECLARED_OR_ABSENT_COLLECTION_FEES')

    maintenance_seq, maintenance = one_cost(
        'annual-maintenance', owner.TARIFF['annual_maintenance'], 364)
    tax_matches = costs.get('modeled-tax', [])
    _require(len(tax_matches) == 1, 'MODELED_TAX_NOT_EXACTLY_ONCE')
    tax_seq, tax = tax_matches[0]
    expected_tax = max(0, tax['before']['profit']) * owner.TARIFF['tax_bps'] // 10000
    _require(tax['args']['amount'] == expected_tax and tax['day'] == 364,
             'PRETAX_PROFIT_TAX_AMOUNT_OR_DATE_CHANGED')
    tax_path = output / 'TAX.json'
    _require(tax_path.is_file() and owner.read(tax_path) == {'amount': expected_tax},
             'FROZEN_TAX_SOURCE_MISMATCH')
    _require(maintenance_seq < tax_seq and all(seq < maintenance_seq for seq in fee_sequences),
             'ANNUAL_CLOSE_COST_ORDER_CHANGED')
    return {
        'accepted': True,
        'scope': 'SIGNED_NATIVE_LEDGER_PLUS_PROJECT_SPECIFIC_CONTRACTUAL_COST_COMPLETENESS_ONLY',
        'settled_fee_count': len(expected_fees),
        'annual_maintenance_microUSD': maintenance['args']['amount'],
        'modeled_tax_microUSD': expected_tax,
        'actual_commerce': False,
        'economic_advantage_or_annual_target': False,
    }
