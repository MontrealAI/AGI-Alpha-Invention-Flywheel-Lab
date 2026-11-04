"""Compile observed KTC receipts and a figure; no reconstruction or fitting."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
import scipy.io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap,BoundaryNorm
ROOT=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 validation=json.loads((ROOT/'original_score_validation.json').read_text())
 assert validation['passed'], 'Independent original-score equivalence must pass first'
 scores=[json.loads((ROOT/'scores_fast'/f'{kind}-{level}.json').read_text()) for level in [1,4,7] for kind in ['limited','full']]
 receipts=[json.loads((ROOT/'receipts'/f'{kind}-{level}.json').read_text()) for level in [1,4,7] for kind in ['limited','full']]
 provenance=[]
 for level in [1,4,7]:
  d=ROOT/'data';lp=d/'EvaluationData'/'evaluation_datasets'/f'level{level}'/'data1.mat';fp=d/'EvaluationData_full'/'evaluation_datasets'/f'level{level}'/'data1.mat'
  l=scipy.io.loadmat(lp)['Uel'];f=scipy.io.loadmat(fp)['Uel'];mask=np.isfinite(l)
  t1=d/'EvaluationData'/'GroundTruths'/f'level_{level}'/'1_true.mat';t2=d/'EvaluationData_full'/'GroundTruths'/f'level_{level}'/'1_true.mat'
  assert np.array_equal(l[mask],f[mask]);assert np.array_equal(scipy.io.loadmat(t1)['truth'],scipy.io.loadmat(t2)['truth'])
  provenance.append({'level':level,'limited_observed_entries':int(mask.sum()),'full_observed_entries':int(np.isfinite(f).sum()),'common_observed_values_identical':True,'corrected_ground_truth_equal':True})
 improvements={str(level):next(s['official_score'] for s in scores if s['level']==level and s['observations']=='full')-next(s['official_score'] for s in scores if s['level']==level and s['observations']=='limited') for level in [1,4,7]}
 r={'schema':'omega/ktc-natural-residual/v1','protocol_sha256':sha(ROOT/'PROTOCOL.md'),'preregistration_url':'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/pull/206','preregistration_public_time':'2026-11-03T23:08:30Z','archives':[{ 'name':n,'sha256':sha(ROOT/n),'bytes':(ROOT/n).stat().st_size} for n in ['Codes_Python.zip','EvaluationData.zip','EvaluationData_full.zip']], 'receipts':receipts,'scores':scores,'paired_input_validation':provenance,'full_minus_limited_official_score':improvements,'all_three_improve':all(x>0 for x in improvements.values()),'registered_hypothesis_verdict':'REJECTED: level1 ties; its full/limited observations are identical, so the all-three strict-improvement criterion was a flawed design choice. Preserved without post-hoc weakening.','scorer_equivalence':validation,'stronger_exploratory_control':[json.loads((ROOT/'scores_fast'/f'cuqi3-{level}.json').read_text()) for level in [1,4,7]],'stronger_control_receipts':[json.loads((ROOT/'receipts'/f'cuqi3-{level}.json').read_text()) for level in [1,4,7]],'scope':'Retrospective numerical reconstruction on physical measured data; additional full observations are privileged information, not an equal-information algorithm comparison; no physical intervention, commercial demand or autonomous discovery established.'}
 (ROOT/'RESULT.json').write_text(json.dumps(r,indent=2))
 cmap=ListedColormap(['#f3f4f5','#2166ac','#f28e2b']);norm=BoundaryNorm([-.5,.5,1.5,2.5],3)
 fig,axes=plt.subplots(3,3,figsize=(10,10.7),layout='constrained')
 for row,level in enumerate([1,4,7]):
  truth=scipy.io.loadmat(ROOT/'data'/'EvaluationData'/'GroundTruths'/f'level_{level}'/'1_true.mat')['truth']
  for col,kind in enumerate(['truth','limited','full']):
   a=truth if kind=='truth' else scipy.io.loadmat(ROOT/'outputs'/f'{kind}-{level}'/'1.mat')['reconstruction']
   axes[row,col].imshow(a,cmap=cmap,norm=norm,interpolation='nearest');axes[row,col].set_xticks([]);axes[row,col].set_yticks([])
   label=f'Level {level} A · corrected reference' if kind=='truth' else f'{kind.title()} observations · SSIM {next(s["official_score"] for s in scores if s["level"]==level and s["observations"]==kind):.4f}'
   axes[row,col].set_title(label,fontsize=10)
 fig.suptitle('What additional physical observations change\nUnmodified KTC organizer reconstruction; three preregistered phantoms',fontsize=15)
 fig.supxlabel('Blue: resistive inclusion · Orange: conductive inclusion · Gray: background\nFull arm has more measured information at levels 4 and 7; this is not algorithm superiority.\nData/code: Räsänen et al., KTC 2023 corrected v3, DOI 10.5281/zenodo.10986692, CC BY 4.0.',fontsize=9)
 fig.savefig(ROOT/'reconstructions.svg');fig.savefig(ROOT/'reconstructions.png',dpi=140);plt.close(fig)
 print(json.dumps({'improvements':improvements,'all_three_improve':r['all_three_improve']}))
if __name__=='__main__':main()
