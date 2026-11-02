"""Purpose-preserving partial identification in a declared linear mixture model."""
from __future__ import annotations

import math
import numpy as np
from scipy.optimize import linprog


def validate(request):
    if request.get("schema") != "portfolio071/water-observation/v1":
        raise ValueError("unsupported observation")
    a, y, error, queries, limits = [np.asarray(request[k], dtype=float) for k in ("A", "observed", "measurement_error", "queries", "limits")]
    bounds = np.asarray(request["concentration_bounds"], dtype=float)
    if bounds.ndim!=2 or bounds.shape[1]!=2 or len(bounds)<1 or not np.isfinite(bounds).all() or (bounds[:,0]<0).any() or (bounds[:,1]<bounds[:,0]).any():
        raise ValueError("invalid concentration envelope")
    if a.ndim!=2 or queries.ndim!=2 or a.shape[1]!=len(bounds) or queries.shape[1]!=len(bounds) or len(queries)<1:
        raise ValueError("invalid observation/query dimensions")
    if y.shape!=(len(a),) or error.shape!=y.shape or limits.shape!=(len(queries),):
        raise ValueError("invalid vector dimensions")
    if any(not np.isfinite(v).all() for v in (a,y,error,queries,limits)) or (error<0).any() or (limits<0).any() or (queries<0).any():
        raise ValueError("invalid nonnegative safety query")
    return a,y,error,queries,limits,bounds


def certify(request):
    a,y,error,queries,limits,bounds = validate(request)
    inequalities, rhs = np.vstack([a,-a]), np.concatenate([y+error,-y+error])
    intervals, witnesses = [], []
    for q in queries:
        low = linprog(q,A_ub=inequalities,b_ub=rhs,bounds=bounds,method="highs")
        high = linprog(-q,A_ub=inequalities,b_ub=rhs,bounds=bounds,method="highs")
        if low.status==2 or high.status==2:
            return {"schema":"portfolio071/water-certificate/v1","decision":"inconsistent","query_intervals":[],"witnesses":[]}
        if not low.success or not high.success:
            return {"schema":"portfolio071/water-certificate/v1","decision":"abstain","reason":"solver could not certify interval","query_intervals":[],"witnesses":[]}
        intervals.append([float(low.fun),float(-high.fun)])
        witnesses.append({"minimum":low.x.tolist(),"maximum":high.x.tolist()})
    if all(hi <= limit+1e-8 for (_,hi),limit in zip(intervals,limits)):
        decision = "safe"
    elif any(lo > limit+1e-8 for (lo,_),limit in zip(intervals,limits)):
        decision = "unsafe"
    else:
        decision = "abstain"
    return {"schema":"portfolio071/water-certificate/v1","decision":decision,"query_intervals":intervals,"witnesses":witnesses,"observation_rank":int(np.linalg.matrix_rank(a)),"state_dimension":len(bounds),"qualification":"Only declared linear queries and bounds; new analytes and nonlinear chemistry require new qualification."}


def blend(request, retained=None):
    if request.get("schema")!="portfolio071/water-blend/v1":
        raise ValueError("unsupported blending request")
    sources, target = request["sources"], float(request["target_volume"])
    limits = np.asarray(request["limits"],dtype=float)
    if not sources or not math.isfinite(target) or target<=0 or limits.ndim!=1 or not len(limits) or not np.isfinite(limits).all() or (limits<0).any():
        raise ValueError("invalid target")
    certificates = []
    for i,source in enumerate(sources):
        if any(not math.isfinite(float(source[k])) or source[k]<0 for k in ("available_volume","unit_cost")):
            raise ValueError("invalid source capacity or cost")
        certificate = certify(source["observation"])
        if retained is not None and i<len(retained) and retained[i]!=certificate:
            raise ValueError("retained certificate must requalify against current request")
        if len(certificate["query_intervals"])!=len(limits):
            return {"schema":"portfolio071/water-blend-design/v1","status":"refused","reason":"unqualified source uncertainty"}
        certificates.append(certificate)
    query_keys = [np.asarray(s["observation"]["queries"],dtype=float).tolist() for s in sources]
    if any(q != query_keys[0] for q in query_keys):
        raise ValueError("incompatible query semantics")
    upper = np.asarray([[r[1] for r in c["query_intervals"]] for c in certificates])
    costs = [s["unit_cost"] for s in sources]
    result = linprog(costs,A_ub=upper.T,b_ub=limits*target,A_eq=np.ones((1,len(sources))),b_eq=[target],bounds=[(0,s["available_volume"]) for s in sources],method="highs")
    if not result.success:
        return {"schema":"portfolio071/water-blend-design/v1","status":"infeasible","solver_status":int(result.status),"source_certificates":certificates}
    return {"schema":"portfolio071/water-blend-design/v1","status":"feasible","volumes":result.x.tolist(),"worst_concentration":(result.x@upper/target).tolist(),"total_cost":float(result.fun),"source_certificates":certificates,"retained_scope":"content reuse with fresh semantic and observation validation; not better discovery"}
