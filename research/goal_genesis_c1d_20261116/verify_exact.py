#!/usr/bin/env python3
"""Exact integer proof for a signed-autoconvolution step function.

Independent of the discovery optimizer, NumPy and SciPy.
For equal steps on [-1/4,1/4], the convolution is piecewise linear;
therefore its absolute maximum occurs at a grid knot. We evaluate ALL knots
using signed Kronecker substitution with enough bits for carry-free products.
"""
from __future__ import annotations
import argparse
from fractions import Fraction
import hashlib
import json
import sys
from pathlib import Path

# SCiEL construction, 21 Oct 2026, listed at Tao's constants 1d page:
# https://teorth.github.io/optimizationproblems/constants/1d.html
INCUMBENT = Fraction(38534420343892614563110610373646557184000,
                     26432274393314964174848236787785831382961)

def validate(doc:dict):
    if doc.get('schema') != 'montreal-ai/c1d-signed-autoconvolution/v1':
        raise ValueError('unknown certificate schema')
    w=doc.get('weights_int')
    if not isinstance(w,list) or len(w)<2 or len(w)>20000:
        raise ValueError('invalid list of weights')
    if any(type(v) is not int for v in w):
        raise ValueError('non-integer or bool weight')
    if not any(w):
        raise ValueError('zero function')
    if sum(w)==0:
        raise ValueError('zero integral; normalization invalid')
    if doc.get('n')!=len(w):raise ValueError('declared length differs')
    if type(doc.get('normalization_scale')) is not int or doc['normalization_scale']<=0:
        raise ValueError('positive integer normalization_scale required')
    return w

def conv_kronecker(w):
    n=len(w);peak=max(abs(v) for v in w)
    B=(n*peak*peak).bit_length()+2
    mask=(1<<B)-1
    def pack(vals):
        out=0
        for i,val in enumerate(vals):
            out+=int(val)<<(B*i)
        return out
    p=pack(v if v>0 else 0 for v in w)
    q=pack(-v if v<0 else 0 for v in w)
    pp=p*p; qq=q*q; pq=p*q
    result=[]
    for k in range(2*n-1):
        shift=B*k
        result.append(((pp>>shift)&mask)+((qq>>shift)&mask)-2*((pq>>shift)&mask))
    return result, B

def conv_direct_at(w,k):
    n=len(w)
    return sum(w[i]*w[k-i] for i in range(max(0,k-n+1), min(k,n-1)+1))

def verify(doc):
    w=validate(doc);n=len(w)
    coeffs,bits=conv_kronecker(w)
    # Independent O(n) direct summation at deterministically selected knots.
    largest=max(range(len(coeffs)),key=lambda k:abs(coeffs[k]))
    witnesses=sorted({0,1,n//2,n-1,n,2*n-2,largest,max(0,largest-1),min(2*n-2,largest+1)})
    for k in witnesses:
        if coeffs[k]!=conv_direct_at(w,k):
            raise AssertionError(f'independent direct check failed at knot {k}')
    max_coeff=max(abs(c) for c in coeffs)
    score=Fraction(2*n*max_coeff,sum(w)**2)
    if doc.get('exact_num') is not None and doc['exact_num']!=score.numerator:
        raise ValueError('claimed numerator mismatch')
    if doc.get('exact_den') is not None and doc['exact_den']!=score.denominator:
        raise ValueError('claimed denominator mismatch')
    if doc.get('max_abs_coefficient') is not None and doc['max_abs_coefficient']!=max_coeff:
        raise ValueError('claimed maximum coefficient mismatch')
    if doc.get('max_knot') is not None and doc['max_knot']!=largest:
        raise ValueError('claimed maximizing knot mismatch')
    better=score < INCUMBENT
    if not better:
        raise ValueError('does not improve strongest listed October 2026 incumbent')
    return {'verdict':'PASS_IMPROVED_EXACT_UPPER_BOUND', 'n':n,
            'new_bound_num':str(score.numerator),'new_bound_den':str(score.denominator),
            'new_bound_decimal':format(float(score),'.15f'),
            'incumbent_decimal':format(float(INCUMBENT),'.15f'),
            'strict_improvement':better,'improvement_float':float(INCUMBENT-score),
            'max_knot':largest,'max_abs_coefficient':str(max_coeff),
            'carry_free_slot_bits':bits,'all_knot_coefficients':len(coeffs),
            'independent_direct_checked_knots':witnesses,
            'interpretation':'Upper bound for C_1d; exact on a 4800-cell signed step function, not proof of optimum or peer review'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('certificate',type=Path)
    a=parser.parse_args();raw=a.certificate.read_bytes()
    doc=json.loads(raw)
    v=verify(doc);v['certificate_sha256']=hashlib.sha256(raw).hexdigest()
    print(json.dumps(v,indent=2))
if __name__=='__main__':main()
