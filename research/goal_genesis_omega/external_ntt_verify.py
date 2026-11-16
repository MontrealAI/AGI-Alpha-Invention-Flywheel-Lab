"""GOAL GENESIS Ω: independent exact reproduction of the Nov 15, 2026 C₁d record.

The externally claimed 51,200-cell signed autoconvolution certificate came from
the Iterate AI Research hackathon. This auditor is written independently of its
two supplied checkers: it performs 5-prime number-theoretic transforms and
Chinese remainder reconstruction, then checks the winning coefficient again
using plain Python integer products. NO floating-point convolution, NumPy,
third-party FFT, or claim-specific shortcut.

Scope: independently replay and potentially falsify an EXISTING mathematical
certificate, not invent a stronger bound. All input rights remain upstream.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen

REPO="https://github.com/ArthurAnache/Hackathon-AI-Reasearch"
REV="c0f8d1837e65d9194350edb7c029897cf031908d"
FILENAME="records/1d/autonomous/c006_31bbf628_int56.json"
SOURCE_URL=("https://raw.githubusercontent.com/ArthurAnache/Hackathon-AI-Reasearch/"
            +REV+"/"+FILENAME)
SOURCE_SHA256="dbca822baa7c8a20d05451b56de2dd77c032e88fa945d4e243d0a785787202d3"
CLAIM_NUM=21267647941510998263770007610303168512
CLAIM_DEN=14626277862557668614837367632277156521
EXPECTED_SUM=19122158522613018945
EXPECTED_MAX=1<<56
EXPECTED_KNOT=12511
EXPECTED_CELLS=51200
# Distinct primitive-friendly primes; 131072 divides each p-1.
# The product exceeds twice the worst-case signed coefficient magnitude.
PRIMES=((998244353,3),(469762049,3),(167772161,3),
        (1224736769,3),(1004535809,3))


def read_pinned(source=None):
    if source is None:
        with urlopen(SOURCE_URL, timeout=30) as stream:
            raw=stream.read(4_000_001)
        if len(raw)>4_000_000:
            raise ValueError("SOURCE_TOO_LARGE")
    else:
        raw=Path(source).read_bytes()
    if sha256(raw).hexdigest()!=SOURCE_SHA256:
        raise ValueError("SOURCE_HASH_MISMATCH")
    obj=json.loads(raw)
    if not isinstance(obj,dict) or not isinstance(obj.get("values"),list):
        raise ValueError("INVALID_EXTERNAL_CERTIFICATE_SHAPE")
    values=obj["values"]
    if len(values)!=EXPECTED_CELLS or any(type(v) is not int for v in values):
        raise ValueError("INVALID_INTEGER_SEQUENCE")
    if sum(values)!=EXPECTED_SUM or max(map(abs,values))!=EXPECTED_MAX:
        raise ValueError("EXTERNAL_SUM_OR_SCALE_CHANGED")
    return values


def ntt(data,prime,root,inverse=False):
    """Iterative radix-2 NTT. Does not use a third-party FFT library."""
    n=len(data)
    if n==0 or n&(n-1) or (prime-1)%n:
        raise ValueError("UNSUPPORTED_TRANSFORM_LENGTH")
    omega=pow(root,(prime-1)//n,prime)
    if pow(omega,n,prime)!=1 or pow(omega,n//2,prime)!=prime-1:
        raise ValueError("INVALID_PRIMITIVE_NTH_ROOT")
    j=0
    for i in range(1,n):
        bit=n//2
        while j&bit:
            j^=bit
            bit>>=1
        j^=bit
        if i<j:
            data[i],data[j]=data[j],data[i]
    step=2
    while step<=n:
        z=pow(root,(prime-1)//step,prime)
        if inverse:
            z=pow(z,prime-2,prime)
        half=step//2
        for i in range(0,n,step):
            w=1
            end=i+half
            for k in range(i,end):
                u=data[k]
                v=data[k+half]*w%prime
                a=u+v
                if a>=prime:
                    a-=prime
                b=u-v
                if b<0:
                    b+=prime
                data[k]=a
                data[k+half]=b
                w=w*z%prime
        step*=2
    if inverse:
        inv=pow(n,prime-2,prime)
        for k in range(n):
            data[k]=data[k]*inv%prime


def signed_convolution(values,primes=PRIMES):
    """Exact square via NTT and centered CRT, with proved reconstruction bound."""
    n=len(values)
    if not n or any(type(v) is not int for v in values):
        raise ValueError("NONINTEGER_OR_EMPTY_SEQUENCE")
    length=1
    while length<2*n-1:
        length*=2
    bound=n*max(map(abs,values))**2
    modulus=1
    result=[0]*(2*n-1)
    prime_ids=[]
    for prime,root in primes:
        if prime in prime_ids:
            raise ValueError("DUPLICATE_MODULUS")
        prime_ids.append(prime)
        arr=[v%prime for v in values]+[0]*(length-n)
        ntt(arr,prime,root,False)
        for j in range(length):
            arr[j]=arr[j]*arr[j]%prime
        ntt(arr,prime,root,True)
        inv=pow(modulus,-1,prime)
        for i in range(2*n-1):
            t=((arr[i]-result[i])%prime)*inv%prime
            result[i]+=modulus*t
        modulus*=prime
    if modulus<=2*bound:
        raise ValueError("CRT_MODULUS_INSUFFICIENT_FOR_EXACT_RECOVERY")
    half=modulus//2
    return [v if v<=half else v-modulus for v in result],{
        "primes":prime_ids,
        "transform_length":length,
        "crt_product":str(modulus),
        "two_sided_coefficient_bound":str(bound),
        "crt_uniqueness_proved":modulus>2*bound
    }


def verify(values):
    if len(values)!=EXPECTED_CELLS or any(type(v) is not int for v in values):
        raise ValueError("WRONG_CERTIFICATE")
    if sum(values)!=EXPECTED_SUM or max(map(abs,values))!=EXPECTED_MAX:
        raise ValueError("WRONG_CERTIFICATE_METADATA")
    coefficients,proof=signed_convolution(values)
    absmax=max(map(abs,coefficients))
    argmax=next(i for i,v in enumerate(coefficients) if abs(v)==absmax)
    if argmax!=EXPECTED_KNOT:
        raise ValueError("CERTIFICATE_MAXIMUM_KNOT_MISMATCH")
    directly=sum(values[i]*values[argmax-i] for i in range(max(0,argmax-len(values)+1),
                                                           min(len(values)-1,argmax)+1))
    if directly!=coefficients[argmax] or abs(directly)!=absmax:
        raise ValueError("INDEPENDENT_DIRECT_KNOT_DISAGREES")
    value=Fraction(2*len(values)*absmax,sum(values)**2)
    if value!=Fraction(CLAIM_NUM,CLAIM_DEN):
        raise ValueError("CLAIMED_EXACT_FRACTION_FALSE")
    return {
        "schema":"montreal-ai/goal-genesis-omega/independent-external-replay/v1",
        "status":"INDEPENDENT_REPLAY_OF_EXTERNAL_BOUND",
        "prior_art":"https://github.com/teorth/optimizationproblems/pull/372",
        "attribution":"Iterate AI Research hackathon team: Murilo Monteiro, Arthur Anache, Marie-Fleur Delort, Thibault Verny",
        "prior_art_status":"Open, unmerged research claim. Independent external peer review still separate.",
        "source_sha256":SOURCE_SHA256,"source_url":SOURCE_URL,
        "exact_numerator":str(value.numerator),"exact_denominator":str(value.denominator),
        "decimal":format(float(value),".16f"),
        "cells":len(values),"critical_knot_zero_based":argmax,
        "max_integer_autoconvolution":str(absmax),"direct_knot_recomputed":True,
        "proof":proof,
        "boundary":"A separate finite exact reconstruction of the authors' existing bound; no new bound, autonomous goal discovery, or economic use established."
    }


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,default=None)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    if args.output.exists():
        raise ValueError("OUTPUT_EXISTS")
    values=read_pinned(args.source)
    result=verify(values)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("INDEPENDENT_EXTERNAL_REPLAY",result["status"],"exact",result["exact_numerator"]+"/"+result["exact_denominator"],flush=True)


if __name__=="__main__":
    main()
