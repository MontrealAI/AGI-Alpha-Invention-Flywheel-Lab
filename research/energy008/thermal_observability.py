import hashlib, json, math, pathlib, resource, time

ROOT = pathlib.Path(__file__).resolve().parent

def cooling_interval(measured_change, pressure_change, thermometry_error, jt_coefficient=0.2176):
    lo, hi = pressure_change
    if not all(math.isfinite(x) for x in (measured_change, lo, hi, thermometry_error, jt_coefficient)) or lo > hi or thermometry_error < 0 or jt_coefficient <= 0:
        raise ValueError("invalid bounded measurement")
    return [jt_coefficient * lo - measured_change - thermometry_error, jt_coefficient * hi - measured_change + thermometry_error]

def paired_pressure_requirement(minimum_cooling, change_error, jt_uncertainty_error=0.0, jt_coefficient=0.2176):
    if minimum_cooling <= change_error + jt_uncertainty_error:
        return {"status":"NO_PRESSURE_PRECISION_SUFFICES", "reason":"thermometry/model uncertainty consumes effect"}
    return {"status":"CONDITIONAL_MEASUREMENT_SPECIFICATION", "max_pressure_change_halfwidth_MPa":(minimum_cooling-change_error-jt_uncertainty_error)/jt_coefficient, "requires":["valid pressure-drop measurement at fracture/well interface", "validated thermometry and water-property model", "exclusion or bounded wellbore mixing and heat transfer"]}

def main():
    started = time.monotonic()
    calibration = {"source":"https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2018/Zhang2.pdf", "source_location":"pages 3-4, scenario 1 at double nominal rate", "reported_simulated_warming_C":0.3, "reported_pressure_difference_MPa":2.8, "relation_coefficient_C_per_MPa":0.2176, "warning":"The paper's 0.3 C is a coupled, spatially distributed scenario and not a direct isenthalpic 2.8 MPa drop measurement. Do not calibrate the local JT formula to this scenario."}
    calibration["naive_entire_difference_correction_C"] = calibration["reported_pressure_difference_MPa"] * calibration["relation_coefficient_C_per_MPa"]
    calibration["naive_difference_from_reported_simulation_C"] = calibration["naive_entire_difference_correction_C"] - calibration["reported_simulated_warming_C"]
    calibration["decision"] = "REFUSE_GLOBAL_INJECTION_TO_PRODUCTION_PRESSURE_AS_LOCAL_JT_DROP"
    cases = [
      {"name":"unobserved_local_pressure_counterexample", "synthetic":True, "measured_temperature_change_C":0.0, "pressure_drop_change_interval_MPa":[0.0,5.0], "temperature_change_error_bound_C":0.05},
      {"name":"conditional_paired_measurement", "synthetic":True, "measured_temperature_change_C":-0.3, "pressure_drop_change_interval_MPa":[-0.1,0.1], "temperature_change_error_bound_C":0.05}
    ]
    for c in cases:
        c["cooling_interval_C"] = cooling_interval(c["measured_temperature_change_C"],c["pressure_drop_change_interval_MPa"],c["temperature_change_error_bound_C"])
        c["verdict"] = "UNKNOWN" if c["cooling_interval_C"][0] <= 0 else "POSITIVE_ONLY_WITHIN_LINEAR_SCENARIO"
    report={"status":"DEVELOPMENT_OBSERVABILITY_PROBE_NOT_PHYSICAL_VALIDATION", "source_informed_local_relation":"deltaT_measured = -cooling + 0.2176 * delta_pressure_drop_MPa + bounded_error, for approximately 30C liquid water and local isenthalpic relation only", "causal_repair":"Replace global-pressure point correction with a bounded local-pressure obligation and refuse unobserved local drop; generate a required pressure precision before collecting thermal confirmation.", "baseline":"Ordinary interval arithmetic with the same local relation gives identical results; no invention or baseline advantage is asserted.", "calibration_attempt":calibration, "cases":cases, "measurement_specification":paired_pressure_requirement(0.3,0.05), "unvalidated":["local pressure-drop data", "field thermometry error bounds", "mixture and conduction contribution", "transfer beyond stated liquid-water conditions", "economic eligibility and demand"], "source_sha256":hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), "wall_seconds":time.monotonic()-started,"cpu_seconds":resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime}
    out=ROOT/"THERMAL_PROBE_RESULT.json"
    if out.exists(): raise FileExistsError(out)
    out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"output":str(out),"status":report["status"],"source_naive_correction_mismatch_C":calibration["naive_difference_from_reported_simulation_C"]}))

if __name__ == "__main__": main()
