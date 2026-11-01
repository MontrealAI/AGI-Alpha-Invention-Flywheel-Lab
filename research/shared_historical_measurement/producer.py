"""Source-bound multi-request producer. No network/model calls or financial state.
Existing recorded semantic readings are explicitly replay, not fresh inference.
"""
import argparse,csv,hashlib,io,json,time
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
VERSION='historical-measurement-batch/1'
ROIS={'road':[(580,165),(700,220),(700,255),(580,190)],'promenade':[(470,260),(500,260),(510,330),(465,330)]}
RIVER=[(250,260),(350,260),(350,340),(250,340)]
CROWN=[(1640,147),(1660,125),(1690,120),(1715,135),(1730,165),(1715,195),(1660,195),(1640,175)]
CAL=['2024-06-15','2024-06-23','2024-06-30','2024-07-14']
def digest(x):return hashlib.sha256(x).hexdigest()
def feature_key(source_sha,query):
 config={'version':VERSION,'source_sha256':source_sha,'observable':query,'roi':CROWN if query=='canopy' else ROIS[query],'normalization':'native RGB median G/(R+G+B)' if query=='canopy' else 'PIL RGB resize720x405 /255;river-relative;median,std,gradient quantiles'}
 return digest(canonical(config))
def in_window(row,window):
 return window is None or window[0]<=row['timestamp']<window[1]
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def mask(poly,size):
 im=Image.new('L',size);ImageDraw.Draw(im).polygon(poly,fill=1);return np.asarray(im).astype(bool)
class Producer:
 def __init__(self,source,data):
  self.source,self.data=Path(source),Path(data);self.count=Counter();self.bindings={}
 def metadata(self,rel):
  b=(self.source/rel).read_bytes();self.count['metadata_reads']+=1;self.count['metadata_bytes']+=len(b);self.bindings[rel]=digest(b);return b
 def read_image(self,entry,path):
  b=Path(path).read_bytes();self.count['image_reads']+=1;self.count['image_bytes']+=len(b);self.count['source_hash_checks']+=1
  if digest(b)!=entry['sha256']:raise ValueError('Source hash mismatch: '+entry.get('filename',str(path)))
  im=Image.open(io.BytesIO(b)).convert('RGB');self.count['image_decodes']+=1
  if im.size!=(1920,1080):raise ValueError('Unapproved camera geometry')
  return im
 def pavement(self,im,queries):
  a=np.asarray(im.resize((720,405)),dtype=float)/255;gray=a.mean(2);gx=np.abs(np.roll(gray,1,1)-gray);gy=np.abs(np.roll(gray,1,0)-gray);ref=np.median(a[mask(RIVER,(720,405))],axis=0)
  self.count['shared_scene_feature_computations']+=1;out={}
  for q in queries:
   m=mask(ROIS[q],(720,405));px=a[m]
   out[q]=(np.r_[np.median(px,axis=0)-ref,np.std(px,axis=0),np.quantile(gx[m],[.5,.9]),np.quantile(gy[m],[.5,.9])],float(np.mean(gray[m])))
   self.count['pavement_roi_feature_computations']+=1
  return out
 def probe_path(self,relative):
  primary=self.data/'v3_canopy'/relative
  return primary if primary.exists() else self.data/'portable_result/v3_canopy'/relative
 def gcc(self,im):
  a=np.asarray(im,dtype=float);px=a[mask(CROWN,im.size)];self.count['canopy_roi_feature_computations']+=1
  return float(np.median(px[:,1]/np.maximum(px.sum(1),1)))
 def run(self,queries,windows=None):
  if len(set(queries))!=len(queries) or not set(queries)<=set(ROIS)|{'canopy'}:raise ValueError('Unsupported or repeated query')
  windows=windows or {}
  if not set(windows)<=set(queries):raise ValueError('Window for unrequested query')
  if any(len(w)!=2 or w[0]>=w[1] for w in windows.values()):raise ValueError('Invalid half-open window')
  start=time.perf_counter();cpu=time.process_time();results={};pq=[q for q in queries if q in ROIS]
  if pq:
   man=[x for x in json.loads(self.metadata('manifest.json')) if 'error' not in x]
   native=json.loads(self.metadata('v2/production_native_responses.json'));lookup={(x['filename'],x['query']):x for x in native}
   if len(lookup)!=len(native):raise ValueError('Duplicate native response')
   cal=[x for x in man if x['timestamp'][:10] in CAL and x['timestamp'][11:13] in ['13','18','23']]
   calnames={x['filename'] for x in cal};features={}
   for x in man:
    needed=[q for q in pq if x['filename'] in calnames or in_window(x,windows.get(q))]
    if not needed:continue
    computed=self.pavement(self.read_image(x,self.data/'images'/x['filename']),needed)
    for q,value in computed.items():features[feature_key(x['sha256'],q)]=value
   labels=np.array([int(x['timestamp'][:10]=='2024-06-30') for x in cal])
   for q in pq:
    train=np.array([features[feature_key(x['sha256'],q)][0] for x in cal]);scale=np.maximum(np.std(train,axis=0),.015);rows=[]
    for x in man:
     if not in_window(x,windows.get(q)):continue
     f,b=features[feature_key(x['sha256'],q)];d=np.sqrt(np.mean(((train-f)/scale)**2,axis=1));d0=float(min(d[labels==0]));d1=float(min(d[labels==1]));margin=abs(d0-d1)/(d0+d1+1e-9)
     state='unknown' if b<.12 or min(d0,d1)>3 or margin<.15 else ('water_contact' if d1<d0 else 'no_water_contact')
     mode='compiled' if state=='no_water_contact' and margin>=.30 and d0<=1 else 'recorded_native_replay'
     s=lookup.get((x['filename'],'sidewalk' if q=='promenade' else q))
     if s and s.get('geometry_valid') is False:mode='recorded_native_replay';state='unknown'
     elif mode=='recorded_native_replay':state=s['state'] if s else 'unknown'
     if mode=='recorded_native_replay':self.count['recorded_semantic_rows_replayed']+=int(s is not None)
     rows.append({**{k:x[k] for k in ['filename','timestamp','url','sha256']},'query':q,'state':state,'method':mode,'compiled_distance_dry':d0,'compiled_distance_wet':d1,'compiled_margin':margin,'evidence':s.get('evidence','') if s else '', 'geometry_valid':s.get('geometry_valid') if s else None})
    results[q]=rows
  if 'canopy' in queries:
   man=[x for x in json.loads(self.metadata('v3_canopy/manifest.json')) if 'error' not in x];native=json.loads(self.metadata('v3_canopy/native_predictions.json'));lookup={x['filename']:x for x in native}
   if len(lookup)!=len(native):raise ValueError('Duplicate canopy response')
   probes=json.loads(self.metadata('v3_canopy/probes/proposal.json'))['probes'];scores={};refs={}
   man=[x for x in man if in_window(x,windows.get('canopy'))]
   # Deduplicate calibration sources against requested observations by content hash.
   for x in man:scores[x['sha256']]=self.gcc(self.read_image(x,self.data/'v3_canopy/images'/x['filename']))
   for x in probes:
    if x['sha256'] not in scores:scores[x['sha256']]=self.gcc(self.read_image(x,self.probe_path(x['file'])))
    refs[x['day']]=scores[x['sha256']]
   low,high=refs['2024-03-15'],refs['2024-05-15'];rows=[]
   for x in man:
    g=scores[x['sha256']];ratio=(g-low)/(high-low) if high>low else None;state='unknown' if ratio is None else 'leafless' if ratio<=.2 else 'leafed' if ratio>=.8 else 'partial';s=lookup.get(x['filename']);n=s['state'] if s else 'unknown';self.count['recorded_semantic_rows_replayed']+=int(s is not None)
    rows.append({**{k:x[k] for k in ['filename','timestamp','url','sha256']},'query':'canopy','state':state,'method':'ordinary_green_chromatic_coordinate','gcc':g,'native_state':n,'native_method':'recorded_native_replay','quality_flag':'native_uncertain' if n=='unknown' else 'method_disagreement' if n!=state else 'methods_agree'})
   results['canopy']=rows
  self.count['fresh_model_calls']=0;self.count['fresh_model_image_interpretations']=0
  return results,{'counts':dict(self.count),'wall_seconds':time.perf_counter()-start,'cpu_seconds':time.process_time()-cpu,'source_bindings':self.bindings}
def commission(source,data,queries,windows=None):
 """Nonfinancial versioned request envelope; no identity/settlement claims."""
 request={'schema':VERSION,'queries':queries,'purpose':'historical sampled observations','fresh_model_inference':False,'windows':windows or {}}
 p=Producer(source,data);outputs,receipt=p.run(queries,windows)
 contract={'request':request,'request_sha256':digest(canonical(request)),'source_bindings':receipt['source_bindings'],'outputs':{q:{'rows':len(rows),'sha256':digest(canonical(rows))} for q,rows in outputs.items()},'native_financial_admission':False,'producer_sha256':digest(Path(__file__).read_bytes())}
 t=time.perf_counter();c=time.process_time();audit=verify_sources(contract,outputs,source);receipt['counts'].update(audit);receipt['commission_verification_wall_seconds']=time.perf_counter()-t;receipt['commission_verification_cpu_seconds']=time.process_time()-c;return outputs,receipt,contract
def verify(contract,outputs):
 if contract['request']['schema']!=VERSION:raise ValueError('Unsupported schema')
 if digest(canonical(contract['request']))!=contract['request_sha256']:raise ValueError('Request binding failed')
 if set(outputs)!=set(contract['request']['queries']):raise ValueError('Scope mismatch')
 for q,rows in outputs.items():
  if any(r['query']!=q for r in rows):raise ValueError('Cross-scope row')
  if len({r['filename'] for r in rows})!=len(rows):raise ValueError('Duplicate observation')
  if {'rows':len(rows),'sha256':digest(canonical(rows))}!=contract['outputs'][q]:raise ValueError('Output binding failed')
 return True

def verify_sources(contract,outputs,source):
 """Independent metadata binding audit; does not re-decode or assert ground truth."""
 verify(contract,outputs);source=Path(source);count=Counter();raw={}
 for rel,h in contract['source_bindings'].items():
  path=(source/rel).resolve()
  if not path.is_relative_to(source.resolve()):raise ValueError('Source path escape')
  b=path.read_bytes();count['verification_metadata_reads']+=1;count['verification_metadata_bytes']+=len(b)
  if digest(b)!=h:raise ValueError('Changed metadata: '+rel)
  raw[rel]=json.loads(b)
 for q,rows in outputs.items():
  rel='v3_canopy/manifest.json' if q=='canopy' else 'manifest.json'
  man={x['filename']:x for x in raw[rel] if 'error' not in x and in_window(x,contract['request'].get('windows',{}).get(q))}
  if set(man)!={r['filename'] for r in rows}:raise ValueError('Incomplete requested source cohort')
  for row in rows:
   if any(row[k]!=man[row['filename']][k] for k in ['filename','timestamp','sha256','url']):raise ValueError('Observation source mismatch')
   count['verification_source_rows']+=1
 return dict(count)
