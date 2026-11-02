from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
import numpy as np
from scipy.linalg import cho_factor, cho_solve

@dataclass(frozen=True)
class Cell:
    capacity_ah: float
    r0_ohm: float
    r1_ohm: float
    tau_s: float
    soc: tuple[float,...]
    ocv_v: tuple[float,...]

    def __post_init__(self):
        p=np.array([self.capacity_ah,self.r0_ohm,self.r1_ohm,self.tau_s],float)
        x=np.array(self.soc,float); y=np.array(self.ocv_v,float)
        if not np.isfinite(p).all() or (p<=0).any(): raise ValueError('POSITIVE_FINITE_CELL_PARAMETERS_REQUIRED')
        if len(x)<2 or len(x)!=len(y) or not np.isfinite(x).all() or not np.isfinite(y).all(): raise ValueError('FINITE_OCV_CURVE_REQUIRED')
        if x[0]!=0 or x[-1]!=1 or (np.diff(x)<=0).any() or (np.diff(y)<0).any(): raise ValueError('MONOTONE_FULL_SOC_CURVE_REQUIRED')
        object.__setattr__(self,'soc',tuple(float(v) for v in x)); object.__setattr__(self,'ocv_v',tuple(float(v) for v in y))

    def voltage(self,soc):
        if np.any(np.asarray(soc)<-1e-9) or np.any(np.asarray(soc)>1+1e-9): raise ValueError('SOC_OUTSIDE_QUALIFIED_DOMAIN')
        return np.interp(soc,self.soc,self.ocv_v)

def cell_from_dict(x):
    return Cell(**{**x,'soc':tuple(x['soc']),'ocv_v':tuple(x['ocv_v'])})

class Ladder:
    def __init__(self,cells,segment_loop_ohm):
        self.cells=tuple(cells); self.n=len(cells)
        seg=np.array(segment_loop_ohm,float)
        if self.n<2 or seg.shape!=(self.n-1,) or not np.isfinite(seg).all() or (seg<0).any(): raise ValueError('NONNEGATIVE_LOOP_SEGMENTS_REQUIRED')
        self.segment_loop_ohm=seg
        self.r=np.array([c.r0_ohm for c in cells]); self.r1=np.array([c.r1_ohm for c in cells]); self.tau=np.array([c.tau_s for c in cells]); self.q=np.array([c.capacity_ah*3600 for c in cells])
        path=np.zeros((self.n,self.n))
        for k,r in enumerate(seg,1): path[k:,k:]+=r
        self.impedance=np.diag(self.r)+path
        self.factor=cho_factor(self.impedance,lower=True,check_finite=True)
        self.one=cho_solve(self.factor,np.ones(self.n)); self.g=float(self.one.sum())

    def currents(self,soc,polarization,total_a):
        soc=np.asarray(soc,float); polarization=np.asarray(polarization,float)
        if soc.shape!=(self.n,) or polarization.shape!=(self.n,) or not np.isfinite(np.r_[soc,polarization,total_a]).all() or np.ndim(total_a)!=0: raise ValueError('FINITE_STATE_AND_SCALAR_LOAD_REQUIRED')
        e=np.array([c.voltage(z) for c,z in zip(self.cells,soc)])-polarization
        v=cho_solve(self.factor,e)
        terminal=(v.sum()-total_a)/self.g
        current=v-terminal*self.one
        return current,float(terminal)

    def derivative(self,state,total_a):
        i,_=self.currents(state[:self.n],state[self.n:],total_a)
        return np.r_[-i/self.q,(self.r1*i-state[self.n:])/self.tau]

    def simulate(self,total_a,duration_s,step_s=1.0,initial_soc=None,initial_polarization=None):
        if not all(np.isfinite(x) for x in [total_a,duration_s,step_s]) or duration_s<0 or step_s<=0: raise ValueError('FINITE_TIME_INPUT_REQUIRED')
        state=np.r_[np.ones(self.n) if initial_soc is None else np.asarray(initial_soc,float),np.zeros(self.n) if initial_polarization is None else np.asarray(initial_polarization,float)]
        t=0.; times=[]; currents=[]; soc=[]; voltage=[]
        while t<=duration_s+1e-9:
            i,v=self.currents(state[:self.n],state[self.n:],total_a)
            times.append(t); currents.append(i); soc.append(state[:self.n].copy()); voltage.append(v)
            dt=min(step_s,duration_s-t)
            if dt<=1e-9: break
            try:
                k1=self.derivative(state,total_a); k2=self.derivative(state+dt*k1/2,total_a); k3=self.derivative(state+dt*k2/2,total_a); k4=self.derivative(state+dt*k3,total_a)
                nxt=state+dt*(k1+2*k2+2*k3+k4)/6
                if np.any(nxt[:self.n]<0) or np.any(nxt[:self.n]>1): break
            except ValueError as e:
                if str(e)=='SOC_OUTSIDE_QUALIFIED_DOMAIN': break
                raise
            state=nxt; t+=dt
        return {'time_s':np.array(times),'current_a':np.array(currents),'soc':np.array(soc),'terminal_v':np.array(voltage),'requested_duration_s':duration_s,'completed':abs(t-duration_s)<1e-8}

def isolated_trace(cell,current_a,duration_s,step_s=1.0,initial_soc=1.0,rest_s=0.):
    times=np.arange(0,duration_s+step_s*.5,step_s); times=times[times<=duration_s]
    if times[-1]<duration_s: times=np.r_[times,duration_s]
    z=initial_soc-current_a*times/(3600*cell.capacity_ah)
    vp=cell.r1_ohm*current_a*(-np.expm1(-times/cell.tau_s))
    voltage=cell.voltage(z)-cell.r0_ohm*current_a-vp
    if rest_s:
        rt=np.arange(step_s,rest_s+step_s*.5,step_s)
        times=np.r_[times,duration_s+rt]; voltage=np.r_[voltage,cell.voltage(z[-1])-vp[-1]*np.exp(-rt/cell.tau_s)]
    return {'time_s':times,'voltage_v':voltage,'final_soc':float(z[-1])}

def minimum_separating_probe(cells,observation_error_v=.002,nominal_capacity_ah=2.):
    fractions=[.05,.10,.20,.30,.40,.50,.60]; rates=[.15,.5,.75]; rows=[]
    if len(cells)!=2 or not np.isfinite(nominal_capacity_ah) or nominal_capacity_ah<=0: raise ValueError('TWO_MODELS_COMMON_NOMINAL_CAPACITY_REQUIRED')
    for fraction in fractions:
        for rate in rates:
            t=fraction/rate*3600
            values=[isolated_trace(c,rate*nominal_capacity_ah,t,step_s=1,rest_s=300)['voltage_v'][-1] for c in cells]
            distance=abs(values[0]-values[1]); rows.append({'fraction':fraction,'c_rate':rate,'discharge_seconds':t,'rest_seconds':300,'total_seconds':t+300,'terminal_separation_v':distance,'separates':distance>2*observation_error_v})
    possible=[r for r in rows if r['separates']]
    best=min(possible,key=lambda r:(r['total_seconds'],r['fraction'],r['c_rate'])) if possible else None
    return {'scope':'finite_two_model_observation_design_only','observation_error_bound_v':observation_error_v,'nominal_capacity_ah':nominal_capacity_ah,'prior_short_observation_seconds':600,'reset_and_soc_preparation_cost':'UNRESOLVED','evaluated_probes':len(rows),'probes':rows,'selected':best,'optimality_gap_seconds_in_menu':0 if best else None,'full_c20_discharge_seconds':20*3600,'physical_safety_qualified':False}

def model_digest(payload):
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
