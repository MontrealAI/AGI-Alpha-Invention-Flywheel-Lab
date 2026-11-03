from __future__ import annotations
import re
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
FORMULAS = {
    "SiO2": (0.6961663,0.0684043,0.4079426,0.1162414,0.8974794,9.896161),
    "MgF2": (0.48755108,0.04338408,0.39875031,0.09461442,2.3120353,23.793604),
}
_TA = np.array([[float(x) for x in line.split()] for line in (ROOT / "tantalum_pentoxide.yml").read_text().splitlines() if re.match(r"^\s+[0-9].*E[+-]",line)])

def index(material,wavelength_um,index_scale=1.0,loss_scale=1.0):
    w = np.asarray(wavelength_um,dtype=float)
    if not np.all(np.isfinite(w)) or np.any(w < .7) or np.any(w > 1.5):
        raise ValueError("qualified wavelength envelope is [0.7,1.5] micrometres")
    if material == "air":
        return np.ones_like(w,dtype=complex)
    if material in FORMULAS:
        a = FORMULAS[material]
        n2 = np.ones_like(w)
        for b,c in zip(a[::2],a[1::2]):
            n2 += b*w*w/(w*w-c*c)
        return np.sqrt(n2)*index_scale+0j
    if material == "Ta2O5":
        return np.interp(w,_TA[:,0],_TA[:,1])*index_scale+1j*np.interp(w,_TA[:,0],_TA[:,2])*loss_scale
    raise ValueError("unsupported material")

def _inputs(thickness_um,materials,wavelengths_um,theta_deg,polarization,index_scale,loss_scale):
    d = np.asarray(thickness_um,dtype=float)
    w = np.atleast_1d(np.asarray(wavelengths_um,dtype=float))
    if w.ndim != 1 or not len(w):
        raise ValueError("wavelength input must be a nonempty one-dimensional array")
    if d.ndim != 1 or len(d) != len(materials) or np.any(~np.isfinite(d)) or np.any(d < 0) or np.sum(d)>6:
        raise ValueError("invalid layer thickness or declared six-micrometre total envelope")
    if not np.isfinite(theta_deg) or not 0<=theta_deg<=45 or polarization not in ("s","p"):
        raise ValueError("invalid incidence/polarization or outside qualified envelope")
    if not np.isfinite(index_scale) or index_scale <= 0 or not np.isfinite(loss_scale) or loss_scale<0:
        raise ValueError("invalid material perturbation")
    n = [index(m,w,index_scale if m != "air" else 1,loss_scale) for m in ["air",*materials,"SiO2"]]
    u = np.sin(np.deg2rad(theta_deg))
    c = [np.sqrt(1-(u/x)**2+0j) for x in n]
    q = [x*y if polarization=="s" else x/y for x,y in zip(n,c)]
    return d,w,n,c,q

def response(thickness_um,materials,wavelengths_um,theta_deg=0,polarization="s",index_scale=1.0,loss_scale=1.0):
    d,w,n,c,q = _inputs(thickness_um,materials,wavelengths_um,theta_deg,polarization,index_scale,loss_scale)
    a = np.ones_like(w,dtype=complex); b = np.zeros_like(a); cc = b.copy(); e = a.copy()
    for j,t in enumerate(d,1):
        delta = 2*np.pi*n[j]*c[j]*t/w
        f = np.cos(delta); g = -1j*np.sin(delta)
        a,b,cc,e = a*f+b*g*q[j],a*g/q[j]+b*f,cc*f+e*g*q[j],cc*g/q[j]+e*f
    z = q[0]*a+q[0]*q[-1]*b+cc+q[-1]*e
    r = (q[0]*a+q[0]*q[-1]*b-cc-q[-1]*e)/z
    t = 2*q[0]/z
    R = np.abs(r)**2
    T = np.real(q[-1])/np.real(q[0])*np.abs(t)**2
    return {"R":R,"T":T,"A":1-R-T}

def recursive_scattering(thickness_um,materials,wavelengths_um,theta_deg=0,polarization="s",index_scale=1.0,loss_scale=1.0):
    d,w,n,c,q = _inputs(thickness_um,materials,wavelengths_um,theta_deg,polarization,index_scale,loss_scale)
    r = (q[-2]-q[-1])/(q[-2]+q[-1]); t = 2*q[-2]/(q[-2]+q[-1])
    for j in range(len(d)-1,-1,-1):
        delta = 2*np.pi*n[j+1]*c[j+1]*d[j]/w
        z = np.exp(1j*delta)
        rr = (q[j]-q[j+1])/(q[j]+q[j+1]); tt = 2*q[j]/(q[j]+q[j+1])
        denominator = 1+rr*r*z*z
        t = tt*t*z/denominator
        r = (rr+r*z*z)/denominator
    R = np.abs(r)**2
    T = np.real(q[-1])/np.real(q[0])*np.abs(t)**2
    return {"R":R,"T":T,"A":1-R-T}

def independent_layer_system(thickness_um,materials,wavelength_um,theta_deg=0,polarization="s"):
    d,w,n,c,q = _inputs(thickness_um,materials,[wavelength_um],theta_deg,polarization,1,1)
    n = [x[0] for x in n]; c = [x[0] for x in c]; q = [x[0] for x in q]
    count = len(d)
    matrix = np.zeros((2*(count+1),2*(count+1)),dtype=complex)
    rhs = np.zeros(2*(count+1),dtype=complex)
    for interface in range(count+1):
        row = 2*interface
        if interface == 0:
            matrix[row,0] = 1; matrix[row+1,0] = -q[0]
            rhs[row] = -1; rhs[row+1] = -q[0]
        else:
            z = np.exp(2j*np.pi*n[interface]*c[interface]*d[interface-1]/wavelength_um)
            col = 1+2*(interface-1)
            matrix[row,col] = z; matrix[row,col+1] = 1/z
            matrix[row+1,col] = q[interface]*z; matrix[row+1,col+1] = -q[interface]/z
        if interface == count:
            matrix[row,-1] = -1; matrix[row+1,-1] = -q[-1]
        else:
            col = 1+2*interface
            matrix[row,col] = -1; matrix[row,col+1] = -1
            matrix[row+1,col] = -q[interface+1]; matrix[row+1,col+1] = q[interface+1]
    x = np.linalg.solve(matrix,rhs)
    R = float(abs(x[0])**2); T = float(np.real(q[-1])/np.real(q[0])*abs(x[-1])**2)
    return {"R":R,"T":T,"A":1-R-T,"boundary_residual":float(np.max(np.abs(matrix@x-rhs)))}
