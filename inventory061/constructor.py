import argparse,hashlib,json,math,time
from pathlib import Path
import numpy as np
from scipy.stats import norm

ROOT=Path(__file__).resolve().parent
LAMBDA_GRID=[0.0,*np.geomspace(0.1,1000000,40).tolist()]
QUANTILE_GRID=[0.5,0.6,0.7,0.75,0.8,0.85,0.9,0.925,0.95,0.975,0.99,1.0]
SERVICE_FRACTIONS=[0.0,0.25,0.5,0.75,1.0]


def circular(values,horizon):
    array=np.asarray(values,dtype=np.int64)
    if horizon==0:return np.zeros(len(array),dtype=np.int64)
    repeated=np.tile(array,1+(horizon+len(array)-1)//len(array));prefix=np.r_[0,np.cumsum(repeated,dtype=np.int64)]
    return prefix[np.arange(len(array))+horizon]-prefix[np.arange(len(array))]


def context(instance):
    products={p['product']:p for p in instance['products']};cdcs={p['node']:p for p in instance['central_warehouses']};rdcs={p['node']:p for p in instance['regional_centers']}
    arrays={(r,p):np.array(instance['demand'][r][p],dtype=np.int64) for r in rdcs for p in products}
    aggregate={p:sum((arrays[r,p] for r in rdcs),np.zeros(365,dtype=np.int64)) for p in products}
    return products,cdcs,rdcs,arrays,aggregate


def diagnostics(instance,solution):
    products,cdcs,rdcs,arrays,aggregate=context(instance);times={(r['node'],r['product']):r['days'] for r in solution['cdc_service_time']};policy={(r['node'],r['product']):r['parameters']['base_stock_level'] for r in solution['inventory_policy']}
    total_safety=0.;total_cycle=0.;services=[];points=[]
    for product,p in products.items():
        node=p['source_central_warehouse'];c=cdcs[node];s=times[node,product];cw=circular(aggregate[product],c['lead_time_days']-s);threshold=policy[node,product];coefficient=p['unit_value']*p['holding_cost_rate']
        safety=max(0.,threshold-float(cw.mean()))*coefficient;cycle=float(aggregate[product].mean())*c['review_interval_days']/2*coefficient;total_safety+=safety;total_cycle+=cycle
        points.append({'node':node,'product':product,'safety_cost_yuan':safety,'cycle_cost_yuan':cycle,'threshold':threshold})
        for region,r in rdcs.items():
            lead=r['replenishment'][p['category']];rw=circular(arrays[region,product],s+lead['lead_time_days']);level=policy[region,product];good=(cw<=threshold)&(rw<=level);service=float(good.mean());services.append({'node':region,'product':product,'service':service,'successes':int(good.sum()),'anchors':365})
            safety=max(0.,level-float(rw.mean()))*coefficient;cycle=float(arrays[region,product].mean())*lead['review_interval_days']/2*coefficient;total_safety+=safety;total_cycle+=cycle
            points.append({'node':region,'product':product,'safety_cost_yuan':safety,'cycle_cost_yuan':cycle,'threshold':level})
    average=sum(r['service'] for r in services)/len(services);cost=total_safety+total_cycle;scale=instance['inventory_cost_normalization_yuan'];a=instance['service_distance_weight'];b=instance['cost_distance_weight'];distance=math.sqrt(a/(a+b)*max(0,instance['ideal_service_level']-average)**2+b/(a+b)*(cost/(cost+scale))**2);level=math.floor(distance/instance['ideal_distance_level_width'])
    return {'annual_inventory_cost_yuan':cost,'annual_safety_stock_holding_cost_yuan':total_safety,'annual_cycle_stock_holding_cost_yuan':total_cycle,'average_cycle_service':average,'minimum_cycle_service':min(r['service'] for r in services),'below_95_percent':sum(r['service']<.95 for r in services),'ideal_distance':distance,'distance_level':level,'rank':[level,-average,cost],'service_by_point':services,'cost_by_point':points}


def output_from_choices(instance,choices):
    policies=[];times=[]
    for product,choice in choices.items():
        times.append({'node':choice['cdc'],'product':product,'days':int(choice['service_days'])})
        for node,stock in choice['stocks'].items():policies.append({'node':node,'product':product,'policy_type':'base_stock','parameters':{'base_stock_level':int(stock)}})
    return {'inventory_policy':sorted(policies,key=lambda x:(x['node'],x['product'])),'cdc_service_time':sorted(times,key=lambda x:(x['node'],x['product']))}


def ordinary(instance,mode,quantile,fraction):
    products,cdcs,rdcs,arrays,aggregate=context(instance);choices={}
    def threshold(w):
        if mode=='empirical':return int(np.quantile(w,quantile,method='higher'))
        if quantile==1:return int(w.max())
        return max(0,int(math.ceil(float(w.mean())+float(norm.ppf(quantile))*float(w.std()))))
    for product,p in products.items():
        node=p['source_central_warehouse'];c=cdcs[node];s=int(round(fraction*c['lead_time_days']));stocks={node:threshold(circular(aggregate[product],c['lead_time_days']-s))}
        for region,r in rdcs.items():stocks[region]=threshold(circular(arrays[region,product],s+r['replenishment'][p['category']]['lead_time_days']))
        choices[product]={'cdc':node,'service_days':s,'stocks':stocks}
    return output_from_choices(instance,choices)


def thresholds(windows):
    mean=float(windows.mean());return np.unique(np.r_[int(math.floor(mean)),windows[windows>=mean]]).astype(np.int64)


def scalarized(instance):
    products,cdcs,rdcs,arrays,aggregate=context(instance);lambdas=np.array(LAMBDA_GRID);all_choices={}
    for product,p in products.items():
        node=p['source_central_warehouse'];c=cdcs[node];coef=p['unit_value']*p['holding_cost_rate'];best=[None]*len(lambdas)
        for s in range(c['lead_time_days']+1):
            cw=circular(aggregate[product],c['lead_time_days']-s);tc=thresholds(cw);mask=cw[None,:]<=tc[:,None];c_cost=np.maximum(0,tc-cw.mean())*coef
            scores=np.repeat((-c_cost)[:,None],len(lambdas),axis=1);r_choices={}
            for region,r in rdcs.items():
                rw=circular(arrays[region,product],s+r['replenishment'][p['category']]['lead_time_days']);tr=thresholds(rw);order=np.argsort(rw,kind='stable');positions=np.searchsorted(rw[order],tr,side='right')-1
                cumulative=np.cumsum(mask[:,order],axis=1,dtype=np.int64);counts=np.where(positions[None,:]>=0,cumulative[:,np.maximum(positions,0)],0);r_cost=np.maximum(0,tr-rw.mean())*coef
                selections=np.empty((len(tc),len(lambdas)),dtype=np.int64)
                for j,lam in enumerate(lambdas):
                    utility=counts*lam-r_cost[None,:];indices=np.argmax(utility,axis=1);selections[:,j]=tr[indices];scores[:,j]+=utility[np.arange(len(tc)),indices]
                r_choices[region]=selections
            for j,lam in enumerate(lambdas):
                i=int(np.argmax(scores[:,j]));record={'scalarized_value':float(scores[i,j]),'cdc':node,'service_days':s,'stocks':{node:int(tc[i]),**{region:int(values[i,j]) for region,values in r_choices.items()}}}
                if best[j] is None or record['scalarized_value']>best[j]['scalarized_value']+1e-9:best[j]=record
        all_choices[product]=best
    return [output_from_choices(instance,{p:choices[j] for p,choices in all_choices.items()}) for j in range(len(lambdas))]


def run(input_path,output_dir):
    start=time.process_time();wall=time.monotonic();input_path=Path(input_path);out=Path(output_dir);out.mkdir(parents=True,exist_ok=False);instance=json.loads(input_path.read_text());candidates=[]
    for mode in ['normal','empirical']:
        for q in QUANTILE_GRID:
            for fraction in SERVICE_FRACTIONS:
                plan=ordinary(instance,mode,q,fraction);metrics=diagnostics(instance,plan);candidates.append({'method':mode,'parameters':{'quantile':q,'CDC_service_fraction':fraction},'plan':plan,'metrics':metrics})
    for lam,plan in zip(LAMBDA_GRID,scalarized(instance)):
        candidates.append({'method':'joint_empirical_scalarized','parameters':{'lambda_yuan_per_successful_anchor':lam},'plan':plan,'metrics':diagnostics(instance,plan)})
    selected=min(candidates,key=lambda c:tuple(c['metrics']['rank']));baseline={mode:min((r for r in candidates if r['method']==mode),key=lambda c:tuple(c['metrics']['rank'])) for mode in ['normal','empirical','joint_empirical_scalarized']}
    for mode,record in baseline.items():(out/(mode+'.json')).write_text(json.dumps(record['plan'],indent=2)+'\n')
    (out/'solution.json').write_text(json.dumps(selected['plan'],indent=2)+'\n')
    summary={'schema':'orlicense061/construction-receipt/v1','source_repo':'NineAbyss/OR-License','source_commit':'2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47','task':'13_inventory','input_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'constructor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'selected_method':selected['method'],'selected_parameters':selected['parameters'],'selected_metrics':selected['metrics'],'methods':{mode:{'parameters':record['parameters'],'metrics':record['metrics'],'output_file':mode+'.json'} for mode,record in baseline.items()},'candidate_count':len(candidates),'candidate_frontier':[{'method':r['method'],'parameters':r['parameters'],'metrics':{k:v for k,v in r['metrics'].items() if k not in {'service_by_point','cost_by_point'}}} for r in candidates],'measured_constructor_process_CPU_seconds':time.process_time()-start,'measured_constructor_wall_seconds':time.monotonic()-wall,'actual_total_LLM_developer_billing':None,'origin':'Assistant-mediated construction from original public client brief/data; known inventory methods; no expert solutions or hidden grading read','optimality_scope':'Exact scalarized search within continuous-base-stock policy family at each registered lambda, complete CDC service-time and historical window breakpoints; finite lambda grid does not prove the original nonconvex multiobjective global optimum; other policy families remain legitimate alternatives','evidence_scope':'Unified historical 2023 replay mandated by client; not an out-of-sample forecast or live inventory savings; no native revenue collected here','cost_scope':'All normal, empirical and joint candidate attempts timed together; earlier source retrieval and assistant inference unmeasured and not zero'}
    (out/'RECEIPT.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:summary[k] for k in ['candidate_count','selected_method','selected_parameters','measured_constructor_process_CPU_seconds','measured_constructor_wall_seconds']}));print(json.dumps({k:selected['metrics'][k] for k in ['average_cycle_service','minimum_cycle_service','below_95_percent','annual_inventory_cost_yuan','distance_level','ideal_distance']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();run(args.input,args.output)
