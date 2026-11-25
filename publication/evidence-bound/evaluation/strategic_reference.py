# SPDX-License-Identifier: Apache-2.0
"""Independent exact oracle for two hidden scenarios and one optional observation."""

from fractions import Fraction
from itertools import combinations, product


def robust_optimum(vectors):
    """Evaluate feasible primal mixtures and dual beliefs with exact arithmetic."""
    points = sorted(set(tuple(map(Fraction, pair)) for pair in vectors))
    if not points:
        raise ValueError("A game needs at least one feasible decision.")
    lower = max(min(point) for point in points)
    for left, right in combinations(points, 2):
        dleft, dright = left[0] - left[1], right[0] - right[1]
        if dleft * dright < 0:
            share = dright / (dright - dleft)
            level = share * left[0] + (1 - share) * right[0]
            lower = max(lower, level)
    beliefs = {Fraction(0), Fraction(1)}
    for left, right in combinations(points, 2):
        a, b = left[0] - right[0], left[1] - right[1]
        if a * b < 0:
            beliefs.add(b / (b - a))
    upper = min(max(q * pay0 + (1 - q) * pay1 for pay0, pay1 in points) for q in beliefs)
    if lower != upper:
        raise ArithmeticError("Independent exact primal and dual disagree.")
    return lower


def exact(case):
    payoffs = case["payoffs"]
    q0, q1 = (Fraction(p, 100) for p in case["accuracy"])
    fee = Fraction(case["fee"])
    skip = robust_optimum(payoffs)
    purchase = robust_optimum((
        (q0 * r0[0] + (1 - q0) * r1[0], (1 - q1) * r0[1] + q1 * r1[1])
        for r0, r1 in product(payoffs, repeat=2)
    ))
    delta = purchase - fee - skip
    return {
        "skip": str(skip),
        "purchase_before_fee": str(purchase),
        "advantage_after_fee": str(delta),
        "choice": "BUY" if delta > 0 else "SKIP",
    }
