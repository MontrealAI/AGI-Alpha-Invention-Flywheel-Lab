import argparse, hashlib, json, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE = 'https://data.mendeley.com/public-api/datasets/zh58byr53c'
VERSION = 2
MAX_RESPONSE = 4_000_000

def catalog_entries(payload, kind='files'):
    if isinstance(payload,dict) and any(k in payload for k in ('error','errors')): raise ValueError('REMOTE_ERROR_PAYLOAD_IS_NOT_A_CATALOG')
    if isinstance(payload,list): entries=payload
    elif isinstance(payload,dict):
        if kind in payload: entries=payload[kind]
        elif 'data' in payload: return catalog_entries(payload['data'],kind)
        elif 'items' in payload: entries=payload['items']
        else: raise ValueError('EXPLICIT_CATALOG_CONTAINER_REQUIRED')
    else: raise ValueError('CATALOG_LIST_OR_OBJECT_REQUIRED')
    if not isinstance(entries,list) or any(not isinstance(e,dict) or not isinstance(e.get('id'),str) or not e['id'].strip() or not any(isinstance(e.get(k),str) and e[k].strip() for k in ('filename','name','label')) for e in entries): raise ValueError('NAMED_CATALOG_ENTRY_IDS_REQUIRED')
    return entries

def schema_summary(payload):
    if isinstance(payload,list): return {'type':'list','length':len(payload),'first_entry_keys':sorted(payload[0]) if payload and isinstance(payload[0],dict) else None}
    if isinstance(payload,dict): return {'type':'object','keys':sorted(payload)[:40],'array_lengths':{k:len(v) for k,v in payload.items() if isinstance(v,list)},'remote_error':payload.get('error',payload.get('errors')) if any(k in payload for k in ('error','errors')) else None}
    return {'type':type(payload).__name__}

def named_summary(entry,path=''):
    details=entry.get('content_details')
    return {'id':entry['id'],'name':entry.get('filename',entry.get('name',entry.get('label'))),'path':path,'parent_id':entry.get('parent_id'),'keys':sorted(entry),'content_details_keys':sorted(details) if isinstance(details,dict) else None,'size':entry.get('size',details.get('size') if isinstance(details,dict) else None)}

class Recorder:
    def __init__(self,output,opener=urllib.request.urlopen):
        self.output,self.opener,self.attempts=Path(output),opener,[]
        self.access_denied=False
    def get(self,url,kind=None):
        row={'url':url,'status':None,'response_received':False}
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'AGI-Alpha-public-research/1.0','Accept':'application/json'})
            try: response=self.opener(request,timeout=45)
            except urllib.error.HTTPError as error: response=error
            with response:
                row.update(status=response.status,response_received=True)
                raw=response.read(MAX_RESPONSE+1); row['content_type']=response.headers.get('Content-Type')
            bounded=raw[:MAX_RESPONSE]
            row.update(bytes=len(bounded),sha256=hashlib.sha256(bounded).hexdigest(),truncated=len(raw)>MAX_RESPONSE,hash_scope='complete_response' if len(raw)<=MAX_RESPONSE else 'bounded_prefix')
            filename='response-'+str(len(self.attempts)).zfill(3)+'.bin'
            (self.output/filename).write_bytes(bounded); row['file']=filename
            if row['status'] in (401,403,451):
                self.access_denied=True
                raise ValueError('PUBLIC_ACCESS_DENIED_NO_AUTHENTICATION_ATTEMPTED')
            if row['truncated']: raise ValueError('BOUNDED_METADATA_RESPONSE_EXCEEDED')
            payload=json.loads(raw); row['schema']=schema_summary(payload)
            if row['status']!=200: raise ValueError('HTTP_METADATA_REQUEST_FAILED')
            if isinstance(payload,dict) and any(k in payload for k in ('error','errors')):
                if payload.get('error') in (401,403,451): self.access_denied=True
                raise ValueError('REMOTE_ERROR_PAYLOAD_IS_NOT_A_CATALOG')
            if kind is not None:
                entries=catalog_entries(payload,kind)
                row.update(entry_count=len(entries),empty_catalog=not entries,named_entries=[named_summary(e) for e in entries[:30]])
            self.attempts.append(row); print(json.dumps({'metadata_response':row},sort_keys=True)[:16000],flush=True)
            return payload
        except Exception as error:
            row['error']=type(error).__name__+': '+str(error); self.attempts.append(row)
            print(json.dumps({'metadata_response':row},sort_keys=True)[:16000],flush=True)
            return None

def endpoint(kind='',**query):
    return BASE+('/'+kind if kind else '')+'?'+urllib.parse.urlencode({'version':VERSION,**query})

def priority(entry):
    name=str(entry.get('name',entry.get('filename',entry.get('label','')))).lower()
    return (not any(x in name for x in ('processed','character','single','hppc')),name,entry['id'])

def acquire(output,max_folders=16,opener=urllib.request.urlopen):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic(); recorder=Recorder(output,opener)
    metadata=recorder.get(endpoint())
    files,folders,visited,queue={},{},set(),[]
    def include(payload,kind,path=''):
        if payload is None: return
        try: rows=catalog_entries(payload,kind)
        except ValueError: return
        for entry in rows:
            key=entry['id']
            if kind=='files': files.setdefault(key,{'path':path,'entry':entry})
            elif key not in folders:
                name=entry.get('name',entry.get('label','')); full='/'.join(x for x in (path,name) if x)
                folders[key]={'path':full,'entry':entry}; queue.append((key,full))
    if isinstance(metadata,dict):
        for kind in ('files','folders'):
            if kind in metadata: include(metadata,kind)
    if not recorder.access_denied: include(recorder.get(endpoint('files',folder_id='root'),'files'),'files')
    if not recorder.access_denied: include(recorder.get(endpoint('folders'),'folders'),'folders')
    queue.sort(key=lambda pair:priority(folders[pair[0]]['entry']))
    candidates=[]
    while queue and len(visited)<max_folders and not recorder.access_denied:
        ident,path=queue.pop(0)
        if ident in visited: continue
        visited.add(ident)
        include(recorder.get(endpoint('files',folder_id=ident),'files'),'files',path)
        candidates=[named_summary(row['entry'],row['path']) for row in files.values() if str(row['entry'].get('filename',row['entry'].get('name',''))).lower().endswith(('.mat','.xlsx','.xls'))]
        if candidates: break
        if not recorder.access_denied: include(recorder.get(endpoint('folders',parent_id=ident),'folders'),'folders',path)
        queue.sort(key=lambda pair:priority(folders[pair[0]]['entry']))
    if not candidates: candidates=[named_summary(row['entry'],row['path']) for row in files.values() if str(row['entry'].get('filename',row['entry'].get('name',''))).lower().endswith(('.mat','.xlsx','.xls'))]
    (output/'catalog.json').write_text(json.dumps({'dataset_id':'zh58byr53c','version_requested':VERSION,'files':list(files.values()),'folders':list(folders.values())},indent=2)+'\n')
    receipt={'stage':'public_metadata_only','dataset_doi':'10.17632/zh58byr53c.2','attempts':recorder.attempts,'elapsed_seconds':time.monotonic()-started,'metadata_received':any(x['response_received'] for x in recorder.attempts),'access_denied':recorder.access_denied,'files_found':len(files),'folders_found':len(folders),'folders_visited':len(visited),'folder_visit_budget':max_folders,'traversal_complete':not queue and not candidates and not recorder.access_denied and all('error' not in x for x in recorder.attempts),'format_candidates':candidates[:30],'measurement_files_downloaded':0,'scientific_verdict':'NOT_EVALUATED','success':bool(candidates),'route_basis':'Public website proxy; official API documents separate versioned dataset metadata, files with folder_id, and folders with parent_id. Proxy mappings are verified only by recorded responses.'}
    (output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'catalog_summary':{k:v for k,v in receipt.items() if k!='attempts'}},sort_keys=True),flush=True)
    return receipt

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--output',required=True); parser.add_argument('--max-folders',type=int,default=16); args=parser.parse_args()
    if args.max_folders<1: raise ValueError('POSITIVE_FINITE_FOLDER_VISIT_BUDGET_REQUIRED')
    return 0 if acquire(args.output,args.max_folders)['success'] else 2

if __name__=='__main__': raise SystemExit(main())
