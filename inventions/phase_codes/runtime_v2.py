"""Version2: exact eligibility for the ideal orthogonal-sector recovery.

The broad code certificate admits common nonzero moments and degenerate error
spaces. This recovery implementation supports the narrower zero-moment class.
Unsupported is not mathematically invalid. Frozen runtime.py remains historical.
"""
from __future__ import annotations
import hashlib, importlib.util, json, pathlib
import numpy as np

HERE=pathlib.Path(__file__).resolve().parent
def _pinned(name,path,digest):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest: raise ValueError('PINNED_DEPENDENCY_CHANGED')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

_old=_pinned('phase_frozen_runtime',HERE/'runtime.py','740de7bb097f3ca3e23c6ee2142ae2559bd8622a0aa3e76c20e5fa28f7bc523e')
_cert=_pinned('phase_frozen_algebra',HERE/'verification/certify.py','83391efeb99982c276e8662ead9d706be0c7ce02f8f0281c4e072d012ffe5b4d')
pauli=_old.pauli
damping=_old.damping

class Instrument(_old.Instrument):
    def __init__(self,path,expected_sha256):
        path=pathlib.Path(path)
        if path.stat().st_size>4*1024**2: raise ValueError('RECOVERY_INPUT_RESOURCE_BOUND')
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_sha256: raise ValueError('CANDIDATE_IDENTITY_MISMATCH')
        data=json.loads(raw,object_pairs_hook=_cert.unique_object,
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
        if type(data) is not dict: raise ValueError('RECOVERY_INPUT_SHAPE')
        n=data.get('n')
        if type(n) is not int or not 2<=n<=20: raise ValueError('RECOVERY_INPUT_RESOURCE_BOUND')
        fields=['n','physical_weights','global_phase_exponent','logical_order','codewords']
        try: projection={k:data[k] for k in fields}
        except KeyError as exc: raise ValueError('RECOVERY_INPUT_SHAPE') from exc
        exact=_cert.certify(json.dumps(projection).encode())
        if exact['status']!='CERTIFIED_EXACT_ALGEBRA_ONLY': raise ValueError('ALGEBRAIC_CODE_NOT_CERTIFIED')
        if sum(exact['support_sizes'])>4096: raise ValueError('RECOVERY_INPUT_RESOURCE_BOUND')
        for moment in exact['exact_diagonal_moments']:
            if moment['values']!=['0']*4:
                raise ValueError('UNSUPPORTED_RECOVERY_CLASS_NONZERO_MOMENTS:'+moment['z_mask'])
        # Disjoint distance>=3 support and exactly zero weight1/2 moments imply
        # all {I,X_i,Y_i,Z_i}|logical_j> are mutually orthonormal. No numerical
        # tolerance is used to turn nonzero moments into eligible zeros.
        super().__init__(path,expected_sha256)
        self.recovery_contract={'version':2,'algebraically_valid':True,
            'runtime_class':'EXACT_ZERO_MOMENTS_ORTHOGONAL_SINGLE_ERROR_SECTORS',
            'general_degenerate_recovery_supported':False,'renormalizes_output':False}

    def recover(self,branches):
        if type(branches) not in (list,tuple) or not 1<=len(branches)<=4096:
            raise ValueError('BAD_KRAUS_BRANCHES')
        for state in branches:
            if type(state) is not dict: raise ValueError('BAD_PHYSICAL_STATE')
            for word,amp in state.items():
                if type(word) is not int or not 0<=word<(1<<self.n): raise ValueError('BAD_PHYSICAL_WORD')
                if not np.isfinite(complex(amp)): raise ValueError('NONFINITE_PHYSICAL_AMPLITUDE')
        result=super().recover(branches)
        mass=result['input_probability'];trace=result['correctable_probability']
        if not np.isfinite(mass) or not np.isfinite(result['logical_density']).all(): raise ValueError('NONFINITE_RECOVERY')
        if trace>mass+1e-10*max(1.,mass) or trace < -1e-10:
            raise ValueError('RECOVERY_PROBABILITY_VIOLATION')
        return result
