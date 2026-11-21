"""Operational ambiguity witness for the first asset's unchanged public readout.

This is a post-freeze descriptive value demonstration, never a new acceptance
test or a source of feedback to second constructors.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import qualify as oracle


def main():
    path=Path(sys.argv[1]).resolve()
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!='f8638af7b2532f8c2161fefe2169bb91788c9fc3a5e3321cf7a05ec717f7c134':
        raise ValueError('Expected the unchanged qualified first asset')
    spec=importlib.util.spec_from_file_location('frozen_first_for_readout_witness',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    case=json.loads((HERE/'cases.json').read_text())['cases'][0]
    s=oracle.physical_oracle(case);recovery=module.Recovery(s['n'],s['code'])
    class Adapter:
        def measurement_operators(self):return recovery.kraus()
    certificate=oracle.measurement_certificate(Adapter(),s)
    response=np.column_stack([np.sum(abs(oracle.output_amplitudes(certificate,s,x))**2,axis=(1,2))
                              for x in s['density_outputs']])
    _,singular,vt=np.linalg.svd(response)
    if oracle.rank_from_values(singular)==response.shape[1]:raise AssertionError('No ambiguity exists')
    direction=vt[-1]
    center=np.full(response.shape[1],.1/(response.shape[1]-1));center[0]=.9
    amplitude=.8*min(center[i]/abs(direction[i]) for i in range(len(center)) if abs(direction[i])>1e-12)
    left=center+amplitude*direction;right=center-amplitude*direction
    difference=left-right
    result={'schema':'frontier.raw_readout_ambiguity.v1','role':'Descriptive public-fixture value witness; not an added acceptance test.',
            'first_asset_sha256':digest,'public_code':'Pollatsek-Ruskai7','hypothesis_order':[h['name'] for h in s['hypotheses']],
            'left_mixture':left.tolist(),'right_mixture':right.tolist(),
            'existing_readout_rank':oracle.rank_from_values(singular),
            'intrinsic_density_rank':s['available_rank'],
            'existing_readout_probability_linf_difference':float(np.max(abs(response@difference))),
            'physical_noisy_density_hilbert_schmidt_distance':float(np.sqrt(difference@s['density_gram']@difference)),
            'mixture_total_variation_distance':float(.5*np.sum(abs(difference))),
            'weight_sums':[float(left.sum()),float(right.sum())],
            'minimum_weights':[float(left.min()),float(right.min())]}
    (HERE/'raw_readout_ambiguity.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('existing_readout_rank','intrinsic_density_rank',
                     'existing_readout_probability_linf_difference','physical_noisy_density_hilbert_schmidt_distance',
                     'mixture_total_variation_distance')}))


if __name__=='__main__':main()
