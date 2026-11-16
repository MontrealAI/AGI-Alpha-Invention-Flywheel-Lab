#!/usr/bin/env python3
"""Optional reproducible numerical search kernel; not trusted for mathematical proof.

The historical 4800-cell certificate resulted from exploratory multiresolution
continuation, seeded perturbations and restarts. This standalone kernel allows
fresh independent searches but is not represented as an exact history replay.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.signal import fftconvolve

HERE=Path(__file__).resolve().parent

def score(v):
    return 2*len(v)*np.max(np.abs(fftconvolve(v,v)))/v.sum()**2

def softmax_and_gradient(unconstrained, beta):
    n=len(unconstrained)
    x=unconstrained-unconstrained.mean()+1
    c=fftconvolve(x,x)
    scaled=2*c/n
    logits=np.r_[scaled,-scaled]*beta
    anchor=logits.max()
    p=np.exp(logits-anchor);z=p.sum();p/=z
    weights=p[:2*n-1]-p[2*n-1:]
    grad=(4/n)*fftconvolve(weights,x[::-1],mode='valid')
    grad-=grad.mean()
    return (anchor+np.log(z))/beta,grad

def search(target,passes,seed):
    entry=json.loads((HERE/'seed600.json').read_text())
    x=np.array(entry['weights_int'],dtype=np.float64)/entry['scale']
    while len(x)<target:x=np.repeat(x,2)
    if len(x)!=target:raise ValueError('target must be 600*2^k')
    x=x*target/x.sum()
    best=x.copy();best_score=score(x)
    rng=np.random.default_rng(seed)
    for step in range(passes):
        if step:
            scale=(.02,.1,.25,.5)[step%4]
            x=best+rng.normal(0,scale,size=target)
        for beta in (1000,4000,16000,64000,100000):
            r=minimize(softmax_and_gradient,x,jac=True,args=(beta,),method='L-BFGS-B',
                       options={'maxiter':2000,'ftol':1e-13,'gtol':1e-8})
            x=r.x-r.x.mean()+1
            new=score(x)
            if new<best_score:
                best_score=new;best=x.copy()
        print(json.dumps({'pass':step,'best_numerical_score':best_score}),flush=True)
    return best,best_score

def main():
    pa=argparse.ArgumentParser()
    pa.add_argument('--n',type=int,choices=(600,1200,2400,4800),default=1200)
    pa.add_argument('--passes',type=int,default=4)
    pa.add_argument('--seed',type=int,default=20261116)
    pa.add_argument('--output',type=Path,required=True)
    args=pa.parse_args()
    if args.output.exists():raise ValueError('refusing to overwrite existing output')
    w,s=search(args.n,args.passes,args.seed)
    args.output.write_text(json.dumps({'n':args.n,'score_floating_not_a_proof':s,
                                     'float_weights':w.tolist()},indent=2)+'\n')
if __name__=='__main__':main()
