"""Exact declared money conversions; probabilities are separately modeled floats."""
from fractions import Fraction
MICRO=1_000_000

def usd(value):
    q=Fraction(str(value))*MICRO
    if q.denominator!=1:raise ValueError('EXACT_MICROUSD_REQUIRED')
    return q.numerator

def floor_share(amount,rate):return (amount*Fraction(str(rate))).numerator//(amount*Fraction(str(rate))).denominator

def ceil_share(amount,rate):
    q=amount*Fraction(str(rate));return -(-q.numerator//q.denominator)

def payment(unit_price,world):return ceil_share(unit_price,world['payment_rate'])+usd(world['payment_fixed_usd'])
