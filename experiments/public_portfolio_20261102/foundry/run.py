from __future__ import annotations
import argparse
import hashlib
import json
import resource
import time
from pathlib import Path
import numpy as np
from scipy.optimize import differential_evolution
from optics import ROOT, index, response, recursive_scattering, independent_layer_system

ARMS = ("retained_procedure","ordinary_equal_content","equal_content_no_discovery_procedure","fresh_specialist_no_inheritance")

def source_identity():
    paths = [ROOT / name for name in ("optics.py","run.py","silica.yml","magnesium_fluoride.yml","tantalum_pentoxide.yml","PREREGISTRATION.json")]
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def materials_for(kind):
    return ["MgF2","Ta2O5"] if kind=="K1" else ["Ta2O5","SiO2"]*6

def task_grid(kind,dense=False,shift=0.0):
    count = 121 if dense else 19
    if kind=="K1":
        return np.linspace(.8,1.06,count)+shift,np.zeros(count,dtype=bool)
    first = np.linspace(.8,1.0,count//2)+shift
    second = np.linspace(1.24,1.49,count//2)+shift
    return np.r_[first,second],np.r_[np.zeros(len(first),dtype=bool),np.ones(len(second),dtype=bool)]

def score(d,kind,solver=response,shift=0):
    w,stop = task_grid(kind,shift=shift)
    losses = []
    for angle in (0,25):
        for pol in ("s","p"):
            for factor in (.99,1.01):
                out = solver(d*factor,materials_for(kind),w,angle,pol)
                loss = 1-out["T"] if kind=="K1" else np.where(stop,1-out["R"],1-out["T"])
                losses.append(float(np.mean(loss)))
    return max(losses)

def build(kind,seed,solver=response,shift=0):
    mats = materials_for(kind)
    if kind=="K1":
        initial = np.array([.93/(4*float(index("MgF2",[.93])[0].real)),.01])
        bounds = [(.01,.3),(.005,.10)]
        iterations = 36
    else:
        center = 1.36+shift
        initial = np.array([center/(4*float(index(m,[center])[0].real)) for m in mats])
        bounds = [(.02,.35)]*len(mats)
        iterations = 40
    calls = 0
    def objective(d):
        nonlocal calls
        calls += 1
        return score(d,kind,solver,shift)
    t = time.perf_counter(); cpu = time.process_time()
    fitted = differential_evolution(objective,bounds,x0=initial,seed=seed,maxiter=iterations,popsize=4,tol=1e-5,polish=False,workers=1,updating="immediate")
    return {"thickness_um":fitted.x.tolist(),"objective":float(fitted.fun),"objective_evaluations":calls,"cpu_seconds":time.process_time()-cpu,"wall_seconds":time.perf_counter()-t,"optimizer":"scipy differential_evolution; no global-optimality claim"}

def validate(d,kind,shift=0,perturbations=(-.015,0,.015),angles=(0,15,30)):
    d = np.asarray(d)
    w,stop = task_grid(kind,True,shift)
    data = []
    max_discrepancy = 0.0; minimum_absorption = 1.0; max_boundary_residual = 0.0
    for angle in angles:
        for pol in ("s","p"):
            for dp in perturbations:
                out = response(d*(1+dp),materials_for(kind),w,angle,pol)
                other = recursive_scattering(d*(1+dp),materials_for(kind),w,angle,pol)
                max_discrepancy = max(max_discrepancy,*(float(np.max(np.abs(out[k]-other[k]))) for k in out))
                minimum_absorption = min(minimum_absorption,float(np.min(out["A"])))
                item = {"angle_deg":angle,"polarization":pol,"thickness_relative_shift":dp,"mean_absorption":float(np.mean(out["A"]))}
                if kind=="K1":
                    item.update(mean_useful_transmission=float(np.mean(out["T"])),max_reflectance=float(np.max(out["R"])))
                else:
                    item.update(mean_pass_transmission=float(np.mean(out["T"][~stop])),mean_stop_reflection=float(np.mean(out["R"][stop])))
                data.append(item)
            for wavelength in (float(w[0]),float(w[len(w)//2]),float(w[-1])):
                independent = independent_layer_system(d,materials_for(kind),wavelength,angle,pol)
                reference = response(d,materials_for(kind),[wavelength],angle,pol)
                max_boundary_residual = max(max_boundary_residual,independent["boundary_residual"])
                max_discrepancy = max(max_discrepancy,*(abs(independent[k]-float(reference[k][0])) for k in ("R","T","A")))
    valid = max_discrepancy<1e-8 and minimum_absorption>=-1e-10 and max_boundary_residual<1e-8
    if kind=="K1":
        performance = min(x["mean_useful_transmission"] for x in data)>=.975
        primary = min(x["mean_useful_transmission"] for x in data)
    else:
        performance = min(x["mean_pass_transmission"] for x in data)>=.80 and min(x["mean_stop_reflection"] for x in data)>=.80
        primary = min(min(x["mean_pass_transmission"],x["mean_stop_reflection"]) for x in data)
    return {"accepted":bool(valid and performance),"physics_checks_passed":bool(valid),"primary_worst_mean":primary,"cross_solver_max_error":max_discrepancy,"minimum_absorption":minimum_absorption,"boundary_residual_max":max_boundary_residual,"cases":data}

def correctness_controls():
    max_fresnel = 0.0
    for w in (.7,.93,1.5):
        n = index("SiO2",[w])[0].real
        analytic = ((1-n)/(1+n))**2
        max_fresnel = max(max_fresnel,abs(float(response([],[],[w])["R"][0])-analytic))
    rejects = {}
    cases = {
        "negative_thickness":([-1],["SiO2"],[1],0,"s"),
        "nonfinite_thickness":([float("nan")],["SiO2"],[1],0,"s"),
        "wrong_material":([.1],["unknown"],[1],0,"s"),
        "wrong_units_nanometres_as_um":([100],["SiO2"],[1],0,"s"),
        "outside_wavelength":([.1],["SiO2"],[.2],0,"s"),
        "outside_incidence":([.1],["SiO2"],[1],60,"s"),
        "wrong_polarization":([.1],["SiO2"],[1],0,"z"),
        "shape_mismatch":([.1,.2],["SiO2"],[1],0,"s"),
    }
    for name,args in cases.items():
        try:
            response(*args)
            rejects[name] = False
        except ValueError:
            rejects[name] = True
    quarter_wavelength = 1.0
    n = index("MgF2",[quarter_wavelength])[0].real
    ns = index("SiO2",[quarter_wavelength])[0].real
    analytical_quarter = ((ns-n*n)/(ns+n*n))**2
    quarter_error = abs(float(response([quarter_wavelength/(4*n)],["MgF2"],[quarter_wavelength])["R"][0])-analytical_quarter)
    return {"bare_interface_fresnel_error":max_fresnel,"quarter_wave_analytic_error":quarter_error,"rejections":rejects,"passed":bool(max_fresnel<1e-12 and quarter_error<1e-12 and all(rejects.values()))}

def run_experiment(output_dir):
    start = time.perf_counter(); cpu = time.process_time()
    output = Path(output_dir); output.mkdir(parents=True,exist_ok=False)
    identity = source_identity()
    control = correctness_controls()
    k1 = build("K1",202611021)
    k1["validation"] = validate(k1["thickness_um"],"K1")
    retained = {"source_identity":identity,"kernel":"optics.py:response","material_provenance":"SOURCES.md","K1_accepted":k1["validation"]["accepted"],"domain":"coherent planar isotropic layers; 0.7–1.5 um; <=45 degrees; room-temperature published optical constants; no fabricated device","does_not_transfer":["automatic physical qualification","K1 task objective","K1 optimum thicknesses","buyer consent","funding","hidden future truth"]}
    (output/"retained_K1_manifest.json").write_text(json.dumps(retained,indent=2)+"\n")
    if not k1["validation"]["accepted"]:
        report = {"schema":"public-foundry-stage1/v1","correctness_controls":control,"K1":k1,"K2":[],"stage_verdict":"K1 acceptance failed; successor is not treated as inherited capability","source_identity":identity}
    else:
        successor = []
        for task,seed,shift in (("spectral-routing-A",202611022,0),("spectral-routing-B",202611023,-.025)):
            arms = {}
            for arm in ARMS:
                solver = recursive_scattering if arm=="fresh_specialist_no_inheritance" else response
                design = build("K2",seed,solver,shift)
                design["validation"] = validate(design["thickness_um"],"K2",shift)
                arms[arm] = design
            d = np.asarray(arms["retained_procedure"]["thickness_um"])
            shifted = validate(d,"K2",shift,perturbations=(-.10,0,.10),angles=(35,40,45))
            bare_w,stop = task_grid("K2",True,shift)
            bare = response([],[],bare_w)
            no_mechanism = {"mean_pass_transmission":float(np.mean(bare["T"][~stop])),"mean_stop_reflection":float(np.mean(bare["R"][stop])),"accepted":bool(np.mean(bare["T"][~stop])>=.8 and np.mean(bare["R"][stop])>=.8)}
            successor.append({"task_id":task,"wavelength_shift_um":shift,"arms":arms,"no_mechanism":no_mechanism,"manufacturing_and_angle_distribution_shift":shifted,"best_complete_alternative_already_allowed_same_means":True,"retained_vs_equal_content_objective_delta":arms["ordinary_equal_content"]["objective"]-arms["retained_procedure"]["objective"]})
        all_accepted = all(t["arms"]["retained_procedure"]["validation"]["accepted"] for t in successor)
        report = {"schema":"public-foundry-stage1/v1","correctness_controls":control,"K1":k1,"K2":successor,"stage_verdict":"computational instrument and fresh successor accepted; conventional tie prevents discovery superiority and no new economically attainable frontier established" if all_accepted else "computational instrument constructed; at least one fresh successor failed frozen acceptance; no flagship admission","source_identity":identity}
    report.update({"actual_artifacts_are_computational":True,"physical_device_built":False,"actual_revenue_established":False,"internal_human_assistance_requested_minutes":0,"user_oversight_minutes":"unknown, not zero by assumption","human_productivity_advantage":"unresolved; no timed competent-human construction observed","cpu_seconds":time.process_time()-cpu,"wall_seconds":time.perf_counter()-start,"peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"costs":"ECONOMIC_INPUTS.json gives estimates; actual model/host billing unknown; canonical accounts executed by portfolio coordinator separately"})
    (output/"RESULTS.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"output":str(output),"verdict":report["stage_verdict"],"K1_accepted":k1["validation"]["accepted"],"K2_count":len(report["K2"]),"cpu_seconds":report["cpu_seconds"]}))
    return report

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args = parser.parse_args()
    run_experiment(args.output)
