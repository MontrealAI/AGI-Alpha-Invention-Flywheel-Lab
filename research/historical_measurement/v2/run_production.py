"""Apply the exact frozen v2 route to completed native-response queue, no model API.
Native worker predictions are required; missing responses remain unknown, never guessed.
"""
import json,csv,hashlib,datetime
from pathlib import Path
from hybrid import route
P=Path(__file__).parent;ROOT=P.parent
r=json.loads((P/'production_native_responses.json').read_text());lookup={(x['filename'],x['query']):x for x in r};manifest={x['filename']:x for x in json.loads((ROOT/'manifest.json').read_text())};out=[]
for c in csv.DictReader((P/'production_compiled.csv').open()):
 k=(c['filename'],c['query']);mode=route(c);s=lookup.get(k);state=c['state'] if mode=='compiled' else (s['state'] if s else 'unknown');m=manifest[c['filename']]
 out.append({'timestamp':m['timestamp'],'query':c['query'],'state':state,'route':mode,'evidence':s.get('evidence','') if s else ('Compiled high-margin dry fast path' if mode=='compiled' else 'Missing native queue response'),'url':m['url'],'sha256':m['sha256'],'filename':c['filename'],'semantic_response_present':bool(s),'water_contact_confidence':'not probabilistically calibrated'})
with (P/'production_measurements.csv').open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
def dt(s):return datetime.datetime.strptime(s,'%Y-%m-%dT%H-%M-%SZ')
summary={}
for q in ['road','sidewalk']:
 rows=sorted([x for x in out if x['query']==q],key=lambda x:x['timestamp']);hours={'water_contact':0,'no_water_contact':0};intervals=[];brackets=[]
 for a,b in zip(rows,rows[1:]):
  h=(dt(b['timestamp'])-dt(a['timestamp'])).total_seconds()/3600
  if 0<h<=65/60 and a['state']==b['state'] and a['state']!='unknown':
   hours[a['state']]+=h;intervals.append({'start':a['timestamp'],'end':b['timestamp'],'state':a['state'],'conditional_hours':h})
  elif a['state']!=b['state']:brackets.append({'left_timestamp':a['timestamp'],'left_state':a['state'],'right_timestamp':b['timestamp'],'right_state':b['state'],'hours_between':h})
 summary[q]={'observations':len(rows),'states':{s:sum(x['state']==s for x in rows) for s in ['water_contact','no_water_contact','unknown']},'conditional_connected_hours':hours,'unassigned_window_hours':720-sum(hours.values()),'conditional_water_hours_range':[hours['water_contact'],720-hours['no_water_contact']],'strict_no_persistence_assumption_duration_hours':[0,720],'source_window_hours':720,'conditional_assumption':'Accepted states persist between adjacent equal-state observations no more than65min apart. Nights/gaps/changes stay unassigned. These are not statistical confidence intervals or validated continuous exposure durations.','state_change_brackets':brackets}
 (P/(q+'_production_intervals.json')).write_text(json.dumps(intervals,indent=2))
(P/'production_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps({q:{k:v for k,v in x.items() if k!='state_change_brackets'} for q,x in summary.items()},indent=2))
