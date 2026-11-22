"""Independent mathematical obligations, not physical measurements or constructor fit."""
import numpy as np

def relative(a,b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))

def checks():
    n=4
    T=np.diag(np.array([.2,.3,.5,.7])*np.exp(1j*np.array([.2,-.3,.7,1.1])))
    R0=.3*np.eye(n); R1=np.diag(np.linspace(.1,.7,n))
    A=np.diag(np.ones(n-1),1)+np.diag(np.ones(n-1),-1)
    R2=.3*np.eye(n)+.08*A
    D=np.diag([1,-1,1,-1]); alt=D@T
    c=lambda t,r:t.T@r@t
    same=[relative(c(alt,r),c(T,r)) for r in (R0,R1)]
    separated=relative(c(alt,R2),c(T,R2))
    assert max(same)<1e-14 and separated>1e-3
    # One-reflector non-sign orthogonal gauge leaves congruence unchanged.
    a=.31; Q=np.eye(n);Q[:2,:2]=[[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]]
    one_gauge=relative(c(Q@T,R0),c(T,R0))
    assert one_gauge<1e-14
    # Disconnect graph into two components: relative component signs unobservable.
    Rd=R2.copy();Rd[1,2]=Rd[2,1]=0
    Dc=np.diag([1,1,-1,-1]); disconnected=relative(c(Dc@T,Rd),c(T,Rd))
    assert disconnected<1e-14
    # Matched filter target-intensity optimum independent of global/row signs.
    ratios=[]
    for i in range(n):
        x=np.conj(alt[i,:]);x=x/np.linalg.norm(x)
        ratios.append(float(abs((T@x)[i])**2/np.linalg.norm(T[i,:])**2))
    assert max(abs(x-1) for x in ratios)<1e-14
    # Reciprocity violation can be observationally hidden: B=s*T.T is
    # indistinguishable in calibration from effective sqrt(s)*T, all reflectors.
    # Therefore exact residual alone cannot certify true one-way transmission.
    s=.81; effective=np.sqrt(s)*T
    hidden_nonreciprocity=max(relative((s*T.T)@r@T,c(effective,r)) for r in (R0,R1,R2))
    assert hidden_nonreciprocity<1e-14
    return {'two_reflector_sign_gauge_residuals':same,'third_reflector_separation':separated,
            'one_reflector_orthogonal_gauge_residual':one_gauge,
            'disconnected_component_gauge_residual':disconnected,
            'target_intensity_ratios':ratios,'undetectable_return_scaling_residual':hidden_nonreciprocity,
            'scope':'Exact-model analytic examples only; no physical truth, constructor performance or new optical method.'}

if __name__=='__main__':
    import json
    print(json.dumps(checks(),indent=2))
