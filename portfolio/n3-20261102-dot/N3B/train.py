import json,time
import numpy as np
from pathlib import Path
from model import fit_statistics,predict
BASE=Path(__file__).parent

def arrays(split):
 a=np.load(BASE/f'{split}.npz');m=a['mask'].astype(float)/255;h=a['height'].astype(float)*280.83/255
 if len(m)!={'train':1030,'val_train':114,'test':300}[split]:raise ValueError('denominator mismatch')
 return m.reshape(-1,64,2,64,2).mean((2,4)),h.reshape(-1,64,2,64,2).mean((2,4))
def errors(model,m,y):
 e=[np.mean((predict(model,a)-b)**2) for a,b in zip(m,y)]
 return {'rmse_um':float(np.sqrt(np.mean(e))),'mean_patch_rmse_um':float(np.mean(np.sqrt(e)))}
def main():
 t=time.monotonic();m,y=arrays('train');v,z=arrays('val_train');models={};dev={}
 for kind,scale in [('point',0)]+[('blur',s) for s in range(1,5)]+[('spatial',0)]:
  key=kind+str(scale);model=fit_statistics(m,y,kind,scale,alpha=1.);models[key]=model;dev[key]=errors(model,v,z);print(key,dev[key],flush=True)
 best=min([k for k in models if k.startswith('blur')],key=lambda k:(dev[k]['rmse_um'],k))
 out={'models':models,'development_errors':dev,'best_blur':best,'candidate':'spatial0','frozen_family':'multiscale cubic+center-neighbor interactions, ridgealpha1','training_seconds':time.monotonic()-t,'training_patches':1030,'development_patches':114,'test_patches_seen':0,'source_height_unit':'µm via0..255→0..280.83','coarse_model_resolution':'64²; physicaltruth andauthorbaselinefinalmetrics at128²'}
 (BASE/'fitted_models.json').write_text(json.dumps(out,indent=2))
if __name__=='__main__':main()
