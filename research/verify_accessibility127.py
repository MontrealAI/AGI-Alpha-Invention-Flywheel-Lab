"""Independent key-free verifier for the accessibility127 source-bound HTML packet."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = 'agi-alpha/accessibility127/public-evidence/v1'

# Independent verifier-owned contract for every fixed non-record text node.
# Do not import the producer's renderer: a producer change must not approve itself.
ALLOWED_TAGS = {'html', 'head', 'meta', 'title', 'body', 'a', 'main', 'h1', 'p',
                'h2', 'table', 'caption', 'thead', 'tr', 'th', 'tbody', 'td', 'strong'}
EXPECTED_META = [{'charset': 'utf-8'},
                 {'name': 'viewport', 'content': 'width=device-width, initial-scale=1'}]
EXPECTED_STATIC = ' '.join("Accessibility127: Public evidence — no bid\nSkip to main content\nPublic document accessibility: evidence and open limits\nThis is a research fact sheet, not an issuer-verified tender package, customer agreement, accessible-PDF remediation, independent WCAG certificate, or paid commercial result.\nEvidence observations\nThree observed public procurement signals; grades are not interchangeable\nOpportunity Verified scope / observation Source grade Observed status Observation date Deadline Award amount Link\nCommercial decision\nNO-BID / NO-DEPLOY. Original issuer terms, supplier eligibility, deliverable acceptance, production capacity, independent accessibility review, buyer choice and complete costs are unverified. No tender budget or collected revenue is established.\nThe Vaughan download fee is not a contract award; a Toronto third-party value estimate is not an observed buyer budget; historical awarded values are not our prices or receipts.\nLimitations\nThis view uses manually transcribed, cited facts, not fetched or cryptographically signed original-source bytes. Semantic HTML checks do not establish screen-reader performance or WCAG compliance. Existing specialist remediators and in-house teams remain capable competitors.".split())


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
        self.meta_attrs = []
        self.static_text = []
        self.stack = []  # Independent well-formed semantic containment contract.

    def handle_starttag(self, tag, attrs):
        att = dict(attrs)
        if tag not in ALLOWED_TAGS or len(att) != len(attrs):
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
        parent = self.stack[-1] if self.stack else None
        # HTMLParser is token-oriented and does not enforce a browser-like tree.
        # A count of <main> alone cannot establish that the verified content
        # remains inside it. Reject all unregistered nesting and orphan tags.
        required_parent = {
            'html': None, 'head': 'html', 'meta': 'head',
            'title': 'head', 'body': 'html', 'main': 'body',
            'h1': 'main', 'h2': 'main', 'p': 'main',
            'strong': 'p', 'table': 'main', 'caption': 'table',
            'thead': 'table', 'tbody': 'table',
            'tr': ('thead', 'tbody'), 'th': 'tr', 'td': 'tr',
            'a': ('body', 'td'),
        }[tag]
        if isinstance(required_parent, tuple):
            permitted = parent in required_parent
        else:
            permitted = parent == required_parent
        if not permitted:
            raise ValueError('SEMANTIC_NESTING_REJECTED')
        if tag == 'meta':
            if att not in EXPECTED_META:
                raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
            self.meta_attrs.append(att)
        elif tag == 'html' and att != {'lang': 'en'}:
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
        elif tag == 'main' and att != {'id': 'main'}:
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
        elif tag == 'a' and set(att) != {'href'}:
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
        elif tag == 'th' and att not in ({'scope': 'col'}, {'scope': 'row'}):
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
        elif tag == 'tr' and (set(att) not in (set(), {'data-record-id'})):
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
        elif tag not in {'meta', 'html', 'main', 'a', 'th', 'tr'} and att:
            raise ValueError('UNSAFE_HTML_TAG_OR_ATTRIBUTE')
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
        if tag != 'meta':  # HTML meta is a void element.
            self.stack.append(tag)
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
        elif self.current is not None:
            if data.strip():
                raise ValueError('UNEXPECTED_ROW_TEXT')
        else:
            self.static_text.append(data)

    def handle_comment(self, data):
        raise ValueError('UNEXPECTED_HTML_COMMENT')

    def handle_decl(self, decl):
        if decl.lower() != 'doctype html':
            raise ValueError('UNSUPPORTED_HTML_DECLARATION')

    def handle_pi(self, data):
        raise ValueError('UNSUPPORTED_HTML_INSTRUCTION')

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            raise ValueError('SEMANTIC_NESTING_REJECTED')
        if tag in {'th', 'td'} and self.cell is not None:
            self.current['cells'].append(''.join(self.cell).strip())
            self.cell = None
            self.current_tag = None
        if tag == 'tr' and self.current is not None:
            if self.cell is not None:
                raise ValueError('UNCLOSED_CELL')
            self.rows.append(self.current)
            self.current = None
        self.stack.pop()


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
    if p.meta_attrs != EXPECTED_META or p.current is not None or p.cell is not None or p.stack:
        raise ValueError('STRUCTURE_REJECTED')
    if ' '.join(' '.join(p.static_text).split()) != EXPECTED_STATIC:
        raise ValueError('UNEXPECTED_STATIC_TEXT')
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
