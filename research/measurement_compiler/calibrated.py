"""One reference-derived mode repairs a testable incomplete response model."""
from dataclasses import dataclass
import hashlib
import numpy as np
from scipy import linalg
from .core import acquisition_order, geometry, signature


def calibration_hash(reference):
    a=np.asarray(reference,dtype='<f8',order='C')
    return hashlib.sha256(str(a.shape).encode()+a.tobytes()).hexdigest()


def response_basis(currents,measurements,reference,mode='physics_plus_one'):
    I,M,C,D=geometry(currents,measurements)
    V=np.asarray(reference,dtype=np.float64)
    if V.shape!=(M.shape[1],I.shape[1]) or not np.isfinite(V).all():
        raise ValueError('Invalid calibration matrix')
    _,_,right=linalg.svd(C,full_matrices=False)
    rank=np.linalg.matrix_rank(C)
    known=right[:rank]
    if mode=='current_only': return known
    if rank+1>min(V.shape): raise ValueError('No extra calibrated mode available')
    if mode=='reference_svd':
        return linalg.svd(V,full_matrices=False)[2][:rank+1]
    if mode!='physics_plus_one': raise ValueError('Unknown calibrated model')
    residual=V-(V@known.T)@known
    _,singular,right_residual=linalg.svd(residual,full_matrices=False)
    if singular[0]<=1e-12*np.linalg.norm(V):
        raise ValueError('Reference supplies no identifiable extra mode')
    extra=right_residual[0]-(right_residual[0]@known.T)@known
    extra/=np.linalg.norm(extra)
    return np.vstack([known,extra])


@dataclass
class CalibratedPlan:
    selected: tuple
    mode: str
    geometry_sha256: str
    calibration_sha256: str
    operator: np.ndarray
    n_measurements: int
    basis_rank: int

    def predict(self,currents,measurements,reference,acquired):
        I,M,_,_=geometry(currents,measurements)
        if signature(I,M)!=self.geometry_sha256:
            raise ValueError('Geometry changed')
        if calibration_hash(reference)!=self.calibration_sha256:
            raise ValueError('Calibration changed; recompile and requalify')
        v=np.asarray(acquired,dtype=np.float64)
        if v.shape!=(self.n_measurements,len(self.selected)) or not np.isfinite(v).all():
            raise ValueError('Incorrect or nonfinite acquired data')
        return v@self.operator


def compile_calibrated(currents,measurements,reference,count,mode='physics_plus_one',selected=None):
    I,M,_,_=geometry(currents,measurements)
    B=response_basis(I,M,reference,mode)
    if type(count) is not int or not B.shape[0]<=count<=B.shape[1]:
        raise ValueError('Insufficient acquisition count')
    ids=tuple(acquisition_order(B)[:count] if selected is None else selected)
    if len(ids)!=count or len(set(ids))!=count or any(type(j) is not int or not 0<=j<I.shape[1] for j in ids):
        raise ValueError('Invalid acquisition indices')
    if np.linalg.matrix_rank(B[:,ids])!=B.shape[0]:
        raise ValueError('Acquired patterns do not identify the retained basis')
    return CalibratedPlan(ids,mode,signature(I,M),calibration_hash(reference),
                          linalg.pinv(B[:,ids],rtol=1e-11)@B,M.shape[1],B.shape[0])
