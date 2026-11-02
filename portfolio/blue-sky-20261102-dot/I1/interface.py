"""Offline reciprocal optical-interface construction. No devices or financial side effects.
Engineering model only; fixed-wavelength selectable reflectors are an assumption.
"""
from dataclasses import dataclass
import numpy as np

@dataclass
class Calibration:
    operator: np.ndarray
    residual: float
    condition: float
    phase_scope: str = 'independent_row_signs'


def reflectors(n):
    if n < 2:
        raise ValueError('at least two modes required')
    r0 = .3 * np.eye(n)
    r1 = np.diag(np.linspace(.1, .7, n))
    r2 = .3*np.eye(n) + .08*(np.eye(n,k=1)+np.eye(n,k=-1))
    return r0, r1, r2


def relative(a,b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))


def calibrate(c0,c1,r0,r1):
    """Consumes proximal observations only; returns intensity-scope interface.
    Present implementation requires scalar R0 and diagonal distinct R1.
    """
    n = len(c0)
    c0,c1,r0,r1 = [np.asarray(x,dtype=complex) for x in (c0,c1,r0,r1)]
    if any(x.shape != (n,n) or not np.all(np.isfinite(x)) for x in (c0,c1,r0,r1)):
        raise ValueError("nonfinite or malformed calibration input")
    alpha = r0[0,0]
    if abs(alpha) < 1e-14 or not np.allclose(r0,alpha*np.eye(n)):
        raise ValueError('unsupported reference reflector')
    if not np.allclose(r1,np.diag(np.diag(r1))):
        raise ValueError('unsupported coding reflector')
    target = np.diag(r1)/alpha
    if np.max(abs(target.imag)) > 1e-12 or np.min(np.diff(target.real)) < 1e-8:
        raise ValueError('reflector spectrum must be real ordered and distinct')
    if not np.all(np.isfinite(c0)) or np.linalg.cond(c0)>1e12:
        raise ValueError('singular or unqualified calibration')
    values,vectors=np.linalg.eig(np.linalg.solve(c0,c1))
    order=np.argsort(values.real)
    values,vectors=values[order],vectors[:,order]
    if np.max(abs(values-target)) > .2*np.min(np.diff(target.real)):
        raise ValueError('coding spectrum inconsistent; recalibrate')
    w=np.linalg.inv(vectors)
    wi=np.linalg.inv(w)
    scale=np.sqrt(np.diag(wi.T@c0@wi)/alpha)
    t=scale[:,None]*w
    residual=max(relative(t.T@r0@t,c0),relative(t.T@r1@t,c1))
    if not np.isfinite(residual) or residual>.05:
        raise ValueError('calibration consistency failed')
    return Calibration(t,residual,float(np.linalg.cond(t)))


def extend_phase(k1,c2,r2):
    """Resolve relative row signs using known connected reflector graph.
    Global sign remains physically ambiguous and is explicit in scope.
    """
    t=np.asarray(k1.operator,dtype=complex)
    c2,r2=np.asarray(c2,dtype=complex),np.asarray(r2,dtype=complex)
    if t.ndim!=2 or t.shape[0]!=t.shape[1] or any(x.shape!=t.shape or not np.all(np.isfinite(x)) for x in (t,c2,r2)):
        raise ValueError("nonfinite or malformed phase input")
    inv=np.linalg.inv(t)
    transformed=inv.T@c2@inv
    n=len(t)
    signs=np.zeros(n)
    signs[0]=1
    todo=[0]
    while todo:
        i=todo.pop()
        for j in range(n):
            if i==j or abs(r2[i,j])<1e-10:
                continue
            ratio=transformed[i,j]/r2[i,j]
            inferred=signs[i]*(1 if ratio.real>=0 else -1)
            if signs[j]==0:
                signs[j]=inferred
                todo.append(j)
    if np.any(signs==0):
        raise ValueError('disconnected reflector: relative phase unidentifiable')
    corrected=signs[:,None]*t
    residual=relative(corrected.T@r2@corrected,c2)
    if not np.isfinite(residual) or residual>.05:
        raise ValueError('phase extension inconsistent; recalibrate')
    return Calibration(corrected,max(residual,k1.residual),float(np.linalg.cond(corrected)),'one_global_sign')


def focus(k1,index):
    row=k1.operator[index]
    return row.conj()/np.linalg.norm(row)


def reconstruct(k2,proximal_field):
    if k2.phase_scope!='one_global_sign':
        raise ValueError('K1 intensity-only scope cannot authorize coherent image')
    field=np.asarray(proximal_field,dtype=complex)
    if field.shape!=(len(k2.operator),) or not np.all(np.isfinite(field)) or not np.all(np.isfinite(k2.operator)):
        raise ValueError('nonfinite or malformed reconstruction input')
    return np.linalg.solve(k2.operator.T,field)
