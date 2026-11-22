"""Secondary image check using the pinned KTC authors' illustrative inverse.

No reconstruction hyperparameters or acquisition count are tuned here. The main
48-pattern result remains REJECT against its registered <=40-pattern objective.
"""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import numpy as np
from scipy import linalg, sparse, signal
from scipy.io import loadmat
from scipy.spatial import Delaunay
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research.measurement_compiler.run import archive,payload,reference,signal as delta_signal
from research.measurement_compiler.calibrated import compile_calibrated


def score(truth,reco):
    """Published KTC SSIM formula, using equivalent FFT convolution."""
    r=80; w=np.arange(-160,161);X,Y=np.meshgrid(w,w)
    ker=(1/np.sqrt(2*np.pi))*np.exp(-.5*(X*X+Y*Y)/(r*r))
    conv=lambda a:signal.fftconvolve(a,ker,mode='same')
    norm=conv(np.ones(truth.shape)); total=0
    for label in [1,2]:
        t=(np.abs(truth-label)<.1).astype(float); v=(np.abs(reco-label)<.1).astype(float)
        mt=conv(t)/norm;mv=conv(v)/norm
        vt=conv(t*t)/norm-mt*mt;vv=conv(v*v)/norm-mv*mv
        cov=conv(t*v)/norm-mt*mv
        total+=np.mean(((2*mt*mv+1e-4)*(2*cov+9e-4))/((mt*mt+mv*mv+1e-4)*(vt+vv+9e-4)))
    return float(total/2)


def interpolate(mesh):
    pix=.23/256
    coords=np.linspace(-.115+pix/2,.115-pix/2+pix,256)
    X,Y=np.meshgrid(coords,coords);pts=np.column_stack([X.ravel(),Y.ravel()])
    tri=Delaunay(mesh.g);which=tri.find_simplex(pts);inside=which>=0
    selected=which[inside]
    bary=np.einsum('nij,nj->ni',tri.transform[selected,:2,:],pts[inside]-tri.transform[selected,2,:])
    bary=np.column_stack([bary,1-bary.sum(axis=1)])
    row=np.repeat(np.flatnonzero(inside),3);col=tri.simplices[selected].ravel()
    matrix=sparse.csr_matrix((bary.ravel(),(row,col)),shape=(len(pts),len(mesh.g)))
    return matrix,pts


def segment(field,scoring):
    level,x=scoring.Otsu2(field.flatten(),256,7)
    masks=[field<x[level[0]],(field>=x[level[0]])&(field<=x[level[1]]),field>x[level[1]]]
    background=int(np.argmax([np.count_nonzero(v) for v in masks]))
    result=np.zeros_like(field)
    if background==0: result[masks[1]|masks[2]]=2
    elif background==1: result[masks[0]]=1;result[masks[2]]=2
    else: result[masks[0]|masks[1]]=1
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True)
    p.add_argument('--confirmation',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    a.data=a.data.resolve();a.output=a.output.resolve()
    frozen=json.loads(a.confirmation.read_text());count=frozen['count']
    if count!=48:raise ValueError('This secondary check is frozen to the original 48-pattern result')
    start=time.perf_counter();cpu=time.process_time()
    code=archive(a.data/'Codes_Python.zip');z=archive(a.data/'EvaluationData_full.zip')
    with tempfile.TemporaryDirectory(prefix='ktc-pinned-') as folder:
        local=Path(folder)
        for name in code.namelist():
            rel=Path(name).relative_to('Codes_Python')
            if '..' in rel.parts:raise ValueError('Unsafe source member')
            if name.endswith('.py') or rel.as_posix()=='Mesh_sparse.mat' or rel.as_posix()=='TrainingData/ref.mat':
                destination=local/rel;destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(code.read(name))
        sys.path.insert(0,str(local));os.chdir(local)
        import KTCScoring,KTCAux
        # Use the authors' setup unchanged, ending before the per-target loop.
        tree=ast.parse((local/'main.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        prefix=[]
        for node in fn.body:
            if isinstance(node,ast.For) and isinstance(node.target,ast.Name) and node.target.id=='objectno':break
            prefix.append(node)
        prefix.append(ast.Return(ast.Tuple([ast.Name(v,ast.Load()) for v in ['Mesh','solver','sigma0','z','smprior','vincl']],ast.Load())))
        fn.body=prefix
        ast.fix_missing_locations(tree);ns={};exec(compile(tree,'pinned_ktc_setup','exec'),ns)
        Mesh,solver,sigma0,contact,prior,vincl=ns['main'](str(local/'TrainingData'),str(a.output),1)
        begin=time.perf_counter()
        solver.SolveForward(sigma0,contact)
        J=solver.Jacobian(sigma0,contact)
        G=solver.InvGamma_n
        precision=np.asarray(G.diagonal() if sparse.issparse(G) else np.diag(G)).ravel()
        lhs=J.T@(precision[:,None]*J)+prior.L.T@prior.L
        cholesky=linalg.cho_factor(lhs,check_finite=True)
        interpolation,points=interpolate(Mesh)
        # Verify the fast interpolation against the source routine on fixed points.
        sample=np.linspace(0,len(points)-1,41,dtype=int)
        fixture=np.sin(Mesh.g[:,0]*30)+Mesh.g[:,1]
        official=KTCAux.Interpolate2Newmesh2DNode(Mesh.g,Mesh.H,Mesh.Node,fixture,points[sample],[])[0]
        interpolation_error=float(np.max(np.abs(interpolation[sample]@fixture-official)))
        if interpolation_error>1e-10:raise RuntimeError('Interpolation mismatch')
        # Same source scoring formula on a small deterministic fixture.
        test=np.arange(16*16).reshape(16,16)%3;other=np.roll(test,2,axis=0)
        official_score=.5*(KTCScoring.ssim((test==1).astype(float),(other==1).astype(float))+
                             KTCScoring.ssim((test==2).astype(float),(other==2).astype(float)))
        scoring_error=abs(score(test,other)-official_score)
        if scoring_error>1e-10:raise RuntimeError('FFT score mismatch')
        setup_seconds=time.perf_counter()-begin
        I,M,U0=reference(payload(code,'Codes_Python/TrainingData/ref.mat'))
        plan=compile_calibrated(I,M,U0,count)
        rows=[];images={}
        for index,row in enumerate(frozen['rows']):
            name=row['target'];delta=delta_signal(payload(z,name),I,M,U0)
            recovered=plan.predict(I,M,U0,delta[:,plan.selected])
            inputs=np.column_stack([delta.T.ravel(),recovered.T.ravel()])
            coefficients=linalg.cho_solve(cholesky,J.T@(precision[:,None]*inputs))
            pixels=interpolation@coefficients
            level=Path(name).parent.name.replace('level','');number=Path(name).stem.replace('data','')
            truth_file=f'EvaluationData_full/GroundTruths/level_{level}/{number}_true.mat'
            td=payload(z,truth_file);truth=next(v for k,v in td.items() if not k.startswith('_') and v.shape==(256,256))
            fields=[np.flipud(pixels[:,k].reshape(256,256)) for k in [0,1]]
            masks=[segment(field,KTCScoring) for field in fields]
            scores=[score(truth,mask) for mask in masks]
            rows.append({'target':name,'full_score':scores[0],'recovered_score':scores[1],
                         'score_change':scores[1]-scores[0],
                         'changed_pixel_fraction':float(np.mean(masks[0]!=masks[1]))})
            images[f'{level}_{number}_truth']=truth
            images[f'{level}_{number}_full']=masks[0]
            images[f'{level}_{number}_recovered']=masks[1]
            if (index+1)%3==0:print(json.dumps({'completed_images':index+1}),flush=True)
        result={'scope':'secondary check with the authors illustrative inverse; no SOTA comparison or industrial qualification',
                'count':count,'targets':len(rows),'rows':rows,
                'mean_full_score':float(np.mean([r['full_score'] for r in rows])),
                'mean_recovered_score':float(np.mean([r['recovered_score'] for r in rows])),
                'worst_score_change':min(r['score_change'] for r in rows),
                'largest_changed_pixel_fraction':max(r['changed_pixel_fraction'] for r in rows),
                'interpolation_crosscheck_error':interpolation_error,'scoring_crosscheck_error':scoring_error,
                'inverse_setup_seconds':setup_seconds,'wall_seconds':time.perf_counter()-start,
                'cpu_seconds':time.process_time()-cpu,'primary_verdict_unchanged':frozen['verdict'],
                'source_archive_sha256':hashlib.sha256((a.data/'Codes_Python.zip').read_bytes()).hexdigest(),
                'secondary_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (a.output/'images.json').write_text(json.dumps(result,indent=2)+'\n')
        np.savez_compressed(a.output/'images.npz',**images)
        print(json.dumps({k:result[k] for k in ['targets','mean_full_score','mean_recovered_score','worst_score_change','largest_changed_pixel_fraction','wall_seconds']}))

if __name__=='__main__':main()
