"""Construct a finite causal service plan with ordinary HiGHS linear programming."""
import argparse
import json
import time
from pathlib import Path
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix, vstack
from .inputs import load_inputs, registration

class LP:
    def __init__(self):
        self.bounds=[]; self.cost=[]; self.eq=[]; self.ineq=[]; self.integer=[]
    def var(self, shape, low=0, high=None, cost=0, integer=0):
        n=int(np.prod(shape)); start=len(self.bounds)
        self.bounds.extend(zip(np.broadcast_to(low,shape).ravel(),np.broadcast_to(high,shape).ravel()))
        self.cost.extend(np.broadcast_to(cost,shape).ravel()); self.integer.extend([integer]*n)
        return np.arange(start,start+n).reshape(shape)
    def add(self, coeff, rhs, equality=False):
        (self.eq if equality else self.ineq).append((coeff,float(rhs)))
    def matrix(self, rows):
        rr=[]; cc=[]; vv=[]
        for i,(coeff,_) in enumerate(rows):
            for j,v in coeff.items():
                if v: rr.append(i); cc.append(int(j)); vv.append(float(v))
        return coo_matrix((vv,(rr,cc)),shape=(len(rows),len(self.bounds))).tocsr(),np.array([b for _,b in rows])
    def solve(self):
        ae,be=self.matrix(self.eq); au,bu=self.matrix(self.ineq)
        lo=np.array([-np.inf if b[0] is None else b[0] for b in self.bounds],float)
        hi=np.array([np.inf if b[1] is None else b[1] for b in self.bounds],float)
        A=vstack([ae,au],format='csc'); lower=np.r_[be,np.full(len(bu),-np.inf)];upper=np.r_[be,bu]
        r=milp(np.array(self.cost),integrality=np.array(self.integer),bounds=Bounds(lo,hi),constraints=LinearConstraint(A,lower,upper),options={'mip_rel_gap':1e-8})
        if r.success:
            r.certificate={'primal_objective':float(r.fun),'dual_objective':float(r.mip_dual_bound),'absolute_gap':abs(r.fun-r.mip_dual_bound),'relative_gap':float(r.mip_gap),'max_equality_residual':float(np.max(abs(ae@r.x-be))),'max_inequality_violation':float(max(0,np.max(au@r.x-bu))),'variables':len(self.bounds),'constraints':len(self.eq)+len(self.ineq)}
        return r

def build(data, site, scale, control='primary'):
    reg=registration(); lp=LP(); eq=reg['equipment']; costs=reg['modeled_usd']; pue=reg['pue']
    rate=costs['capital_opportunity_rate']; life=costs['capital_life_years']; crf=rate/(1-(1+rate)**-life)
    multiplier=(1+costs['construction_contingency_fraction'])*crf+costs['performance_reserve_fraction_of_capex']*rate
    cap=lp.var((3,), high=[0,0,0] if control=='no_equipment' else [eq['battery_mwh_per_it_mw_max']*scale,eq['battery_mw_per_it_mw_max']*scale,eq['backup_mw_per_it_mw_max']*scale],cost=np.array([costs['battery_capex_per_mwh'],costs['battery_power_capex_per_mw'],costs['backup_capex_per_mw']])*multiplier/365)
    E,P,K=map(int,cap)
    x=lp.var((24,),low=scale/2 if control=='fixed_work' else 0,high=scale/2 if control=='fixed_work' else scale)
    for a,b in ((0,12),(12,24)): lp.add({int(i):1 for i in x[a:b]},6*scale,True)
    worst=int(lp.var((1,),cost=1)[0]); idx={int(b['Bus ID']):i for i,b in enumerate(data['buses'])}
    genbus=[idx[int(g['Bus ID'])] for g in data['gens']]
    largest=max(data['thermal'],key=lambda i:float(data['gens'][i]['PMax MW']))
    commitment=lp.var((len(data['gens']),),high=[1 if i in data['thermal'] else 0 for i in range(len(data['gens']))],integer=1)
    witnesses=[]
    for s,name in enumerate(reg['scenarios']):
        lo=data['lower'].copy(); hi=data['upper'].copy(); demand=data['load'].copy()
        if name=='largest_thermal_out_8_24': lo[8:,largest]=hi[8:,largest]=0
        if name=='line_A1_out_load_110pct_8_24': demand[8:]*=1.1
        bounds_low=lo.copy(); bounds_low[:,data['thermal']]=0
        pg=lp.var(lo.shape,low=bounds_low,high=hi);theta=lp.var((24,len(idx)),low=-np.pi,high=np.pi)
        for t in range(24): lp.bounds[int(theta[t,0])]=(0,0)
        gridhigh=np.full(24,pue*scale)
        if name=='connection_trip_8_14': gridhigh[8:14]=0
        if name=='connection_trip_8_20_and_backup_failure': gridhigh[8:20]=0
        grid=lp.var((24,),high=gridhigh);b=lp.var((24,));c=lp.var((24,));d=lp.var((24,));soc=lp.var((25,))
        z={'generation':pg,'theta':theta,'grid':grid,'backup':b,'charge':c,'discharge':d,'soc':soc}
        for t in range(24):
            for g in data['thermal']:
                lp.add({int(pg[t,g]):1,int(commitment[g]):-hi[t,g]},0)
                lp.add({int(pg[t,g]):-1,int(commitment[g]):lo[t,g]},0)
            lp.add({int(grid[t]):1,int(b[t]):1,int(d[t]):1,int(c[t]):-1,int(x[t]):-pue},0,True)
            lp.add({int(b[t]):1,K:-1},0);lp.add({int(c[t]):1,int(d[t]):1,P:-1},0)
            lp.add({int(soc[t+1]):1,int(soc[t]):-1,int(c[t]):-eq['charge_efficiency'],int(d[t]):1/eq['discharge_efficiency']},0,True)
            if t>=8 and name in ('backup_failure_8_24','connection_trip_8_20_and_backup_failure'): lp.bounds[int(b[t])]=(0,0)
            if t>=8 and name=='battery_failure_8_24': lp.bounds[int(c[t])]=(0,0);lp.bounds[int(d[t])]=(0,0)
            nodal=[{int(pg[t,g]):1 for g,bus in enumerate(genbus) if bus==i} for i in range(len(idx))]
            nodal[idx[site]][int(grid[t])]=-1
            for line in data['lines']:
                if name=='line_A1_out_load_110pct_8_24' and t>=8 and line['UID']=='A1': continue
                a=idx[int(line['From Bus'])];dest=idx[int(line['To Bus'])]
                factor=100/(float(line['X'])*(float(line['Tr Ratio']) or 1));flow={int(theta[t,a]):factor,int(theta[t,dest]):-factor};limit=float(line['Cont Rating'])
                lp.add(flow,limit);lp.add({k:-v for k,v in flow.items()},limit)
                for key,value in flow.items():
                    nodal[a][key]=nodal[a].get(key,0)-value;nodal[dest][key]=nodal[dest].get(key,0)+value
            for i,row in enumerate(nodal): lp.add(row,demand[t,i],True)
            if t:
                for g in data['thermal']:
                    if name=='largest_thermal_out_8_24' and g==largest and t==8: continue
                    ramp=60*float(data['gens'][g]['Ramp Rate MW/Min'])
                    lp.add({int(pg[t,g]):1,int(pg[t-1,g]):-1},ramp);lp.add({int(pg[t,g]):-1,int(pg[t-1,g]):1},ramp)
        for v in soc: lp.add({int(v):1,E:-1},0)
        lp.add({int(soc[0]):1,E:-eq['initial_soc_fraction']},0,True);lp.add({E:eq['terminal_soc_fraction'],int(soc[-1]):-1},0)
        lp.add({int(v):1 for v in b},eq['backup_fuel_mwh_per_it_mw_max']*scale)
        operating={worst:-1}
        for ar,price in ((grid,costs['electricity_per_mwh']),(b,costs['backup_per_mwh']),(c,costs['battery_throughput_per_mwh']),(d,costs['battery_throughput_per_mwh'])): operating.update({int(v):price for v in ar})
        lp.add(operating,0)
        if s:
            for key,ar in z.items():
                stop=9 if key=='soc' else 8
                for v,u in zip(ar[:stop].ravel(),witnesses[0][key][:stop].ravel()): lp.add({int(v):1,int(u):-1},0,True)
        witnesses.append(z)
    return lp,cap,x,worst,witnesses,largest,commitment

def construct(directory,day,site,scale,control='primary'):
    start=time.monotonic(); data=load_inputs(directory,day);lp,cap,x,worst,ids,largest,commitment=build(data,site,scale,control);result=lp.solve()
    out={'day':day,'site':site,'it_capacity_mw':scale,'control':control,'solver_status':int(result.status),'solver_message':result.message,'elapsed_seconds':time.monotonic()-start,'largest_thermal_uid':data['gens'][largest]['GEN UID'],'accepted':False}
    if not result.success:return out
    out.update({'thermal_commitment':result.x[commitment].tolist(),'capacities':dict(zip(('battery_mwh','battery_mw','backup_mw'),result.x[cap].tolist())),'work':result.x[x].tolist(),'worst_daily_opex_usd':float(result.x[worst]),'optimization':result.certificate,'plans':{name:{k:result.x[v].tolist() for k,v in plan.items()} for name,plan in zip(registration()['scenarios'],ids)}})
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',required=True);ap.add_argument('--day',required=True);ap.add_argument('--site',type=int,default=101);ap.add_argument('--scale',type=float,default=10);ap.add_argument('--control',default='primary',choices=('primary','no_equipment','fixed_work'));ap.add_argument('--output',required=True);args=ap.parse_args()
    out=construct(args.data,args.day,args.site,args.scale,args.control);Path(args.output).write_text(json.dumps(out,separators=(',',':'))+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('plans','work')}))
if __name__=='__main__':main()
