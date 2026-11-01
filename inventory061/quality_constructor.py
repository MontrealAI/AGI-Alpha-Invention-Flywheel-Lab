import argparse,hashlib,json,time,math
from pathlib import Path
from decimal import Decimal
import numpy as np
from constructor import context,circular,ordinary,diagnostics,QUANTILE_GRID,SERVICE_FRACTIONS

ROOT=Path(__file__).resolve().parent
DENOMINATOR=7300000
TARGET_SUCCESS_COUNT=347
FAMILIES=['base_stock','periodic_review_order_up_to']


def coefficient(product):
    value=Decimal(str(product['unit_value']))*Decimal(str(product['holding_cost_rate']))*10000
    if value!=value.to_integral_value():raise ValueError('SOURCE_REQUIRES_FINER_EXACT_COST_QUANTUM')
    return int(value)


def point(raw,values,local,s,cdc=False,family='base_stock'):
    horizon=max(0,local['lead_time_days']-s) if cdc else local['lead_time_days']+s
    if family=='periodic_review_order_up_to':horizon+=local['review_interval_days']
    windows=circular(values,horizon);return windows


def metric(instance,plan):
    products,cdcs,rdcs,arrays,aggregate=context(instance);times={(r['node'],r['product']):r['days'] for r in plan['cdc_service_time']};policies={(r['node'],r['product']):r for r in plan['inventory_policy']};cost=0;services=[]
    for name,p in products.items():
        node=p['source_central_warehouse'];s=times[node,name];pc=policies[node,name];level=next(iter(pc['parameters'].values()));cw=point(instance,aggregate[name],cdcs[node],s,True,pc['policy_type']);coef=coefficient(p)
        cost+=coef*(2*max(0,level*365-int(cw.sum()))+int(aggregate[name].sum())*cdcs[node]['review_interval_days'])
        for region,r in rdcs.items():
            pr=policies[region,name];stock=next(iter(pr['parameters'].values()));local=r['replenishment'][p['category']];rw=point(instance,arrays[region,name],local,s,False,pr['policy_type']);count=int(np.sum((cw<=level)&(rw<=stock)));services.append({'node':region,'product':name,'successes':count,'anchors':365,'service':count/365})
            cost+=coef*(2*max(0,stock*365-int(rw.sum()))+int(arrays[region,name].sum())*local['review_interval_days'])
    avg=sum(r['successes'] for r in services)/(48*365);yuan=cost/DENOMINATOR;distance=math.sqrt(.5*(1-avg)**2+.5*(yuan/(yuan+instance['inventory_cost_normalization_yuan']))**2)
    return {'cost_exact_numerator':cost,'cost_exact_denominator':DENOMINATOR,'annual_inventory_cost_yuan':yuan,'average_cycle_service':avg,'minimum_cycle_service':min(r['service'] for r in services),'below_95_percent':sum(r['successes']<TARGET_SUCCESS_COUNT for r in services),'original_distance':distance,'original_distance_level':math.floor(distance/instance['ideal_distance_level_width']),'services':services}


def optimize(instance,allowed_families):
    products,cdcs,rdcs,arrays,aggregate=context(instance);records=[];times=[];certificates=[]
    for name,p in products.items():
        node=p['source_central_warehouse'];cdc=cdcs[node];coef=coefficient(p);best=None;examined=0;domain=[]
        for s in range(cdc['lead_time_days']+1):
            for cf in allowed_families:
                cw=point(instance,aggregate[name],cdc,s,True,cf);tc=np.unique(np.r_[int(cw.sum())//365,cw]);tc=tc[tc>=int(cw.sum())//365];masks=cw[None,:]<=tc[:,None];valid=masks.sum(axis=1)>=TARGET_SUCCESS_COUNT;tc=tc[valid];masks=masks[valid]
                if not len(tc):continue
                choices_by_c=[]
                for index,threshold in enumerate(tc):
                    cost=coef*(2*max(0,int(threshold)*365-int(cw.sum()))+int(aggregate[name].sum())*cdc['review_interval_days']);policies=[{'node':node,'product':name,'policy_type':cf,'parameters':{'base_stock_level' if cf=='base_stock' else 'order_up_to_level':int(threshold)}}];service_sum=0
                    for region,r in rdcs.items():
                        local=r['replenishment'][p['category']];options=[]
                        for family in allowed_families:
                            rw=point(instance,arrays[region,name],local,s,False,family);order=np.argsort(rw,kind='stable');cumulative=np.cumsum(masks[index,order]);at=int(np.argmax(cumulative>=TARGET_SUCCESS_COUNT));stock=max(int(rw[order[at]]),int(rw.sum())//365);count=int(np.sum(masks[index]&(rw<=stock)))
                            point_cost=coef*(2*max(0,stock*365-int(rw.sum()))+int(arrays[region,name].sum())*local['review_interval_days']);row={'node':region,'product':name,'policy_type':family,'parameters':{'base_stock_level' if family=='base_stock' else 'order_up_to_level':stock}}
                            options.append((point_cost,-count,family,stock,row))
                        selected=min(options,key=lambda x:x[:4]);cost+=selected[0];service_sum-=selected[1];policies.append(selected[4])
                    examined+=1;candidate=(cost,-service_sum,s,cf,int(threshold),policies)
                    if best is None or candidate[:5]<best[:5]:best=candidate
                domain.append({'CDC_service_days':s,'CDC_policy_family':cf,'nondominated_CDC_thresholds_examined':len(tc)})
        if best is None:raise ValueError('NO_ALL_POINT_95_PERCENT_POLICY')
        records.extend(best[5]);times.append({'node':node,'product':name,'days':best[2]});certificates.append({'product':name,'minimum_product_cost_numerator':best[0],'denominator':DENOMINATOR,'chosen_CDC_days':best[2],'chosen_CDC_family':best[3],'chosen_CDC_threshold':best[4],'candidate_CDC_states_examined':examined,'domains':domain})
    plan={'inventory_policy':sorted(records,key=lambda r:(r['node'],r['product'])),'cdc_service_time':sorted(times,key=lambda r:(r['node'],r['product']))};return plan,certificates


def run(input_path,outpath):
    started=time.process_time();wall=time.monotonic();instance=json.loads(Path(input_path).read_text());out=Path(outpath);out.mkdir(exist_ok=False);comparators={}
    for mode in ['normal','empirical']:
        feasible=[]
        for q in QUANTILE_GRID:
            for f in SERVICE_FRACTIONS:
                plan=ordinary(instance,mode,q,f);metrics=metric(instance,plan)
                if metrics['below_95_percent']==0:feasible.append((metrics['cost_exact_numerator'],-metrics['average_cycle_service'],q,f,plan,metrics))
        best=min(feasible,key=lambda x:x[:4]);comparators[mode]={'parameters':{'quantile':best[2],'CDC_service_fraction':best[3]},'metrics':best[5]};(out/(mode+'_floor95.json')).write_text(json.dumps(best[4],indent=2)+'\n')
    candidates={}
    for name,families in [('joint_base_stock',['base_stock']),('joint_two_family',FAMILIES)]:
        plan,certificate=optimize(instance,families);metrics=metric(instance,plan);assert metrics['below_95_percent']==0
        candidates[name]={'metrics':metrics,'certificate':certificate};(out/(name+'_floor95.json')).write_text(json.dumps(plan,indent=2)+'\n')
    selected=min(candidates,key=lambda k:(candidates[k]['metrics']['cost_exact_numerator'],-candidates[k]['metrics']['average_cycle_service']));(out/'solution.json').write_bytes((out/(selected+'_floor95.json')).read_bytes())
    result={'schema':'orlicense061/additional-quality-contract/v1','selected_method':selected,'quality_clause':'All48RDC-product jointCDC/RDC empirical cycle service>=95%, i.e.347of365anchors; minimize annualinventoryholdingcost. This is a separately registered qualityoffer, not a revision of originalclientranking or acceptance.','original_rankbest_kept':'Original-ranking delivery is separate historical evidence; this distribution retains the quality95 reference policy only.','comparators':comparators,'constructed':candidates,'CPU_seconds':time.process_time()-started,'wall_seconds':time.monotonic()-wall,'input_sha256':hashlib.sha256(Path(input_path).read_bytes()).hexdigest(),'quality_constructor_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'actual_LLM_total_billing':None,'optimality_scope':'Exact minimum cost in source-defined static inventory model under added347/365perpointfloor: continuous reorder families weakly dominated bybase_stock atsamepointthreshold; remainingbase+periodicfamilies fullyenumerated CDCservice/time/windowbreakpoints; regionalchoice conditionalonCDCmask separable. Independent certificate review required before asserting global source-model minimum. Notfutureinventoryperformance or economicmarket equilibrium.'}
    (out/'RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'selected':selected,'metrics':candidates[selected]['metrics'],'CPU_seconds':result['CPU_seconds'],'wall_seconds':result['wall_seconds']}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.input,a.output)
