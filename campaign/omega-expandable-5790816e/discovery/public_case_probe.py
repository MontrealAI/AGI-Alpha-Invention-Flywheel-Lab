"""First eligible public DOT model; local registration precedes all queries."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def digest(raw): return hashlib.sha256(raw).hexdigest()


def unquote(value):
    if value is None: return None
    return json.loads(value) if value.startswith('"') else value


def read_model(path):
    import pydot
    graphs = pydot.graph_from_dot_file(str(path))
    if len(graphs) != 1: raise ValueError('one_graph_required')
    graph = graphs[0]
    nodes = {unquote(n.get_name()) for n in graph.get_nodes()}
    nodes -= {'', '\n', '\\n', 'node', 'edge', 'graph'}
    states = {n for n in nodes if not n.startswith('__start')}
    if not 1 <= len(states) <= 5: raise ValueError('state_bound_outside_registered_screen')
    table = {s: {} for s in states}; alphabet = set(); initials = []
    for edge in graph.get_edges():
        left, right = unquote(edge.get_source()), unquote(edge.get_destination())
        if left.startswith('__start'):
            initials.append(right); continue
        label = unquote(edge.get_label())
        if left not in states or right not in states or label is None or '/' not in label:
            raise ValueError('explicit_mealy_transition_required')
        symbol, output = (x.strip() for x in label.split('/', 1))
        if not symbol or symbol in table[left]: raise ValueError('distinct_deterministic_inputs_required')
        table[left][symbol] = (right, output); alphabet.add(symbol)
    if len(initials) != 1 or initials[0] not in states: raise ValueError('one_initial_required')
    if not 2 <= len(alphabet) <= 3: raise ValueError('alphabet_outside_registered_screen')
    if any(set(t) != alphabet for t in table.values()): raise ValueError('complete_machine_required')
    exhaustive = sum(len(alphabet)**n for n in range(2*len(states)))
    if exhaustive > 20000 or 2*(exhaustive+40) > 20000:
        raise ValueError('unchanged_query_budget_insufficient')
    return table, tuple(sorted(alphabet)), initials[0]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab-root',required=True);p.add_argument('--aalpy-root',required=True)
    p.add_argument('--registration',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();lab=Path(a.lab_root).resolve();upstream=Path(a.aalpy_root).resolve()
    registration=Path(a.registration).read_bytes()
    if digest(registration)!='714b0da386b4afeeafaf77ca0bf0248f28fe751e8d66e5590002497a0ad5a2c8':
        raise ValueError('EXACT_PRIOR_LOCAL_REGISTRATION_REQUIRED')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=upstream,text=True).strip()
    if commit!='4c7b4a8746460fd84eaccb48d4891e5e0ac90883' or subprocess.check_output(['git','status','--porcelain'],cwd=upstream,text=True):
        raise ValueError('EXACT_UNMODIFIED_PUBLIC_SOURCE_REQUIRED')
    expected_checker='1fd025189b6473a1a568b62a4273139819a8a26857ca7cb2f0dfb47a6cf7ebbf'
    if digest((lab/'omega/compatibility.py').read_bytes())!=expected_checker:
        raise ValueError('EXACT_UNCHANGED_LEARNER_AND_CHECKER_REQUIRED')
    sys.path[:0]=[str(lab),str(upstream)]
    spec=importlib.util.spec_from_file_location('specialist_dependency_guard',Path(__file__).with_name('aalpy_probe.py'))
    guards=importlib.util.module_from_spec(spec);spec.loader.exec_module(guards)
    dependencies=guards.dependency_identities()
    from omega.compatibility import ActiveLearner,buyer_contract,independent_acceptance,SCHEMA,RUNNER
    from aalpy.base import SUL
    from aalpy.learning_algs import run_Lstar
    from aalpy.oracles import WMethodEqOracle
    scan=[]; eligible=[]
    for path in sorted((upstream/'DotModels').rglob('*.dot')):
        relative=path.relative_to(upstream).as_posix()
        try:
            parsed=read_model(path)
            scan.append({'path':relative,'eligible':True,'states':len(parsed[0]),'alphabet':len(parsed[1])})
            eligible.append((path,parsed))
        except (ValueError,TypeError,IndexError,AttributeError) as exc:
            scan.append({'path':relative,'eligible':False,'reason':str(exc)})
    if not eligible: raise ValueError('NO_ELIGIBLE_PUBLIC_MODEL')
    path,(table,alphabet,initial)=eligible[0]
    selection={'registration_sha256':digest(registration),'path':path.relative_to(upstream).as_posix(),
               'model_sha256':digest(path.read_bytes()),'states':len(table),'alphabet':list(alphabet),
               'selection_scope':'FIRST_ELIGIBLE_CANONICAL_FILENAME_BEFORE_ORACLE_CALLS',
               'scan':scan}
    output=Path(a.output)
    selection_path=output.with_name(output.stem+'_SELECTION.json')
    if output.exists() or selection_path.exists(): raise ValueError('NEW_OUTPUT_PATH_REQUIRED')
    selection_path.write_text(json.dumps(selection,sort_keys=True,indent=2)+'\n')
    # No oracle callable or learner exists until the selection is durable.
    contract=buyer_contract('public-AALpy:'+commit+':'+selection['model_sha256'],list(alphabet),
        max_states=len(table),max_queries=20000,max_verification_queries=20000,
        assumptions={'deterministic':True,'reliable_reset':True,'state_bound_valid':True,'local_probe_authorized':True})
    def query(word):
        state=initial;out=[]
        for symbol in word:
            state,value=table[state][symbol];out.append(value)
        return tuple(out)
    class Counter:
        def __init__(self):self.calls=self.symbols=0
        def __call__(self,word):
            self.calls+=1;self.symbols+=len(word)
            if self.calls>20000:raise RuntimeError('QUERY_BUDGET_EXHAUSTED')
            return query(word)
    class WordSUL(SUL):
        def __init__(self,counter):super().__init__();self.counter=counter;self.prefix=()
        def pre(self):self.prefix=()
        def post(self):pass
        def query(self,word):
            self.num_queries+=1;self.num_steps+=len(word);return list(self.counter(tuple(word)))
        def step(self,symbol):self.prefix+=(symbol,);return self.counter(self.prefix)[-1]
    rows=[]
    for method in ('registered_learner','aalpy_lstar_wmethod'):
        counter=Counter()
        if method=='registered_learner':adapter=ActiveLearner(counter,contract).learn()
        else:
            sul=WordSUL(counter);oracle=WMethodEqOracle(list(alphabet),sul,max_number_of_states=len(table))
            learned=run_Lstar(list(alphabet),sul,oracle,'mealy',print_level=0)
            indices={state:i for i,state in enumerate(learned.states)}
            adapter={'schema':SCHEMA,'alphabet':list(alphabet),'initial':indices[learned.initial_state],
                'transitions':{str(indices[s]):{symbol:{'next':indices[s.transitions[symbol]],
                    'output':s.output_fun[symbol]} for symbol in alphabet} for s in learned.states}}
        checking=Counter();accepted=independent_acceptance(adapter,contract,checking)
        smoke=tuple(alphabet)*2
        with tempfile.TemporaryDirectory(prefix='omega-public-case-') as d:
            target=Path(d);(target/'adapter.json').write_text(json.dumps(adapter,sort_keys=True))
            (target/'runner.py').write_text(RUNNER)
            actual=subprocess.check_output([sys.executable,str(target/'runner.py'),*smoke],text=True).splitlines()
            if tuple(actual)!=query(smoke):raise ValueError('PORTABLE_PUBLIC_MODEL_SMOKE_MISMATCH')
        rows.append({'method':method,'accepted':accepted,'learning_oracle_calls':counter.calls,
            'learning_input_symbols':counter.symbols,'checking_oracle_calls':checking.calls,
            'checking_input_symbols':checking.symbols,'portable_smoke_oracle_calls':1,
            'portable_smoke_input_symbols':len(smoke),'all_measured_oracle_calls':counter.calls+checking.calls+1,
            'all_measured_input_symbols':counter.symbols+checking.symbols+len(smoke),
            'adapter_sha256':digest(json.dumps(adapter,sort_keys=True,separators=(',',':')).encode())})
    result={'schema':'omega/public-specialist-case-diagnostic/v1','scope':'ONE_UNFAMILIAR_PUBLIC_SOFTWARE_MODEL_NOT_FIELD_VALIDATION',
        'registration_sha256':digest(registration),'selection_sha256':digest(selection_path.read_bytes()),
        'model_path':selection['path'],'model_sha256':selection['model_sha256'],
        'source_commit':commit,'checker_sha256':expected_checker,'dependencies':dependencies,
        'script_sha256':digest(Path(__file__).read_bytes()),'contract':contract,'rows':rows,
        'limitations':['Local prospective selection, not yet public preregistration','Public teaching model unless separately established as measured protocol',
        'No field restoration, demand, financial mutation or Super Alpha evidence','Shared supplied checker, not external certification',
        'Complete setup and human effort are not measured']}
    output.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'model':result['model_path'],'states':len(table),'alphabet':list(alphabet),'rows':rows},sort_keys=True))


if __name__=='__main__':main()
