"""Exact checks of fixed finite binary64 sparse-ray inputs using integer sums.

This newly written narrow primal checker replaces no lost generic dual helper.
It proves only the declared closed binary64 model, not physical validity.
"""
import math
import numpy as np

BITS=2148
SCALE=1<<BITS
def dyadic(value):
    value=float(value)
    if not math.isfinite(value):raise ValueError('nonfinite input')
    numerator,denominator=value.as_integer_ratio()
    return numerator,denominator.bit_length()-1
def scaled(value):
    n,e=dyadic(value)
    return n<<(BITS-e)
def lower_float(n,d):
    if d<=0:raise ValueError('positive denominator required')
    result=n/d
    if not math.isfinite(result):raise OverflowError('unrepresentable ratio')
    while True:
        a,b=result.as_integer_ratio()
        if a*d<=n*b:break
        result=float(np.nextafter(result,-np.inf))
    return result
def exact_rows(A,x):
    A=A.tocsr()
    x=np.asarray(x,dtype=float)
    if x.shape!=(A.shape[1],) or not np.all(np.isfinite(x)):raise ValueError('x shape or finite guard')
    if not np.all(np.isfinite(A.data)):raise ValueError('nonfinite matrix')
    xp=[dyadic(v) for v in x]
    result=[]
    for row in range(A.shape[0]):
        acc=0
        for k in range(A.indptr[row],A.indptr[row+1]):
            an,ae=dyadic(A.data[k]);xn,xe=xp[A.indices[k]]
            acc+=(an*xn)<<(BITS-ae-xe)
        result.append(acc)
    return result
def exact_dot(c,x):
    if len(c)!=len(x):raise ValueError('dot shape')
    total=0
    for a,b in zip(c,x):
        an,ae=dyadic(a);bn,be=dyadic(b)
        total+=(an*bn)<<(BITS-ae-be)
    return total
def check(A,y,eps,x,c):
    y=np.asarray(y);eps=np.asarray(eps);x=np.asarray(x)
    if y.shape!=(A.shape[0],) or eps.shape!=y.shape or x.shape!=(A.shape[1],) or np.asarray(c).shape!=x.shape:raise ValueError('shape mismatch')
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(eps)) or np.any(eps<0):raise ValueError('invalid rays/envelope')
    values=exact_rows(A,x)
    margins=[scaled(e)-(abs(value-scaled(v))) for value,v,e in zip(values,y,eps)]
    low=min(margins)
    roi=exact_dot(c,x)
    return {'feasible':bool(np.min(x)>=0 and low>=0),'nonnegative':bool(np.min(x)>=0),'exact_min_ray_margin_numerator':str(low),'denominator_power':BITS,'min_ray_margin_float_lower':lower_float(low,SCALE),'roi_numerator':str(roi),'roi_float_lower':lower_float(roi,SCALE),'inequalities_checked':2*A.shape[0]},values
