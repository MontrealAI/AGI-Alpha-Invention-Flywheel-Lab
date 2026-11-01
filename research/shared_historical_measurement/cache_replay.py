"""Strong ordinary delivery outside option: existing finished measurements.
No new feature computation, image acquisition/decoding or model inference.
"""
import argparse,csv,io,json,time,statistics,hashlib,datetime
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args();runs=[]
for trial in range(3):
 start=time.perf_counter();cpu=time.process_time();nbytes=0;reads=0;bindings={}
 def read(rel):
  global nbytes,reads
  b=(a.source/rel).read_bytes();nbytes+=len(b);reads+=1;bindings[rel]=hashlib.sha256(b).hexdigest();return b.decode()
 water=list(csv.DictReader(io.StringIO(read('v2/production_measurements.csv'))));canopy=list(csv.DictReader(io.StringIO(read('v3_canopy/selected_measurements.csv'))))
 outputs={q:[] for q in ['road','promenade','canopy']}
 for row in water:
  q='promenade' if row['query']=='sidewalk' else row['query'];outputs[q].append({k:row[k] for k in ['filename','timestamp','state','url','sha256']})
 for row in canopy:outputs['canopy'].append({k:row[k] for k in ['filename','timestamp_utc','state','url','sha256','quality_flag']})
 wall=time.perf_counter()-start;cp=time.process_time()-cpu
 # Outside timed path, compare cached primary semantics to new computation.
 checked=0
 for q,rows in outputs.items():
  new={r['filename']:r for r in json.loads((a.evidence/(q+'.json')).read_text())}
  assert len(rows)==len(new)
  for r in rows:
   expected=new[r['filename']]
   for key in ['state','url','sha256']+(['quality_flag'] if q=='canopy' else ['timestamp']):assert r[key]==expected[key]
   if q=='canopy':assert r['timestamp_utc']==datetime.datetime.strptime(expected['timestamp'],'%Y-%m-%dT%H-%M-%SZ').isoformat()+'Z'
   checked+=1
 runs.append({'trial':trial,'wall_seconds':wall,'cpu_seconds':cp,'file_reads':reads,'file_bytes':nbytes,'image_decodes':0,'feature_computations':0,'fresh_model_calls':0,'cached_measurement_rows':checked,'source_bindings':bindings})
report={'schema':'ordinary-cached-measurement-delivery/1','runs':runs,'median_wall_seconds':statistics.median(x['wall_seconds'] for x in runs),'median_cpu_seconds':statistics.median(x['cpu_seconds'] for x in runs),'scope':'Existing finished historical measurements; primary observables and retained quality flags match newly recomputed outputs. Does not revalidate original image bytes or computational derivation. Cache authenticity/trust/verification policy is a separate cost. No newly measured observations or financial admission.'}
(a.evidence/'ordinary_cache_replay.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
