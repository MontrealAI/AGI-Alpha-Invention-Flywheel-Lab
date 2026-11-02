import math
import numpy as np
from numpy.polynomial import Polynomial

F = Polynomial([1, 0, -6, 0, 15, 0, -20, 0, 15, 0, -6, 0, 1])

def material(E, nu):
    if not math.isfinite(E) or E <= 0 or not math.isfinite(nu) or not -1 < nu < .5:
        raise ValueError('finite E>0 and -1<nu<0.5 required')

def observation(directions, E=200000., nu=.3):
    material(E, nu)
    q = np.asarray(directions, dtype=float)
    if q.ndim != 2 or q.shape[1] != 3 or not len(q) or not np.isfinite(q).all() or not np.allclose(np.sum(q*q, axis=1), 1., rtol=0, atol=1e-12):
        raise ValueError('finite unit direction rows required')
    return np.column_stack(((1+nu)*q*q-nu, 2*(1+nu)*q[:,0]*q[:,1], 2*(1+nu)*q[:,0]*q[:,2], 2*(1+nu)*q[:,1]*q[:,2])) / E

def certificate(H, measured, target, uncertainty=0.):
    H = np.asarray(H, dtype=float); y = np.asarray(measured, dtype=float); ell = np.asarray(target, dtype=float)
    if H.ndim != 2 or H.shape[1] != 6 or not H.shape[0] or y.shape != (H.shape[0],) or ell.shape != (6,):
        raise ValueError('incompatible observation/target shapes')
    u = np.broadcast_to(np.asarray(uncertainty, dtype=float), y.shape)
    if not all(np.isfinite(v).all() for v in (H,y,ell,u)) or np.any(u < 0):
        raise ValueError('finite values and nonnegative uncertainty required')
    w = np.linalg.lstsq(H.T, ell, rcond=1e-12)[0]
    remainder = ell-H.T@w
    scale = max(1., float(np.linalg.norm(ell)))
    if np.linalg.norm(remainder) > 1e-9*scale:
        witness = remainder / np.linalg.norm(remainder)
        return {'status':'UNIDENTIFIED','scope':'declared local linear model only','null_direction':witness.tolist(),'observation_gap_per_mpa':float(np.max(np.abs(H@witness))),'target_gap_per_mpa':float(ell@witness),'estimate_mpa':None,'radius_mpa':None}
    estimate = float(w@y); radius = float(np.abs(w)@u)
    return {'status':'IDENTIFIED_MODEL_ONLY','scope':'common-support material/direction model, no physical admission','weights_mpa_per_strain':w.tolist(),'estimate_mpa':estimate,'radius_mpa':radius,'interval_mpa':[estimate-radius,estimate+radius],'target_residual':float(np.linalg.norm(remainder))}

def compact_stress(x, y, z, halfwidths=(1.,1.,1.), center_xx_mpa=100.):
    widths = np.asarray(halfwidths, dtype=float); p = np.array([x,y,z], dtype=float)
    if widths.shape != (3,) or not np.isfinite(widths).all() or np.any(widths <= 0) or not np.isfinite(p).all() or not math.isfinite(center_xx_mpa):
        raise ValueError('finite coordinates/amplitude and positive halfwidths required')
    t = p/widths
    if np.any(np.abs(t) >= 1):
        return np.zeros((3,3))
    polys = (F,F.deriv(2),F)
    values = [[poly.deriv(k)(coord)/width**k for k in range(3)] for poly,coord,width in zip(polys,t,widths)]
    A = center_xx_mpa/(360/widths[1]**2+144/widths[2]**2)
    h = np.empty((3,3))
    for i in range(3):
        for j in range(3):
            h[i,j] = A*math.prod(values[k][int(k==i)+int(k==j)] for k in range(3))
    return np.trace(h)*np.eye(3)-h

def elastic_strain(stress, E=200000., nu=.3):
    material(E, nu); s = np.asarray(stress, dtype=float)
    if s.shape != (3,3) or not np.isfinite(s).all() or not np.allclose(s,s.T,rtol=0,atol=1e-12):
        raise ValueError('finite symmetric stress tensor required')
    return ((1+nu)*s-nu*np.trace(s)*np.eye(3))/E

def centered_rmse(reference, prediction):
    a = np.asarray(reference, dtype=float); b = np.asarray(prediction, dtype=float)
    if a.ndim != 1 or not a.size or a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('finite matched one-dimensional series required')
    return float(np.sqrt(np.mean(((a-a.mean())-(b-b.mean()))**2)))
