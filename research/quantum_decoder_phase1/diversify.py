"""Bounded non-oracle repair: force competing measured logical parities.
This is candidate discovery, not an assumption that true logical bits are known.
"""
import numpy as np,stim,tesseract_decoder as td
from kernel import mask,bits
class ParityDiversifier:
 def __init__(self,normalized_dem,num_logicals,detectors):
  self.decoders=[];self.detectors=detectors
  for logical in range(num_logicals):
   augmented=stim.DetectorErrorModel()
   for inst in normalized_dem.flattened():
    if inst.type=='error':
     targets=inst.targets_copy()
     if sum(t.is_logical_observable_id() and t.val==logical for t in targets)%2:
      targets.append(stim.target_relative_detector_id(detectors))
     augmented.append('error',inst.args_copy(),targets)
    else:augmented.append(inst)
   augmented.append('detector',[],[stim.target_relative_detector_id(detectors)])
   self.decoders.append(td.tesseract.TesseractConfig(augmented,merge_errors=False,det_beam=10,pqlimit=10000,beam_climbing=True).compile_decoder())
 def candidates(self,syndrome,k,pool):
  _,base,_=k.decide(pool);s=mask(syndrome.nonzero()[0]);out=set();invalid=0
  # Fixed work: two adjacent logical checks selected by a syndrome-only hash.
  n=len(self.decoders);first=(s^(s>>64)^(s>>128))%n
  for logical in [first,(first+1)%n]:
   desired=1-((base>>logical)&1)
   aug=np.append(syndrome,bool(desired))
   candidate=mask(self.decoders[logical].decode_to_errors(aug,0,10))
   if k.syndrome(candidate)==s and ((k.logical(candidate)>>logical)&1)==desired:out.add(candidate)
   else:invalid+=1
  return out,invalid
