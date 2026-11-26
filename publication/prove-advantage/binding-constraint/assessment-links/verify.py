#!/usr/bin/env python3
"""List the independently checked public assessment links and reverify a source."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


INDEX = Path(__file__).with_name('LINKS.json')
PORTAL_HOST = 'open.canada.ca'
STORAGE_HOST = 'opencanada.blob.core.windows.net'
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
HASH = re.compile(r'[0-9a-f]{64}')


def portal_download(url, dataset_id, resource_id):
    parts = urlsplit(url)
    paths = unquote(parts.path).split('/')
    if paths[:2] == ['', 'data'] and len(paths) > 2 and paths[2] in ('en', 'fr'):
        del paths[2]
    prefix = ['', 'data', 'dataset', dataset_id, 'resource', resource_id, 'download']
    return (
        parts.scheme == 'https' and parts.netloc == PORTAL_HOST
        and not parts.query and not parts.fragment
        and paths[:-1] == prefix and paths[-1] not in ('', '.', '..') and '\\' not in paths[-1]
    )


class ResourceRedirect(HTTPRedirectHandler):
    def __init__(self, dataset_id, resource_id):
        self.dataset_id = dataset_id
        self.resource_id = resource_id

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        paths = unquote(parts.path).split('/')
        same_blob = (
            parts.scheme == 'https' and parts.netloc == STORAGE_HOST
            and len(paths) == 5 and paths[:4] == ['', 'opengovprod', 'resources', self.resource_id]
            and paths[-1] not in ('', '.', '..') and '\\' not in paths[-1] and not parts.fragment
        )
        if not (same_blob or portal_download(newurl, self.dataset_id, self.resource_id)):
            raise ValueError('The official download redirected outside the registered resource.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify(source):
    dataset_id, resource_id = source['dataset_id'], source['resource_id']
    digest, expected_size = source['sha256'], source['bytes']
    if (not UUID.fullmatch(dataset_id) or not UUID.fullmatch(resource_id) or not HASH.fullmatch(digest)
            or type(expected_size) is not int or not 0 < expected_size <= 6_291_456):
        raise ValueError('Invalid resource identity in the published index.')
    if not portal_download(source['download'], dataset_id, resource_id):
        raise ValueError('The download does not bind the indexed assessment.')
    request = Request(source['download'], headers={'Accept-Encoding': 'identity'})
    opener = build_opener(ResourceRedirect(dataset_id, resource_id))
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise ValueError(f'The official resource returned unexpected HTTP status {response.status}.')
            body = response.read(expected_size + 1)
    except HTTPError as error:
        raise ValueError(f'The official resource returned HTTP {error.code}.') from None
    except OSError:
        raise ValueError('The official resource could not be retrieved.') from None
    if len(body) != expected_size or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError('Published resource bytes differ. Review the new edition before reuse.')
    return {'resource_id': resource_id, 'bytes': expected_size, 'sha256': digest, 'verified': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--system', help='Exact ID from the Government of Canada AI Register.')
    parser.add_argument('--verify', action='store_true', help='Download and hash the exact listed source.')
    args = parser.parse_args()
    if args.verify and not args.system:
        parser.error('--verify requires --system')
    index = json.loads(INDEX.read_text(encoding='utf-8'))
    if not args.system:
        result = index
    else:
        matches = [row for row in index['links'] if row['register_id'] == args.system]
        if len(matches) != 1:
            parser.exit(1, 'No independently checked link in this snapshot for that register ID.\n')
        result = {'register_sha256': index['register_sha256'], **matches[0]}
        if args.verify:
            try:
                result['verification'] = verify(result['assessment'])
            except ValueError as error:
                parser.exit(2, f'{error}\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
