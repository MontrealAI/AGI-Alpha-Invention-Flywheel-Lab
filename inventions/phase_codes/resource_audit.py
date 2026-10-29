"""Count the actual frozen native preparation, with explicit unmapped costs."""
import argparse, collections, hashlib, json, pathlib
import encoder

def audit(candidate,numeric):
    d,pivots,free,levels=encoder.tables(candidate)
    raw=pathlib.Path(numeric).read_bytes();num=json.loads(raw)
    if hashlib.sha256(raw).hexdigest()!=d['source_numeric_sha256']: raise ValueError('NUMERIC_IDENTITY')
    gates=[]
    def wire(q): return f'H{1-q}' if q<2 else f'D{free[q-2]}'
    for level in levels:
        target=2+level['depth'];size=1<<target
        for i,angle in enumerate(level['native_angles']):
            gates.append(('Ry',wire(target)))
            nxt=(i+1)%size;toggle=((i^(i>>1))^(nxt^(nxt>>1))).bit_length()-1
            gates.append(('CNOT',wire(target-1-toggle),wire(target)))
    for target,controls in pivots:
        for c in controls:gates.append(('CNOT',f'D{c}',f'D{target}'))
    for j,mask in enumerate(num['color_masks']):
        for bit in range(d['n']):
            if mask>>bit&1:gates.append(('CNOT',f'D{bit}',f'H{j}'))
    clock=collections.defaultdict(int);two_clock=collections.defaultdict(int);counts=collections.Counter();edges=collections.Counter()
    for name,*qs in gates:
        t=1+max(clock[q] for q in qs)
        for q in qs:clock[q]=t
        counts[name]+=1
        if len(qs)==2:
            t2=1+max(two_clock[q] for q in qs)
            for q in qs:two_clock[q]=t2
            edges['->'.join(qs)]+=1
    return {'candidate_sha256':hashlib.sha256(pathlib.Path(candidate).read_bytes()).hexdigest(),
      'native_preparation_gate_count':len(gates),'counts':dict(counts),'ideal_all_to_all_ASAP_depth':max(clock.values()),
      'CNOT_dependency_depth_ignoring_Ry_duration':max(two_clock.values()),'peak_wires':d['n']+2,
      'directed_CNOT_connectivity_counts':dict(sorted(edges.items())),'distinct_directed_CNOT_edges':len(edges),
      'wire_convention':'D0 is least-significant classical word bit. H0/H1 initially carry the logical input and are erased coherently.',
      'logical_gate_after_preparation':{'S_gates':d['n'],'ideal_depth':1},
      'scope':'Counts the literally executed native circuit, including zero-angle rotations and cancelable gates. ASAP is an ideal all-to-all dependency schedule, not a measured device runtime.',
      'complete_route_unknowns':{'finite_gate_set_synthesis':None,'fault_tolerant_preparation':None,'routing_SWAPS':None,'syndrome_extraction_and_recovery_circuit':None,'recovery_ancillas':None,'measurements_and_feedforward':None,'resets':None,'retry_rate':None,'matched_logical_error_target':None,'physical_wall_time':None,'physical_energy':None,'device_billing':None},
      'complete_system_advantage':'NOT_ESTABLISHED'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--numeric',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    with pathlib.Path(a.output).open('x') as h:json.dump(audit(a.candidate,a.numeric),h,indent=2);h.write('\n')
