"""Fetch the preregistered PHerc0139 level-zero public render chunks."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree as ET

HOST = 'https://vesuvius-challenge-open-data.s3.amazonaws.com/'
KEY = ('PHerc0139/segments/20260206000002-w054_2026020617/surface-volumes/'
       '9.362um-1.2m-113keV-volume-20250728140407.zarr/0/')
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'observations'
OUT.mkdir(exist_ok=True)
def get(url, limit):
    for attempt in range(3):
        try:
            with urlopen(url,timeout=30) as response:
                body = response.read(limit+1)
            break
        except HTTPError as e:
            if e.code in (404,403) or attempt == 2:
                raise
        except OSError:
            if attempt == 2:
                raise
    if len(body)>limit:
        raise ValueError('source exceeds bound')
    return body

def endpoint(y):
    prefix = KEY + '0/' + str(y) + '/'
    xml=ET.fromstring(get(HOST+'?'+urlencode({'list-type':2,'prefix':prefix,'max-keys':100}), 100000))
    if xml.findtext('{*}IsTruncated') != 'false':
        raise ValueError('unexpected listing truncation')
    keys=[obj.findtext('{*}Key') for obj in xml.findall('{*}Contents')]
    ids=sorted(int(k.removeprefix(prefix)) for k in keys if k and k.removeprefix(prefix).isdigit())
    if len(ids)<2:
        return []
    return [(y, ids[0]), (y, ids[-1])]

def sample(pos):
    y,x=pos
    url=HOST+KEY+f'0/{y}/{x}'
    result={'row':y,'col':x,'url':url}
    try:
        body=get(url,28*128*128)
    except HTTPError as e:
        if e.code == 404:
            return {**result,'available':False,'status':404}
        raise
    if len(body)!=28*128*128:
        raise ValueError('unexpected chunk size')
    # Use only authentic, fetched bytes for timing. Archive the whole returned object's hash.
    patch=body[5*128*128:22*128*128]
    (OUT / f'{y}_{x}.raw').write_bytes(patch)
    return {**result,'available':True,'size':len(body),'sha256':hashlib.sha256(body).hexdigest(),
            'crop_sha256':hashlib.sha256(patch).hexdigest()}

def main():
    spec=json.loads(get(HOST+KEY+'.zarray',4096))
    expected={'shape':[28,7660,11140],'chunks':[28,128,128],'dtype':'|u1','order':'C','compressor':None,
              'filters':None, 'dimension_separator':'/','fill_value':0}
    if any(spec.get(k)!=v for k,v in expected.items()):
        raise ValueError(f'source format changed: {spec}')
    cases=[(y,x) for y in (5,20,40,55) for x in (5,40,80)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        extra=list(pool.map(endpoint,(10,30,50)))
        cases.extend(v for pair in extra for v in pair)
        results=list(pool.map(sample,cases))
    (OUT/'manifest.json').write_text(json.dumps({'source':spec,'cases':results},indent=2)+'\n')
    print([(v['row'],v['col'],v['available']) for v in results])

if __name__=='__main__':
    main()
