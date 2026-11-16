#!/usr/bin/env python3
"""Second exact verifier: finite-field NTT + three-prime Chinese remainder theorem.

Does not share the Kronecker implementation, integer-convolution helper,
or SciPy/NumPy with verify_exact.py. Every convolution coefficient is
recovered from its residues under a provably sufficient CRT modulus.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path

MODS=(998244353,1004535809,469762049)
PRIMITIVE_ROOT=3
INCUMBENT=Fraction(38534420343892614563110610373646557184000,
                   26432274393314964174848236787785831382961)

def ntt(x, p, invert=False):
    n=len(x)
    j=0
    for i in range(1,n):
        bit=n>>1
        while j&bit:
            j^=bit
            bit>>=1
        j^=bit
        if i<j:x[i],x[j]=x[j],x[i]
    size=2
    while size<=n:
        root=pow(PRIMITIVE_ROOT,(p-1)//size,p)
        if invert:root=pow(root,p-2,p)
        half=size//2
        for lo in range(0,n,size):
            w=1
            for k in range(half):
                u=x[lo+k]
                v=(x[lo+k+half]*w)%p
                x[lo+k]=(u+v)%p
                x[lo+k+half]=(u-v)%p
                w=(w*root)%p
        size*=2
    if invert:
        invn=pow(n,p-2,p)
        for i in range(n):x[i]=(x[i]*invn)%p

def square_mod(weights,p,m):
    x=[0]*m
    for i,w in enumerate(weights):x[i]=w%p
    ntt(x,p)
    for k in range(m):x[k]=(x[k]*x[k])%p
    ntt(x,p,True)
    return x[:2*len(weights)-1]

def all_coeffs_ntt(weights):
    n=len(weights)
    length=1<<(2*n-2).bit_length()
    residues=[square_mod(weights,p,length) for p in MODS]
    p,q,r=MODS; pq=p*q;P=pq*r
    assert len(set(MODS))==3 and (p-1)%length==0 and (q-1)%length==0 and (r-1)%length==0
    safe_bound=n*max(abs(x) for x in weights)**2
    if 2*safe_bound>=P:
        raise ValueError('CRT modulus too small to guarantee signed reconstruction')
    invp=pow(p,-1,q)
    invpq=pow(pq,-1,r)
    result=[]
    for a,b,c in zip(*residues):
        t=((b-a)*invp)%q
        ab=a+p*t
        v=ab+pq*((c-ab)*invpq%r)
        if v>P//2:v-=P
        result.append(v)
    return result

def verify(doc):
    if doc.get('schema')!='montreal-ai/c1d-signed-autoconvolution/v1':
        raise ValueError('schema mismatch')
    w=doc['weights_int'];n=doc['n']
    if not isinstance(w,list) or len(w)!=n or not (2<=n<=20000):
        raise ValueError('invalid shape')
    if any(type(a) is not int for a in w) or sum(w)==0:raise ValueError('invalid coefficients')
    cs=all_coeffs_ntt(w)
    peak=max(abs(a) for a in cs)
    k=next(i for i,a in enumerate(cs) if abs(a)==peak)
    new=Fraction(2*n*peak,sum(w)**2)
    if (doc.get('exact_num'),doc.get('exact_den'))!=(new.numerator,new.denominator):
        raise ValueError('claimed rational mismatch')
    if (doc.get('max_abs_coefficient'),doc.get('max_knot'))!=(peak,k):
        raise ValueError('wrong max/certificate')
    if not new<INCUMBENT:raise ValueError('does not beat incumbent')
    return {'verdict':'PASS_INDEPENDENT_NTT_CRT','n':n,'knots':len(cs),
            'fraction':f'{new.numerator}/{new.denominator}',
            'score':format(float(new),'.15f'),
            'strictly_beats_strongest_listed_incumbent':True,
            'max_knot':k,
            'method':'Three independent modular NTT squares, exact signed CRT uniqueness from absolute coefficient bound'}

def main():
    pa=argparse.ArgumentParser();pa.add_argument('certificate',type=Path)
    args=pa.parse_args()
    doc=json.loads(args.certificate.read_text())
    print(json.dumps(verify(doc),indent=2))
if __name__=='__main__': main()
