"""Confirm collection titles and observe the ordinary unauthenticated HDF5 response."""

from hashlib import sha256
import json
from pathlib import Path
from time import monotonic_ns
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from capture import COLLECTIONS, NoRedirect, query, utc_now

base='https://cmr.earthdata.nasa.gov/search/collections.umm_json'
opener=build_opener(NoRedirect())
receipts={}
for family,concept in COLLECTIONS.items():
    url=base+'?'+urlencode({'concept_id':concept,'page_size':5})
    data,receipt=query(opener,url)
    payload=json.loads(data)
    if receipt['hits']!=1 or payload['items'][0]['meta']['concept-id']!=concept:
        raise ValueError('Unexpected collection result')
    receipt['entry_title']=payload['items'][0]['umm']['EntryTitle']
    receipt['short_name']=payload['items'][0]['umm']['ShortName']
    receipt['version']=payload['items'][0]['umm']['Version']
    with (Path('raw')/(family+'-collection.json')).open('xb') as stream: stream.write(data)
    receipts[family]=receipt

sample=json.loads(Path('raw/montreal-nisar.json').read_bytes())['items'][0]
data_url=next(x['URL'] for x in sample['umm']['RelatedUrls'] if x['Type']=='GET DATA' and x['URL'].endswith('.h5'))
assert urlsplit(data_url).hostname=='nisar.asf.earthdatacloud.nasa.gov'
start_at=utc_now();started=monotonic_ns()
access={'url':data_url,'granule':sample['meta']['concept-id'],'method':'HEAD','auth_supplied':False,
        'data_file_body_requested':False,'started_at':start_at}
try:
    with opener.open(Request(data_url,headers={'User-Agent':'MONTREAL.AI-public-catalog-study/1.0'},method='HEAD'),timeout=12) as response:
        access['status']=response.status
except HTTPError as error:
    access['status']=error.code
    location=error.headers.get('Location')
    if location:
        access['redirect_hostname']=urlsplit(location).hostname
except (URLError, TimeoutError) as error:
    access['error_type']=type(error).__name__
access['finished_at']=utc_now()
access['elapsed_ns']=monotonic_ns()-started
encoded=(json.dumps({'collection_metadata':receipts,'representative_hdf5_access':access},indent=2,sort_keys=True)+'\n').encode()
with Path('COLLECTION-ACCESS.json').open('xb') as stream: stream.write(encoded)
print(sha256(encoded).hexdigest(),{k:v['entry_title'] for k,v in receipts.items()}, {k:access[k] for k in ('status','redirect_hostname','error_type') if k in access})
