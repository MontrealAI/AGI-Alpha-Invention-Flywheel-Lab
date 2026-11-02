import argparse, hashlib, json, time, urllib.request
from pathlib import Path

ENDPOINTS = [
    'https://data.mendeley.com/public-api/datasets/zh58byr53c/files?folder_id=root&version=2',
    'https://data.mendeley.com/public-api/datasets/zh58byr53c/files?version=2',
    'https://data.mendeley.com/public-api/datasets/zh58byr53c/versions/2',
    'https://api.data.mendeley.com/datasets/zh58byr53c/files?version=2',
]

def catalog_entries(payload):
    if isinstance(payload,dict) and any(k in payload for k in ('error','errors')): raise ValueError('REMOTE_ERROR_PAYLOAD_IS_NOT_A_CATALOG')
    if isinstance(payload,list): entries=payload
    elif isinstance(payload,dict):
        entries=payload.get('files',payload.get('data',[]))
        if isinstance(entries,dict): entries=entries.get('files',entries.get('items',[]))
    else: entries=[]
    if not isinstance(entries,list) or not entries or any(not isinstance(e,dict) or not e.get('id') or not any(e.get(k) for k in ('filename','name','label')) for e in entries): raise ValueError('NONEMPTY_NAMED_CATALOG_ENTRIES_REQUIRED')
    return entries

def main():
    p=argparse.ArgumentParser(); p.add_argument('--output',required=True); a=p.parse_args()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=False)
    attempts=[]; started=time.time()
    for i,url in enumerate(ENDPOINTS):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'AGI-Alpha-public-research/1.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=45) as r:
                raw=r.read(4_000_001); status=r.status
            if len(raw)>4_000_000: raise ValueError('catalog exceeds bounded metadata size')
            payload=json.loads(raw)
            entries=catalog_entries(payload)
            file=out/f'catalog-{i}.json'; file.write_bytes(raw)
            attempts.append({'url':url,'status':status,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'file':file.name,'entry_count':len(entries)})
            print(json.dumps({'catalog':payload},sort_keys=True)[:50000],flush=True)
            break
        except Exception as e:
            attempts.append({'url':url,'error':type(e).__name__+': '+str(e)})
    receipt={'stage':'public_catalog_only','dataset_doi':'10.17632/zh58byr53c.2','attempts':attempts,'elapsed_seconds':time.time()-started,'scientific_verdict':'NOT_EVALUATED','success':any('sha256' in x for x in attempts)}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt),flush=True)
    return 0 if receipt['success'] else 2

if __name__=='__main__': raise SystemExit(main())
