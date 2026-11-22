"""Public fact-sheet prototype, not PDF remediation or WCAG certification."""
import argparse
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = 'agi-alpha/accessibility127/public-evidence/v1'
GRADES = {'official_listing', 'secondary_notice', 'secondary_award_report'}
IDS = re.compile(r'^[a-z0-9][a-z0-9-]{1,63}$')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def clean_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('INVALID_DATE')
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('INVALID_DATE') from exc
    return value


def safe_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError('UNSAFE_SOURCE_URL')
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('UNSAFE_SOURCE_URL')
    return value


def validate(data):
    if not isinstance(data, dict) or data.get('schema') != SCHEMA:
        raise ValueError('SCHEMA_MISMATCH')
    day = clean_date(data.get('observed_on'))
    if data.get('verdict') != 'NO-BID / NO-DEPLOY':
        raise ValueError('UNAUTHORIZED_VERDICT')
    if data.get('tender_budget_cad') is not None:
        raise ValueError('UNVERIFIED_TENDER_BUDGET')
    records = data.get('records')
    if not isinstance(records, list) or len(records) != 3:
        raise ValueError('RECORD_COUNT')
    seen = set()
    for r in records:
        if not isinstance(r, dict) or set(r) != {'id','name','fact','grade','status','date','deadline','source_url','reported_award_cad'}:
            raise ValueError('RECORD_FIELDS')
        rid = r['id']
        if not isinstance(rid, str) or not IDS.fullmatch(rid) or rid in seen:
            raise ValueError('DUPLICATE_OR_INVALID_ID')
        seen.add(rid)
        if r['grade'] not in GRADES:
            raise ValueError('EVIDENCE_GRADE')
        for k in ('name', 'fact', 'status'):
            if not isinstance(r[k], str) or not 2 <= len(r[k].strip()) <= 320 or '\x00' in r[k]:
                raise ValueError('EMPTY_OR_OVERSIZE_FACT')
        clean_date(r['date'])
        if r['date'] > day:
            raise ValueError('FUTURE_OBSERVATION')
        if r['deadline'] is not None:
            clean_date(r['deadline'])
            if r['deadline'] < r['date']:
                raise ValueError('INVALID_DEADLINE')
        safe_url(r['source_url'])
        if r['reported_award_cad'] is not None:
            if r['grade'] != 'secondary_award_report' or not re.fullmatch(r'\d{1,10}\.\d\d', str(r['reported_award_cad'])):
                raise ValueError('UNVERIFIED_AWARD')
        if r['grade'] != 'secondary_award_report' and r['reported_award_cad'] is not None:
            raise ValueError('UNVERIFIED_AWARD')
    return records


def render(data):
    records = validate(data)
    esc = lambda s: html.escape(str(s), quote=True)
    rows = []
    for r in records:
        amount = ('Reported historical award: CAD ' + r['reported_award_cad']) if r['reported_award_cad'] is not None else 'Not established'
        deadline = r['deadline'] if r['deadline'] is not None else 'Not established'
        rows.append('  <tr data-record-id="' + esc(r['id']) + '"><th scope="row">' + esc(r['name']) + '</th>'
            + '<td>' + esc(r['fact']) + '</td><td>' + esc(r['grade']) + '</td><td>' + esc(r['status'])
            + '</td><td>' + esc(r['date'])
            + '</td><td>' + esc(deadline) + '</td><td>' + esc(amount) + '</td>'
            + '<td><a href="' + esc(r['source_url']) + '">Evidence source</a></td></tr>')
    body = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accessibility127: Public evidence — no bid</title></head><body>
<a href="#main">Skip to main content</a><main id="main">
<h1>Public document accessibility: evidence and open limits</h1>
<p>This is a research fact sheet, not an issuer-verified tender package, customer agreement, accessible-PDF remediation, independent WCAG certificate, or paid commercial result.</p>
<h2>Evidence observations</h2>
<table><caption>Three observed public procurement signals; grades are not interchangeable</caption>
<thead><tr><th scope="col">Opportunity</th><th scope="col">Verified scope / observation</th><th scope="col">Source grade</th><th scope="col">Observed status</th><th scope="col">Observation date</th><th scope="col">Deadline</th><th scope="col">Award amount</th><th scope="col">Link</th></tr></thead>
<tbody>
''' + '\n'.join(rows) + '''
</tbody></table>
<h2>Commercial decision</h2>
<p><strong>NO-BID / NO-DEPLOY.</strong> Original issuer terms, supplier eligibility, deliverable acceptance, production capacity, independent accessibility review, buyer choice and complete costs are unverified. No tender budget or collected revenue is established.</p>
<p>The Vaughan download fee is not a contract award; a Toronto third-party value estimate is not an observed buyer budget; historical awarded values are not our prices or receipts.</p>
<h2>Limitations</h2>
<p>This view uses manually transcribed, cited facts, not fetched or cryptographically signed original-source bytes. Semantic HTML checks do not establish screen-reader performance or WCAG compliance. Existing specialist remediators and in-house teams remain capable competitors.</p>
</main></body></html>
'''
    return body.encode('utf-8')


def produce(input_path, output_dir):
    raw = Path(input_path).read_bytes()
    data = json.loads(raw)
    output = render(data)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'fact_sheet.html').write_bytes(output)
    manifest = {'schema': SCHEMA, 'input_sha256': sha256(raw), 'html_sha256': sha256(output),
                'record_ids': [r['id'] for r in data['records']], 'record_count': len(data['records']),
                'verdict': 'NO-BID / NO-DEPLOY', 'tender_budget_cad': None,
                'scope': 'technical_semantic_html_only_not_WCAG_not_commercial'}
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(produce(args.input, args.output), sort_keys=True))
