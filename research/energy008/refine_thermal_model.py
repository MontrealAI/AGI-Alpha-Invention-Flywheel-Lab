import hashlib, importlib.util, json, pathlib, resource, time
import numpy as np

root=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("energy_excitation",root/"excitation_probe.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
start=time.monotonic(); rows=[]
for nx,ny,step in [(30,120,3600.0),(60,240,1800.0),(120,480,900.0)]:
    t=np.arange(0,64*m.DAY+1,step)
    numerical=m.finite_volume_history(t,[(0.0,-18.5)],30.0,nx,ny)
    analytical=m.full_thermal_history(t,[(0.0,-18.5)],30.0)
    difference=numerical-analytical
    rows.append({"nx":nx,"ny":ny,"time_step_seconds":step,"rmse_C":float(np.sqrt(np.mean(difference**2))),"max_abs_error_C":float(np.max(np.abs(difference))),"numerical_cooling_day24_C":float(-numerical[round(24*m.DAY/step)]),"analytical_cooling_day24_C":float(-analytical[round(24*m.DAY/step)])})
result={"scope":"NUMERICAL_CONSISTENCY_ONLY_NOT_FIELD_CALIBRATION","forward_model_sha256":hashlib.sha256((root/"excitation_probe.py").read_bytes()).hexdigest(),"rows":rows,"convergence_monotone":all(b["rmse_C"]<a["rmse_C"] for a,b in zip(rows,rows[1:])),"field_validation_error":None,"unavailable_field_reason":"Documented GDR1301 circulation source returned195byte SiteUnavailable HTML","wall_seconds":time.monotonic()-start,"cpu_seconds":resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime}
out=root/"REFINEMENT_RESULT.json"
if out.exists(): raise FileExistsError(out)
out.write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result))
