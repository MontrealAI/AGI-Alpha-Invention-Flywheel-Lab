import collections,itertools,json,time,resource
from pathlib import Path
t=time.perf_counter()
A=(0,1,4,10,12,17);B=(0,1,8,11,13,17)
def ac(S,mask=False):
 return collections.Counter({d:sum(((x+1)*(y+1) if mask else 1) for x in S for y in S if x-y==d) for d in range(-17,18)})
target=ac(A)
matches=[(0,*s,17) for s in itertools.combinations(range(1,17),4) if ac((0,*s,17))==target]
out={'scope':'authored finite exact physical-model diagnostic; no measured diffraction, calibration, general uniqueness or novelty claim','a':A,'b':B,'same_uncoded_autocorrelation':target==ac(B),'same_uncoded_intensity_all_q':'follows exactly from matching autocorrelation Fourier polynomial coefficients','translation_or_reflection_equivalent':A==B or A==tuple(sorted(17-x for x in B)),'complete_finite_baseline_candidates':1820,'complete_finite_baseline_matches':matches,'added_linear_amplitude_mask_separates_pair':ac(A,True)!=ac(B,True),'ordinary_coded_diffraction_prior_art':'Candes, Li, Soltanolkotabi, 2013 report/2015 article; candidate does not invent coded diffraction','physical_error_bound':'UNKNOWN','cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,'wall_seconds':time.perf_counter()-t}
Path(__file__).with_name('RESULT.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
