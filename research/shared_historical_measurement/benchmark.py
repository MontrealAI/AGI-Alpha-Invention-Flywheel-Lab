"""Actual image work benchmark; warm filesystem cache, no acquisition/model work."""
import argparse,csv,json,statistics,time
from pathlib import Path
from producer import Producer,commission,canonical,digest,verify

def validate(outputs,source):
 expected={(x['filename'],'promenade' if x['query']=='sidewalk' else x['query']):x for x in csv.DictReader((source/'v2/production_measurements.csv').open())}
 compiled={(x['filename'],'promenade' if x['query']=='sidewalk' else x['query']):x for x in csv.DictReader((source/'v2/production_compiled.csv').open())}
 n=0;maxerr=0
 for q in ['road','promenade']:
  for r in outputs[q]:
   e=expected[r['filename'],q];c=compiled[r['filename'],q]
   assert r['state']==e['state'],(q,r['filename'],r['state'],e['state'])
   assert ('compiled' if r['method']=='compiled' else 'semantic')==e['route']
   for rk,ck in [('compiled_distance_dry','distance_dry'),('compiled_distance_wet','distance_wet'),('compiled_margin','separation_margin')]:maxerr=max(maxerr,abs(r[rk]-float(c[ck])))
   n+=1
 gcc=json.loads((source/'v3_canopy/cached_gcc.json').read_text());selected={r['filename']:r for r in csv.DictReader((source/'v3_canopy/selected_measurements.csv').open())}
 for r in outputs['canopy']:
  assert abs(r['gcc']-float(gcc[r['filename']]['gcc']))<1e-12
  assert r['state']==selected[r['filename']]['state'];assert r['quality_flag']==selected[r['filename']]['quality_flag'];n+=1
 assert maxerr<1e-12,maxerr
 return {'matched_state_route_and_canopy_quality_rows':n,'maximum_pavement_feature_derived_distance_difference':maxerr,'gcc_tolerance':1e-12}
def main():
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path,required=True);a.add_argument('--data',type=Path,required=True);a.add_argument('--out',type=Path,required=True);a.add_argument('--rounds',type=int,default=3);args=a.parse_args();args.out.mkdir(parents=True,exist_ok=True);allruns=[];last=None
 modes=['separate','ordinary_shared','commissioned']
 for iteration in range(args.rounds):
  for mode in modes[iteration%3:]+modes[:iteration%3]:
   start=time.perf_counter();cpu=time.process_time();outputs={};receipts=[]
   if mode=='separate':
    for q in ['road','promenade','canopy']:
     out,r=Producer(args.source,args.data).run([q]);outputs.update(out);receipts.append(r)
   elif mode=='ordinary_shared':
    outputs,r=Producer(args.source,args.data).run(['road','promenade','canopy']);receipts.append(r)
   else:
    outputs,r,contract=commission(args.source,args.data,['road','promenade','canopy']);receipts.append(r);last=(outputs,contract)
   wall=time.perf_counter()-start;cp=time.process_time()-cpu;counts={}
   for r in receipts:
    for k,v in r['counts'].items():counts[k]=counts.get(k,0)+v
   check=validate(outputs,args.source)
   row={'mode':mode,'round':iteration,'wall_seconds':wall,'cpu_seconds':cp,'counts':counts,'validation':check,'output_hashes':{q:digest(canonical(v)) for q,v in outputs.items()},'verification_wall_seconds':sum(r.get('commission_verification_wall_seconds',0) for r in receipts)}
   allruns.append(row);print(json.dumps({'mode':mode,'round':iteration,'wall_seconds':wall,'counts':counts}),flush=True)
 assert all(r['output_hashes']==allruns[0]['output_hashes'] for r in allruns)
 outputs,contract=last
 for q,rows in outputs.items():(args.out/(q+'.json')).write_bytes(canonical(rows))
 (args.out/'commission.json').write_text(json.dumps(contract,indent=2))
 report={'schema':'shared-production-benchmark/1','runs':allruns,'summary':{m:{'median_wall_seconds':statistics.median(r['wall_seconds'] for r in allruns if r['mode']==m),'median_cpu_seconds':statistics.median(r['cpu_seconds'] for r in allruns if r['mode']==m),'counts':next(r['counts'] for r in allruns if r['mode']==m)} for m in modes},'all_output_hashes_equal':True,'limitations':['Warm local filesystem cache; image bytes read are process-level reads, not measured physical disk traffic.','No source acquisition, fresh model interpretation, setup labor, calibration labor, independent physical validation or maintenance billed/measured.','Historical recorded native readings replayed; no standalone model API integration.','No customers, observed prices, financial admission, account mutations or revenue.','Shared ordinary implementation intentionally identical to commissioned production: no novelty or savings over competent sharing claimed.']}
 (args.out/'benchmark.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['summary'],indent=2))
if __name__=='__main__':main()
