"""Non-ink material diagnostic; never loads the IR/photo/label/mask images."""
from pathlib import Path
import hashlib,json,time,warnings
import numpy as np
from PIL import Image
from scipy import ndimage,signal
R=Path(__file__).resolve().parent
spec=(R/'MATERIAL_POSE_SPEC.json').read_bytes()
pose=json.loads((R/'sealed-inputs/ir_pose.json').read_text())
regions=json.loads((R/'CT_HALO_RECEIPT.json').read_text())['selected']
Image.MAX_IMAGE_PIXELS=300_000_000
fine=np.asarray(Image.open(R/'source_front_ct_00.png'))
if fine.ndim!=2:raise ValueError(('CT image not 2D',fine.shape))
print('Fine CT shape',fine.shape,flush=True)
fs=pose['scale'];rh=int(round(fine.shape[0]*fs));rw=int(round(fine.shape[1]*fs))
t=np.deg2rad(pose['rot']);a=np.cos(t);b=np.sin(t);cx=rw/2;cy=rh/2
A=np.array([[a,b,(1-a)*cx-b*cy],[-b,a,b*cx+(1-a)*cy],[0,0,1.]])
AI=np.linalg.inv(A)
def template(y,x):
 # Pixel-centred sixteen-sample average approximates the area's CT texture independently.
 yy,xx=np.meshgrid(y+np.arange(256),x+np.arange(256),indexing='ij')
 out=np.zeros((256,256),np.float64)
 for sy in [-.375,-.125,.125,.375]:
  for sx in [-.375,-.125,.125,.375]:
   xd=xx+sx-pose['ox'];yd=yy+sy-pose['oy']
   xr=AI[0,0]*xd+AI[0,1]*yd+AI[0,2];yr=AI[1,0]*xd+AI[1,1]*yd+AI[1,2]
   xf=(xr+.5)/fs-.5;yf=(yr+.5)/fs-.5
   if pose['flip'] is not None:raise ValueError('Unexpected flip; do not guess')
   out+=ndimage.map_coordinates(fine,[yf,xf],order=1,mode='constant',cval=0,prefilter=False)
 return (out/16).astype(np.float64)
def ncc_field(img,tpl):
 n=tpl.size;tpl=tpl-tpl.mean();var=float((tpl*tpl).sum())
 def integral(a):return np.pad(a.cumsum(0).cumsum(1),((1,0),(1,0)))
 def sums(a):
  s=integral(a);k=256;return s[k:,k:]-s[:-k,k:]-s[k:,:-k]+s[:-k,:-k]
 sd=sums(img);ss=sums(img*img);den=np.sqrt(np.maximum(ss-sd*sd/n,0)*var)
 num=signal.correlate(img,tpl,mode='valid',method='fft')
 return np.divide(num,den,out=np.full_like(num,np.nan),where=den>1e-8)
results={}
for name,r in regions.items():
 v=np.load(r['path'],allow_pickle=False).astype(np.float64);oy,ox=r['global_origin_yx'];tpl=template(oy+64,ox+64)
 modes={}
 for mode in ['raw','highpass_sigma3']:
  tt=tpl if mode=='raw' else tpl-ndimage.gaussian_filter(tpl,3)
  per=[]
  for z in range(31):
   im=v[z] if mode=='raw' else v[z]-ndimage.gaussian_filter(v[z],3)
   field=ncc_field(im,tt)[32:97,32:97]
   by,bx=np.unravel_index(np.nanargmax(field),field.shape)
   per.append(dict(plane=z,expected_pose_ncc=float(field[32,32]),best_ncc=float(field[by,bx]),best_shift_yx=[int(by-32),int(bx-32)],peak_on_search_edge=bool(by in [0,64] or bx in [0,64])))
  modes[mode]=dict(plane26=per[26],best_over31=max(per,key=lambda q:q['best_ncc']),all_planes=per)
 results[name]=modes
rec=dict(completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),spec_sha256=hashlib.sha256(spec).hexdigest(),
 fine_CT_shape=list(fine.shape),fine_CT_sha256=hashlib.sha256((R/'source_front_ct_00.png').read_bytes()).hexdigest(),
 truth_or_IR_or_model_read=False,independent_original_IR_registration_certified=False,
 resampler_limit='Independent approximate area resampler; not bitwise OpenCV reproduction',results=results)
(R/'MATERIAL_POSE_DIAGNOSTIC.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps({k:{mode:{kk:vv for kk,vv in m.items() if kk!='all_planes'} for mode,m in modes.items()} for k,modes in results.items()},indent=2))
