from __future__ import annotations

from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_CEILING
from itertools import product


PRECISION = 48


def rounded(operation, mode):
    with localcontext() as context:
        context.prec = PRECISION
        context.rounding = mode
        return +operation()


class Interval:
    def __init__(self, lower, upper=None):
        self.lo = Decimal(lower)
        self.hi = self.lo if upper is None else Decimal(upper)
        if not self.lo.is_finite() or not self.hi.is_finite() or self.lo > self.hi:
            raise ValueError("invalid finite interval")

    def __add__(self, other):
        if not isinstance(other, Interval):
            other = Interval(other)
        return Interval(rounded(lambda:self.lo+other.lo,ROUND_FLOOR), rounded(lambda:self.hi+other.hi,ROUND_CEILING))

    __radd__ = __add__

    def __neg__(self):
        return Interval(self.hi.copy_negate(),self.lo.copy_negate())

    def __sub__(self, other):
        return self + (-other if isinstance(other,Interval) else -Interval(other))

    def __rsub__(self, other):
        return Interval(other) + (-self)

    def __mul__(self, other):
        if not isinstance(other, Interval):
            other = Interval(other)
        pairs = list(product((self.lo,self.hi),(other.lo,other.hi)))
        lower = min(rounded(lambda:a*b,ROUND_FLOOR) for a,b in pairs)
        upper = max(rounded(lambda:a*b,ROUND_CEILING) for a,b in pairs)
        return Interval(lower,upper)

    __rmul__ = __mul__

    def square(self):
        lower = Decimal(0) if self.lo <= 0 <= self.hi else min(rounded(lambda:x*x,ROUND_FLOOR) for x in (self.lo,self.hi))
        upper = max(rounded(lambda:x*x,ROUND_CEILING) for x in (self.lo,self.hi))
        return Interval(lower,upper)

    def contains(self, other):
        return self.lo < other.lo and other.hi < self.hi

    def inflate(self):
        width = rounded(lambda:self.hi-self.lo,ROUND_CEILING)
        padding = rounded(lambda:width*Decimal("0.01")+Decimal("1e-30"),ROUND_CEILING)
        return Interval(rounded(lambda:self.lo-padding,ROUND_FLOOR),rounded(lambda:self.hi+padding,ROUND_CEILING))

    def as_json(self):
        return [str(self.lo),str(self.hi)]


def network_interval(inputs,weights,biases):
    value = inputs
    for index,(weight,bias) in enumerate(zip(weights,biases)):
        value = [sum((Interval(Decimal.from_float(float(coefficient))) * x for coefficient,x in zip(row,value)),Interval(Decimal.from_float(float(b)))) for row,b in zip(weight,bias)]
        if index < len(weights)-1:
            value = [Interval(max(Decimal(0),x.lo),max(Decimal(0),x.hi)) for x in value]
    return value[0]


def rhs_interval(state,command):
    xl,vl,al,xe,ve,ae = state
    return [vl,al,-2*al-4-Interval("0.0001")*vl.square(),ve,ae,-2*ae+2*command-Interval("0.0001")*ve.square()]


def flow_step(initial,command):
    duration = Interval("0","0.01")
    tube = [(x+duration*f).inflate() for x,f in zip(initial,rhs_interval(initial,command))]
    for iteration in range(16):
        proposal = [x+duration*f for x,f in zip(initial,rhs_interval(tube,command))]
        if all(y.contains(z) for y,z in zip(tube,proposal)):
            endpoint = [x+Interval("0.01")*f for x,f in zip(initial,rhs_interval(tube,command))]
            return endpoint,tube,iteration+1
        tube = [Interval(min(y.lo,z.lo),max(y.hi,z.hi)).inflate() for y,z in zip(tube,proposal)]
    raise ArithmeticError("Picard tube inclusion not established")


def check_box(box,weights,biases):
    state = [Interval(str(lo),str(hi)) for lo,hi in box]
    worst_margin = None
    substeps = 0
    try:
        for sample in range(50):
            inputs = [Interval("30"),Interval("1.4"),state[4],state[0]-state[3],state[1]-state[4]]
            command = network_interval(inputs,weights,biases)
            for _ in range(10):
                state,tube,_ = flow_step(state,command)
                substeps += 1
                margin = tube[0]-tube[3]-10-Interval("1.4")*tube[4]
                worst_margin = margin.lo if worst_margin is None else min(worst_margin,margin.lo)
                if margin.lo < 0:
                    return {"verdict":"INCONCLUSIVE","reason":"enclosure overlaps unsafe margin; no actual counterexample inferred","substeps":substeps,"minimum_enclosure_margin":str(worst_margin)}
                if any(max(x.lo.copy_abs(),x.hi.copy_abs()) > Decimal("1e12") for x in state):
                    return {"verdict":"INCONCLUSIVE","reason":"declared numerical enclosure working range exceeded","substeps":substeps}
        return {"verdict":"ENCLOSURE_ACCEPTED","substeps":substeps,"minimum_enclosure_margin":str(worst_margin),"final_box":[x.as_json() for x in state]}
    except ArithmeticError as error:
        return {"verdict":"INCONCLUSIVE","reason":str(error),"substeps":substeps}


def check_original_network(weights,biases,initial):
    full = check_box(initial,weights,biases)
    refined = []
    for bits in product((0,1),repeat=4):
        box = list(initial)
        for index,bit in zip((0,1,3,4),bits):
            lo,hi = initial[index]
            midpoint = (lo+hi)/2
            box[index] = (lo,midpoint) if bit==0 else (midpoint,hi)
        refined.append(check_box(box,weights,biases))
    accepted = full["verdict"]=="ENCLOSURE_ACCEPTED" or all(x["verdict"]=="ENCLOSURE_ACCEPTED" for x in refined)
    return {"verdict":"CONDITIONAL_INTERVAL_CERTIFICATE_REQUIRES_INDEPENDENT_IMPLEMENTATION_AUDIT" if accepted else "UNRESOLVED_INTERVAL_OVERAPPROXIMATION", "full_initial_box":full,"fixed_16_box_refinement":refined,"semantics":"Directed Decimal interval arithmetic; Picard tube inclusion and first-order endpoint enclosure; original NN is sample-and-hold for0.1s, continuous ODE integrated in0.01s enclosures","numerical_scope":"48decimal digits;16Picard inflation steps; polynomial dynamics on finite tubes; no simulation-only trajectory is promoted to universal safety; full interval implementation needs independent audit even if it accepts"}
