#!/usr/bin/env python3
"""Check the frozen September 29 Prusa product-page capture without executing it."""

import argparse
import gzip
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

CAPTURED_AT = '2026-09-29T19:26:30Z'
MEMENTO = 'Tue, 29 Sep 2026 19:26:30 GMT'
PRODUCT = 'https://www.prusa3d.com/product/ht-hotend-upgrade-for-core-one-and-core-one-l/'
ARCHIVE = 'https://web.archive.org/web/20260929192630id_/' + PRODUCT
ARCHIVED_HTML_SHA256 = 'ae0d4313f129c38c1eed62fa4d92af732fed4bc8cfdf8db2436bf755c7d8633b'
TITLE = 'HT Hotend Upgrade (for CORE One/+ and CORE One L/+)'
COMPATIBILITY = {
    'CORE One/+': ('core-one', 'core-one-plus'),
    'CORE One L': ('core-one-l',),
    'CORE One+ (Gen 2)': ('core-one-plus-gen2',),
    'CORE One L+': ('core-one-l-plus',),
}
LIMIT = 2_000_000
RECEIPT = Path(__file__).resolve().parents[1] / 'publication/frontier-alpha-1-oem-archive.json'


class ProductPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.visible = []
        self.structured = []
        self.inert = None
        self.product_json = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.inert = tag
            attrs = dict(attrs)
            self.product_json = tag == 'script' and attrs.get('id') == 'product-jsonld'

    def handle_endtag(self, tag):
        if tag == self.inert:
            self.inert = None
            self.product_json = False

    def handle_data(self, text):
        if self.product_json:
            self.structured.append(text)
        elif self.inert is None and text.strip():
            self.visible.append(text.strip())


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_capture():
    request = Request(ARCHIVE, headers={'User-Agent': 'FRONTIER research evidence check'})
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        if (response.status != 200 or response.url != ARCHIVE
                or response.headers.get('Memento-Datetime') != MEMENTO):
            raise ValueError('The archive did not return the pinned September capture.')
        return response.read(LIMIT + 1)


def check(raw):
    if len(raw) > LIMIT:
        raise ValueError('Capture exceeds its byte limit.')
    if raw.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=BytesIO(raw)) as stream:
            raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT or sha256(raw).hexdigest() != ARCHIVED_HTML_SHA256:
        raise ValueError('Decoded content does not match the frozen manufacturer page.')
    page = ProductPage()
    page.feed(raw.decode('utf-8'))
    page.close()
    product = json.loads(''.join(page.structured))
    if product['name'] != TITLE or product['@type'] != 'Product':
        raise ValueError('Unexpected product listing.')
    panel = page.visible[page.visible.index(TITLE):]
    divider = panel.index('Not compatible with')
    listed = [text for text in panel[:divider] if text in COMPATIBILITY]
    market = page.visible.index('Shipping to')
    exclusions = {'INDX (C1)', 'INDX (C1L)'}
    if (set(listed) != COMPATIBILITY.keys() or len(listed) != len(COMPATIBILITY)
            or page.visible[market + 1] != 'United States'
            or 'Add to cart' not in panel or 'Order preparation time is 2 weeks.' not in panel
            or not any('400°C HT Hotend' in line for line in panel[:45])
            or not exclusions.issubset(panel[divider:divider + 40])
            or not any(offer.get('availability') == 'InStock' for offer in product['offers'])):
        raise ValueError('Manufacturer offer or its compatibility scope was not reproduced.')
    return {
        'schema': 'frontier-omega-alpha/alpha-1-oem-archive-v1',
        'captured_at': CAPTURED_AT,
        'manufacturer_url': PRODUCT,
        'archive_url': ARCHIVE,
        'decoded_html_sha256': ARCHIVED_HTML_SHA256,
        'captured_storefront': 'United States',
        'catalog_nozzle_limit_c': 400,
        'compatible_configurations': [model for group in listed for model in COMPATIBILITY[group]],
        'excluded_configurations': sorted(exclusions),
        'order_preparation_weeks_listed': 2,
        'order_surface_visible': True,
        'fulfillment_verified': False,
        'continuous_daily_availability_verified': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Check an existing copy of the archived response')
    parser.add_argument('--check', action='store_true', help='Compare with the published extracted receipt')
    args = parser.parse_args()
    if args.snapshot:
        with args.snapshot.open('rb') as stream:
            result = check(stream.read(LIMIT + 1))
    else:
        result = check(get_capture())
    if args.check and json.loads(RECEIPT.read_text(encoding='utf-8')) != result:
        raise SystemExit('The extracted metadata differs from the published receipt.')
    print(json.dumps(result, indent=2))
