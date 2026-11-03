# Generated known-method linear-response plan. No network or external actions.
import hashlib
import json
import sys
import warnings
import numpy as np
from scipy.linalg import lu_factor, lu_solve, LinAlgWarning

METHOD = 'woodbury'
REQUEST_SHA256 = '459805f947fcbe52f664edab6214750598d39625b45849a30496268f65935671'

def solve_payload(request):
    observed = hashlib.sha256(json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if observed != REQUEST_SHA256:
        raise ValueError("REQUEST_CHANGED")
    base = np.asarray(request["base_matrix"], dtype=float)
    cases = request["cases"]
    output = []
    if METHOD == "reuse":
        reference = np.asarray(cases[0]["matrix"], dtype=float)
        if any(not np.array_equal(np.asarray(c["matrix"], dtype=float), reference) for c in cases):
            raise ValueError("REUSE_INAPPLICABLE")
    elif METHOD == "woodbury":
        for case in cases:
            update = case["update"]
            if update is None:
                raise ValueError("WOODBURY_INAPPLICABLE")
            u, v = np.asarray(update["u"], dtype=float), np.asarray(update["v"], dtype=float)
            a = np.asarray(case["matrix"], dtype=float)
            bound = 8 * np.finfo(float).eps * max(1.0, float(np.max(np.abs(a))))
            if not np.allclose(a, base + u @ v.T, rtol=0, atol=bound):
                raise ValueError("WOODBURY_INAPPLICABLE")
    with warnings.catch_warnings():
        warnings.simplefilter("error", LinAlgWarning)
        shared = lu_factor(base if METHOD == "woodbury" else np.asarray(cases[0]["matrix"], dtype=float)) if METHOD != "direct" else None
        updates = {}
        for case in cases:
            b = np.asarray(case["rhs"], dtype=float)
            if METHOD == "direct":
                x = lu_solve(lu_factor(np.asarray(case["matrix"], dtype=float)), b)
            elif METHOD == "reuse":
                x = lu_solve(shared, b)
            else:
                update = case["update"]
                key = json.dumps(update, sort_keys=True, separators=(",", ":"))
                if key not in updates:
                    u = np.asarray(update["u"], dtype=float)
                    v = np.asarray(update["v"], dtype=float)
                    z = lu_solve(shared, u)
                    small = np.eye(u.shape[1]) + v.T @ z
                    updates[key] = (z, v, lu_factor(small))
                z, v, small_factor = updates[key]
                y = lu_solve(shared, b)
                x = y - z @ lu_solve(small_factor, v.T @ y)
            if not np.isfinite(x).all():
                raise ValueError("NONFINITE_SOLUTION")
            output.append(x.tolist())
    return output

if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as source:
        request = json.load(source)
    print(json.dumps({"solutions": solve_payload(request), "request_sha256": REQUEST_SHA256}, allow_nan=False))
