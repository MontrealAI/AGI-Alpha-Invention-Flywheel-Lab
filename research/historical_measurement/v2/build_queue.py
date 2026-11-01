import sys,json,csv,argparse
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from instrument import features,ROIS,ROOT,CAL_DAYS
from hybrid import route
from PIL import Image,ImageDraw
P=ROOT/'v2'
a=argparse.ArgumentParser();a.add_argument('--phase',required=True);args=a.parse_args();phase=args.phase
manifest=json.loads((ROOT/'manifest.json').read_text());sample=manifest if phase=='production' else json.loads((P/(phase+'_sample.json')).read_text());cal=[x for x in manifest if x['timestamp'][:10] in CAL_DAYS and x['timestamp'][11:13] in ['13','18','23']];rows=[]
for q,poly in ROIS.items():
 train=np.array([features(ROOT/'images'/x['filename'],poly)[0] for x in cal]);labels=np.array([int(x['timestamp'][:10]=='2024-06-30') for x in cal]);scale=np.maximum(np.std(train,axis=0),.015)
 for x in sample:
  f,b,t=features(ROOT/'images'/x['filename'],poly);d=np.sqrt(np.mean(((train-f)/scale)**2,axis=1));d0=float(min(d[labels==0]));d1=float(min(d[labels==1]));m=abs(d0-d1)/(d0+d1+1e-9);state='unknown' if b<.12 or min(d0,d1)>3 or m<.15 else ('water_contact' if d1<d0 else 'no_water_contact')
  rows.append({'filename':x['filename'],'query':q,'state':state,'distance_dry':d0,'distance_wet':d1,'separation_margin':m})
with (P/(phase+'_compiled.csv')).open('w') as fp:w=csv.DictWriter(fp,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
queue=[{'filename':r['filename'],'query':r['query'],'path':str(ROOT/'images'/r['filename'])} for r in rows if route(r)=='semantic'];(P/(phase+'_semantic_queue.json')).write_text(json.dumps(queue,indent=2))
# Crop text, retain unaltered scene pixels. IDs identify evidence; no predicted states in review sheets.
names=list(dict.fromkeys(x['filename'] for x in queue));(P/(phase+'_queue_ids.json')).write_text(json.dumps({str(i):n for i,n in enumerate(names)},indent=2))
for start in range(0,len(names),4):
 canvas=Image.new('RGB',(1440,710),'white');draw=ImageDraw.Draw(canvas)
 for j,name in enumerate(names[start:start+4]):
  im=Image.open(ROOT/'images'/name).convert('RGB').resize((720,405));d=ImageDraw.Draw(im)
  qs=[x['query'] for x in queue if x['filename']==name]
  for q in qs:d.polygon(ROIS[q],outline='red',width=2)
  im=im.crop((0,80,720,405));xx=j%2*720;yy=j//2*355;canvas.paste(im,(xx,yy+30));draw.text((xx+5,yy+5),'ID '+str(start+j)+' '+','.join(qs),fill='black')
 canvas.save(P/(phase+'_queue_'+str(start//4)+'.jpg'))
print(phase,'compiled_rows',len(rows),'fallback_queries',len(queue),'fallback_images',len(names))
