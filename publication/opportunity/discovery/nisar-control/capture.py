"""Fetch four matched public CMR point catalog responses without data-file downloads."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from time import monotonic_ns
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

SITES = {'montreal': '-73.5673,45.5017', 'quebec-city': '-71.2080,46.8139'}
COLLECTIONS = {'nisar': 'C3622247503-ASF', 'opera': 'C3294057315-ASF'}
WINDOW = '2026-10-21T00:00:00Z,2026-11-24T23:59:59.999Z'
CMR = 'https://cmr.earthdata.nasa.gov/search/granules.umm_json'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')


def query(opener, url):
    started=utc_now()
    start=monotonic_ns()
    with opener.open(Request(url, headers={'User-Agent':'MONTREAL.AI-public-catalog-study/1.0','Cache-Control':'no-cache'}), timeout=18) as response:
        if response.status != 200 or response.url != url:
            raise ValueError('Unexpected CMR response')
        payload=response.read(8_000_001)
        hit_header=int(response.headers['CMR-Hits'])
        request_id=response.headers.get('CMR-Request-Id')
    if not 0 < len(payload) <= 8_000_000:
        raise ValueError('Unexpected CMR body length')
    data=json.loads(payload)
    if hit_header!=data['hits'] or data['hits']!=len(data['items']):
        raise ValueError('Incomplete catalog page')
    receipt={'url':url,'status':200,'bytes':len(payload),'sha256':sha256(payload).hexdigest(),
             'started_at':started,'finished_at':utc_now(),'elapsed_ns':monotonic_ns()-start,
             'hits':data['hits'],'cmr_request_id':request_id}
    return payload,receipt


def main():
    raw=Path('raw')
    raw.mkdir(exist_ok=False)
    opener=build_opener(NoRedirect())
    receipts={}
    for site, point in SITES.items():
        for family, collection in COLLECTIONS.items():
            url=CMR+'?'+urlencode({'collection_concept_id':collection,'point':point,'temporal':WINDOW,'page_size':200})
            name=f'{site}-{family}'
            payload,receipt=query(opener,url)
            with (raw/(name+'.json')).open('xb') as stream:
                stream.write(payload)
            receipts[name]=receipt
            print(name,receipt['hits'],receipt['bytes'],flush=True)
    encoded=(json.dumps(receipts,indent=2,sort_keys=True)+'\n').encode()
    with Path('CAPTURES.json').open('xb') as stream: stream.write(encoded)
    print(sha256(encoded).hexdigest())


if __name__=='__main__':
    main()
