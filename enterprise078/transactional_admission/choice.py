"""Exact offered-package participation, without inferred additive buyer values."""
import json

ALTERNATIVES = frozenset(('human', 'competitor_ai', 'self_service', 'no_purchase'))


def money(value):
    if type(value) is not int or value < 0:
        raise ValueError('EXACT_NONNEGATIVE_MONEY_REQUIRED')
    return value


def subset_key(ids):
    ids = tuple(ids)
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('DISTINCT_NAMED_OFFERS_REQUIRED')
    return json.dumps(sorted(ids), separators=(',', ':'), ensure_ascii=True)


def quote(rows):
    """Consent binds offer identity, exact total prices and declared contract terms."""
    return {row['id']: {'price': row['price'], 'terms_id': row['terms_id']} for row in rows}


def participation(rows, choices):
    """Missing exact-package evidence refuses; malformed evidence raises.

    Outside utilities are net of the alternative's own complete price/friction,
    in the same buyer utility/microUSD scale, not its gross value. Every package
    is a mutually exclusive proposal, not a simultaneously available menu.
    An explicitly unavailable alternative is {'available': False}; missing or
    unknown utility is not zero. No-purchase must always remain available.
    """
    reasons = []
    by_buyer = {}
    for row in rows:
        by_buyer.setdefault(row['buyer'], []).append(row)
    for buyer, buyer_rows in by_buyer.items():
        evidence = choices.get(buyer, {}) if isinstance(choices, dict) else {}
        if not isinstance(evidence, dict):
            raise ValueError('EXPLICIT_BUYER_CHOICE_MAP_REQUIRED')
        entry = evidence.get(subset_key(r['id'] for r in buyer_rows))
        if entry is None:
            reasons.append('WHOLE_BUYER_CHOICE_UNESTABLISHED:' + buyer)
            continue
        if not isinstance(entry, dict) or set(entry) != {'joint_value', 'outside', 'consent', 'quote'}:
            raise ValueError('EXACT_BUYER_CHOICE_FIELDS_REQUIRED')
        money(entry['joint_value'])
        if type(entry['consent']) is not bool:
            raise ValueError('EXPLICIT_WHOLE_BUYER_CONSENT_REQUIRED')
        expected_quote = quote(buyer_rows)
        offered = entry['quote']
        # Equality alone would allow True == 1 in an exact-price consent receipt.
        if not isinstance(offered, dict):
            raise ValueError('EXACT_BUYER_QUOTE_REQUIRED')
        for value in offered.values():
            if not isinstance(value, dict) or set(value) != {'price', 'terms_id'}:
                raise ValueError('EXACT_BUYER_QUOTE_REQUIRED')
            money(value['price'])
            if not isinstance(value['terms_id'], str) or not value['terms_id']:
                raise ValueError('DECLARED_TERMS_ID_REQUIRED')
        if offered != expected_quote:
            reasons.append('WHOLE_BUYER_QUOTE_CHANGED:' + buyer)
        outside = entry['outside']
        if not isinstance(outside, dict) or set(outside) != ALTERNATIVES:
            reasons.append('COMPLETE_OUTSIDE_OPTIONS_UNESTABLISHED:' + buyer)
            continue
        utilities = []
        for alternative, value in outside.items():
            if isinstance(value, dict) and set(value) == {'available'} and value['available'] is False:
                if alternative == 'no_purchase':
                    raise ValueError('NO_PURCHASE_MUST_REMAIN_AVAILABLE')
                continue
            utilities.append(money(value))
        if not entry['consent']:
            reasons.append('NO_WHOLE_BUYER_CONSENT:' + buyer)
        total = sum(row['price'] for row in buyer_rows)
        if entry['joint_value'] - total <= max(utilities):
            reasons.append('BUYER_OUTSIDE_OPTION_WINS_OR_TIES:' + buyer)
    return reasons


def registered_rows(rows, wallets):
    by_id = {}
    for row in rows:
        ident = row['id']
        if not isinstance(ident, str) or not ident or ident in by_id:
            raise ValueError('UNIQUE_OFFER_REQUIRED')
        if not isinstance(row['buyer'], str) or not row['buyer'] or row['buyer'] not in wallets:
            raise ValueError('EXPLICIT_FINITE_WALLET_REQUIRED')
        if not isinstance(row.get('terms_id'), str) or not row['terms_id']:
            raise ValueError('DECLARED_TERMS_ID_REQUIRED')
        money(row['price'])
        partner = row.get('partner')
        if partner is not None and (not isinstance(partner, str) or not partner):
            raise ValueError('NAMED_PARTNER_REQUIRED')
        by_id[ident] = row
    return by_id


def registered_bundles(bundles, by_id):
    seen = {subset_key(())}
    result = []
    for ids in bundles:
        if not isinstance(ids, (list, tuple)):
            raise ValueError('REGISTERED_BUNDLE_SEQUENCE_REQUIRED')
        key = subset_key(ids)
        if key in seen or any(i not in by_id for i in ids):
            raise ValueError('DISTINCT_REGISTERED_BUNDLE_REQUIRED')
        seen.add(key)
        result.append(list(ids))
    return result


def partner_participation(rows, partners):
    """A blanket partner response cannot authorize different complete packages."""
    reasons, groups = [], {}
    for row in rows:
        if row.get('partner') is not None:
            groups.setdefault(row['partner'], []).append(row)
    for partner, group in groups.items():
        evidence = partners.get(partner, {})
        if not isinstance(evidence, dict):
            raise ValueError('EXACT_PARTNER_PACKAGE_MAP_REQUIRED')
        entry = evidence.get(subset_key(r['id'] for r in group))
        if entry is None:
            reasons.append('PARTNER_PARTICIPATION_UNESTABLISHED:' + partner)
            continue
        if not isinstance(entry, dict) or set(entry) != {'consent', 'quote'}:
            raise ValueError('EXACT_PARTNER_PARTICIPATION_REQUIRED')
        if type(entry['consent']) is not bool:
            raise ValueError('EXPLICIT_PARTNER_CONSENT_REQUIRED')
        expected = quote(group)
        actual = entry['quote']
        if not isinstance(actual, dict):
            raise ValueError('EXACT_PARTNER_QUOTE_REQUIRED')
        for item in actual.values():
            if not isinstance(item, dict) or set(item) != {'price', 'terms_id'}:
                raise ValueError('EXACT_PARTNER_QUOTE_REQUIRED')
            money(item['price'])
        if not entry['consent'] or actual != expected:
            reasons.append('PARTNER_PARTICIPATION_UNESTABLISHED:' + partner)
    return reasons
