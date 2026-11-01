"""Query-specific archive instrument. No gauge or temporal features enter inference."""
import json,csv,hashlib,argparse,datetime,time
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).parent
CAL_DAYS=['2024-06-15','2024-06-23','2024-06-30','2024-07-14']
ROIS={'road':[(580,165),(700,220),(700,255),(580,190)],'sidewalk':[(470,260),(500,260),(510,330),(465,330)]}
RIVER=[(250,260),(350,260),(350,340),(250,340)]
def mask(poly):
 im=Image.new('L',(720,405));ImageDraw.Draw(im).polygon(poly,fill=1);return np.array(im).astype(bool)
def features(path,poly):
 im=np.asarray(Image.open(path).convert('RGB').resize((720,405)),dtype=float)/255
 # Text lies above y80; neither features nor reference touch overlay, timestamp, site name.
 m=mask(poly);r=mask(RIVER);px=im[m];rv=im[r];gray=im.mean(2)
 gx=np.abs(np.roll(gray,1,axis=1)-gray);gy=np.abs(np.roll(gray,1,axis=0)-gray)
 # Relative river color discounts exposure and white balance. Texture retained separately.
 mu=np.median(px,axis=0);ref=np.median(rv,axis=0)
 f=np.r_[mu-ref, np.std(px,axis=0),np.quantile(gx[m],[.5,.9]),np.quantile(gy[m],[.5,.9])]
 return f,float(np.mean(gray[m])),float(np.mean(gx[m]+gy[m]))
def main():
 a=argparse.ArgumentParser();a.add_argument('--query',choices=list(ROIS),required=True);a.add_argument('--output');args=a.parse_args();q=args.query
 manifest=json.loads((ROOT/'manifest.json').read_text());valid=[x for x in manifest if 'error' not in x]
 cal=[x for x in valid if x['timestamp'][:10] in CAL_DAYS and x['timestamp'][11:13] in ['13','18','23']]
 train=np.array([features(ROOT/'images'/x['filename'],ROIS[q])[0] for x in cal]);labels=np.array([int(x['timestamp'][:10]=='2024-06-30') for x in cal]);scale=np.maximum(np.std(train,axis=0),.015)
 rows=[]
 for x in valid:
  f,brightness,texture=features(ROOT/'images'/x['filename'],ROIS[q]);dist=np.sqrt(np.mean(((train-f)/scale)**2,axis=1));d0=float(min(dist[labels==0]));d1=float(min(dist[labels==1]));margin=abs(d0-d1)/(d0+d1+1e-9)
  # Distance/margin are diagnostics, NOT calibrated probabilities. Conservative abstention.
  state='unknown' if brightness<.12 or min(d0,d1)>3 or margin<.15 else ('water_contact' if d1<d0 else 'no_water_contact')
  rows.append(dict(timestamp=x['timestamp'],query=q,state=state,split='calibration_exposed_day' if x['timestamp'][:10] in CAL_DAYS else 'heldout',distance_dry=round(d0,5),distance_wet=round(d1,5),separation_margin=round(margin,5),brightness=round(brightness,5),texture=round(texture,5),url=x['url'],sha256=x['sha256']))
 out=ROOT/(args.output or q+'_measurements.csv')
 with out.open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 # Only adjacent observations <=65 min with equal known state are connected. Night/gaps stay unknown.
 hours={'water_contact':0.,'no_water_contact':0.,'unknown':720.};segments=[]
 def dt(t):return datetime.datetime.strptime(t,'%Y-%m-%dT%H-%M-%SZ').replace(tzinfo=datetime.timezone.utc)
 for l,r in zip(rows,rows[1:]):
  h=(dt(r['timestamp'])-dt(l['timestamp'])).total_seconds()/3600
  if 0<h<=65/60 and l['state']==r['state'] and l['state']!='unknown':
   hours[l['state']]+=h;hours['unknown']-=h;segments.append({'start':l['timestamp'],'end':r['timestamp'],'state':l['state'],'hours':h})
 summary={'query':q,'window_start':'2024-06-15T00:00:00Z','window_end':'2024-07-15T00:00:00Z','window_hours':720,'observations':len(rows),'states':{s:sum(x['state']==s for x in rows) for s in ['water_contact','no_water_contact','unknown']},'calibration_frames':len(cal),'heldout_observations':sum(x['split']=='heldout' for x in rows),'conditional_connected_hours':hours,'water_contact_hours_bounds_assuming_accepted_classifications_and_between_frame_persistence':[hours['water_contact'],720-hours['no_water_contact']],'strict_continuous_duration_bounds_without_between_frame_assumption':[0,720],'warning':'No duration is directly observed between frames. Bounds rely on accepted classifications and persistence between consecutive <=65-minute frames. They are not statistical confidence intervals. Gauge validation is separate; no claims of safety fitness.','roi_720x405':ROIS[q],'training_files':[x['filename'] for x in cal]}
 (ROOT/(q+'_summary.json')).write_text(json.dumps(summary,indent=2));(ROOT/(q+'_intervals.json')).write_text(json.dumps(segments,indent=2));print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
