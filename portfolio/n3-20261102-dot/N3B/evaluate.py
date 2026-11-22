"""Single frozen heldout run. Decide from masks/predictions before using physical heights."""
import json,hashlib,argparse,time
from pathlib import Path
import numpy as np
from data_io import BASE,load_split
from baseline_io import load_baselines
from model import predict
from produce import upsample128,select_archived,targets

def digest(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def stats(actual,pred):
 d=actual-pred;return {'fullfield_rmse_um':float(np.sqrt(np.mean(d*d))),'active_rmse_um':float(np.sqrt(np.mean(d[32:96,32:96]**2)))}
def mask_audit(train,dev,test):
 exact={digest(a) for a in train};devset={digest(a) for a in dev};dihedral=set()
 for a in train:
  for k in range(4):
   b=np.rot90(a,k);dihedral.add(digest(b));dihedral.add(digest(np.fliplr(b)))
 return {'train_count':len(train),'development_count':len(dev),'test_count':len(test),'unique_train_masks':len(exact),'test_exact_train_matches':[i for i,a in enumerate(test) if digest(a) in exact],'test_exact_dev_matches':[i for i,a in enumerate(test) if digest(a) in devset],'test_dihedral_train_matches':[i for i,a in enumerate(test) if digest(a) in dihedral],'test_fiducial_indices':[i for i,a in enumerate(test) if np.all(a[32:96,32:96]==255)]}
def run(receipt):
 start=time.monotonic();load_split('test',receipt);data=np.load(BASE/'test.npz');masks=data['mask'];names=[r['name'] for r in json.loads((BASE/'test_lineage.json').read_text())]
 if len(names)!=300 or len(set(names))!=300:raise ValueError('requires exact300 unique heldoutmembers')
 fitted=json.loads((BASE/'fitted_models.json').read_text());predictions={};decisions={};out=BASE/'artifact';out.mkdir(exist_ok=True)
 inputs=masks.astype(float).reshape(300,64,2,64,2).mean((2,4))/255
 for label in ['spatial0','point0',fitted['best_blur']]:
  continuous=np.stack([upsample128(predict(fitted['models'][label],a)) for a in inputs])
  predictions[label]=(np.clip(continuous/280.83*255,0,255).astype(np.uint8).astype(np.float32)*np.float32(280.83/255))
 author,binding=load_baselines(masks,receipt)
 for label,p in author.items():predictions['author_'+label]=p.astype(np.float32)
 for label,p in predictions.items():decisions[label]=select_archived(p,names)
 #Durable decision receipt precedes conversion/use of heldout physicalheight outcomes.
 decision_record={'public_final_freeze':receipt,'fitted_model_file_sha256':hashlib.sha256((BASE/'fitted_models.json').read_bytes()).hexdigest(),'target_file_sha256':hashlib.sha256((BASE/'INVERSE_REQUEST.json').read_bytes()).hexdigest(),'predictions_sha256':{k:digest(v) for k,v in predictions.items()},'choices':decisions,'physical_heights_used_for_selection':False}
 (out/'decisions_before_truth.json').write_text(json.dumps(decision_record,indent=2))
 np.savez_compressed(out/'frozen_predictions.npz',**predictions)
 #Physicalevaluation starts here; no refit/reselection below.
 truth=data['height'].astype(float)*280.83/255
 audit=mask_audit(np.load(BASE/'train.npz')['mask'],np.load(BASE/'val_train.npz')['mask'],masks);fid=set(audit['test_fiducial_indices']);results={}
 for label,p in predictions.items():
  rows=[{'member':names[i],'fiducial':i in fid,**stats(truth[i],p[i])} for i in range(300)]
  strata={}
  for cat,ids in [('all',list(range(300))),('random',[i for i in range(300) if i not in fid]),('fiducial',sorted(fid))]:
   strata[cat]={'count':len(ids),'mean_patch_active_rmse_um':float(np.mean([rows[i]['active_rmse_um'] for i in ids])) if ids else None,'mean_patch_fullfield_rmse_um':float(np.mean([rows[i]['fullfield_rmse_um'] for i in ids])) if ids else None}
  inverse={}
  for tid,target in targets(128).items():
   i=decisions[label][tid]['selected_index'];actual=truth[i];nonzero=target>0;zero=~nonzero;errors=np.mean((truth[:,32:96,32:96]-target[None,32:96,32:96])**2,(1,2));oi=min(range(300),key=lambda j:(float(errors[j]),names[j]))
   inverse[tid]={'choice':names[i],**stats(actual,target),'target_feature_mae_um':float(np.mean(abs(actual[nonzero]-target[nonzero]))),'zero_target_excess_mean_um':float(np.mean(np.maximum(actual[zero],0))),'choice_prediction_error':stats(actual,p[i]),'hindsight_oracle_unavailable_to_policy':{'member':names[oi],'active_rmse_um':float(np.sqrt(errors[oi]))}}
  results[label]={'strata':strata,'per_patch':rows,'inverse_exact_archived_recipe':inverse}
 #Allnewmaskoutputs retain no physicaltruth, auditnovelty only.
 allmasks=np.concatenate([np.load(BASE/'train.npz')['mask'],np.load(BASE/'val_train.npz')['mask'],masks]);known={digest(a) for a in allmasks};novel={}
 from PIL import Image
 for p in out.glob('*_padded16.png'):
  a=np.asarray(Image.open(p));expanded=np.repeat(np.repeat(a,8,0),8,1);novel[p.name]={'exact_archive_match':digest(expanded) in known,'physical_truth':None}
 result={'source':'NISTmds2-2950','public_freeze':receipt,'test_count':300,'independent_test_slides':1,'newmask_physical_acceptance':False,'commercial_acceptance':False,'native_revenue':0,'baseline_binding':binding,'mask_audit':audit,'models':results,'generatedmask_novelty':novel,'runtime_seconds':time.monotonic()-start}
 (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps({'test_count':300,'model_strata':{k:v['strata'] for k,v in results.items()},'baseline_binding':binding,'runtime_seconds':result['runtime_seconds']},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--public-freeze',required=True);run(p.parse_args().public_freeze)
