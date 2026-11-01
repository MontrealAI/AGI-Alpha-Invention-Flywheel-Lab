import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
import argparse,glob,time,json,hashlib,resource,platform,importlib.metadata
import numpy as np,stim,tesseract_decoder as td
from kernel import MassKernel,mask
p=argparse.ArgumentParser();p.add_argument('--diversify',action='store_true');p.add_argument('--noise',default='0.001');p.add_argument('--shots',type=int,default=128);p.add_argument('--seed',type=int,default=2026110101);p.add_argument('--seconds',type=float,default=240);p.add_argument('--output',default='result.json');a=p.parse_args()
start=time.perf_counter();path=glob.glob(f'upstream/testdata/bivariatebicyclecodes/r=6,d=6,p={a.noise},*_Z,*72*')[0]
c=stim.Circuit.from_file(path);dem=c.detector_error_model(decompose_errors=False)
dec=td.tesseract.TesseractConfig(dem,det_beam=10,pqlimit=10000,beam_climbing=True).compile_decoder()
# Recompile the normalized DEM so public original-DEM IDs equal retained IDs.
# Merging identical detector+logical columns uses exact independent XOR probability.
dec=td.tesseract.TesseractConfig(dec.config.dem,merge_errors=False,det_beam=10,pqlimit=10000,beam_climbing=True).compile_decoder()
k=MassKernel(dec,move_cap=1024,expansion_cap=256);
if a.diversify:
 from diversify import ParityDiversifier
 diver=ParityDiversifier(dec.config.dem,c.num_observables,c.num_detectors)
prep=time.perf_counter()-start
print('prepared',prep,k.prep_stats,flush=True)
sampler=c.compile_detector_sampler(seed=a.seed);timing=[];badt=badm=disagree=win=loss=invalid=fallback=0;fallback_bad_min=0;fallback_bad_mass=0;pooln=[];seedn=[];classn=[];witnesses=[]
for i in range(a.shots):
 if time.perf_counter()-start>a.seconds:break
 s,obs=sampler.sample(1,separate_observables=True); t=time.perf_counter();pool,stats=k.pool(s[0])
 if a.diversify:
  extra,missed=diver.candidates(s[0],k,pool);stats['invalid_searches']+=missed
  if extra:pool.update(k.expand(extra,mask(s[0].nonzero()[0])))
 best,mass,weights=k.decide(pool);timing.append(time.perf_counter()-t);stats['pool_count']=len(pool);classn.append(len(weights))
 truth=mask(obs[0].nonzero()[0]);eb=best!=truth;em=mass!=truth;badt+=eb;badm+=em;disagree+=best!=mass;win+=eb and not em;loss+=em and not eb
 invalid+=stats['invalid_searches'];fallback+=stats['fallback'];fallback_bad_min+=stats['fallback'] and eb;fallback_bad_mass+=stats['fallback'] and em;pooln.append(stats['pool_count']);seedn.append(stats['seed_count'])
 if best!=mass and len(witnesses)<8:witnesses.append({'shot':i,'detector_indices':s[0].nonzero()[0].tolist(),'truth_logical':truth,'best':best,'mass':mass,'pool':stats['pool_count'],'class_weights':weights})
 if (i+1)%16==0:print('progress',i+1,badt,badm,disagree,'seconds',round(time.perf_counter()-start,2),flush=True)
n=len(timing);result={'protocol':'diagnostic_not_confirmation','circuit_path':path,'circuit_sha256':hashlib.sha256(open(path,'rb').read()).hexdigest(),'dem_sha256':hashlib.sha256(str(dem).encode()).hexdigest(),'noise':a.noise,'shots':n,'requested_shots':a.shots,'seed':a.seed,'sample_batch':1,'stim_version':stim.__version__,'tesseract_version':importlib.metadata.version('tesseract-decoder'),'detectors':c.num_detectors,'observables':c.num_observables,'dem_errors':len(dec.errors),'settings':{'diversify':a.diversify,'orders':4,'beam':10,'pqlimit':10000,'move_cap':1024,'expansion_cap':256},'prep':k.prep_stats,'prep_seconds':prep,'total_seconds':time.perf_counter()-start,'same_pool_min_failures':badt,'same_pool_mass_failures':badm,'disagreements':disagree,'mass_only_wins':win,'mass_only_losses':loss,'invalid_searches':invalid,'fallback_shots':fallback,'fallback_min_failures':fallback_bad_min,'fallback_mass_failures':fallback_bad_mass,'rejected_shots':0,'mean_classes':float(np.mean(classn)),'mean_pool':float(np.mean(pooln)),'mean_seeds':float(np.mean(seedn)),'kernel_seconds_quantiles':{str(q):float(np.quantile(timing,q)) for q in [.5,.99,.999,1]},'maxrss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'compact_witnesses':witnesses,'limitations':['No matched strongest baseline or hardware validation','Partial-pool mass, not exact coset partition function','DEM mechanisms not microscopic circuit-fault assignments','Shared CPU tail estimates, not hard real-time guarantee']}
open(a.output,'w').write(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
