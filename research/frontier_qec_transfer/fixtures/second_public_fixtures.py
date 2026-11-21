"""Public data and visible checks for nondestructive noise-identification design."""
import numpy as np
from public_fixtures import pollatsek_ruskai_7, shor_9


def pauli_hypotheses(n):
    paulis={'X':np.array([[0,1],[1,0]],complex),
            'Y':np.array([[0,-1j],[1j,0]],complex),
            'Z':np.array([[1,0],[0,-1]],complex)}
    out=[{'name':'identity','qubit':0,'kraus':[np.eye(2,dtype=complex)]}]
    for q in range(n):
        for name,matrix in paulis.items():
            out.append({'name':f'{name}{q}','qubit':q,'kraus':[matrix.copy()]})
    return out


def development_example(experiment_class):
    for factory,available_rank in ((pollatsek_ruskai_7,22),(shor_9,22)):
        n,code=factory()
        models=pauli_hypotheses(n)
        experiment=experiment_class(n,code,models)
        response=np.asarray(experiment.response_matrix(),float)
        assert response.ndim==2 and response.shape[1]==len(models)
        assert np.min(response)>=-2e-8
        assert np.max(abs(response.sum(axis=0)-1))<2e-8
        info=experiment.identifiability()
        assert info['rank']==available_rank
        assert info['unique']==(available_rank==len(models))
        weights=np.arange(1,len(models)+1,dtype=float)
        weights/=weights.sum()
        estimate=experiment.estimate(response@weights)
        projector=np.asarray(info['identifiable_projector'],float)
        assert np.max(abs(np.asarray(estimate['identifiable_coordinates'])-projector@weights))<2e-6
        assert np.max(abs(np.asarray(estimate['predicted_frequencies'])-response@weights))<2e-6
    return True
