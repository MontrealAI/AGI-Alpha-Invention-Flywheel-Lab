"""Offline design bounds; does not control equipment or certify potable water."""
import argparse,csv,datetime,hashlib,json,math,time,urllib.request
from pathlib import Path
DATES=['2022-08-15','2022-09-15','2022-10-15','2022-12-15','2023-01-15','2023-02-15','2023-03-15']
F=96485.33212
MW=.05844 # kg/mol NaCl

def separate(feed_l,feed_g_l,product_g_l,recovery,current_a,eta=.4,pairs=150,voltage=50):
    """Ideal monovalent-salt transfer, no water transport or leakage model."""
    vals=[feed_l,feed_g_l,product_g_l,recovery,current_a,eta,pairs,voltage]
    if not all(math.isfinite(v) for v in vals): raise ValueError('nonfinite')
    if feed_l<=0 or feed_g_l<0 or not 0<=product_g_l<=feed_g_l or not 0<recovery<1 or current_a<=0 or not 0<eta<=1 or pairs<=0 or voltage<0: raise ValueError('outside ideal model envelope')
    product=feed_l*recovery; brine=feed_l-product
    transferred_kg=product*(feed_g_l-product_g_l)/1000
    charge=transferred_kg/MW*F/(eta*pairs)
    seconds=charge/current_a
    salt_in=feed_l*feed_g_l/1000
    salt_product=product*product_g_l/1000
    salt_brine=salt_in-salt_product
    return dict(product_l=product,brine_l=brine,brine_g_l=salt_brine*1000/brine,salt_in_kg=salt_in,salt_product_kg=salt_product,salt_brine_kg=salt_brine,charge_c=charge,seconds=seconds,stack_kwh=charge*voltage/3600000,physical_qualification=False)

def simulate(production,demand,capacity,initial):
    stock=initial; states=[stock]; spill=0.; missing=0.
    for p,d in zip(production,demand):
        # Hourly balance, production considered available at end of hour.
        net=stock+p-d
        missing+=max(0,-net);spill+=max(0,net-capacity)
        stock=min(capacity,max(0,net));states.append(stock)
    return dict(states_l=states,spill_l=spill,unserved_l=missing,terminal_l=stock,initial_l=initial,capacity_l=capacity)

def construct(production,demand):
    if len(production)!=len(demand) or not production or any(not math.isfinite(v) or v<0 for v in production+demand): raise ValueError('bad hourly inputs')
    net=[p-d for p,d in zip(production,demand)]
    if sum(net)<-1e-8: return dict(feasible=False,reason='total supply below obligation',deficit_l=-sum(net))
    n=len(net)
    cap=max([0.]+[-sum((net+net)[i:i+k]) for i in range(n) for k in range(1,n+1)])
    initial=max(0.,-min([0.]+[sum(net[:k]) for k in range(1,n+1)]))
    r=simulate(production,demand,cap,initial)
    r.update(feasible=r['unserved_l']<=1e-8 and r['terminal_l']>=initial-1e-8)
    return r

def extract(file):
    """Hash complete stream; keep only24 hourly buckets, not raw CSV."""
    h=hashlib.sha256();md5=hashlib.md5();size=0
    def lines(response):
        nonlocal size
        for raw in response:
            size+=len(raw);h.update(raw);md5.update(raw)
            yield raw.decode('utf-8-sig')
    production=[0.]*24; unknown_increment=0.; pv=[0.]*24;rows=0;counter_rows=0;resets=0;gaps=0;prev=None;prevpower=None;origin=None
    with urllib.request.urlopen(file['download_url'],timeout=90) as response:
        for row in csv.DictReader(lines(response)):
            rows+=1
            if not row.get('_time'): continue
            t=datetime.datetime.fromisoformat(row['_time']).timestamp()
            if origin is None:origin=math.floor(t/3600)*3600
            hour=int((t-origin)//3600)
            if not 0<=hour<24:continue
            value=row.get('DD/EDR/PRODUCTION_WATER','')
            if value:
                c=float(value);counter_rows+=1
                if prev:
                    dt=t-prev[0];delta=c-prev[1]
                    if dt>900:
                        gaps+=1;unknown_increment+=max(0,delta)
                    if delta<0:resets+=1
                    elif 0<=dt<=900:production[hour]+=delta
                prev=(t,c)
            value=row.get('DD/EDR/PV_Power_DS','')
            if value:
                power=float(value)
                if prevpower:
                    dt=t-prevpower[0]
                    if 0<=dt<=900:pv[hour]+=max(0,(power+prevpower[1])/2)*dt/3600000
                prevpower=(t,power)
    return dict(name=file['name'],file_id=file['id'],bytes=size,sha256=h.hexdigest(),md5=md5.hexdigest(),expected_md5=file.get('computed_md5'),source_hash_ok=md5.hexdigest()==file.get('computed_md5'),rows=rows,counter_rows=counter_rows,counter_resets=resets,counter_gaps_over15min=gaps,unqualified_gap_increment_l=unknown_increment,production_l=production,pv_kwh=pv,quality_acceptance='ABSTAIN: conductivity mapping and full contaminant acceptance unqualified',window_start_utc=datetime.datetime.fromtimestamp(origin,datetime.timezone.utc).isoformat() if origin is not None else None,interval_attribution='all increment at later observation; conservative delayed availability',data_status='missing' if not counter_rows else 'quantity_only')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--metadata',default='figshare_metadata.json');ap.add_argument('--out',default='results.json');ap.add_argument('--development',action='store_true');a=ap.parse_args()
    start=time.time();cpu=time.process_time();meta=json.load(open(a.metadata));dates=['2022-08-01'] if a.development else DATES;results=[]
    for date in dates:
        f=next(x for x in meta['files'] if x['name']=='Influx Data '+date+'.csv')
        try:
            r=extract(f);r['designs']={}
            if not r['source_hash_ok']: raise ValueError('source MD5 mismatch; design prohibited')
            for daily in [500,1000,2000,5000]:
                p=r['production_l'];d=[daily/24]*24
                n=max(1,math.ceil(daily/sum(p))) if sum(p)>0 else None
                r['designs'][str(daily)]={'single_train_with_storage':construct(p,d),'single_train_without_storage':simulate(p,d,0,0),'parallel_train_count':n,'parallel_design':construct([n*x for x in p],d) if n else None,'parallel_scale_is_assumption':True}
            results.append(r)
        except Exception as e:results.append(dict(name=f['name'],error=type(e).__name__+': '+str(e),data_status='error'))
        Path(a.out).write_text(json.dumps(dict(stage='development' if a.development else 'registered replay',cases=results),indent=2))
    physics=[dict(recovery=rec,eta=eta,**separate(1000,2,.5,rec,10,eta)) for rec in [.5,.8,.95] for eta in [.4,.9]]
    output=dict(stage='development' if a.development else 'registered replay',cases=results,physics_k1_k2=physics,elapsed_s=time.time()-start,cpu_s=time.process_time()-cpu,actual_incremental_spend=0,unknown_deployment_costs=True,commercial_acceptance=False,k2_physical_qualification=False)
    Path(a.out).write_text(json.dumps(output,indent=2));print(json.dumps({k:v for k,v in output.items() if k not in ['cases','physics_k1_k2']}))
if __name__=='__main__':main()
