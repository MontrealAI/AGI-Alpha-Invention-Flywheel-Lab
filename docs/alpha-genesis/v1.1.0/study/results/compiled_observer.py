"""Generated observer: supplied linear model only, not a hardware protocol."""
from fractions import Fraction
def estimate(y_sum, y_difference):
    a, b = Fraction(y_sum), Fraction(y_difference)
    return (a+b)/2, (a-b)/2
