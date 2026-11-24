"""Qualify a historical ENSO episode replay against NOAA's ERSSTv5 ONI table."""

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
from html import unescape
from itertools import groupby
import json
from pathlib import Path
import re


LOCATION = Path(__file__).resolve().parent
FIXTURE = LOCATION / 'study/cascade/FRESH-DOMAIN.json'
if not FIXTURE.exists() and len(LOCATION.parents) >= 3:
    FIXTURE = LOCATION.parents[2] / 'publication/cascade/FRESH-DOMAIN.json'
SOURCE_URL = 'https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v5/'
SOURCE_SHA256 = 'f758bd32a26ac7c390b0d91c78fceba2256f758a5dbb29d9916cfea489d41a2c'
PROJECTION_SHA256 = '1c9d1eb47378c01b779386546bc2e4c7e73c0b77f89920d10d09fab8c4c24163'
REGISTRATION_SHA256 = '4239c9415957161092ec2d2fa3e96159adb76ba6a38edd93cce2cfcbbb462097'
OPERATIONAL_NOTICE_URL = 'https://www.weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf'
FIRST_YEAR, LAST_YEAR = 1950, 2024
SEASONS = 'DJF JFM FMA MAM AMJ MJJ JJA JAS ASO SON OND NDJ'.split()
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))
SEASONS_REQUIRED = 5
THRESHOLD_TENTHS_C = 5
LABEL_NAMES = {'W': 'warm', 'C': 'cold', 'N': 'uncolored', 'U': 'unresolved'}
BASIS = {
    'index': 'ONI',
    'dataset': 'ERSSTv5',
    'unit': 'tenths of a degree Celsius (SST anomaly)',
    'climatology': 'CPC centered 30-year periods updated every five years',
    'vintage': 'archived CPC historical table retrieved 2026-11-24',
    'season_order_by_middle_month': SEASONS,
}


def digest(value):
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return sha256(data.encode('utf-8')).hexdigest()


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'DUPLICATE_JSON_KEY {key}')
        result[key] = value
    return result


def phase(value):
    if value >= THRESHOLD_TENTHS_C:
        return 'W'
    if value <= -THRESHOLD_TENTHS_C:
        return 'C'
    return 'N'


def classify(values):
    """Return labels and the maximal confirmed runs from a complete ordered slice."""
    labels, episodes = [], []
    for kind, run in groupby(values, key=phase):
        start = len(labels)
        size = sum(1 for _ in run)
        stop = start + size
        touches_boundary = start == 0 or stop == len(values)
        if kind != 'N' and size >= SEASONS_REQUIRED:
            episodes.append((kind, start, stop))
        elif kind != 'N':
            kind = 'U' if touches_boundary else 'N'
        labels.extend(kind * size)
    return ''.join(labels), episodes


def season_at(index):
    year_offset, month = divmod(index, len(SEASONS))
    return {'middle_month': f'{FIRST_YEAR + year_offset:04d}-{month + 1:02d}', 'season': SEASONS[month]}


def evaluate(readings, *, basis, intent='historical'):
    if intent != 'historical':
        return {'status': 'ABSTAIN_SCOPE', 'intent': intent, 'reason': 'HISTORICAL_ONI_ARCHIVE_ONLY',
                'official_monitoring_index': 'RONI', 'effective_date': '2026-02-01',
                'source': OPERATIONAL_NOTICE_URL}
    if basis != BASIS:
        return {'status': 'ABSTAIN_BASIS'}
    if (not isinstance(readings, list)
            or any(not isinstance(row, list) or len(row) != 2 or type(row[0]) is not int for row in readings)
            or [row[0] for row in readings] != YEARS
            or any(not isinstance(row[1], list) or len(row[1]) != len(SEASONS) for row in readings)):
        return {'status': 'ABSTAIN_SEASON_COVERAGE'}
    values = [value for _, row in readings for value in row]
    if any(type(value) is not int or not -99 <= value <= 99 for value in values):
        return {'status': 'ABSTAIN_VALUE'}
    labels, runs = classify(values)
    counts = Counter(labels)
    return {
        'status': 'CLASSIFIED_HISTORICAL',
        'labels': labels,
        'season_counts': {name: counts[label] for label, name in LABEL_NAMES.items()},
        'episodes': [
            {'phase': LABEL_NAMES[kind],
             'first': season_at(start), 'last': season_at(stop - 1),
             'seasons': stop - start, 'left_censored': start == 0, 'right_censored': stop == len(values)}
            for kind, start, stop in runs
        ],
    }


def conventional_windows(readings):
    """Compute the union of qualifying windows directly without grouping runs."""
    values = [value for _, row in readings for value in row]
    labels = ['N'] * len(values)
    for start in range(len(values) - 4):
        window = values[start:start + 5]
        if min(window) >= 5:
            labels[start:start + 5] = 'WWWWW'
        if max(window) <= -5:
            labels[start:start + 5] = 'CCCCC'
    return ''.join(labels)


def extract_snapshot(raw):
    """Project the published values and presentation labels separately from CPC HTML."""
    html = raw.decode('utf-8')
    match = re.search(r'Cold &amp; Warm Episodes by Season[^\r\n]+\(ERSSTv5\)', html)
    headers = re.findall(r'<strong>(Year|' + '|'.join(SEASONS) + r')</strong>', html)
    if not match or headers[:13] != ['Year', *SEASONS]:
        raise ValueError('CPC_TABLE_BASIS')
    readings, published = [], []
    colors = {'red': 'W', 'blue': 'C', 'black': 'N'}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, flags=re.DOTALL):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', row, flags=re.DOTALL)
        if not cells:
            continue
        contents = [unescape(re.sub(r'<[^>]+>', '', cell)).strip() for cell in cells]
        if re.fullmatch(r'\d{4}', contents[0]) is None:
            continue
        year = int(contents[0])
        if year not in YEARS:
            continue
        if len(contents) != 13 or any(re.fullmatch(r'-?\d\.\d', cell) is None for cell in contents[1:]):
            raise ValueError(f'CPC_TABLE_VALUE {year}')
        shades = [re.findall(r'\bstyle="color:(red|blue|black)"', cell) for cell in cells[1:]]
        if any(len(shade) != 1 for shade in shades):
            raise ValueError(f'CPC_TABLE_COLOR {year}')
        readings.append([year, [int(Decimal(value) * 10) for value in contents[1:]]])
        published.append([year, ''.join(colors[shade[0]] for shade in shades)])
    if [year for year, _ in readings] != YEARS:
        raise ValueError('CPC_TABLE_COVERAGE')
    return {'readings': readings, 'published_labels': published}


def challenges(readings):
    year, values = readings[0]
    cases = {
        'missing_year': evaluate(readings[1:], basis=BASIS)['status'],
        'duplicate_year': evaluate([readings[0], *readings[:-1]], basis=BASIS)['status'],
        'missing_season': evaluate([[year, values[1:]], *readings[1:]], basis=BASIS)['status'],
        'duplicate_season': evaluate(readings, basis={
            **BASIS, 'season_order_by_middle_month': [SEASONS[0], *SEASONS[:-1]]})['status'],
        'missing_value': evaluate([[year, [None, *values[1:]]], *readings[1:]], basis=BASIS)['status'],
        'inexact_value': evaluate([[year, [float(values[0]), *values[1:]]], *readings[1:]], basis=BASIS)['status'],
        'missing_sentinel': evaluate([[year, [-999, *values[1:]]], *readings[1:]], basis=BASIS)['status'],
        'wrong_dataset': evaluate(readings, basis={**BASIS, 'dataset': 'ERSSTv6'})['status'],
        'wrong_units': evaluate(readings, basis={**BASIS, 'unit': 'degrees Fahrenheit'})['status'],
        'provisional_vintage': evaluate(readings, basis={**BASIS, 'vintage': 'provisional'})['status'],
        'operational': evaluate(readings, basis=BASIS, intent='operational')['status'],
        'forecast': evaluate(readings, basis=BASIS, intent='forecast')['status'],
    }
    expected = {
        'missing_year': 'ABSTAIN_SEASON_COVERAGE',
        'duplicate_year': 'ABSTAIN_SEASON_COVERAGE',
        'missing_season': 'ABSTAIN_SEASON_COVERAGE',
        'duplicate_season': 'ABSTAIN_BASIS',
        'missing_value': 'ABSTAIN_VALUE',
        'inexact_value': 'ABSTAIN_VALUE',
        'missing_sentinel': 'ABSTAIN_VALUE',
        'wrong_dataset': 'ABSTAIN_BASIS',
        'wrong_units': 'ABSTAIN_BASIS',
        'provisional_vintage': 'ABSTAIN_BASIS',
        'operational': 'ABSTAIN_SCOPE',
        'forecast': 'ABSTAIN_SCOPE',
    }
    for name, values_to_test, expected_labels in (
        ('exact_thresholds', [0, *([5] * 5), 0, *([-5] * 5), 0], 'NWWWWWNCCCCCN'),
        ('interior_short_run', [0, 5, 5, 5, 5, 0], 'NNNNNN'),
        ('incomplete_boundary_runs', [5, 5, 0, -5, -5, -5, -5], 'UUNUUUU'),
    ):
        cases[name] = classify(values_to_test)[0]
        expected[name] = expected_labels
    return cases, cases == expected


def qualify(fixture=FIXTURE, *, source_html=None, middle_months=()):
    archive = json.loads(Path(fixture).read_bytes(), object_pairs_hook=reject_duplicate_keys)
    if (archive['source']['url'] != SOURCE_URL or archive['source']['sha256'] != SOURCE_SHA256
            or archive['basis'] != BASIS or digest(archive['registration']) != REGISTRATION_SHA256):
        raise ValueError('ARCHIVE_SOURCE_OR_BASIS')
    projection = {key: archive[key] for key in ('readings', 'published_labels')}
    projection_sha256 = digest(projection)
    if projection_sha256 != PROJECTION_SHA256 or projection_sha256 != archive['source']['projection_sha256']:
        raise ValueError('ARCHIVE_PROJECTION_CHANGED')
    source_verification = 'PINNED_OFFLINE_PROJECTION'
    if source_html is not None:
        raw = Path(source_html).read_bytes()
        if extract_snapshot(raw) != projection:
            raise ValueError('CPC_SNAPSHOT_PROJECTION_CHANGED')
        source_verification = ('EXACT_SOURCE_BYTES' if sha256(raw).hexdigest() == SOURCE_SHA256
                               else 'HISTORICAL_PROJECTION_MATCHED')
    candidate = evaluate(projection['readings'], basis=archive['basis'])
    if candidate['status'] != 'CLASSIFIED_HISTORICAL':
        raise ValueError(candidate['status'])
    predicted = candidate.pop('labels')
    published = ''.join(labels for _, labels in projection['published_labels'])
    conventional = conventional_windows(projection['readings'])
    differences = [
        {**season_at(index), 'candidate': candidate_label, 'noaa': published_label,
         'conventional': control_label}
        for index, (candidate_label, published_label, control_label) in
        enumerate(zip(predicted, published, conventional, strict=True))
        if len({candidate_label, published_label, control_label}) != 1
    ]
    fault_outcomes, fault_pass = challenges(projection['readings'])
    summary = {
        'seasons_compared': len(predicted),
        'matches_published': sum(a == b for a, b in zip(predicted, published, strict=True)),
        'matches_conventional': sum(a == b for a, b in zip(predicted, conventional, strict=True)),
        'season_counts': candidate['season_counts'],
        'episode_counts': dict(Counter(episode['phase'] for episode in candidate['episodes'])),
        'left_censored_runs': sum(episode['left_censored'] for episode in candidate['episodes']),
        'right_censored_runs': sum(episode['right_censored'] for episode in candidate['episodes']),
        'challenges': len(fault_outcomes),
        'challenges_passed': fault_pass,
    }
    summary_matches = summary == archive['observed']
    accepted = not differences and fault_pass and summary_matches
    outcome = {
        'status': 'QUALIFIED_HISTORICAL_REPLAY' if accepted else 'UNQUALIFIED_HISTORICAL_REPLAY',
        'source': SOURCE_URL,
        'source_verification': source_verification,
        'projection_sha256': projection_sha256,
        **summary,
        'episodes': candidate['episodes'],
        'disagreements': differences,
        'challenge_outcomes': fault_outcomes,
        'recorded_summary_matches': summary_matches,
        'operational_decision': 'ABSTAIN_SCOPE',
    }
    if not accepted or not middle_months:
        return outcome
    positions = {season_at(index)['middle_month']: index for index in range(len(predicted))}
    requested = list(middle_months)
    missing = [month for month in requested if month not in positions]
    if missing:
        return {'status': 'ABSTAIN_WINDOW', 'unavailable_middle_months': missing, 'source': SOURCE_URL}
    outcome['selected_seasons'] = [
        {**season_at(index),
         'anomaly_tenths_c': projection['readings'][index // len(SEASONS)][1][index % len(SEASONS)],
         'classification': LABEL_NAMES[predicted[index]], 'published_label': published[index]}
        for index in (positions[month] for month in requested)
    ]
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    parser.add_argument('--source-html', type=Path, help='verify the archive against a downloaded CPC table')
    parser.add_argument('--intent', choices=('historical', 'operational', 'forecast'), default='historical')
    parser.add_argument('--season', action='append', default=[], metavar='YYYY-MM',
                        help='return a named season by its middle month')
    args = parser.parse_args()
    try:
        result = (qualify(args.fixture, source_html=args.source_html, middle_months=args.season)
                  if args.intent == 'historical'
                  else evaluate(None, basis=BASIS, intent=args.intent))
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result['status'] == 'UNQUALIFIED_HISTORICAL_REPLAY')


if __name__ == '__main__':
    raise SystemExit(main())
