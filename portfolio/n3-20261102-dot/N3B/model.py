"""Spatial effective-response models; ordinary numerical methods, not novelAI claims."""
import numpy as np
from scipy.ndimage import gaussian_filter,zoom
from scipy.optimize import minimize
SCALES=(0.,.5,1.,2.,4.)
RES=64

def spatial_inputs(mask):
 a=np.asarray(mask,dtype=float)
 if a.shape!=(64,64) or not np.all(np.isfinite(a)) or np.min(a)<0 or np.max(a)>1:raise ValueError('requires finite64x64 maskfraction[0,1], inclsourceborder')
 return np.stack([a if s==0 else gaussian_filter(a,s,mode='constant',cval=0) for s in SCALES],axis=-1)
def features(fields,kind='spatial',scale=0):
 v=fields.reshape(-1,5)
 if kind in ('point','blur'):v=v[:,[scale]]
 parts=[np.ones((len(v),1)),v,v*v,v*v*v]
 if kind=='spatial':parts.append(v[:,[0]]*v[:,1:])
 return np.concatenate(parts,axis=1)
def fit_statistics(masks,heights,kind='spatial',scale=0,alpha=1.):
 d=features(spatial_inputs(masks[0]),kind,scale).shape[1];xx=np.zeros((d,d));xy=np.zeros(d)
 for mask,height in zip(masks,heights):
  f=features(spatial_inputs(mask),kind,scale);y=np.asarray(height).ravel();xx+=f.T@f;xy+=f.T@y
 penalty=np.eye(d)*alpha;penalty[0,0]=0
 coef=np.linalg.solve(xx+penalty,xy)
 return {'kind':kind,'scale':int(scale),'alpha':float(alpha),'coef':coef.tolist(),'resolution':64,'scope':'effective spatial response same resin/engine/fixed5s; not mechanistic uncertainty guarantee'}
def predict(model,mask):
 f=features(spatial_inputs(mask),model['kind'],model['scale']);return np.clip((f@np.asarray(model['coef'])).reshape(64,64),0,280.83)
def mask_from_native(native):
 #Source16x16native field has central8x8active and4blackborder eachside.
 n=np.asarray(native,dtype=float)
 if n.size!=64 or not np.all(np.isfinite(n)) or np.min(n)<0 or np.max(n)>1:raise ValueError('requires64finite native maskfractions[0,1]')
 a=np.zeros((16,16));a[4:12,4:12]=n.reshape(8,8)
 return np.repeat(np.repeat(a,4,axis=0),4,axis=1)
def inverse(model,target,maxiter=100):
 target=np.asarray(target,float)
 if target.shape!=(64,64) or not np.all(np.isfinite(target)) or np.min(target)<0 or np.max(target)>280.83:raise ValueError('finite target64x64 in[0,280.83]um required')
 def objective(v):
  y=predict(model,mask_from_native(v));return float(np.mean((y[16:48,16:48]-target[16:48,16:48])**2))
 #Fixed initial50% and finite iterationbudget; allmethods equal initialization.
 r=minimize(objective,np.full(64,.5),method='L-BFGS-B',bounds=[(0,1)]*64,options={'maxiter':maxiter,'ftol':1e-10,'maxfun':20000})
 quant=np.rint(np.clip(r.x,0,1)*255).astype(np.uint8).reshape(8,8)
 p=predict(model,mask_from_native(quant.astype(float)/255))
 return quant,p,{'optimizer_success':bool(r.success),'message':str(r.message),'iterations':int(r.nit),'evaluations':int(r.nfev),'quantized_model_rmse_um':float(np.sqrt(np.mean((p-target)**2))),'quantized_model_active_rmse_um':float(np.sqrt(np.mean((p[16:48,16:48]-target[16:48,16:48])**2))),'physical_acceptance':False,'status':'MODEL-ONLY' if r.success and np.all(np.isfinite(p)) else 'COMPUTATIONAL HOLD'}
