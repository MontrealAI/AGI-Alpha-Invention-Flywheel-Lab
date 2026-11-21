"""Post-qualification descriptive demonstration of the fixed ambiguity witness."""
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
    manifest=json.loads(Path(sys.argv[1]).read_text())
    root=Path(manifest['package_root']).resolve()
    for name,expected in manifest['source_hashes'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Frozen package identity mismatch')
    path=root/manifest['entry'];sys.path.insert(0,str(root))
    spec=importlib.util.spec_from_file_location('qualified_successor_for_witness',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    case=json.loads((HERE/'cases.json').read_text())['cases'][0]
    s=oracle.physical_oracle(case)
    start=time.perf_counter()
    experiment=module.NoiseExperiment(s['n'],s['code'],s['hypotheses'])
    certificate=oracle.measurement_certificate(experiment,s)
    info=oracle.validate_response(experiment,certificate,s)
    witness=json.loads((HERE/'raw_readout_ambiguity.json').read_text())
    left=np.asarray(witness['left_mixture']);right=np.asarray(witness['right_mixture'])
    p=info['response']@left;q=info['response']@right
    estimated_left=oracle.estimator_result(experiment,info,p,left)
    estimated_right=oracle.estimator_result(experiment,info,q,right)
    result={'schema':'frontier.qualified_successor.ambiguity_resolution.v1',
            'role':'Descriptive post-qualification value demonstration; no new primary gate or constructor feedback.',
            'candidate_source_sha256':manifest['source_hashes'][manifest['entry']],
            'dependency_source_sha256':{k:v for k,v in manifest['source_hashes'].items() if k!=manifest['entry']},
            'witness_sha256':hashlib.sha256((HERE/'raw_readout_ambiguity.json').read_bytes()).hexdigest(),
            'previous_readout_rank':witness['existing_readout_rank'],'constructed_readout_rank':info['rank'],
            'previous_outcome_probability_linf_difference':witness['existing_readout_probability_linf_difference'],
            'constructed_outcome_probability_linf_difference':float(np.max(abs(p-q))),
            'constructed_outcome_total_variation_distance':float(.5*np.sum(abs(p-q))),
            'ideal_left_weight_linf_error':float(np.max(abs(estimated_left['weights']-left))),
            'ideal_right_weight_linf_error':float(np.max(abs(estimated_right['weights']-right))),
            'constructed_outcome_count':certificate['outcomes'],'previous_outcome_count':22,
            'logical_nondisturbance_residual':certificate['metrics']['logical_nondisturbance_residual'],
            'wall_seconds_including_physical_certificate':time.perf_counter()-start,
            'limitations':['Ideal probabilities, not observed hardware frequencies.','More measurement outcomes and unoptimized shot/circuit cost.','Established informationally complete measurement principles; no global novelty claim.']}
    output=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else HERE/'qualified_successor_ambiguity_resolution.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('previous_readout_rank','constructed_readout_rank',
             'constructed_outcome_total_variation_distance','ideal_left_weight_linf_error','ideal_right_weight_linf_error')}))


if __name__=='__main__':main()
