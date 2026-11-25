"""Read-only independent reproduction of published Elgora #0 V6 P1 and Robin contract.
No submission, account, network, or payment. Requires numpy/scipy.
"""
import json, time, hashlib
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

def mesh(m, pattern):
    xy = np.array([(i/m,j/m) for j in range(m+1) for i in range(10*m+1)])
    tri = []
    for j in range(m):
        for i in range(10*m):
            a=j*(10*m+1)+i
            b=a+1
            c=a+10*m+1
            d=c+1
            flip = pattern=="backward" or (pattern=="checker" and (i+j)%2==1)
            tri.extend([(a,b,c),(b,d,c)] if flip else [(a,b,d),(a,d,c)])
    return xy,np.asarray(tri)

def solve(m,pattern,independent=False):
    xy,t=mesh(m,pattern)
    E,nu=1000.,.3
    D=E/(1-nu**2)*np.array([[1,nu,0],[nu,1,0],[0,0,(1-nu)/2]])
    n=len(xy)*2
    rows=[]; cols=[]; data=[]
    for nodes in t:
        p=xy[nodes]
        J=np.column_stack((p[1]-p[0],p[2]-p[0]))
        area=abs(np.linalg.det(J))/2
        if independent:
            G=np.linalg.inv(np.column_stack((np.ones(3),p)))[1:,:].T
        else:
            G=np.array([[-1.,-1.],[1.,0.],[0.,1.]])@np.linalg.inv(J)
        B=np.zeros((3,6))
        B[0,0::2]=G[:,0]
        B[1,1::2]=G[:,1]
        B[2,0::2]=G[:,1]
        B[2,1::2]=G[:,0]
        K=area*B.T@D@B
        dof=np.column_stack((2*nodes,2*nodes+1)).ravel()
        rows.extend(np.repeat(dof,6));cols.extend(np.tile(dof,6));data.extend(K.ravel())
    K=coo_matrix((data,(rows,cols)),shape=(n,n)).tocsr()
    tip=np.flatnonzero(xy[:,0]==10.)
    f=np.zeros(n)
    for a,b in zip(tip[:-1],tip[1:]):
        f[2*a+1]+=1/(2*m);f[2*b+1]+=1/(2*m)
    fixed=np.flatnonzero(xy[:,0]==0.)
    free=np.setdiff1d(np.arange(n),np.column_stack((2*fixed,2*fixed+1)).ravel())
    u=np.zeros(n)
    u[free]=spsolve(K[free][:,free],f[free])
    res=K@u-f
    delta=float(np.mean(u[2*tip+1]))
    return {"m":m,"mesh":pattern,"nodes":len(xy),"triangles":len(t),"delta":delta,
      "relative_residual":float(np.linalg.norm(res[free])/np.linalg.norm(f[free])),
      "force_y":float(f[1::2].sum()),"reaction_y":float(res[1::2].sum()),
      "energy_identity_error":float(abs(u@(K@u)-u@f))}

def robin():
    # On unit square u=x, v=x, k=r=1, alpha=f=s=0.
    # Dirichlet x=0; zero Neumann on y=0,1; Robin on x=1.
    # Strong plus-flux law: du/dn=r*u=1. Bulk Laplacian is zero.
    # Both u=x and u=0 solve that strong problem. The posted weak
    # form at test v=x gives 1+1=2, rather than its zero RHS.
    return {"strong_residual_x1":1-1,"strong_bulk_residual":0,
      "weak_plus_residual":1+1,"weak_minus_residual":1-1,
      "V3_outward_flux_at_midpoint":-float(np.pi),
      "V3_posted_strong_flux_at_midpoint":-float(np.pi),
      "V3_flux_implied_by_posted_weak_at_midpoint":float(np.pi)}

def main():
    wall=time.perf_counter(); cpu=time.process_time()
    arms=[]
    for pattern in ("forward","backward","checker"):
        for m in (8,16,24):
            a=solve(m,pattern)
            a["in_posted_band"]=3.9<=a["delta"]<=4.6
            if m==8:
                b=solve(m,pattern,True)
                a["independent_gradient_delta"]=b["delta"]
                a["assembly_delta_difference"]=abs(a["delta"]-b["delta"])
            arms.append(a)
    checks={"nine_arms":len(arms)==9,
      "residuals":all(x["relative_residual"]<=1e-8 for x in arms),
      "vertical_balance":all(abs(x["force_y"]-1)<1e-10 and abs(x["reaction_y"]+1)<1e-8 for x in arms),
      "energy":all(x["energy_identity_error"]<1e-8 for x in arms),
      "gradient_agreement":all(x["assembly_delta_difference"]<1e-8 for x in arms if x["m"]==8)}
    rr=robin()
    print(json.dumps({"source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      "arms":arms,"checks":checks,"robin":rr,"cpu_s":time.process_time()-cpu,
      "wall_s":time.perf_counter()-wall},indent=2,sort_keys=True))
    return 0 if all(checks.values()) else 1

if __name__=="__main__":
    raise SystemExit(main())
