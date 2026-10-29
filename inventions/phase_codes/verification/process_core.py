"""Independent small logical-process tomography. No builder imports or physical simulation.

The caller supplies channel(psi)->unnormalized4x4 logical density. Ideal target is fixed.
"""
import itertools
import numpy as np

TOL=2e-8
U=np.diag([1,1,1,1j]).astype(np.complex128)


def analyze(channel):
    basis=np.eye(4,dtype=np.complex128)
    errors=[];allrho=[]
    def run(v,label):
        r=np.asarray(channel(v.copy()),dtype=np.complex128)
        if r.shape!=(4,4) or not np.isfinite(r).all():
            raise ValueError(f'{label}: invalid logical density shape or entries')
        herm=float(np.max(np.abs(r-r.conj().T)))
        tr=complex(np.trace(r));mineig=float(np.linalg.eigvalsh((r+r.conj().T)/2).min())
        allrho.append(dict(label=label,trace_real=float(tr.real),trace_imag=float(tr.imag),Hermiticity_error=herm,minimum_eigenvalue=mineig))
        if abs(tr-1)>TOL or herm>TOL or mineig < -TOL:errors.append(label)
        return r
    diagonal=[run(basis[a],f'basis{a}') for a in range(4)]
    blocks={}
    for a in range(4):blocks[a,a]=diagonal[a]
    for a,b in itertools.combinations(range(4),2):
        plus=run((basis[a]+basis[b])/np.sqrt(2),f'plus{a}{b}')
        ip=run((basis[a]+1j*basis[b])/np.sqrt(2),f'iplus{a}{b}')
        real=2*plus-diagonal[a]-diagonal[b]
        imag=2*ip-diagonal[a]-diagonal[b]
        blocks[a,b]=(real+1j*imag)/2
        blocks[b,a]=blocks[a,b].conj().T
    J=np.block([[blocks[a,b] for b in range(4)] for a in range(4)])/4
    target=np.zeros(16,dtype=np.complex128)
    for a in range(4):target[4*a+a]=U[a,a]/2
    ideal=np.outer(target,target.conj())
    fid=float(np.vdot(target,J@target).real)
    partial=np.array([[np.trace(J[4*a:4*a+4,4*b:4*b+4]) for b in range(4)] for a in range(4)])
    extra=[]
    vectors={
        'logical_product_plus':np.ones(4,dtype=np.complex128)/2,
        'logical_Bell':np.array([1,0,0,1],dtype=np.complex128)/np.sqrt(2),
        'logical_generic_complex':np.array([1,2j,-1+1j,3-2j],dtype=np.complex128)/np.sqrt(20),
    }
    for label,v in vectors.items():
        r=run(v,label);want=U@v;err=float(np.max(np.abs(r-np.outer(want,want.conj()))))
        reconstructed=sum(v[a]*v[b].conjugate()*blocks[a,b] for a in range(4) for b in range(4))
        extra.append(dict(label=label,ideal_matrix_error=err,tomographic_linearity_error=float(np.max(np.abs(r-reconstructed)))))
    maxerr=float(np.max(np.abs(J-ideal)))
    tperr=float(np.max(np.abs(partial-np.eye(4)/4)))
    mineig=float(np.linalg.eigvalsh((J+J.conj().T)/2).min())
    good=(not errors and maxerr<=TOL and abs(1-fid)<=TOL and tperr<=TOL and mineig>=-TOL
          and all(r['ideal_matrix_error']<=TOL and r['tomographic_linearity_error']<=TOL for r in extra))
    return dict(passed=bool(good),tolerance=TOL,normalized_Choi_matrix_error=maxerr,
        entanglement_fidelity=fid,trace_preservation_error=tperr,Choi_minimum_eigenvalue=mineig,
        invalid_density_labels=errors,probe_diagnostics=allrho,extra_probes=extra,
        limitation='Finite numerical implementation check; not physical execution or general empirical noise validation')
