"""Exact finite-horizon Bayes-adaptive capability allocation.

Every probability/cost is authored, not estimated from actual markets. The latent
viability state is a deliberately simplified binary state and evidence access is
explicit. A fully general commercial/invention planner would require identified
causal models, uncertainty calibration, strategic actors and real validations.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
from fractions import Fraction
from typing import Tuple

NAMES = ("A", "B")


def frac(v):
    if isinstance(v, Fraction):
        return v
    return Fraction(str(v))


@dataclass(frozen=True)
class Config:
    title: str = "Construct only if it beats accessible frontier tools"
    horizon: int = 4
    starting_cash: int = 25
    protected_reserve: int = 10
    initial_p_good: Fraction = Fraction(35, 100)
    signal_sensitivity: Fraction = Fraction(9, 10)
    signal_false_positive: Fraction = Fraction(1, 10)
    probe_cost: int = 3
    construction_cost: int = 12
    maintenance_per_delivery: int = 0
    frontier_access: bool = True
    frontier_net_delivery: Tuple[int, int] = (14, 16)
    specialist_net_delivery: Tuple[int, int] = (10, 12)
    constructed_net_delivery: Tuple[int, int] = (32, 36)

    def __post_init__(self):
        if self.horizon < 1 or self.horizon > 12:
            raise ValueError("Finite declared horizon must be 1..12")
        if self.starting_cash < self.protected_reserve or self.protected_reserve < 0:
            raise ValueError("Starting cash must cover protected reserve")
        for p in (self.initial_p_good, self.signal_sensitivity, self.signal_false_positive):
            if not (0 <= p <= 1):
                raise ValueError("Probabilities must be in [0,1]")
        if any(v < 0 for v in (self.probe_cost, self.construction_cost, self.maintenance_per_delivery)):
            raise ValueError("Costs must be nonnegative")
        for xs in (self.frontier_net_delivery, self.specialist_net_delivery, self.constructed_net_delivery):
            if len(xs) != 2:
                raise ValueError("The illustrative environment has exactly two markets")

    @classmethod
    def from_dict(cls, d):
        keys = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        for name in ("initial_p_good", "signal_sensitivity", "signal_false_positive"):
            if name in keys:
                keys[name] = frac(keys[name])
        for name in ("frontier_net_delivery", "specialist_net_delivery", "constructed_net_delivery"):
            if name in keys:
                keys[name] = tuple(int(x) for x in keys[name])
        return cls(**keys)


@dataclass(frozen=True)
class State:
    remaining: int
    cash: int
    p_good: Fraction
    probed: bool = False
    construction: int = 0   # 0 not attempted, 1 qualified, -1 rejected
    delivered: int = 0      # bitmask of markets fulfilled


class Planner:
    """Finite optimal planner *conditional on a disclosed toy game*.

    Belief updates are exact Fractions. The candidate can probe, construct, use a
    frontier tool, use a conventional specialist, deliver with qualified means,
    or stop. Building may expand the available actions, rather than merely
    improve an existing score. All costs and state changes are modeled visibly.
    """
    def __init__(self, config: Config):
        self.c = config
        self.cache = lru_cache(maxsize=None)(self._solve)

    def initial(self):
        return State(self.c.horizon, self.c.starting_cash, self.c.initial_p_good)

    def actions(self, s):
        if s.remaining <= 0:
            return ("stop",)
        a = ["stop"]
        for i, name in enumerate(NAMES):
            if not (s.delivered & (1 << i)):
                if self.c.frontier_access:
                    a.append("frontier:" + name)
                a.append("specialist:" + name)
                if s.construction == 1:
                    a.append("own:" + name)
        if s.construction == 0 and s.cash - self.c.construction_cost >= self.c.protected_reserve:
            a.append("construct")
        if not s.probed and s.construction == 0 and s.cash - self.c.probe_cost >= self.c.protected_reserve:
            a.append("probe")
        return tuple(a)

    def outcomes(self, s, a):
        """Return probability, net immediate reward, successor state (not ground-truth evidence)."""
        if a not in self.actions(s):
            raise ValueError("Inaccessible, prohibited or unavailable action: " + a)
        if a == "stop":
            return ()
        nxt = replace(s, remaining=s.remaining - 1)
        if a.startswith(("frontier:", "specialist:", "own:")):
            mode, which = a.split(":")
            i = NAMES.index(which)
            if mode == "frontier":
                reward = self.c.frontier_net_delivery[i]
            elif mode == "specialist":
                reward = self.c.specialist_net_delivery[i]
            else:
                reward = self.c.constructed_net_delivery[i] - self.c.maintenance_per_delivery
            return ((Fraction(1), Fraction(reward), replace(nxt, cash=s.cash + reward, delivered=s.delivered | (1 << i))),)
        if a == "construct":
            cost = self.c.construction_cost
            # Physical qualification is an explicit toy model assumption; no real prototype tested.
            good = replace(nxt, cash=s.cash - cost, p_good=Fraction(1), construction=1)
            bad = replace(nxt, cash=s.cash - cost, p_good=Fraction(0), construction=-1)
            return tuple((p, Fraction(-cost), state) for p, state in ((s.p_good, good), (1 - s.p_good, bad)) if p > 0)
        if a == "probe":
            p, tp, fp = s.p_good, self.c.signal_sensitivity, self.c.signal_false_positive
            pos = p * tp + (1-p) * fp
            cost = self.c.probe_cost
            result = []
            if pos > 0:
                result.append((pos, Fraction(-cost), replace(nxt, cash=s.cash-cost, probed=True, p_good=p*tp/pos)))
            if pos < 1:
                result.append((1-pos, Fraction(-cost), replace(nxt, cash=s.cash-cost, probed=True, p_good=p*(1-tp)/(1-pos))))
            return tuple(result)
        raise AssertionError(a)

    def q(self, s, a):
        if a == "stop":
            return Fraction(0)
        return sum((prob * (reward + self.cache(nxt)[0]) for prob, reward, nxt in self.outcomes(s, a)), Fraction(0))

    def _solve(self, s):
        if s.remaining == 0 or s.delivered == 3:
            return (Fraction(0), "stop")
        best = (Fraction(0), "stop")
        for a in self.actions(s):
            v = self.q(s, a)
            if v > best[0]:  # stable tie-break: stop/known means before speculative construction
                best = (v, a)
        return best

    def choose(self, state=None):
        return self.cache(state or self.initial())

    def ranking(self, state=None):
        s = state or self.initial()
        return sorted(((a, self.q(s, a)) for a in self.actions(s)), key=lambda x: (-x[1], x[0]))

    def greedy_no_experiment(self, state=None):
        """A strong but myopic control: highest immediate positive net delivery, no research."""
        s = state or self.initial()
        total = Fraction(0)
        sequence=[]
        while s.remaining > 0:
            acts = [(a, o[0][1]) for a in self.actions(s) if a.startswith(("frontier:", "specialist:")) for o in [self.outcomes(s,a)]]
            if not acts:
                break
            a, gain = max(acts, key=lambda t: (t[1], t[0]))
            if gain <= 0:
                break
            total += gain
            s = self.outcomes(s, a)[0][2]
            sequence.append(a)
        return total, sequence
