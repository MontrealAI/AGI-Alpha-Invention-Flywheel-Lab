"""Exact upstream carry_labels.pose_img applied to CT only, then same fixed material diagnostics.

pose_img copyright2026 Domenico Russo/MIT; sources/IR_LICENSE.txt retains notice.
"""
import ast,hashlib,json,time,sys
from pathlib import Path
import numpy as np
from scipy import ndimage,signal
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'cv-vendor'))
import cv2
cv2.setNumThreads(2)
src=(R/'sources/carry_labels.py').read_text();tree=ast.parse(src)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pose_img')
ns={'np':np,'cv2':cv2};exec(compile(ast.Module(body=[fn],type_ignores=[]),'upstream_pose_img','exec'),ns)
fine=cv2.imread(str(R/'source_front_ct_00.png'),cv2.IMREAD_UNCHANGED)
p=json.loads((R/'sealed-inputs/ir_pose.json').read_text())
warped=ns['pose_img'](fine,p['flip'],p['scale'],p['rot'],p['oy'],p['ox'],3440,2060,cv2.INTER_AREA).astype(np.float64)
def ncc_field(img,tpl):
 tpl=tpl-tpl.mean();n=tpl.size;var=float((tpl*tpl).sum())
 def sums(a):
  s=np.pad(a.cumsum(0).cumsum(1),((1,0),(1,0)));k=256
  return s[k:,k:]-s[:-k,k:]-s[k:,:-k]+s[:-k,:-k]
 ss=sums(img*img);sd=sums(img);den=np.sqrt(np.maximum(ss-sd*sd/n,0)*var)
 num=signal.correlate(img,tpl,mode='valid',method='fft')
 return np.divide(num,den,out=np.full_like(num,np.nan),where=den>1e-8)
result={}
for name,r in json.loads((R/'CT_HALO_RECEIPT.json').read_text())['selected'].items():
 oy,ox=r['global_origin_yx'];tpl=warped[oy+64:oy+320,ox+64:ox+320];v=np.load(r['path'],allow_pickle=False).astype(np.float64)
 modes={}
 for mode in ['raw','highpass_sigma3']:
  tt=tpl if mode=='raw' else tpl-ndimage.gaussian_filter(tpl,3);per=[]
  for z in range(31):
   im=v[z] if mode=='raw' else v[z]-ndimage.gaussian_filter(v[z],3)
   field=ncc_field(im,tt)[32:97,32:97];by,bx=np.unravel_index(np.nanargmax(field),field.shape)
   per.append(dict(plane=z,expected_pose_ncc=float(field[32,32]),best_ncc=float(field[by,bx]),best_shift_yx=[int(by-32),int(bx-32)],peak_on_search_edge=bool(by in [0,64] or bx in [0,64])))
  modes[mode]=dict(plane26=per[26],best_over31=max(per,key=lambda q:q['best_ncc']),all_planes=per)
 result[name]=modes
rec=dict(completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),opencv_version=cv2.__version__,
 carry_labels_sha256=hashlib.sha256(src.encode()).hexdigest(),original_IR_registration_certified=False,
 CT_only=True,truth_or_IR_or_model_read=False,results=result)
(R/'OPENCV_POSE_REPEAT.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps({k:{m:{kk:vv for kk,vv in v.items() if kk!='all_planes'} for m,v in modes.items()} for k,modes in result.items()},indent=2))
