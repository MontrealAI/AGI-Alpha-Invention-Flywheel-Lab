"""K1-generated bounded identifiability instrument, not a general discovery agent.

Find multiplicative symmetries of a supplied polynomial/monomial representation.
Known inputs and measured outputs stay fixed. A nonzero exponent on the required
physical quantity witnesses a scale ambiguity in this representation. Absence of
such a symmetry does NOT prove identifiability, good conditioning or safe control.
The constructor searches allowed monomial reference measurements and returns the
least declared-cost set breaking the witnessed target scale freedom.

No domain names, physical-world truth, fitted values or future observations occur
in this retained file. Equations and measurement rights must be independently
validated by the domain adapter. All algebra uses exact rationals.
"""
from fractions import Fraction
from itertools import combinations, product

VERSION = "grid074.k1-retained-symmetry.v1"


def nullspace(rows, n):
    a = [[Fraction(v) for v in row] for row in rows if any(row)]
    pivots = []
    k = 0
    for col in range(n):
        idx = next((i for i in range(k, len(a)) if a[i][col]), None)
        if idx is None:
            continue
        a[k], a[idx] = a[idx], a[k]
        scale = a[k][col]
        a[k] = [v / scale for v in a[k]]
        for i in range(len(a)):
            if i != k and a[i][col]:
                scale = a[i][col]
                a[i] = [v - scale * x for v, x in zip(a[i], a[k])]
        pivots.append(col)
        k += 1
        if k == len(a):
            break
    basis = []
    for free in sorted(set(range(n)) - set(pivots)):
        vector = [Fraction(0) for _ in range(n)]
        vector[free] = Fraction(1)
        for row, pivot in enumerate(pivots):
            vector[pivot] = -a[row][free]
        basis.append(vector)
    return basis


def constraints(card):
    variables = card["variables"]
    if len(variables) != len(set(variables)):
        raise ValueError("duplicate variables")
    def vector(monomial):
        if set(monomial) - set(variables):
            raise ValueError("unknown monomial variable")
        return [Fraction(monomial.get(v, 0)) for v in variables]
    rows = []
    for equation in card["equations"]:
        if not equation:
            raise ValueError("empty equation")
        first = vector(equation[0])
        rows.extend([[x-y for x,y in zip(vector(term), first)] for term in equation[1:]])
    rows.extend(vector({v: 1}) for v in card["fixed"])
    return variables, rows


def target_free(card, added=()):
    variables, rows = constraints(card)
    for measurement in added:
        rows.append([Fraction(measurement.get(v, 0)) for v in variables])
    target = [Fraction(card["target"].get(v, 0)) for v in variables]
    basis = nullspace(rows, len(variables))
    affecting = [v for v in basis if sum(a*b for a,b in zip(v,target))]
    return variables, basis, affecting


def construct(card):
    variables, basis, affecting = target_free(card)
    def encode(v):
        return {name: str(power) for name, power in zip(variables,v) if power}
    result = {
        "version": VERSION,
        "symmetry_basis": [encode(v) for v in basis],
        "target_affecting_symmetries": [encode(v) for v in affecting],
        "has_witnessed_scale_ambiguity": bool(affecting),
        "identifiable": None,
        "scope": "multiplicative symmetry of validated supplied representation only",
    }
    if not affecting:
        result.update(decision="no_scale_breaking_instrument_justified_by_this_test", instruments=[], cost=0)
        return result
    measurements = card.get("allowed_references", [])
    feasible = []
    # Finite declared construction grammar: combinations of permitted reference
    # monomials. Nothing is purchased or physically created by this search.
    for size in range(1, len(measurements)+1):
        for choices in combinations(measurements, size):
            if not target_free(card, [c["monomial"] for c in choices])[2]:
                cost = sum(Fraction(str(c["cost"])) for c in choices)
                if cost <= Fraction(str(card.get("construction_budget", cost))):
                    feasible.append((cost, tuple(c["name"] for c in choices), choices))
    if not feasible:
        result.update(decision="unresolved_within_declared_construction_budget", instruments=[], cost=0)
        return result
    cost, names, choices = min(feasible, key=lambda x:(x[0],x[1]))
    result.update(decision="construct_reference_then_requalify", instruments=list(names), cost=float(cost),
                  executable_measurements=[dict(c["monomial"]) for c in choices])
    return result


def self_test():
    for rows,n in [([[1,2,3],[2,4,6]],3), ([[1,0],[0,1]],2),([],3)]:
        for v in nullspace(rows,n):
            assert all(sum(Fraction(a)*b for a,b in zip(row,v)) == 0 for row in rows)
    # No thermal/grid test data here. Relabeling all variables leaves decisions invariant.
    c={"variables":["u","v","z"],"equations":[[{"u":1,"v":1},{"z":1}]],
       "fixed":["z"],"target":{"u":1},"allowed_references":[
         {"name":"anchor","monomial":{"u":1},"cost":3}],"construction_budget":3}
    assert construct(c)["instruments"] == ["anchor"]
    c["construction_budget"]=2
    assert construct(c)["decision"] == "unresolved_within_declared_construction_budget"
    c["fixed"].append("u")
    assert not construct(c)["has_witnessed_scale_ambiguity"]
    return {"passed":True,"scope":"algebra and cost/anchor mechanics, no physics qualification"}
