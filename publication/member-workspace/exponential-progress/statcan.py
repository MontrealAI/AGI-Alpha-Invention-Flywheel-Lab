# SPDX-License-Identifier: Apache-2.0
"""Verify one public Canadian business survey comparison against both editions."""

import argparse
import csv
from decimal import Decimal
import io
import json
from hashlib import file_digest
from pathlib import Path
from zipfile import ZipFile

from qualify import canonical


REGISTRATION = Path(__file__).with_name('STATCAN-REGISTRATION.json')
COLUMNS = {
    'en': ('REF_DATE', 'DGUID', 'UOM_ID', 'SCALAR_ID', 'VECTOR', 'COORDINATE', 'VALUE', 'STATUS', 'SYMBOL'),
    'fr': ("PÉRIODE DE RÉFÉRENCE", 'DGUID', "IDENTIFICATEUR D'UNITÉ DE MESURE", 'IDENTIFICATEUR SCALAIRE',
           'VECTEUR', 'COORDONNÉES', 'VALEUR', 'STATUS', 'SYMBOLE'),
}
DELIMITERS = {'en': ',', 'fr': ';'}


def observations(archive, locale, registration):
    with archive.open('rb') as stream:
        if file_digest(stream, 'sha256').hexdigest() != registration['files'][locale]['sha256']:
            raise ValueError(f'Unexpected official snapshot for {locale}')
    codes = registration['coordinates']
    result = {}
    with ZipFile(archive) as source:
        with io.TextIOWrapper(source.open('33101207.csv'), encoding='utf-8-sig', newline='') as stream:
            rows = csv.DictReader(stream, delimiter=DELIMITERS[locale])
            for row in rows:
                period, geo_id, unit, scalar, vector, coordinate, value, quality, symbol = (
                    row[key] for key in COLUMNS[locale]
                )
                geo, field, yes = coordinate.split('.')
                if geo not in (codes['canada'], codes['quebec']) or field not in (
                    codes['all_industries'], codes['information_and_cultural'],
                    codes['professional_scientific_and_technical']
                ) or yes != codes['planned_next_12_months']:
                    continue
                if (period != registration['data_period'] or unit != '239' or scalar != '0'
                        or not vector or not geo_id or quality not in {'A', 'B', 'C', 'D', 'E'} or symbol or not value
                        or coordinate in result):
                    raise ValueError(f'Missing, suppressed, incompatible or duplicate cell: {coordinate}')
                if geo == codes['canada'] and geo_id != registration['canada_dguid']:
                    raise ValueError(f'Unexpected national geography: {coordinate}')
                amount = Decimal(value)
                if not 0 <= amount <= 100:
                    raise ValueError(f'Percentage outside its range: {coordinate}')
                result[coordinate] = {'vector': vector, 'geo_id': geo_id, 'percentage': value, 'quality': quality}
    if len(result) != 6:
        raise ValueError('The registered comparison requires six valid cells')
    return result


def ordinary_labels(archive):
    # Direct English workflow using the published labels as filters, without the bilingual crosswalk.
    industries = {
        'North American Industry Classification System (NAICS), all industries': '1',
        'Information and cultural industries [51]': '9',
        'Professional, scientific and technical services [54]': '12',
    }
    places = {'Canada': '1', 'Quebec': '6'}
    direct = {}
    with ZipFile(archive) as source:
        with io.TextIOWrapper(source.open('33101207.csv'), encoding='utf-8-sig', newline='') as stream:
            rows = csv.DictReader(stream)
            measure = rows.fieldnames[4]
            for row in rows:
                if (row['GEO'] in places and row['Business characteristics'] in industries
                        and row[measure].startswith('Yes, business plans to use artificial intelligence')):
                    expected = f'{places[row["GEO"]]}.{industries[row["Business characteristics"]]}.1'
                    if expected in direct:
                        raise ValueError(f'Duplicate conventional result: {expected}')
                    direct[expected] = row['VALUE']
    return direct


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('en', type=Path)
    cli.add_argument('fr', type=Path)
    opts = cli.parse_args()
    registration = json.loads(REGISTRATION.read_bytes())
    english = observations(opts.en, 'en', registration)
    french = observations(opts.fr, 'fr', registration)
    conventional = ordinary_labels(opts.en)
    if english != french or conventional != {key: cell['percentage'] for key, cell in english.items()}:
        raise ValueError('The language editions or the exact conventional result disagree')
    published_canada = {'1.1.1': '25.2', '1.9.1': '48.0', '1.12.1': '54.8'}
    if any(english[key]['percentage'] != value for key, value in published_canada.items()):
        raise ValueError('The published national summary disagrees with the table')
    codes = registration['coordinates']
    differences = {}
    for industry in ('all_industries', 'information_and_cultural', 'professional_scientific_and_technical'):
        coordinate_suffix = f'.{codes[industry]}.{codes["planned_next_12_months"]}'
        quebec = english[codes['quebec'] + coordinate_suffix]['percentage']
        canada = english[codes['canada'] + coordinate_suffix]['percentage']
        differences[industry] = str(Decimal(quebec) - Decimal(canada))
    print(canonical({'source': registration['source'], 'scope': registration['scope'],
                     'observations': english, 'quebec_minus_canada_percentage_points': differences,
                     'matched_language_editions': len(english),
                     'matched_conventional_english': len(conventional),
                     'matched_published_summary': len(published_canada),
                     'independent_survey_replication': False}).decode(), end='')


if __name__ == '__main__':
    main()
