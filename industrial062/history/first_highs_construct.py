import argparse,json,math,sys,time,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix

ROOT=Path(__file__).resolve().parent

def prepare(folder):
    d=json.loads((folder/'01.json').read_text())
    if d['variant']=='mixed':
        sys.path.insert(0,str(folder))
        from _network_mixed import prepare_mixed
        d=prepare_mixed(d)
    return d

def distance(d,node,customer):
    old=d['arcs']['node_to_customer']['distance_km'].get(node,{}).get(customer)
    if old is not None:return float(old)
    if d['variant']!='direct' or not d['direct_delivery'].get('allow_new_relations'):return None
    a,b=d['coordinates'][node],d['coordinates'][customer]
    la,lb,oa,ob=map(math.radians,[a['latitude'],b['latitude'],a['longitude'],b['longitude']])
    h=math.sin((lb-la)/2)**2+math.cos(la)*math.cos(lb)*math.sin((ob-oa)/2)**2
    p=d['direct_delivery']
    return round(p['distance_multiplier']*2*p['earth_radius_km']*math.asin(math.sqrt(min(1,max(0,h)))),p['distance_decimals'])

def construct(folder,output,seconds):
    t=time.monotonic();cpu=time.process_time();d=prepare(folder);P=d['products'];F=d['factories'];C=d['central_warehouses'];R=d['regional_centers'];A=d['arcs'];T=d['days_per_year'];U=d['totals']['demand_pieces']
    rows=defaultdict(dict);lower={};upper={};cost=[];ub=[];names=[];types=[];through=defaultdict(dict)
    def add(section,key,c,u):
        i=len(cost);cost.append(c);ub.append(u);names.append((section,key));types.append(1);return i
    def term(row,i,v):rows[row][i]=rows[row].get(i,0)+v
    def balance(n,p,i,v):term(('balance',n,p),i,v);lower['balance',n,p]=upper['balance',n,p]=0
    def holding(flow,arc,value,rate,cycle=True):return flow*value*rate*(arc['transit_days']+(arc['shipment_interval_days']/2 if cycle else 0))/T
    def warehouse_flow(n,i):through[n][i]=through[n].get(i,0)+1
    def transfer(section,key,source,destination,p,arc):
        q=P[p];rate=(C.get(destination) or R[destination])['holding_rate'][q['category']]
        c=arc['freight_rate']*q['unit_volume']*arc['distance_km']+holding(1,arc,q['unit_value'],rate)
        i=add(section,key,c,U);balance(source,p,i,-1);balance(destination,p,i,1)
        if source in C or source in R:warehouse_flow(source,i)
    for f,meta in F.items():
        z=add('factory_open',(f,),meta['fixed_operating_cost'],1)
        term(('factory_min',f),z,-1);lower['factory_min',f]=0
        term(('capacity',f),z,-meta['capacity_pieces']);upper['capacity',f]=0
        for p in meta['products']:
            c=P[p]['production_cost'];valid=True
            for m,n in d['bom'][p].items():
                material=d['materials'][m];arc=A['supplier_to_factory'].get(material['supplier']+'|'+f+'|'+m)
                if arc is None:valid=False;break
                c+=n*(arc['freight_rate']*material['unit_weight']*arc['distance_km']+holding(1,arc,material['unit_value'],meta['holding_rate_material']))
            if not valid:continue
            i=add('production',(f,p),c,meta['capacity_pieces']);balance(f,p,i,1);term(('capacity',f),i,1);term(('factory_min',f),i,1)
    for key,arc in A['factory_to_cdc'].items():
        f,c=key.split('|')
        for p in F[f]['products']:
            if P[p]['category']==arc['category']:transfer('factory_to_cdc',(f,c,p),f,c,p,arc)
    for section,sources in [('cdc_to_rdc',C),('factory_to_rdc',F)]:
        for key,arc in A.get(section,{}).items():
            a,b,cat=key.split('|')
            for p,q in P.items():
                if q['category']==cat and (a not in F or p in F[a]['products']):transfer(section,(a,b,p),a,b,p,arc)
    nodes=list(R)+(list(C)+list(F) if d['variant']=='direct' else [])
    for k,customer in d['customers'].items():
        for p,demand in customer['demand'].items():
            if not demand:continue
            row=('demand',k,p);lower[row]=upper[row]=demand;q=P[p];cat=q['category'];mode='ambient' if cat=='candy' else customer['temperature_zone']
            for n in nodes:
                if n in F and p not in F[n]['products']:continue
                km=distance(d,n,k)
                if km is None:continue
                transit=A['node_to_customer']['transit_days'].get(n,{}).get(k)
                if transit is None:transit=km/d['direct_delivery']['average_speed_kmh']/24
                rate=F[n]['holding_rate_finished'] if n in F else (C.get(n) or R[n])['holding_rate'][cat]
                c=A['node_to_customer']['freight_rate'][cat][mode]*q['unit_volume']*km+q['unit_value']*rate*transit/T
                i=add('customer_service',(k,p,n),c,demand);term(row,i,1);balance(n,p,i,-1)
                if n in C or n in R:warehouse_flow(n,i)
                if km<=d['service_distance_km']:term(('coverage',),i,1)
    lower['coverage',]=math.ceil(U*d['service_coverage_floor'])
    for n,meta in list(C.items())+list(R.items()):
        tiers=meta['operating_cost_tiers'];lo=('tier_lo',n);hi=('tier_hi',n);one=('tier_one',n)
        for i,v in through[n].items():term(lo,i,v);term(hi,i,v)
        lower[lo]=0;upper[hi]=0;upper[one]=1
        for j,(threshold,amount) in enumerate(tiers):
            low=max(1,threshold);high=tiers[j+1][0]-1 if j+1<len(tiers) else U
            z=add('warehouse_tier',(n,j),amount,1);term(lo,z,-low);term(hi,z,-high);term(one,z,1)
    rr=[];cc=[];vv=[];lbs=[];ubs=[]
    for r,coeffs in rows.items():
        at=len(lbs);lbs.append(lower.get(r,-np.inf));ubs.append(upper.get(r,np.inf))
        for i,v in coeffs.items():rr.append(at);cc.append(i);vv.append(v)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(lbs),len(cost))).tocsc()
    result=milp(np.array(cost),integrality=np.array(types),bounds=Bounds(np.zeros(len(cost)),np.array(ub)),constraints=LinearConstraint(matrix,lbs,ubs),options={'time_limit':seconds,'mip_rel_gap':1e-7})
    output.mkdir(parents=True,exist_ok=False)
    receipt={'input_sha256':hashlib.sha256((folder/'01.json').read_bytes()).hexdigest(),'variables':len(cost),'constraints':len(lbs),'status':int(result.status),'message':result.message,'objective_yuan':getattr(result,'fun',None),'dual_bound_yuan':getattr(result,'mip_dual_bound',None),'relative_gap':getattr(result,'mip_gap',None),'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-t,'solver':'scipy.optimize.milp/HiGHS','novel_algorithm_claim':False,'service_floor_unchanged':d['service_coverage_floor'],'enterprise_collections':0,'economic_scope':'Client operating-cost model only; no realized savings, purchase, vendor revenue, or funded expansion.'}
    if result.x is not None:
        x=np.rint(result.x).astype(np.int64);error=float(np.max(np.abs(result.x-x)));receipt['max_rounding_error']=error
        if error>1e-4:raise ValueError('NONINTEGRAL_OUTPUT')
        solution={k:[] for k in ['production','factory_to_cdc','cdc_to_rdc','customer_service']+(['factory_to_rdc'] if d['variant']=='direct' else [])}
        fields={'production':['factory','product'],'factory_to_cdc':['factory','cdc','product'],'cdc_to_rdc':['cdc','rdc','product'],'factory_to_rdc':['factory','rdc','product'],'customer_service':['customer','product','node']}
        for (section,key),value in zip(names,x):
            if section in solution and value>0:solution[section].append(dict(zip(fields[section],key),pieces=int(value)))
        (output/'solution.json').write_text(json.dumps(solution,indent=2)+'\n')
    (output/'production.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--output',required=True);p.add_argument('--seconds',type=float,default=60);a=p.parse_args();construct(ROOT/'inputs'/a.case,Path(a.output),a.seconds)
