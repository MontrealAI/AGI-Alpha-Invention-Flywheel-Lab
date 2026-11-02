#!/usr/bin/env python3
"""Independent integer dispatch control using scipy.optimize.milp / HiGHS.

No project solver or kernel is imported. The request is the sole task input.
All post-solve payments and deliveries are recomputed with exact integers.
"""
import time
WALL_START = time.perf_counter()
CPU_START = time.process_time()
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import milp, LinearConstraint, Bounds

ROOT = Path(__file__).resolve().parent
request = json.loads((ROOT / 'request.json').read_text())
canonical = lambda obj: json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
input_hash = hashlib.sha256(canonical(request)).hexdigest()
devices = request['devices']
target = request['target_wh']
T = len(target)
N = len(devices)
events = [t for t, demand in enumerate(target) if demand > 0]
factor = 1_000_000 - request['derating_ppm']
margin = request['participant_margin_microUSD']
K = N*T + N
c = np.zeros(K)
lower = np.zeros(K)
upper = np.ones(K)
rows, lows, highs = [], [], []
constant = 0
for i, d in enumerate(devices):
    btot = sum(d['baseline_wh'][t] for t in events)
    cost = d['disutility_microUSD_per_wh']
    constant += btot * cost
    row = np.zeros(K)
    for t in range(T):
        k = i*T+t
        row[k] = 1
        upper[k] = d['power_wh'][t] if d['available'][t] else 0
        if t in events:
            upper[k] = min(upper[k], d['baseline_wh'][t])
            c[k] = -cost
    rows.append(row); lows.append(d['required_wh']); highs.append(d['required_wh'])
    z = N*T+i
    c[z] = margin
    # R_i <= btot*z_i, equivalently sum_event x_i + btot*z_i >= btot.
    row = np.zeros(K)
    for t in events: row[i*T+t] = 1
    row[z] = btot
    rows.append(row); lows.append(btot); highs.append(np.inf)
    # R_i >= z_i, ensuring the activation variable matches positive reduction.
    row = np.zeros(K)
    for t in events: row[i*T+t] = 1
    row[z] = 1
    rows.append(row); lows.append(-np.inf); highs.append(btot)
for t in events:
    raw_needed = (target[t]*1_000_000 + factor-1)//factor
    row = np.zeros(K)
    for i in range(N): row[i*T+t] = 1
    baseline = sum(d['baseline_wh'][t] for d in devices)
    rows.append(row); lows.append(-np.inf); highs.append(baseline-raw_needed)
rows.append(c.copy()); lows.append(-np.inf); highs.append(request['buyer_budget_microUSD']-constant)
result = milp(c, integrality=np.ones(K), bounds=Bounds(lower, upper),
              constraints=LinearConstraint(np.array(rows), np.array(lows), np.array(highs)),
              options={'time_limit': 240.0, 'mip_rel_gap': 0.0})
receipt = {
    'control': 'independent_scipy_milp_frontier_generalist',
    'input_sha256': input_hash,
    'solver': 'scipy.optimize.milp / HiGHS',
    'python_version': platform.python_version(),
    'scipy_version': scipy.__version__,
    'solver_status_code': int(result.status),
    'solver_message': str(result.message),
    'model_billing': 'unknown; no paid APIs used',
}
if result.x is not None:
    rounded = np.rint(result.x).astype(np.int64)
    assert np.max(np.abs(result.x-rounded)) < 1e-5
    dispatch = {d['id']: [int(v) for v in rounded[i*T:(i+1)*T]] for i,d in enumerate(devices)}
    payments = {}
    for d in devices:
        x = dispatch[d['id']]
        assert sum(x) == d['required_wh']
        for t in range(T):
            assert 0 <= x[t] <= d['power_wh'][t]
            assert d['available'][t] or x[t] == 0
            if t in events: assert x[t] <= d['baseline_wh'][t]
        removed = sum(d['baseline_wh'][t]-x[t] for t in events)
        payments[d['id']] = removed*d['disutility_microUSD_per_wh'] + (margin if removed > 0 else 0)
    delivered = [sum(d['baseline_wh'][t]-dispatch[d['id']][t] for d in devices)*factor//1_000_000 if t in events else 0 for t in range(T)]
    assert all(delivered[t] >= target[t] for t in events)
    assert sum(payments.values()) <= request['buyer_budget_microUSD']
    output = {'schema':'flexibility063/dispatch/v1', 'request_id':request['id'], 'input_sha256':input_hash,
              'dispatch_wh':dispatch, 'payments_microUSD':payments, 'delivered_wh':delivered}
    (ROOT/'dispatch.json').write_text(json.dumps(output, indent=2)+'\n')
    receipt['output_sha256'] = hashlib.sha256(canonical(output)).hexdigest()
    receipt['output_file_sha256'] = hashlib.sha256((ROOT/'dispatch.json').read_bytes()).hexdigest()
    receipt['total_payment_microUSD'] = sum(payments.values())
    receipt['exact_integer_feasibility_checks_passed'] = True
    receipt['optimality_proved_by_solver'] = result.status == 0
    receipt['mip_gap'] = float(result.mip_gap)
    receipt['mip_dual_bound_including_constant'] = float(result.mip_dual_bound)+constant
else:
    receipt['output_sha256'] = None
    receipt['exact_integer_feasibility_checks_passed'] = False
receipt['wall_seconds'] = time.perf_counter()-WALL_START
receipt['cpu_seconds'] = time.process_time()-CPU_START
(ROOT/'control_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt, indent=2))
