"""Independent physical validation of constructed noise-identification experiments."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import resource
import sys
import time
import traceback
import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import first_physics as fp
TOL=2e-8
INFERENCE_TOL=2e-6


def rank_from_values(values):
    return int(np.count_nonzero(np.asarray(values)>1e-9*max(1,float(np.max(values)))))


def load_hypotheses(case):
    return [{'name':h['name'],'qubit':h['qubit'],
             'kraus':[fp.load_complex(a) for a in h['kraus']]} for h in case['hypotheses']]


def physical_oracle(case):
    s=fp.system(case|{'channels':case['hypotheses']})
    hypotheses=load_hypotheses(case)
    outputs=[]
    for hypothesis in hypotheses:
        x=np.zeros((len(s['coordinates']),len(hypothesis['kraus'])),complex)
        for column,kraus in enumerate(hypothesis['kraus']):
            state=fp.local(s['code'][0],s['n'],hypothesis['qubit'],kraus)
            for word,amplitude in state.items():x[s['index'][word],column]=amplitude
        outputs.append(x)
    gram=np.empty((len(outputs),len(outputs)),float)
    for i,left in enumerate(outputs):
        for j,right in enumerate(outputs):gram[i,j]=float(np.sum(abs(left.conj().T@right)**2))
    eigenvalues=np.linalg.eigvalsh((gram+gram.T)/2)
    available_rank=rank_from_values(eigenvalues)
    s.update({'hypotheses':hypotheses,'density_outputs':outputs,'density_gram':gram,
              'available_rank':available_rank,'density_gram_eigenvalues':eigenvalues})
    return s


def measurement_certificate(experiment,s):
    exported=experiment.measurement_operators()
    if not isinstance(exported,(list,tuple)) or not exported:
        raise TypeError('Measurement operators must be a nonempty list')
    operators=[]
    for operator in exported:
        if len(operator)!=s['k']:raise ValueError('Incorrect measurement operator row count')
        operators.append([fp.valid_state(row,s['n']) for row in operator])
    coordinates=sorted(set(s['coordinates']).union(*(row for op in operators for row in op)))
    index={w:i for i,w in enumerate(coordinates)}
    matrix=np.zeros((len(operators)*s['k'],len(coordinates)),complex)
    for outcome,operator in enumerate(operators):
        for row,entries in enumerate(operator):
            for word,coefficient in entries.items():matrix[outcome*s['k']+row,index[word]]=coefficient
    u=np.zeros((len(coordinates),s['rank']),complex)
    b=np.zeros((len(coordinates),s['b'].shape[1]),complex)
    destination=[index[w] for w in s['coordinates']]
    u[destination]=s['subspace'];b[destination]=s['b']
    compressed=matrix@u
    support_residual=float(np.linalg.norm(matrix-compressed@u.conj().T))
    completeness=float(np.linalg.norm(compressed.conj().T@compressed-np.eye(s['rank']),ord=2))
    fp.assert_small(support_residual,'Measurement leakage outside correctable span')
    fp.assert_small(completeness,'Measurement completeness on correctable span')
    images=(matrix@b).reshape(len(operators),s['k'],len(s['errors']),s['k'])
    scalars=np.trace(images,axis1=1,axis2=3)/s['k']
    preservation=float(np.max(abs(images-np.einsum('oa,ij->oiaj',scalars,np.eye(s['k'])))))
    fp.assert_small(preservation,'Outcome-by-outcome logical nondisturbance')
    fp.assert_small(np.max(abs(np.sum(abs(scalars)**2,axis=0)-1)),
                    'No loss on supported Pauli errors')
    # The first two bounds jointly establish full-space contraction and the
    # classical erasure completion without forming a large ambient operator.
    return {'matrix':matrix,'index':index,'coordinates':coordinates,'outcomes':len(operators),
            'metrics':{'support_residual':support_residual,'completeness_residual':completeness,
                       'logical_nondisturbance_residual':preservation,
                       'contraction_upper_bound':float((np.sqrt(1+completeness)+support_residual)**2)}}


def output_amplitudes(certificate,s,state_columns):
    x=np.zeros((len(certificate['coordinates']),state_columns.shape[1]),complex)
    x[[certificate['index'][w] for w in s['coordinates']],:]=state_columns
    return (certificate['matrix']@x).reshape(certificate['outcomes'],s['k'],state_columns.shape[1])


def validate_response(experiment,certificate,s):
    response=np.asarray(experiment.response_matrix(),float)
    expected=np.column_stack([np.sum(abs(output_amplitudes(certificate,s,x))**2,axis=(1,2))
                              for x in s['density_outputs']])
    if response.shape!=expected.shape or not np.all(np.isfinite(response)):
        raise ValueError('Invalid response matrix shape or values')
    fp.assert_small(np.max(abs(response-expected)),'Physical response matrix')
    fp.assert_small(max(0,-float(response.min())),'Negative response probability')
    fp.assert_small(np.max(abs(response.sum(axis=0)-1)),'Response column mass')
    _,singular,vt=np.linalg.svd(expected,full_matrices=False)
    rank=rank_from_values(singular)
    if rank!=s['available_rank']:
        raise AssertionError(f'Measurement rank {rank} does not attain physical density rank {s["available_rank"]}')
    projector=vt[:rank].T@vt[:rank]
    info=experiment.identifiability()
    if info['rank']!=rank or bool(info['unique'])!=(rank==expected.shape[1]):
        raise AssertionError('Incorrect rank or uniqueness claim')
    returned_projector=np.asarray(info['identifiable_projector'],float)
    if returned_projector.shape!=projector.shape or not np.all(np.isfinite(returned_projector)):
        raise ValueError('Invalid identifiable projector')
    fp.assert_small(np.max(abs(returned_projector-projector)),'Identifiable subspace projector')
    return {'response':expected,'projector':projector,'rank':rank,'unique':rank==expected.shape[1],
            'smallest_nonzero_response_singular_value':float(singular[rank-1])}


def check_logical_state(certificate,s,info,probe,hindex,mass):
    vector=np.sqrt(mass)*probe
    encoded=fp.encode(s['code'],vector)
    hypothesis=s['hypotheses'][hindex]
    x=np.zeros((len(s['coordinates']),len(hypothesis['kraus'])),complex)
    for column,kraus in enumerate(hypothesis['kraus']):
        branch=fp.local(encoded,s['n'],hypothesis['qubit'],kraus)
        for word,amplitude in branch.items():x[s['index'][word],column]=amplitude
    y=output_amplitudes(certificate,s,x)
    actual=np.einsum('olk,omk->olm',y,y.conj())
    expected=info['response'][:,hindex,None,None]*np.outer(vector,vector.conj())[None,:,:]
    fp.assert_small(np.max(abs(actual-expected)),'Logical state and probability preserved in each outcome')
    fp.assert_small(np.max(abs(actual.sum(axis=0)-np.outer(vector,vector.conj()))),
                    'Unconditional unknown logical state')
    fp.assert_small(abs(float(np.sum(abs(x)**2))-mass),'Physical channel raw input mass')


def estimator_result(experiment,info,observations,target_weights=None):
    observations=np.asarray(observations,float)
    estimate=experiment.estimate(observations.copy())
    h=info['response'].shape[1]
    weights=np.asarray(estimate['mixture_weights'],float)
    coordinates=np.asarray(estimate['identifiable_coordinates'],float)
    fitted=np.asarray(estimate['predicted_frequencies'],float)
    if weights.shape!=(h,) or coordinates.shape!=(h,) or fitted.shape!=(len(observations),):
        raise ValueError('Invalid estimator output shape')
    if not all(np.all(np.isfinite(a)) for a in (weights,coordinates,fitted)):
        raise ValueError('Nonfinite estimator output')
    fp.assert_small(max(0,-float(weights.min())),'Negative mixture weight',INFERENCE_TOL)
    fp.assert_small(abs(float(weights.sum())-1),'Mixture normalization',INFERENCE_TOL)
    if bool(estimate['unique'])!=info['unique']:raise AssertionError('Estimator uniqueness claim is wrong')
    fp.assert_small(np.max(abs(coordinates-info['projector']@weights)),
                    'Estimator identifiable-coordinate consistency',INFERENCE_TOL)
    fp.assert_small(np.max(abs(fitted-info['response']@weights)),
                    'Estimator predicted-frequency consistency',INFERENCE_TOL)
    output={'fit_linf':float(np.max(abs(fitted-observations/observations.sum())))}
    if target_weights is not None:
        target_weights=np.asarray(target_weights,float)
        coordinate_error=float(np.max(abs(coordinates-info['projector']@target_weights)))
        output['identifiable_coordinate_linf_error']=coordinate_error
        fp.assert_small(coordinate_error,'Noiseless identifiable inference',INFERENCE_TOL)
        fp.assert_small(np.max(abs(fitted-info['response']@target_weights)),
                        'Noiseless fitted observation model',INFERENCE_TOL)
        if info['unique']:
            fp.assert_small(np.max(abs(weights-target_weights)),'Unique mixture inference',INFERENCE_TOL)
    output.update({'weights':weights,'coordinates':coordinates,'fitted':fitted})
    return output


def run_case(case,Experiment,rec,secondary):
    s=physical_oracle(case); prefix=case['id']
    start=time.perf_counter()
    experiment=rec.run(prefix+'/construct',lambda:Experiment(s['n'],[dict(c) for c in s['code']],
             [{'name':h['name'],'qubit':h['qubit'],'kraus':[a.copy() for a in h['kraus']]}
              for h in s['hypotheses']]))
    constructor_wall=time.perf_counter()-start
    if experiment is None:return {'id':prefix,'construction_failed':True}
    certificate=rec.run(prefix+'/global_instrument',lambda:measurement_certificate(experiment,s))
    if certificate is None:return {'id':prefix,'instrument_failed':True}
    info=rec.run(prefix+'/physical_response_and_identifiability',lambda:validate_response(experiment,certificate,s))
    if info is None:return {'id':prefix,'response_or_identifiability_failed':True}
    for pindex,packed in enumerate(case['logical_probes']):
        probe=fp.load_complex(packed)
        for hindex in (0,len(s['hypotheses'])//2,len(s['hypotheses'])-1):
            for mass in (1.0,.37):
                rec.run(f'{prefix}/unknown_logical/{pindex}/{hindex}/{mass}',
                        lambda probe=probe,hindex=hindex,mass=mass:
                        check_logical_state(certificate,s,info,probe,hindex,mass))
    ideal_metrics=[]
    for index,weights in enumerate(case['mixtures']):
        truth=np.asarray(weights,float);probabilities=info['response']@truth
        result=rec.run(f'{prefix}/ideal_inference/{index}',
                       lambda truth=truth,probabilities=probabilities:
                       estimator_result(experiment,info,probabilities,truth))
        if result is not None:
            ideal_metrics.append({k:v for k,v in result.items() if k not in ('weights','coordinates','fitted')})
    def zero_counts():
        try:experiment.estimate(np.zeros(certificate['outcomes']))
        except Exception:return True
        raise AssertionError('Zero total observations were not rejected')
    rec.run(prefix+'/zero_observations',zero_counts)
    rng=np.random.default_rng(case['finite_counts_seed'])
    for replicate in range(case['finite_counts_replicates']):
        truth=np.asarray(case['mixtures'][replicate],float)
        probabilities=np.maximum(info['response']@truth,0);probabilities/=probabilities.sum()
        counts=rng.multinomial(case['finite_counts_shots'],probabilities)
        count_hash=hashlib.sha256(counts.astype('<i8').tobytes()).hexdigest()
        start=time.perf_counter()
        try:
            estimate=estimator_result(experiment,info,counts)
            row={'id':prefix+f'/finite_counts/{replicate}','status':'completed',
                 'shots':case['finite_counts_shots'],'counts_sha256':count_hash,
                 'identifiable_coordinate_linf_error':float(np.max(abs(estimate['coordinates']-info['projector']@truth))),
                 'predicted_probability_linf_error':float(np.max(abs(estimate['fitted']-probabilities))),
                 'mixture_weight_linf_error':float(np.max(abs(estimate['weights']-truth))) if info['unique'] else None}
        except Exception as exc:
            row={'id':prefix+f'/finite_counts/{replicate}','status':'error',
                 'shots':case['finite_counts_shots'],'counts_sha256':count_hash,
                 'error':type(exc).__name__+': '+str(exc)}
        row['wall_seconds']=time.perf_counter()-start;secondary.append(row)
    return {'id':prefix,'n':s['n'],'hypotheses':len(s['hypotheses']),
            'syndrome_vector_rank':s['gram_rank'],'intrinsic_density_rank':s['available_rank'],
            'measurement_response_rank':info['rank'],'unique':info['unique'],
            'measurement_outcomes':certificate['outcomes'],'constructor_wall_seconds':constructor_wall,
            'certificate':certificate['metrics'],
            'smallest_nonzero_response_singular_value':info['smallest_nonzero_response_singular_value'],
            'ideal_metrics':ideal_metrics}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('candidate',nargs='?')
    parser.add_argument('--output',required=True);parser.add_argument('--audit-inputs',action='store_true')
    args=parser.parse_args();wall=time.perf_counter();cpu=time.process_time()
    data=json.loads((HERE/'cases.json').read_text())
    result={'schema':'frontier.noise_experiment.qualification.v1',
            'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'physics_dependency_sha256':hashlib.sha256((HERE/'first_physics.py').read_bytes()).hexdigest(),
            'frozen_inputs_sha256':hashlib.sha256((HERE/'cases.json').read_bytes()).hexdigest(),
            'scope':'Independent non-adversarial procedural black-box qualification; ordinary shared host.'}
    if args.audit_inputs:
        rows=[]
        for case in data['cases']:
            s=physical_oracle(case)
            nonzero=s['density_gram_eigenvalues'][s['density_gram_eigenvalues']>1e-9]
            rows.append({'id':case['id'],'hypotheses':len(s['hypotheses']),
                         'syndrome_vector_rank':s['gram_rank'],'density_rank':s['available_rank'],
                         'smallest_nonzero_density_gram_eigenvalue':float(nonzero[0]),
                         'kl_residual':s['kl_residual']})
        result.update({'input_audit':rows,'pass':True})
    else:
        path=Path(args.candidate).resolve();result['candidate_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        spec=importlib.util.spec_from_file_location('qualified_noise_experiment',path)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
        sys.path.insert(0,str(path.parent));rec=fp.Recorder();secondary=[];cases=[]
        loaded=rec.run('module_import',lambda:spec.loader.exec_module(module) or True)
        if loaded:
            for case in data['cases']:
                try:cases.append(run_case(case,module.NoiseExperiment,rec,secondary))
                except Exception as exc:
                    rec.records.append({'id':case['id']+'/checker_or_unexpected_error','pass':False,
                                        'error':type(exc).__name__+': '+str(exc),
                                        'traceback':traceback.format_exc()})
        result.update({'cases':cases,'primary_checks':rec.records,'secondary_count_trials':secondary,
                       'passed_checks':sum(row['pass'] for row in rec.records),'total_checks':len(rec.records),
                       'pass':bool(loaded) and len(cases)==len(data['cases']) and all(row['pass'] for row in rec.records),
                       'secondary_note':'Finite-count errors are descriptive; not substituted for primary acceptance or used to repair candidates.'})
    result.update({'wall_seconds':time.perf_counter()-wall,'cpu_seconds':time.process_time()-cpu,
                   'maximum_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   'finished_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('pass','wall_seconds','cpu_seconds','maximum_rss_kib')}
                    |{k:result[k] for k in ('passed_checks','total_checks') if k in result}))


if __name__=='__main__':main()
