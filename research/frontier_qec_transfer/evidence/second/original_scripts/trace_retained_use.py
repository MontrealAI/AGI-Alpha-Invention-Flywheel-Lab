"""Descriptive public-fixture call trace; no source edits or acceptance changes."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
import numpy as np
HERE=Path(__file__).resolve().parent


def main():
    manifest=json.loads(Path(sys.argv[1]).read_text());root=Path(manifest['package_root']).resolve()
    for name,digest in manifest['source_hashes'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen package mismatch')
    dependency=(root/'recovery.py').resolve();entry=root/manifest['entry']
    sys.path.insert(0,str(HERE.parent/'public'))
    from second_public_fixtures import pollatsek_ruskai_7,pauli_hypotheses
    n,code=pollatsek_ruskai_7();hypotheses=pauli_hypotheses(n)
    calls={name:0 for name in ('Recovery.__init__','Recovery.kraus','Recovery.encode','Recovery.recover')}
    def profiler(frame,event,arg):
        if event=='call' and frame.f_code.co_filename==str(dependency):
            name=frame.f_code.co_qualname
            if name in calls:calls[name]+=1
    with tempfile.TemporaryDirectory(prefix='frontier-retained-trace-cache-') as cache:
        sys.pycache_prefix=cache;sys.path.insert(0,str(root))
        spec=importlib.util.spec_from_file_location('qualified_successor_for_use_trace',entry)
        module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        start=time.perf_counter();cpu=time.process_time()
        sys.setprofile(profiler)
        try:experiment=module.NoiseExperiment(n,code,hypotheses)
        finally:sys.setprofile(None)
        elapsed=time.perf_counter()-start;process_cpu=time.process_time()-cpu
        response=np.asarray(experiment.response_matrix(),float)
        info=experiment.identifiability()
    unchanged={name:hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
               for name,digest in manifest['source_hashes'].items()}
    result={'schema':'frontier.retained_dependency.executed_use.v1',
            'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'role':'Descriptive public-fixture trace after qualification; no changed source, acceptance or constructor feedback.',
            'source_hashes':manifest['source_hashes'],'phase':'NoiseExperiment constructor only',
            'fixture':'public Pollatsek-Ruskai7 with all22 Pauli hypotheses',
            'public_api_calls_into_exact_recovery_source':calls,
            'produced_response_shape':list(response.shape),'produced_identifiability_rank':info['rank'],
            'source_files_unchanged':unchanged,'profiled_wall_seconds':elapsed,'profiled_cpu_seconds':process_cpu,
            'inference':'Observed calls establish actual use of the retained constructor and exported recovery operators in constructing this successor instance. They do not by themselves establish a causal timing benefit or full economic advantage.'}
    output=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else HERE/'retained_functional_use_trace.json'
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'calls':calls,'response_shape':list(response.shape),'rank':info['rank'],
                      'all_sources_unchanged':all(unchanged.values())}))


if __name__=='__main__':main()
