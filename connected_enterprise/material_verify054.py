"""Independent exact checks for authored one-dimensional material plans.

No optimizer or producer is imported. These checks establish consistency with
the supplied simulation inputs, not material quality, custody or physical cuts.
Hashes bind evidence bytes; they do not establish that a physical claim is true.
"""
from __future__ import annotations

import hashlib
import json


SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
ORDER_FIELDS = {'schema', 'scope', 'order_id', 'kerf_mm', 'min_remnant_mm',
                'stocks', 'pieces'}
STOCK_FIELDS = {'id', 'length_mm', 'grade', 'source_sha256', 'cost_microUSD'}
PIECE_FIELDS = {'id', 'length_mm', 'grade'}
PLAN_FIELDS = {'schema', 'order_id', 'scope', 'input_sha256', 'patterns',
               'unused_stock_ids', 'remnants', 'material_cost_microUSD',
               'consumed_mm'}
PATTERN_FIELDS = {'stock_id', 'piece_ids', 'used_mm', 'remnant_mm'}
REMNANT_FIELDS = STOCK_FIELDS | {'parent_stock_id'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _safe_digest(value):
    try:
        return digest(value)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return None


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hex(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in '0123456789abcdef' for c in value))


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _unique_text_list(value, *, nonempty=False):
    return (type(value) is list and (not nonempty or bool(value))
            and all(_text(item) for item in value)
            and len(set(value)) == len(value))


def validate_order(raw):
    """Validate only declared input structure and exact nonnegative quantities."""
    _require(type(raw) is dict and set(raw) == ORDER_FIELDS, 'EXACT_ORDER_FIELDS_REQUIRED')
    _require(raw['schema'] == 'material054/order/v1' and raw['scope'] == SCOPE,
             'MATERIAL_ORDER_SCOPE_REQUIRED')
    _require(_text(raw['order_id']), 'ORDER_ID_REQUIRED')
    _require(_integer(raw['kerf_mm']) and _integer(raw['min_remnant_mm'], 1),
             'EXACT_KERF_AND_REMNANT_LENGTH_REQUIRED')
    for name, fields in [('stocks', STOCK_FIELDS), ('pieces', PIECE_FIELDS)]:
        rows = raw[name]
        _require(type(rows) is list, 'DECLARED_SOURCE_LIST_REQUIRED:' + name)
        identifiers = set()
        for row in rows:
            _require(type(row) is dict and set(row) == fields,
                     'EXACT_SOURCE_ROW_REQUIRED:' + name)
            _require(_text(row['id']) and row['id'] not in identifiers,
                     'UNIQUE_SOURCE_ID_REQUIRED:' + name)
            identifiers.add(row['id'])
            _require(_integer(row['length_mm'], 1) and _text(row['grade']),
                     'POSITIVE_LENGTH_AND_GRADE_REQUIRED:' + name)
            if name == 'stocks':
                _require(_integer(row['cost_microUSD']) and _hex(row['source_sha256']),
                         'SOURCE_HASH_AND_EXACT_STOCK_COST_REQUIRED')
    return raw


def _check(raw, artifact):
    validate_order(raw)
    _require(type(artifact) is dict and set(artifact) == PLAN_FIELDS,
             'EXACT_PLAN_FIELDS_REQUIRED')
    _require(artifact['schema'] == 'material054/plan/v1'
             and artifact['scope'] == SCOPE
             and artifact['order_id'] == raw['order_id'], 'PLAN_SCOPE_OR_ORDER_CHANGED')
    input_hash = digest(raw)
    _require(artifact['input_sha256'] == input_hash, 'INPUT_BINDING_CHANGED')
    _require(type(artifact['patterns']) is list and type(artifact['remnants']) is list,
             'DECLARED_PATTERNS_AND_REMNANTS_REQUIRED')
    _require(_unique_text_list(artifact['unused_stock_ids']), 'UNIQUE_UNUSED_STOCKS_REQUIRED')
    _require(_integer(artifact['material_cost_microUSD'])
             and _integer(artifact['consumed_mm']), 'EXACT_PLAN_TOTALS_REQUIRED')
    stocks = {row['id']: row for row in raw['stocks']}
    pieces = {row['id']: row for row in raw['pieces']}
    used_stocks, used_pieces = set(), set()
    expected_remnants = {}
    material_cost = consumed = 0
    for row in artifact['patterns']:
        _require(type(row) is dict and set(row) == PATTERN_FIELDS,
                 'EXACT_PATTERN_FIELDS_REQUIRED')
        stock_id = row['stock_id']
        _require(_text(stock_id) and stock_id in stocks and stock_id not in used_stocks,
                 'UNIQUE_EXISTING_PATTERN_STOCK_REQUIRED')
        _require(_unique_text_list(row['piece_ids'], nonempty=True)
                 and row['piece_ids'] == sorted(row['piece_ids']),
                 'SORTED_UNIQUE_NONEMPTY_PATTERN_PIECES_REQUIRED')
        _require(_integer(row['used_mm']) and _integer(row['remnant_mm']),
                 'EXACT_PATTERN_LENGTHS_REQUIRED')
        stock = stocks[stock_id]
        used = 0
        for piece_id in row['piece_ids']:
            _require(piece_id in pieces and piece_id not in used_pieces,
                     'EACH_REQUESTED_PIECE_EXACTLY_ONCE')
            piece = pieces[piece_id]
            _require(piece['grade'] == stock['grade'], 'MATERIAL_GRADE_MISMATCH')
            used += piece['length_mm'] + raw['kerf_mm']
            used_pieces.add(piece_id)
        remaining = stock['length_mm'] - used
        _require(remaining >= 0, 'PATTERN_OVERCUTS_STOCK')
        _require(row['used_mm'] == used and row['remnant_mm'] == remaining,
                 'CUT_AND_REMNANT_CONSERVATION_MISMATCH')
        used_stocks.add(stock_id)
        material_cost += stock['cost_microUSD']
        consumed += used
        if remaining >= raw['min_remnant_mm']:
            remnant_id = raw['order_id'] + ':' + stock_id + ':remnant'
            expected_remnants[remnant_id] = {
                'id': remnant_id, 'parent_stock_id': stock_id,
                'length_mm': remaining, 'grade': stock['grade'],
                'source_sha256': digest({'input_sha256': input_hash, 'stock_id': stock_id,
                                         'piece_ids': row['piece_ids'], 'remnant_mm': remaining}),
                'cost_microUSD': 0}
    _require(used_pieces == set(pieces), 'REQUESTED_PIECE_COVERAGE_MISMATCH')
    unused = set(artifact['unused_stock_ids'])
    _require(not (used_stocks & unused) and used_stocks | unused == set(stocks),
             'EXACT_STOCK_PARTITION_REQUIRED')
    remnants = {}
    for row in artifact['remnants']:
        _require(type(row) is dict and set(row) == REMNANT_FIELDS,
                 'EXACT_REMNANT_FIELDS_REQUIRED')
        _require(_text(row['id']) and row['id'] not in remnants, 'UNIQUE_REMNANT_ID_REQUIRED')
        _require(_text(row['parent_stock_id']) and _integer(row['length_mm'], 1)
                 and _text(row['grade']) and _hex(row['source_sha256'])
                 and _integer(row['cost_microUSD']), 'EXACT_REMNANT_VALUES_REQUIRED')
        remnants[row['id']] = row
    _require(remnants == expected_remnants, 'REMNANT_PROVENANCE_OR_COVERAGE_MISMATCH')
    _require(artifact['material_cost_microUSD'] == material_cost
             and artifact['consumed_mm'] == consumed, 'MATERIAL_TOTALS_MISMATCH')


def audit_plan(raw, artifact):
    """Check feasibility/conservation, not optimality or physical provenance."""
    errors = []
    try:
        _check(raw, artifact)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        errors.append(str(error))
    return {'accepted': not errors, 'errors': errors,
            'input_sha256': _safe_digest(raw), 'artifact_sha256': _safe_digest(artifact)}


def audit_transfer(parent_raw, parent_artifact, next_raw):
    """Check a two-order evidence link; this is not a global inventory ledger.

    Parent remnants have a parent_stock_id field absent from order stocks. Their
    exact stock-field projection must transfer unchanged. Unrelated fresh source
    stocks are allowed. Previously consumed parent stock cannot be reused.
    """
    errors = []
    try:
        parent = audit_plan(parent_raw, parent_artifact)
        _require(parent['accepted'], 'PARENT_PLAN_NOT_ACCEPTED')
        validate_order(next_raw)
        _require(next_raw['order_id'] != parent_raw['order_id'], 'DISTINCT_SUCCESSOR_ORDER_REQUIRED')
        prefix = parent_raw['order_id'] + ':'
        remnants = {row['id']: {key: row[key] for key in STOCK_FIELDS}
                    for row in parent_artifact['remnants']}
        known_hashes = {row['source_sha256']: ident for ident, row in remnants.items()}
        original = {row['id']: row for row in parent_raw['stocks']}
        consumed = {row['stock_id'] for row in parent_artifact['patterns']}
        for stock in next_raw['stocks']:
            ident = stock['id']
            _require(ident not in consumed, 'CONSUMED_PARENT_STOCK_REUSED')
            if ident.startswith(prefix) or stock['source_sha256'] in known_hashes:
                _require(ident in remnants and stock == remnants[ident],
                         'EXACT_PARENT_REMNANT_TRANSFER_REQUIRED')
            if ident in original:
                _require(stock == original[ident], 'UNUSED_PARENT_STOCK_CHANGED')
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        errors.append(str(error))
    return {'accepted': not errors, 'errors': errors,
            'parent_input_sha256': _safe_digest(parent_raw),
            'parent_artifact_sha256': _safe_digest(parent_artifact),
            'next_input_sha256': _safe_digest(next_raw)}
