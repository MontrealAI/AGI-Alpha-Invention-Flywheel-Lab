"""Source-bound quantities and executable ephemeris uncertainty contracts."""

import argparse
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
from math import ceil, floor
from pathlib import Path
import re

from bridge.instruments import strict_portable_json


PAPER = 'f8f4ef76d9a7b3d401191a2f40e9864f0d8d44e2a01817e3fe28ab50cdbd54ff'
ARCHIVE = 'd1ba2cead1200bf0379d1b2369332153908c53283bf10a87ad63aeff96c05fe7'
FIELDS = ('t0_day', 't0_sigma_day', 'period_day', 'period_sigma_day', 'duration_hour')
MEANINGS = {
    't0_day': ('day', 'fitted_midpoint', 'BJD_TDB'),
    't0_sigma_day': ('day', 'marginal_standard_deviation', None),
    'period_day': ('day', 'fitted_cycle_period', None),
    'period_sigma_day': ('day', 'marginal_standard_deviation', None),
    'duration_hour': ('hour', 'nominal_transit_duration', None),
}
SOURCE_FIELDS = ('t0_bjd_tdb', 't0_unc', 'period_days', 'period_unc', 'duration_hours')
DECIMAL = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,2})?\Z')
IDENTIFIER = re.compile(r'[A-Za-z0-9_.:-]{1,100}\Z')
PAPER_URL = 'https://content.cld.iop.org/journals/0067-0049/283/1/5/revision1/apjsae3238t8_mrt.txt'
ARCHIVE_URL = 'https://www.exoclock.space/database/planets_json'


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def fingerprint(value):
    return sha256(canonical(value)).hexdigest()


def read_json(path, maximum=2_000_000):
    with Path(path).open('rb') as stream:
        raw = stream.read(maximum+1)
    if not 0 < len(raw) <= maximum:
        raise ValueError('ARTIFACT_LENGTH')
    return strict_portable_json(raw.decode())


def exact(value):
    if type(value) is not str or len(value) > 30 or not DECIMAL.fullmatch(value):
        raise ValueError('DECIMAL_QUANTITY')
    parsed = Decimal(value)
    if not -18 <= parsed.as_tuple().exponent <= 18 or abs(parsed) > 10**10:
        raise ValueError('DECIMAL_RANGE')
    return Fraction(parsed)


def problem(target, witness, basis, anchor, values):
    return {'target': target, 'witness': witness, 'basis': basis, 'anchor': anchor,
            'ephemeris': dict(zip(FIELDS, values, strict=True))}


def positional(case):
    return {**{key: value for key, value in case.items() if key != 'ephemeris'},
            'row': [case['ephemeris'][key] for key in FIELDS]}


def typed_fields(case):
    data = case.get('ephemeris')
    if (set(case) != {'target','witness','basis','anchor','ephemeris'} or type(data) is not dict
            or set(data) != set(FIELDS) or not all(type(case[key]) is str and IDENTIFIER.fullmatch(case[key])
                for key in ('target', 'witness'))):
        raise ValueError('SCIENTIFIC_CONTRACT_SHAPE')
    return [data[key] for key in FIELDS]


def calculate(case):
    values = typed_fields(case)
    witness = case['witness']
    if case['basis'] != 'BJD_TDB' or case['anchor'] is None:
        return {'decision': 'ABSTAIN_TIME_BASIS', 'epoch': None, 'sigma_s': None, 'witness': witness}
    if any(value is None for value in values):
        return {'decision': 'ABSTAIN_MISSING', 'epoch': None, 'sigma_s': None, 'witness': witness}
    midpoint, midpoint_sigma, period, period_sigma, duration = map(exact, values)
    if midpoint <= 0 or period <= 0 or duration <= 0 or midpoint_sigma < 0 or period_sigma < 0:
        raise ValueError('SCIENTIFIC_CONTRACT_RANGE')
    anchor = exact(case['anchor'])
    epoch = ceil((anchor - midpoint) / period)
    a, b = 86400 * midpoint_sigma, 86400 * abs(epoch) * period_sigma
    low, high, threshold = abs(a - b), a + b, 300 * duration
    decision = ('WITHIN' if high <= threshold else 'EXCEEDS' if low > threshold else 'COVARIANCE_SENSITIVE')
    return {'decision': decision, 'epoch': epoch, 'sigma_s': [floor(low), ceil(high)], 'witness': witness}


def source_records(raw, source):
    expected = {'paper': PAPER, 'archive': ARCHIVE}.get(source)
    if not expected or sha256(raw).hexdigest() != expected:
        raise ValueError('SOURCE_DIGEST')
    if source == 'paper':
        rows = []
        columns = ((15, 30), (31, 40), (41, 53), (54, 65), (66, 75))
        for index, line in enumerate(raw.decode('ascii').splitlines(), 1):
            if len(line) < 84 or not re.fullmatch(r'[0-9]{7}\.[0-9 ]+', line[15:30].strip()):
                continue
            rows.append((line[:14].strip(), f'paper:T8:L{index}', [line[a:b].strip() or None for a, b in columns]))
        if len(rows) != 620 or len({name for name, _, _ in rows}) != len(rows):
            raise ValueError('PAPER_TABLE_COMPLETE')
        return rows
    archive = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    if len(archive) != 776:
        raise ValueError('ARCHIVE_SNAPSHOT')
    rows = []
    for name, item in sorted(archive.items()):
        if name != item.get('name'):
            raise ValueError('ARCHIVE_OBJECT_IDENTITY')
        cited = item.get('ephem_parameters_ref')
        link = {'native_key': name, 'ephemeris_reference': cited} if type(cited) is str else {'native_key': name}
        witness = f'archive:{fingerprint(link)[:16]}'
        values = [item.get(field) for field in SOURCE_FIELDS]
        rows.append((name, witness, [str(value) if isinstance(value, Decimal) else None for value in values]))
    return rows


def review(raw, source, anchor):
    records = source_records(raw, source)
    outcomes = Counter()
    sensitive = []
    independent_only = 0
    for target, witness, values in records:
        case = problem(target, witness, 'BJD_TDB', anchor, values)
        result = calculate(case)
        decision = result['decision']
        outcomes[decision] += 1
        if decision.startswith('ABSTAIN'):
            continue
        _, s0, _, sp, duration = map(exact, values)
        a, b, threshold = 86400 * s0, 86400 * sp * abs(result['epoch']), 300 * duration
        if a*a + b*b <= threshold*threshold and decision != 'WITHIN':
            independent_only += 1
        if decision == 'COVARIANCE_SENSITIVE':
            sensitive.append({**result, 'target': target})
    return {'source': source, 'source_sha256': sha256(raw).hexdigest(), 'anchor_bjd_tdb': anchor,
            'rows': len(records), 'decisions': dict(outcomes), 'zero_covariance_pass_not_robust': independent_only,
            'covariance_sensitive': sensitive}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    one = sub.add_parser('check')
    one.add_argument('file', type=Path)
    batch = sub.add_parser('survey')
    batch.add_argument('file', type=Path)
    batch.add_argument('--source', choices=('paper', 'archive'), required=True)
    batch.add_argument('--anchor', required=True)
    args = parser.parse_args()
    if args.command == 'check':
        output = calculate(read_json(args.file))
    else:
        with args.file.open('rb') as stream:
            content = stream.read(2_000_001)
        if len(content) > 2_000_000:
            parser.error('Source file exceeds the documented public input bound.')
        output = review(content, args.source, args.anchor)
    print(canonical(output).decode())


if __name__ == '__main__':
    main()
