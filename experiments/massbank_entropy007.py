import argparse,hashlib,importlib.metadata,itertools,json,time
from pathlib import Path
import ms_entropy
import numpy as np

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(data,output):
 if output.exists():raise FileExistsError(output)
 rows=json.loads((data/'observations.json').read_text());ad=json.loads((data/'ADMISSION.json').read_text());ids=ad['identities'];energies=ad['energies'];lookup={(r['inchikey'],r['energy']):r for r in rows}
 for row in rows:
  if digest(data/row['record_file'])!=row['sha256']:raise ValueError('record identity mismatch')
 start=time.perf_counter();cpu=time.process_time();results=[]
 for energy in energies:
  matrix=[[float(ms_entropy.calculate_entropy_similarity(lookup[i,energy]['peaks'],lookup[j,energy]['peaks'],ms2_tolerance_in_da=0.02,clean_spectra=True))for j in ids]for i in ids]
  off=[matrix[i][j]for i in range(len(ids))for j in range(i+1,len(ids))]
  results.append({'energy':energy,'matrix':matrix,'maximum_wrong_identity_similarity':max(off),'reference_self_match_all_unique':all(matrix[i][i]>max(matrix[i][j]for j in range(len(ids))if j!=i)+1e-8 for i in range(len(ids)))})
 pairs=list(itertools.combinations(range(len(ids)),2));frontier=[]
 for threshold in [0.90,0.95,0.96,0.98,0.99]:
  best=None
  for count in range(1,len(energies)+1):
   for panel in itertools.combinations(range(len(energies)),count):
    if all(any(results[k]['matrix'][i][j]<threshold for k in panel)for i,j in pairs):best=[energies[k]for k in panel];break
   if best is not None:break
  frontier.append({'similarity_threshold':threshold,'ordinary_exhaustive_minimum_energy_panel':best,'count':len(best)if best else None,'meaning':'Exploratory numerical sensitivity only, not a calibrated measurement error or identification guarantee.'})
 summary={'type':'RETROSPECTIVE_REFERENCE_GEOMETRY_ONLY','packages':{m:importlib.metadata.version(m)for m in ['ms-entropy','numpy']},'input_sha256':digest(data/'observations.json'),'admission_sha256':digest(data/'ADMISSION.json'),'source_sha256':digest(Path(__file__)),'parameters':{'ms2_tolerance_in_da':0.02,'clean_spectra':True,'other_parameters':'maintainer defaults'},'identities':ids,'results':results,'all_energy_mean_similarity':np.mean([x['matrix']for x in results],axis=0).tolist(),'ordinary_exhaustive_panel_sensitivity':frontier,'wall_seconds':time.perf_counter()-start,'process_cpu_seconds':time.process_time()-cpu,'interpretation':'One higher recorded energy already distinguishes the exact reference profiles. This eliminates the noiseless closed-library enabling-gap hypothesis. Self-matching is not fresh-unknown accuracy. Independent acquisitions, noise robustness, current complete LFP pipeline, physical acquisition costs and commercial feasibility remain unqualified. Energy-setting count does not imply injection/scan count.'}
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({'decision':'RETAIN_INCUMBENT_AND_PIVOT','single_energy_unique':[r['energy']for r in results if r['reference_self_match_all_unique']],'sensitivity':frontier,'wall_seconds':summary['wall_seconds']}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.data,a.output)
