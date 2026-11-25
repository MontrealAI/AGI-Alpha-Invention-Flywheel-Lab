"""Project reviewed opportunity work and existing monitor intake into the Atlas."""

import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import re

from frontier_public_watch import unique_object


ASSET = 'opportunity-capture.json'
MARKER = '<!-- OPPORTUNITY_CAPTURE -->'
SECTION = 'opportunity-capture'
ROOT = Path(__file__).resolve().parents[1] / 'publication' / 'opportunity'
SCHEMA = 'frontier/opportunity-capture-v1'
CATALOG_CASE = 'nisar-l2-quebec'
CATALOG_RECEIPT = 'discovery/RADAR-CONTROL.json'
CAPTIONS = {
    'DISCOVERED': ('Discovered', 'Repérée'),
    'VERIFIED': ('Evidence verified', 'Preuve vérifiée'),
    'INVESTIGATING': ('Under investigation', 'À l’étude'),
    'CONSTRUCTING': ('Under construction', 'En construction'),
    'QUALIFIED': ('Qualified', 'Qualifiée'),
    'OPERATING': ('In use', 'En service'),
    'VALUE CAPTURED': ('Value captured', 'Valeur réalisée'),
    'WATCH': ('Watch', 'À surveiller'),
    'REJECTED': ('Rejected', 'Écartée'),
    'BLOCKED': ('Blocked', 'Bloquée'),
    'ABSTAIN': ('Abstain', 'Abstention'),
    'SUPERSEDED': ('Superseded', 'Remplacée'),
}


def parse(raw):
    study = json.loads(raw, object_pairs_hook=unique_object)
    if study['schema'] != SCHEMA:
        raise ValueError('Unexpected opportunity evidence schema')
    receipts = study.get('receipts', {})
    for path, fingerprint in receipts.items():
        if not all(re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]*', part) for part in path.split('/')):
            raise ValueError('Unexpected opportunity receipt path')
        if not re.fullmatch('[0-9a-f]{64}', fingerprint):
            raise ValueError('Unexpected opportunity receipt digest')
    ids = set()
    for case in study['opportunities']:
        identity = case['id']
        if not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}', identity) or identity in ids:
            raise ValueError('Ambiguous opportunity identity')
        ids.add(identity)
        if case['state'] not in CAPTIONS or case['action'] not in {'TEST', 'MONITOR', 'HOLD'}:
            raise ValueError('Unexpected opportunity disposition')
        if case['state'] in {'VERIFIED', 'QUALIFIED', 'OPERATING', 'VALUE CAPTURED'} and not case['evidence']:
            raise ValueError('An admitted opportunity requires reviewed evidence')
        if case['state'] == 'VALUE CAPTURED':
            raise ValueError('A value promotion requires an authorized observed outcome')
        if case['state'] in {'QUALIFIED', 'OPERATING'}:
            if (identity != CATALOG_CASE or case.get('evidence_stage') != 'PUBLIC_CATALOG_METADATA'
                    or case.get('acceptance_receipt') != CATALOG_RECEIPT or CATALOG_RECEIPT not in receipts):
                raise ValueError('A productive promotion requires acceptance for the exact case and scope')
        for locale in ('en', 'fr'):
            if any(not isinstance(case[locale][key], str) or not case[locale][key].strip()
                   for key in ('title', 'finding', 'next')):
                raise ValueError('Incomplete bilingual opportunity')
    return study


def study_bytes(path):
    source = ROOT / path
    if source.resolve() != ROOT.resolve() / path or not source.is_file():
        raise ValueError('Unexpected opportunity study file: ' + path)
    with source.open('rb') as stream:
        raw = stream.read(1_000_001)
    if not 0 < len(raw) <= 1_000_000:
        raise ValueError('Unexpected opportunity study size: ' + path)
    return raw


def verify_catalog(case, raw):
    receipt = json.loads(raw, object_pairs_hook=unique_object)
    sites = receipt['sites']
    if (receipt['schema'] != 'frontier/nisar-ordinary-source-control-v1'
            or set(sites) != {'montreal', 'quebec-city'}
            or receipt['verified_site_displacement_or_safety'] is not False
            or receipt['data_access']['data_file_body_requested'] is not False):
        raise ValueError('Catalog acceptance scope differs from the released operation')
    for city, result in sites.items():
        counts = result['nisar']
        chains = counts['two_product_full_frame_within_window_chains']
        expected = {'validated_products': counts['query_hits'], 'earlier_reference_inputs': counts['reference_before_window'],
                    'longest_exact_chain_links': 2 if chains else 0}
        if case['repeat_use'][city] != expected:
            raise ValueError('Catalog repeat-use record differs from the independent receipt')


def source_study():
    raw = study_bytes('CAPTURE.json')
    study = parse(raw)
    admitted = next((case for case in study['opportunities'] if case['state'] in {'QUALIFIED', 'OPERATING'}), None)
    for path, fingerprint in study['receipts'].items():
        receipt = study_bytes(path)
        if sha256(receipt).hexdigest() != fingerprint:
            raise ValueError('Opportunity receipt bytes differ: ' + path)
        if admitted and path == CATALOG_RECEIPT:
            verify_catalog(admitted, receipt)
    return raw, study


def projection(ledger, raw):
    """Use the existing observation log. Release metadata only enters intake."""
    study = parse(raw)
    observations = []
    for atlas_record in ledger['records']:
        for identity, versions in atlas_record['sources'].items():
            current = versions[-1]
            observations.append({
                'identity': identity, 'version': current['source_version'],
                'atlas_id': atlas_record['id'], 'first_observed_at': versions[0]['observed_at'],
                'observed_at': current['observed_at'], 'source_date': current['source_date'],
                'primary_sha256': current['primary_sha256'], 'publisher_commit': current['publisher_commit'],
                'source_url': current['url'], 'evidence_stage': 'PRIMARY_METADATA',
                'state': 'DISCOVERED' if current['decision'] == 'test' else 'WATCH',
            })
    observations.sort(key=lambda row: (row['observed_at'], row['identity']), reverse=True)
    cases = study['opportunities']
    open_checks = [case['id'] for case in cases if case['action'] == 'TEST'
                   and case['state'] in {'DISCOVERED', 'VERIFIED', 'INVESTIGATING', 'QUALIFIED', 'OPERATING'}]
    return {'schema': SCHEMA, 'study_sha256': sha256(raw).hexdigest(), 'monitor_intake': observations,
            'reviewed': [{'id': case['id'], 'state': case['state'], 'action': case['action']}
                         for case in cases],
            'next_supported_check': open_checks[0] if open_checks else None}


def report_url(revision):
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Expected an exact opportunity report revision')
    return ('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/'
            f'{revision}/publication/opportunity/REPORT.md')


def render(study, language, revision):
    fr = language == 'fr'
    case_cards = []
    for case in study['opportunities']:
        text = case[language]
        status = CAPTIONS[case['state']][fr]
        case_cards.append(
            f'<article class="mv-tool" data-opportunity="{escape(case["id"], quote=True)}" '
            f'data-stage="{escape(case["state"], quote=True)}">'
            f'<p class="packet-meta">{status}</p><h5>{escape(text["title"])}</h5>'
            f'<p>{escape(text["finding"])}</p><p>{escape(text["next"])}</p></article>'
        )
    intro = escape(study['summary'][language])
    label = 'Résultats et sources (JSON)' if fr else 'Results and sources (JSON)'
    method = 'Méthode et comparaison' if fr else 'Method and comparison'
    all_checks = 'Autres possibilités examinées' if fr else 'More reviewed opportunities'
    return (f'<p>{intro}</p><div class="mv-grid factory-findings">{"".join(case_cards[:3])}</div>'
            f'<details><summary>{all_checks}</summary><div class="mv-grid factory-findings">'
            f'{"".join(case_cards[3:])}</div></details>'
            f'<p class="mv-links"><a href="{ASSET}" download>{label}</a> '
            f'<a href="{report_url(revision)}">{method}</a></p>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ledger', type=Path)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--verify', action='store_true')
    arguments = parser.parse_args()
    ledger = json.loads(arguments.ledger.read_bytes(), object_pairs_hook=unique_object)
    result = projection(ledger, arguments.evidence.read_bytes())
    if arguments.verify and result != ledger.get('opportunity_capture'):
        parser.error('The opportunity inventory does not bind this Atlas and study')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
