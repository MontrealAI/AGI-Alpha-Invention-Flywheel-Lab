"""Independent key-free verifier for the accessibility127 source-bound HTML packet."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = 'agi-alpha/accessibility127/public-evidence/v1'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class FactParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.current = None
        self.cell = None
        self.current_tag = None
        self.links = []
        self.lang = []
        self.main_count = 0
        self.h1 = 0
        self.h2 = 0
        self.captions = 0
        self.col_scopes = 0
        self.row_scopes = 0
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        att = dict(attrs)
        if tag in {'script', 'iframe', 'form', 'object', 'embed'} or any(x.lower().startswith('on') for x in att):
            raise ValueError('UNSAFE_HTML')
        if tag == 'html':
            self.lang.append(att.get('lang'))
        if tag == 'main':
            self.main_count += 1
            if att.get('id') != 'main':
                raise ValueError('INVALID_MAIN')
        if tag == 'h1':
            self.h1 += 1
        if tag == 'h2':
            self.h2 += 1
        if tag == 'caption':
            self.captions += 1
        if tag == 'a':
            href = att.get('href')
            if href == '#main':
                self.skip += 1
            else:
                if not href or urlsplit(href).scheme != 'https':
                    raise ValueError('UNSAFE_SOURCE_LINK')
                self.links.append(href)
        if tag == 'tr' and 'data-record-id' in att:
            if self.current is not None:
                raise ValueError('NESTED_ROW')
            self.current = {'id': att['data-record-id'], 'cells': []}
        if tag in {'th', 'td'}:
            if att.get('scope') == 'col' and tag == 'th':
                self.col_scopes += 1
            if att.get('scope') == 'row' and tag == 'th':
                self.row_scopes += 1
            if self.current is not None:
                self.cell = []
                self.current_tag = tag

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in {'th', 'td'} and self.cell is not None:
            self.current['cells'].append(''.join(self.cell).strip())
            self.cell = None
            self.current_tag = None
        if tag == 'tr' and self.current is not None:
            if self.cell is not None:
                raise ValueError('UNCLOSED_CELL')
            self.rows.append(self.current)
            self.current = None


def verify(input_path, html_path, manifest_path):
    raw = Path(input_path).read_bytes()
    document = Path(html_path).read_bytes()
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    data = json.loads(raw)
    if data.get('schema') != SCHEMA or manifest.get('schema') != SCHEMA:
        raise ValueError('SCHEMA_MISMATCH')
    if digest(raw) != manifest.get('input_sha256') or digest(document) != manifest.get('html_sha256'):
        raise ValueError('HASH_MISMATCH')
    if data.get('verdict') != 'NO-BID / NO-DEPLOY' or data.get('tender_budget_cad') is not None:
        raise ValueError('UNAUTHORIZED_COMMERCIAL_CLAIM')
    if manifest.get('verdict') != 'NO-BID / NO-DEPLOY' or manifest.get('tender_budget_cad') is not None:
        raise ValueError('MANIFEST_BUDGET_OR_VERDICT')
    if not isinstance(data.get('records'), list) or len(data['records']) != 3:
        raise ValueError('RECORD_COUNT')
    p = FactParser()
    p.feed(document.decode('utf-8', errors='strict'))
    p.close()
    if p.lang != ['en'] or p.main_count != 1 or p.h1 != 1 or p.h2 != 3 or p.captions != 1 or p.col_scopes != 8 or p.row_scopes != 3 or p.skip != 1:
        raise ValueError('STRUCTURE_REJECTED')
    ids = [r['id'] for r in data['records']]
    if ids != manifest.get('record_ids') or len(ids) != len(set(ids)) or len(ids) != manifest.get('record_count'):
        raise ValueError('MANIFEST_RECORDS')
    if [x['id'] for x in p.rows] != ids:
        raise ValueError('RENDERED_RECORD_IDS')
    if p.links != [r['source_url'] for r in data['records']]:
        raise ValueError('SOURCE_LINKS')
    for rendered, source in zip(p.rows, data['records']):
        amount = ('Reported historical award: CAD ' + source['reported_award_cad']) if source['reported_award_cad'] is not None else 'Not established'
        expect = [source['name'], source['fact'], source['grade'], source['status'], source['date'], source['deadline'] or 'Not established', amount, 'Evidence source']
        if rendered['cells'] != expect:
            raise ValueError('FACT_MISMATCH')
    return {'accepted': True, 'scope': 'source_bound_semantic_html_only', 'records': len(ids),
            'input_sha256': digest(raw), 'html_sha256': digest(document), 'commercial_verdict': 'NO-BID / NO-DEPLOY'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--html', required=True)
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.input, args.html, args.manifest), sort_keys=True))
