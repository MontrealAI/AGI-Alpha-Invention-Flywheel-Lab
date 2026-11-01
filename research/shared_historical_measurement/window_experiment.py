"""Real non-overlap/window production; calibration costs remain visible."""
import argparse,json
from pathlib import Path
from producer import Producer,commission,verify_sources,canonical,digest,CAL,in_window
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();results=[]
scenarios=[('disjoint_observables_and_seasons',{'road':['2024-06-20','2024-06-21'],'canopy':['2024-04-20','2024-04-21']}),('disjoint_observation_windows_shared_calibration',{'road':['2024-06-20','2024-06-21'],'promenade':['2024-07-10','2024-07-11']})]
for name,windows in scenarios:
 separate={};counts={}
 for q in windows:
  o,r=Producer(a.source,a.data).run([q],{q:windows[q]});separate.update(o)
  for k,v in r['counts'].items():counts[k]=counts.get(k,0)+v
 ordinary,ordinary_r=Producer(a.source,a.data).run(list(windows),windows)
 commissioned,receipt,contract=commission(a.source,a.data,list(windows),windows)
 assert separate==ordinary==commissioned
 assert all(in_window(row,windows[q]) for q,rows in ordinary.items() for row in rows)
 overlap=set(r['sha256'] for r in ordinary['road'])&set(r['sha256'] for q,rows in ordinary.items() if q!='road' for r in rows)
 assert not overlap
 if name=='disjoint_observables_and_seasons':assert counts['image_decodes']==ordinary_r['counts']['image_decodes']==receipt['counts']['image_decodes']
 else:
  man=json.loads((a.source/'manifest.json').read_text());cal=[x for x in man if x['timestamp'][:10] in CAL and x['timestamp'][11:13] in ['13','18','23']]
  assert counts['image_decodes']-ordinary_r['counts']['image_decodes']==len(cal)
 results.append({'scenario':name,'windows':windows,'output_rows':{q:len(rows) for q,rows in ordinary.items()},'observation_image_overlap':0,'separate_counts':counts,'ordinary_shared_counts':ordinary_r['counts'],'commissioned_counts':receipt['counts'],'outputs_identical':True,'explanation':'No generic sharing discount: only actually common calibration/observation work may be shared.'})
a.out.write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
