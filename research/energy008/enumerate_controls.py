import hashlib, importlib.util, itertools, json, pathlib, resource
import numpy as np

root=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("energy_excitation",root/"excitation_probe.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
t=np.arange(0,64*m.DAY+1,6*3600.0)
pressure=10+1.5*np.sin(2*np.pi*t/(31*m.DAY))+0.5*(t>27*m.DAY)
nuisance=np.column_stack([np.ones(len(t)),t/(64*m.DAY),pressure])
r=m.projector(nuisance); rows=[]
for bits in itertools.product((0,1),repeat=6):
    schedule=m.schedule_from_bits(bits)
    curves=np.array([m.full_thermal_history(t,schedule,a) for a in (15.0,30.0,60.0)])
    derivative=(curves[0]-curves[2])/45.0
    x=np.column_stack([derivative,pressure,np.ones(len(t)),t/(64*m.DAY)])
    rows.append({"bits":"".join(map(str,bits)),"raw_pair_distance":m.score(curves,np.eye(len(t))),"nuisance_robust_pair_distance":m.score(curves,r),"ordinary_d_opt":float(np.linalg.slogdet(x.T@x+np.eye(4)*1e-9)[1]),"schedule_seconds_and_delta_C":schedule})
result={"scope":"ALL_DEVELOPMENT_DESIGNS_NOT_CONFIRMATION","count":len(rows),"forward_source_sha256":hashlib.sha256((root/"excitation_probe.py").read_bytes()).hexdigest(),"rows":rows,"cpu_seconds":resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime}
out=root/"ALL64.json"
if out.exists(): raise FileExistsError(out)
out.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps({"file":str(out),"rows":len(rows)}))
