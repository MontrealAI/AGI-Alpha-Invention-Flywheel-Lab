"""Incidental canopy query: ordinary GCC comparator and native-response measurement merger.
No image-generation, API model calls or chronological label smoothing.
"""
import json,csv,datetime,zoneinfo,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
P=Path(__file__).parent;ROOT=P.parent
ROI=[(1640,147),(1660,125),(1690,120),(1715,135),(1730,165),(1715,195),(1660,195),(1640,175)]
EXPOSED=['2024-03-15','2024-04-15','2024-05-15']
def gcc(path):
 im=Image.open(path).convert('RGB');assert im.size==(1920,1080),'Geometry needs new inspection, never silently scale changed viewpoint'
 a=np.asarray(im,dtype=float);m=Image.new('L',im.size);ImageDraw.Draw(m).polygon(ROI,fill=1);px=a[np.array(m).astype(bool)];return float(np.median(px[:,1]/np.maximum(px.sum(1),1)))
def main():
 man=json.loads((P/'manifest.json').read_text());native=json.loads((P/'native_predictions.json').read_text());lookup={x['filename']:x for x in native};assert len(lookup)==len(native)
 probes=json.loads((P/'probes/proposal.json').read_text())['probes'];ref={x['day']:gcc(P/x['file']) for x in probes};low=ref['2024-03-15'];high=ref['2024-05-15'];delta=high-low
 rows=[]
 for x in man:
  if 'error'in x:continue
  score=gcc(ROOT/x['path']);ratio=(score-low)/delta if delta>0 else None;baseline='unknown' if ratio is None else ('leafless' if ratio<=.2 else 'leafed' if ratio>=.8 else 'partial')
  n=lookup.get(x['filename']);state=n['state'] if n else 'unknown';raw=x['timestamp'];u=datetime.datetime.strptime(raw,'%Y-%m-%dT%H-%M-%SZ').replace(tzinfo=datetime.timezone.utc)
  rows.append({'timestamp_utc':u.isoformat().replace('+00:00','Z'),'timestamp_local':u.astimezone(zoneinfo.ZoneInfo('US/Central')).isoformat(),'state':state,'green_chromatic_coordinate':score,'gcc_baseline_state':baseline,'evidence':n['evidence'] if n else 'Missing native interpretation','split':'exposed_probe_day' if raw[:10] in EXPOSED else 'heldout_candidate','url':x['url'],'sha256':x['sha256'],'filename':x['filename']})
 with (P/'measurements.csv').open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 # Earliest three-consecutive-daily-frame leafed sequence, not continuous physiology.
 sustained=None
 for i in range(len(rows)-2):
  group=rows[i:i+3];dates=[datetime.datetime.fromisoformat(x['timestamp_utc'].replace('Z','+00:00')).date() for x in group]
  if all(x['state']=='leafed' for x in group) and (dates[1]-dates[0]).days==1 and (dates[2]-dates[1]).days==1:
   prior=[x for x in rows[:i] if x['state'] in ['leafless','partial']]
   sustained={'last_prior_observed_nonleafed':prior[-1]['timestamp_utc'] if prior else None,'first_of_three_leafed_samples':group[0]['timestamp_utc'],'three_sample_timestamps':[x['timestamp_utc'] for x in group],'interpretation':'Observed daily sample transition bracket; not biological budburst time or proof of continuous leaf state between frames.'};break
 result={'planned_days':61,'acquired_frames':len(rows),'missing_days':json.loads((P/'missing_days.json').read_text()),'states':{s:sum(x['state']==s for x in rows) for s in ['leafless','partial','leafed','unknown']},'gcc_reference_values':ref,'sustained_sampled_leafon':sustained,'roi_original_1920x1080':ROI,'limitations':['AI visible-foliage interpretation,not field phenology truth.','Only one fixed crown, camera and season; no shade,health,species or ecosystem claims.','No interpolation across unknown/missing images.','Native semantic review is the strong ordinary manual-AI method; GCC is transparent ordinary scalar comparator,not novelphenology.']}
 (P/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
