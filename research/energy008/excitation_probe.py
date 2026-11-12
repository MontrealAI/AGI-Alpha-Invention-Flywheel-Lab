import hashlib, itertools, json, math, pathlib, resource, time
import numpy as np
from scipy.special import erfc
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import splu

ROOT = pathlib.Path(__file__).resolve().parent
DAY = 86400.0
PARAMETERS = {"flow_m3_s":400e-6/60, "length_m":10.0,"width_m":3.0,"aperture_m":0.0006,"rock_k_W_m_K":5.0,"rock_rho_cp_J_m3_K":2500.0*790.0,"fluid_rho_cp_J_m3_K":1000.0*4460.0,"jt_C_per_MPa":0.2176,"initial_C":30.0}

def step_response(t, area):
    p=PARAMETERS
    delay=area*p["aperture_m"]/p["flow_m3_s"]
    alpha=p["rock_k_W_m_K"]/p["rock_rho_cp_J_m3_K"]
    a=2*p["rock_k_W_m_K"]*area/(p["fluid_rho_cp_J_m3_K"]*p["flow_m3_s"]*math.sqrt(alpha))
    z=np.maximum(np.asarray(t)-delay,1e-100)
    return np.where(np.asarray(t)>delay,erfc(a/(2*np.sqrt(z))),0.0)

def full_thermal_history(t, schedule, area):
    ans=np.zeros(len(t))
    last=0.0
    for when,value in schedule:
        ans+=(value-last)*step_response(np.asarray(t)-when,area)
        last=value
    return ans

def finite_volume_history(t, schedule, area, nx=30, ny=120, depth=10.0):
    p=PARAMETERS; dt=float(t[1]-t[0]); dx=p["length_m"]/nx; dy=depth/ny; width=area/p["length_m"]
    n=nx*(ny+1); mat=lil_matrix((n,n)); capacity=np.empty(n)
    f=p["fluid_rho_cp_J_m3_K"]*p["flow_m3_s"]
    rock_c=2*p["rock_rho_cp_J_m3_K"]*width*dx*dy
    fluid_c=p["fluid_rho_cp_J_m3_K"]*width*dx*p["aperture_m"]
    g=2*p["rock_k_W_m_K"]*width*dx/dy
    for x in range(nx):
        i=x*(ny+1); capacity[i]=fluid_c/dt; mat[i,i]=capacity[i]+f+2*g
        if x: mat[i,i-(ny+1)]=-f
        mat[i,i+1]=-2*g
        for y in range(ny):
            j=i+y+1; capacity[j]=rock_c/dt
            mat[j,j]=capacity[j]+(3*g if y in (0,ny-1) else 2*g)
            if y==0: mat[j,i]=-2*g
            else: mat[j,j-1]=-g
            if y<ny-1: mat[j,j+1]=-g
    solve=splu(mat.tocsc()); state=np.zeros(n); output=[0.0]; k=0;value=0.0
    for when in t[1:]:
        while k<len(schedule) and schedule[k][0]<when+1e-6: value=schedule[k][1];k+=1
        rhs=capacity*state; rhs[0]+=f*value
        state=solve.solve(rhs); output.append(float(state[(nx-1)*(ny+1)]))
    return np.asarray(output)

def projector(nuisance):
    return np.eye(nuisance.shape[0])-nuisance@np.linalg.pinv(nuisance)

def score(curves, residualizer):
    return min(float(np.linalg.norm(residualizer@(a-b))) for a,b in itertools.combinations(curves,2))

def schedule_from_bits(bits):
    return [(i*8*DAY,-18.5 if bit else -2.0) for i,bit in enumerate(bits)]+[(48*DAY,0.0)]

def main():
    start=time.monotonic(); cpu0=resource.getrusage(resource.RUSAGE_SELF)
    t=np.arange(0,64*DAY+1,6*3600.0)
    areas=[15.0,30.0,60.0]
    pressure=10.0+1.5*np.sin(2*np.pi*t/(31*DAY))+0.5*(t>27*DAY)
    nuisance=np.column_stack([np.ones(len(t)),t/(64*DAY),pressure])
    residualizer=projector(nuisance)
    options=[]
    for bits in itertools.product((0,1),repeat=6):
        schedule=schedule_from_bits(bits)
        curves=np.array([full_thermal_history(t,schedule,a) for a in areas])
        raw_score=score(curves,np.eye(len(t)))
        protected_score=score(curves,residualizer)
        deriv1=(curves[0]-curves[2])/(60-15)
        design=np.column_stack([deriv1,pressure,np.ones(len(t)),t/(64*DAY)])
        ordinary_d_opt=float(np.linalg.slogdet(design.T@design+np.eye(4)*1e-9)[1])
        options.append({"bits":"".join(map(str,bits)),"raw_pair_distance":raw_score,"nuisance_robust_pair_distance":protected_score,"ordinary_d_opt":ordinary_d_opt,"schedule":schedule})
    proposed_v0=max(options,key=lambda d:d["raw_pair_distance"])
    proposed_v1=max(options,key=lambda d:d["nuisance_robust_pair_distance"])
    conventional=max(options,key=lambda d:d["ordinary_d_opt"])
    ordinary_robust=max(options,key=lambda d:d["nuisance_robust_pair_distance"])
    calibration_t=np.arange(0,64*DAY+1,3600.0)
    full=finite_volume_history(calibration_t,[(0.0,-18.5)],30.0)
    analytic=full_thermal_history(calibration_t,[(0.0,-18.5)],30.0)
    error=np.abs(full-analytic)
    selected_curves={}
    for name,record in [("v0",proposed_v0),("repaired",proposed_v1),("ordinary_D_optimal",conventional),("ordinary_robust_OED",ordinary_robust)]:
        selected_curves[name]={"design":record,"responses_C_below_baseline":[full_thermal_history(t,record["schedule"],a).tolist() for a in areas]}
    witness_curve=full_thermal_history(t,[(0.0,-18.5)],30.0)
    adversary=np.column_stack([nuisance,witness_curve])
    perfect_confound_score=float(np.linalg.norm(projector(adversary)@witness_curve))
    cpu1=resource.getrusage(resource.RUSAGE_SELF)
    report={"status":"SOURCE_INFORMED_MODEL_DESIGN_ONLY", "physical_validation":False,"protected_confirmation":False,"parameters":PARAMETERS,"sources":["https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2020/Fu.pdf","https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2018/Zhang2.pdf"],"parameter_treatment":{"source_base":"10m path, 3m flow-channel width, 0.6mm channel aperture, 400mL/min, k=5 W/m/K, rock rho=2500, cp=790, water cp=4460 from Fu2020. Local JT coefficient from Zhang2018.","sensitivity_not_empirical":["area15/30/60m2","64day horizon","8day binary input segments","synthetic pressure history","fixed linear nuisance basis","constant fluid and rock properties"],"mixing_of_source_models":"A reduced rectangular flow channel is used. This is not the source's full 3D fracture network; source parameters are not fitted measurements of this reduction.","no_field_fit":"GDR circulation data were not obtained. No validation error against field data is available."},"causal_model":{"thermal":"Advection in a fixed-aperture channel with two semi-infinite conductive rock half spaces; analytical Laplace transfer exp(-a sqrt(s)-delay*s). Independently checked by implicit fluid/rock finite volumes.","pressure":"A local downstream isenthalpic pressure drop adds beta*0.2176*pressure_drop to outlet temperature; beta is a nuisance parameter. Does not assume entire injection-production pressure difference is that drop.","unmodelled":["3D heterogeneous fracture network","changing permeability and flow allocation","mixing among fracture outlets","water property changes across11.5-30C","unknown unbounded thermal drift","leakoff and geology","sensor calibration"]},"conventional_full_model_comparison":{"within_reduced_physics":"Ordinary coupled thermal/JT modelling uses exactly the same thermal transfer and nuisance model as candidate.","external_3D_strong_baseline":"Wu2021/TOUGH/STOMP full-field model is NOT reproduced. It remains an unexecuted strong comparator, so no useful-service superiority is established."},"executed_criticism":{"defect":"Raw response separation can be a pressure/calibration signature and is not sufficient thermal identifiability.","typed_constraint":{"type":"NUISANCE_IDENTIFIABILITY","requirement":"Score differences only after eliminating the prospectively allowed local pressure response, constant offset and linear drift; refuse when nuisance spans thermal response."},"stress_witness_residual_norm":perfect_confound_score,"interpretation":"The expanded-nuisance witness is deliberately adversarial, not empirical; it proves identifiability is conditional on a defensible nuisance class. Free-form drift destroys the guarantee."},"design_search":{"grammar":"Six sequential8day inlet-temperature interventions, each28C or11.5C, followed by30C return; all64 sequences executed under the same forward model.","insight_provenance":"Assistant-authored transfer of nuisance annihilation/lock-in logic to known geothermal JT confounding. Sequence search is executed; governing physics and grammar are developer-supplied.","constraints":["constant400mL/min through model","same64day observation horizon","same temperature levels for all arms","local pressure measurement required","no live pump or sensor commands"]},"selected":selected_curves,"calibration":{"scope":"Independent numerical discretization check of the reduced equations, not field calibration.","n_steps":len(calibration_t),"finite_volume_grid":[30,120],"rock_half_depth_m":10.0,"rmse_C":float(np.sqrt(np.mean(error**2))),"max_abs_error_C":float(np.max(error)),"analytic_cooling_at_day24_C":float(-analytic[24*24]),"finite_volume_cooling_at_day24_C":float(-full[24*24]),"source_consistency":"Fu2020 reports a very small early thermal signal obscured by several-degree JT effects; the source does not supply a scalar24day ground truth for this rectangular reduction."},"verdict":{"enabling_capability":"NOT_ESTABLISHED","ordinary_robust_reuse_tie":proposed_v1["bits"]==ordinary_robust["bits"],"conditional_design_gain_over_raw":proposed_v1["nuisance_robust_pair_distance"]-proposed_v0["nuisance_robust_pair_distance"],"profit":"NOT_ESTABLISHED","simulated_unrestricted_earned_funds":0,"physical_next_step":"Obtain local pressure, temperature, mixing and calibration data; qualify forward model and actual controls before prescribing or claiming a thermal result."},"source_sha256":hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),"wall_seconds":time.monotonic()-start,"cpu_seconds":cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime}
    output=ROOT/"EXCITATION_RESULT.json"
    if output.exists(): raise FileExistsError(output)
    output.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"output":str(output),"selected":{n:x["design"]["bits"] for n,x in selected_curves.items()},"repaired_score":proposed_v1["nuisance_robust_pair_distance"],"raw_score_in_robust_metric":proposed_v0["nuisance_robust_pair_distance"],"ordinary_D_score_in_robust_metric":conventional["nuisance_robust_pair_distance"],"independent_numeric_rmse_C":report["calibration"]["rmse_C"],"cpu_seconds":report["cpu_seconds"]}))

if __name__=="__main__": main()
