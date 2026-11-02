"""Bounded orbital-design mathematics; no flight authority or operational safety claim."""
from itertools import product
import math
import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.linalg import expm


def cw_transition(n, t):
    if not np.isfinite([n, t]).all() or n <= 0 or t < 0 or t > 21600:
        raise ValueError("outside registered circular-orbit model envelope")
    c, s = math.cos(n*t), math.sin(n*t)
    return np.array([[4-3*c, 0, 0, s/n, 2*(1-c)/n, 0],
                     [6*(s-n*t), 1, 0, -2*(1-c)/n, (4*s-3*n*t)/n, 0],
                     [0, 0, c, 0, 0, s/n],
                     [3*n*s, 0, 0, c, 2*s, 0],
                     [-6*n*(1-c), 0, 0, -2*s, 4*c-3, 0],
                     [0, 0, -n*s, 0, 0, c]])


def generator(n):
    a = np.zeros((6, 6))
    a[:3, 3:] = np.eye(3)
    a[3, 0], a[3, 4], a[4, 3], a[5, 2] = 3*n*n, 2*n, -2*n, -n*n
    return a


def impulse_effect(n, t):
    return cw_transition(n, t)[:, 3:]


def collision_bound(mean2, cov2, radius, execution_bound=0.0):
    m, c = np.asarray(mean2, float), np.asarray(cov2, float)
    if m.shape != (2,) or c.shape != (2, 2) or not np.isfinite(m).all() or not np.isfinite(c).all():
        raise ValueError("finite 2D mean/covariance required, in metres")
    if not np.isfinite([radius, execution_bound]).all() or radius <= 0 or execution_bound < 0:
        raise ValueError("invalid radius/execution bound")
    if not np.allclose(c, c.T, rtol=0, atol=1e-12):
        raise ValueError("asymmetric covariance")
    eig = np.linalg.eigvalsh(c)
    if eig[0] <= 0:
        raise ValueError("covariance must be positive definite")
    gap = max(0.0, float(np.linalg.norm(m))-radius-execution_bound)
    return math.exp(-gap*gap/(2*eig[-1]))


def disk_probability(mean2, cov2, radius):
    collision_bound(mean2, cov2, radius)
    m, c = np.asarray(mean2, float), np.asarray(cov2, float)
    inv, den = np.linalg.inv(c), 2*math.pi*math.sqrt(np.linalg.det(c))
    def angular(theta):
        u = np.array([math.cos(theta), math.sin(theta)])
        return quad(lambda r: math.exp(-0.5*((r*u-m)@inv@(r*u-m)))*r/den,
                    0, radius, epsabs=1e-13, epsrel=1e-10)[0]
    return quad(angular, 0, 2*math.pi, epsabs=1e-12, epsrel=1e-9)[0]


def _request(r):
    required = {"mean_m", "cov_m2", "radius_m", "execution_bound_m", "n_rad_s", "lead_s",
                "actions_mps", "fuel_cost_usd_per_mps", "fixed_burn_usd", "asset_loss_usd",
                "cash_usd", "platform_fee_usd", "transfer_grid_usd", "max_overlap_bound",
                "consent", "units", "linearization_scale_m", "execution_default"}
    if set(r) != required:
        raise ValueError("request schema mismatch")
    if (r["units"] != "SI_USD" or not isinstance(r["consent"], list)
            or len(r["consent"]) != 2 or any(type(value) is not bool or not value for value in r["consent"])):
        raise ValueError("units or scoped permission absent")
    if (not np.isfinite(r["linearization_scale_m"])
            or r["linearization_scale_m"] > 1000 or r["linearization_scale_m"] < 0):
        raise ValueError("linearized position-error envelope exceeded")
    if type(r["execution_default"]) is not bool:
        raise ValueError("execution qualification flag must be boolean")
    if not 0 < r["max_overlap_bound"] < 1:
        raise ValueError("risk threshold outside (0,1)")
    for key in ["fuel_cost_usd_per_mps", "fixed_burn_usd", "asset_loss_usd", "cash_usd"]:
        if len(r[key]) != 2 or not np.isfinite(r[key]).all() or min(r[key]) < 0:
            raise ValueError("invalid nonnegative participant parameter")
    if not np.isfinite(r["platform_fee_usd"]) or r["platform_fee_usd"] < 0:
        raise ValueError("invalid platform fee")
    if len(r["actions_mps"]) != 2 or any(0.0 not in a for a in r["actions_mps"]):
        raise ValueError("each participant must have no-burn outside action")
    if any(not np.isfinite(a).all() or max(abs(float(u)) for u in a) > 0.25 for a in r["actions_mps"]):
        raise ValueError("impulse envelope exceeded")
    if not r["transfer_grid_usd"] or not np.isfinite(r["transfer_grid_usd"]).all():
        raise ValueError("finite transfer grid required")
    collision_bound(r["mean_m"], r["cov_m2"], r["radius_m"], r["execution_bound_m"])
    cw_transition(r["n_rad_s"], r["lead_s"])


def physical_options(r, actions=None):
    _request(r)
    response = impulse_effect(r["n_rad_s"], r["lead_s"])[[0, 1], 1]
    output = []
    for u, v in product(*(r["actions_mps"] if actions is None else actions)):
        mean = np.asarray(r["mean_m"])+(u-v)*response
        bound = collision_bound(mean, r["cov_m2"], r["radius_m"], r["execution_bound_m"])
        fuel = [abs(a)*r["fuel_cost_usd_per_mps"][i]+(r["fixed_burn_usd"][i] if a else 0)
                for i, a in enumerate([u, v])]
        costs = [fuel[i]+bound*r["asset_loss_usd"][i] for i in range(2)]
        output.append({"impulses_mps": [u, v], "mean_m": mean.tolist(), "overlap_bound": bound,
                       "fuel_cost_usd": fuel, "private_cost_usd": costs,
                       "qualifies": bound <= r["max_overlap_bound"]})
    return output


def outside_game(r):
    options = physical_options(r)
    equilibria = []
    for o in options:
        uv = o["impulses_mps"]
        regret = []
        for i in range(2):
            best = min(p["private_cost_usd"][i] for p in options
                       if p["impulses_mps"][1-i] == uv[1-i])
            regret.append(max(0.0, o["private_cost_usd"][i]-best))
        if max(regret) <= 1e-8:
            equilibria.append(o)
    if not equilibria:
        return {"status": "no_pure_equilibrium_no_contract", "cost_usd": None, "equilibria": []}
    return {"status": "pure_equilibrium_outside_option", "cost_usd": [
        min(o["private_cost_usd"][i] for o in equilibria) for i in range(2)], "equilibria": equilibria}


def select_contract(request, technical=True, arrangement=True):
    r = request
    outside = outside_game(r)
    if outside["cost_usd"] is None:
        return {"accepted": False, "reason": outside["status"], "outside": outside}
    actions = r["actions_mps"] if technical else [
        [a for a in r["actions_mps"][0] if a >= 0], [0.0]]
    transfers = r["transfer_grid_usd"] if arrangement else [0.0]
    candidates = []
    for o, t in product(physical_options(r, actions), transfers):
        if not o["qualifies"]:
            continue
        fee = r["platform_fee_usd"]
        cost = [o["private_cost_usd"][0]+t+fee, o["private_cost_usd"][1]-t]
        cash_need = [o["fuel_cost_usd"][0]+max(0, t)+fee,
                     o["fuel_cost_usd"][1]+max(0, -t)]
        if any(cash_need[i] > r["cash_usd"][i] for i in range(2)):
            continue
        if any(cost[i] > outside["cost_usd"][i]+1e-8 for i in range(2)):
            continue
        if r["execution_default"]:
            continue
        candidates.append({**o, "transfer_A_to_B_usd": t, "platform_fee_usd": fee,
                           "participant_cost_usd": cost, "cash_required_usd": cash_need,
                           "participation_surplus_usd": [outside["cost_usd"][i]-cost[i] for i in range(2)]})
    candidates.sort(key=lambda o: (sum(o["participant_cost_usd"]), o["impulses_mps"], o["transfer_A_to_B_usd"]))
    return {"accepted": bool(candidates), "reason": "feasible_voluntary_model_contract" if candidates else "refusal",
            "selected": candidates[0] if candidates else None, "outside": outside,
            "feasible_contract_count": len(candidates), "finite_selection_gap_usd": 0.0,
            "solution_concept": "exhaustive min total private cost over individually rational funded quote-grid contracts; not truthful mechanism"}


def participant_response(offer, private_request):
    outside = outside_game(private_request)
    if not offer.get("accepted") or outside["cost_usd"] is None:
        return {"consent": [False, False], "executed": False, "reason": "no_offer_or_pure_outside_option"}
    chosen = offer["selected"]
    physical = next((o for o in physical_options(private_request)
                     if o["impulses_mps"] == chosen["impulses_mps"]), None)
    if physical is None or not physical["qualifies"]:
        return {"consent": [False, False], "executed": False, "reason": "private_qualification_failure"}
    t, fee = chosen["transfer_A_to_B_usd"], chosen["platform_fee_usd"]
    cost = [physical["private_cost_usd"][0]+t+fee, physical["private_cost_usd"][1]-t]
    cash = [physical["fuel_cost_usd"][0]+max(t, 0)+fee, physical["fuel_cost_usd"][1]+max(-t, 0)]
    consent = [bool(cost[i] <= outside["cost_usd"][i]+1e-8 and cash[i] <= private_request["cash_usd"][i])
               for i in range(2)]
    return {"consent": consent, "executed": all(consent) and not private_request["execution_default"],
            "participant_cost_usd": cost, "private_outside_cost_usd": outside["cost_usd"],
            "reason": "private_participation_response_no_requote_or_payment_after_refusal"}


def reconstruct_transition(n, t):
    cw_transition(n, t)
    return expm(generator(n)*t)


def servicing_transfer(n, duration_s, initial, target, transition=cw_transition):
    initial, target = np.asarray(initial, float), np.asarray(target, float)
    if initial.shape != (6,) or target.shape != (6,) or not np.isfinite(initial).all() or not np.isfinite(target).all():
        raise ValueError("finite 6D SI endpoint states required")
    if max(np.linalg.norm(initial[:3]), np.linalg.norm(target[:3])) > 1500:
        raise ValueError("outside close-proximity state envelope")
    half = duration_s/2
    f, h = transition(n, duration_s), transition(n, half)
    a = np.column_stack([f[:, 3:], h[:, 3:]])
    cond = float(np.linalg.cond(a))
    if cond > 1e10:
        return {"accepted": False, "reason": "ill_conditioned_transfer", "condition": cond}
    burns = np.linalg.solve(a, target-f@initial).reshape(2, 3)
    terminal = f@initial+a@burns.ravel()
    fuel = float(np.linalg.norm(burns[0])+np.linalg.norm(burns[1]))
    residual = float(np.linalg.norm(terminal-target))
    return {"accepted": bool(fuel <= 5.0 and residual <= 1e-7), "burns_mps": burns.tolist(),
            "fuel_mps": fuel, "terminal_state": terminal.tolist(), "residual": residual,
            "condition": cond, "scope": "two-impulse linear CW endpoint design, not continuous collision clearance"}


def numerical_replay(n, duration_s, initial, burns):
    s = np.asarray(initial, float).copy()
    for burn in burns:
        s[3:] += burn
        s = solve_ivp(lambda t, y: generator(n)@y, (0, duration_s/2), s,
                      rtol=1e-11, atol=1e-11).y[:, -1]
    return s
