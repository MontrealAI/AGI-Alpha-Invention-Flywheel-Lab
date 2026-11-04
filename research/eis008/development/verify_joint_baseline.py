import hashlib,json,resource,time
from pathlib import Path
import numpy as np
from scipy.io import loadmat
from scipy.linalg import lstsq

r=Path(__file__).resolve().parent;start=time.monotonic();d=loadmat(r/'operandoEIS_5degrees.mat');h=d['Hexc'].ravel().astype(int);n=len(d['i'])//int(d['P'].item());x=np.column_stack([d['i'][:n,0],d['v'][:n,0]])
t=np.arange(n)/n;p=np.column_stack([np.ones(n),2*t-1,(2*t-1)**2]);angle=2*np.pi*t[:,None]*h;f=np.column_stack([np.cos(angle),np.sin(angle)]);design=np.column_stack([f,p])
direct,_,rank,_=lstsq(design,x,lapack_driver='gelsy');m=len(h);direct_complex=direct[:m]-1j*direct[m:2*m]
pf=np.fft.rfft(p,axis=0);c=np.vstack([pf[h].real,-pf[h].imag]);yf=np.fft.rfft(x,axis=0)[h];rhs=np.vstack([yf.real,-yf.imag]);s=p.T@p-(2/n)*(c.T@c);b=np.linalg.solve(s,p.T@x-(2/n)*(c.T@rhs));coef=(2/n)*(rhs-c@b);reduced_complex=coef[:m]-1j*coef[m:]
relative=float(np.linalg.norm(direct_complex-reduced_complex)/np.linalg.norm(direct_complex));passed=relative<1e-8 and rank==2*m+3
report={'purpose':'Code qualification of closed-form Fourier/Schur ordinary least squares against a natural dense pivoted-QR baseline on the same real first period; not a second scientific candidate or confirmation','source_data_sha256':hashlib.sha256((r/'operandoEIS_5degrees.mat').read_bytes()).hexdigest(),'probe_code_sha256':hashlib.sha256((r/'probe_eis.py').read_bytes()).hexdigest(),'rows':n,'columns':2*m+3,'dense_rank':rank,'relative_coefficient_disagreement':relative,'qualification_tolerance':1e-8,'passed':passed,'cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'wall_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
(r/'JOINT_BASELINE_QUALIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if not passed:raise SystemExit(1)
