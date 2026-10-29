"""Independent finite parity-scaffold adjudication, with no builder/verifier imports.

The scaffold is ker(H), where column j is the binary expansion of j for
j=1..n. Physical coordinate j is bit(j-1) of the integer word. A dual row
specified by u has mask_j=parity(u & j). It has parity zero on ker(H), so
the corresponding Z product has eigenvalue+1 on every scaffold word.
This only obstructs a ZERO moment goal, not general equal-moment KL.
"""
import argparse,datetime,hashlib,itertools,json,pathlib,time

def digest(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def syndrome(word,n):
    value=0
    for j in range(1,n+1):
        if word>>(j-1)&1:value^=j
    return value

def audit(n):
    scaffold=[word for word in range(1<<n) if syndrome(word,n)==0]
    dual=[]
    for u in range(1,1<<n.bit_length()):
        mask=sum(((u&j).bit_count()%2)<<(j-1) for j in range(1,n+1))
        parity_counts=[sum((word&mask).bit_count()%2==p for word in scaffold) for p in (0,1)]
        assert parity_counts==[len(scaffold),0]
        dual.append(dict(row_combination=u,mask_integer=mask,mask_bitstring=format(mask,f'0{n}b'),weight=mask.bit_count(),column_positions_LSB_numbered=[j for j in range(1,n+1) if mask>>(j-1)&1],plus_eigenstates=parity_counts[0],minus_eigenstates=parity_counts[1]))
    low_masks=[1<<j for j in range(n)]+[(1<<a)|(1<<b) for a,b in itertools.combinations(range(n),2)]
    low=[]
    for mask in low_masks:
        count0=sum((word&mask).bit_count()%2==0 for word in scaffold);count1=len(scaffold)-count0
        if count1==0:low.append(dict(mask_integer=mask,weight=mask.bit_count(),constant_Z_product='+1',counts=[count0,count1]))
        else:assert count0==count1
    witnesses=[r for r in dual if r['weight']<=2]
    assert {r['mask_integer'] for r in witnesses}=={r['mask_integer'] for r in low}
    if n==15:assert not witnesses and {r['weight'] for r in dual}=={8}
    if n==16:assert any(r['column_positions_LSB_numbered']==[16] for r in witnesses)
    if n==17:assert any(r['column_positions_LSB_numbered']==[16,17] for r in witnesses)
    return dict(n=n,all_binary_words_tested=1<<n,scaffold_words=len(scaffold),parity_rank=n.bit_length(),dual_vectors_exhaustively_checked=len(dual),dual_weight_histogram={str(w):sum(r['weight']==w for r in dual) for w in sorted({r['weight'] for r in dual})},one_or_two_coordinate_masks_checked=len(low_masks),zero_moment_obstruction=bool(witnesses),low_weight_dual_witnesses=witnesses,all_nonconstant_weight1_or2_masks_balanced=True)

def recount_encoder(n,color_masks):
    # Independent elementary row reduction of the declared parity matrix.
    rows=[sum(((j>>bit)&1)<<(j-1) for j in range(1,n+1)) for bit in range(n.bit_length())]
    rank=0;piv=[]
    for col in range(n):
        pivot=next((r for r in range(rank,len(rows)) if rows[r]>>col&1),None)
        if pivot is None:continue
        rows[rank],rows[pivot]=rows[pivot],rows[rank]
        for r in range(len(rows)):
            if r!=rank and rows[r]>>col&1:rows[r]^=rows[rank]
        piv.append(col);rank+=1
    free=[j for j in range(n) if j not in piv];details=[]
    for r,p in enumerate(piv):details.append(dict(pivot_bit_LSB=p,free_controls_LSB=[q for q in free if rows[r]>>q&1]))
    per_depth=[1<<(depth+2) for depth in range(len(free))]
    ry=sum(per_depth);prep_cnot=ry;parity_cnot=sum(len(r['free_controls_LSB']) for r in details);erase_cnot=sum(mask.bit_count() for mask in color_masks)
    assert (len(free),ry,prep_cnot,parity_cnot,erase_cnot)==(11,8188,8188,28,13)
    return dict(data_qubits=n,logical_input_helpers=2,helpers_initially_clean=False,helpers_initial_role='arbitrary coherent two-qubit logical input',final_helpers='zero by independently tested color-mask erasure',peak_wires=n+2,parity_rank=rank,free_coordinates=len(free),native_Ry_count=ry,native_CNOT_preparation_count=prep_cnot,native_CNOT_parity_count=parity_cnot,native_CNOT_helper_erase_count=erase_cnot,native_gate_total=ry+prep_cnot+parity_cnot+erase_cnot,per_depth_Ry_and_preparation_CNOT_counts=per_depth,parity_computation=details,scope='Recounts the frozen encoder algorithm; neither a lower bound nor an optimal encoder, noisy fault-tolerant resource or full monetary cost.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--lab-root',required=True,type=pathlib.Path);p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();cpu=time.process_time();root=a.lab_root
    fpath=root/'campaign/cycle-004/CANDIDATE_FREEZE.json';freeze=json.loads(fpath.read_text())
    identities={name:dict(expected=h,actual=digest(root/name)) for name,h in freeze['source_sha256'].items()}
    assert all(r['expected']==r['actual'] for r in identities.values())
    results=[audit(n) for n in (16,17,15)]
    records={}
    for run,n in [('002',16),('003',17),('004',15)]:
        path=root/f'evidence/cycle-004/development/run-{run}/NUMERIC.json';d=json.loads(path.read_text());assert d['n']==n
        expected={0,*[1<<j for j in range(n)],*[(1<<i)|(1<<j) for i,j in itertools.combinations(range(n),2)]}
        assert set(d['moment_masks'])==expected and d['classical_parity_columns']==list(range(1,n+1))
        witness_masks=[r['mask_integer'] for r in next(r for r in results if r['n']==n)['low_weight_dual_witnesses']]
        assert all(mask in d['moment_masks'] for mask in witness_masks)
        records[str(n)]=dict(path=str(path.relative_to(root)),sha256=digest(path),all_numeric_feasible=d['all_numeric_feasible'],registered_zero_goal_contains_witness_masks=witness_masks)
    numeric=root/'inventions/phase_codes/artifacts/controlled_s15_numeric.json';num=json.loads(numeric.read_text())
    report={'status':'CONFIRMED_WITH_SCOPE_LIMIT','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'script_sha256':digest(__file__),'mathematical_definition':'H columns1..n; integer-word bit(j-1) corresponds to columnj; no builder applicability imports','adjudication':'n16 has a weight1 dual row and n17 a weight2 dual row, each identically+1 on every scaffold word. Any normalized probability measure on any subset therefore has this Z/ZZ moment+1, contradicting the selected zero goal. n15 has no weight1/2 dual vector, so removes this obstruction while retaining the same zero goal. Its actual exact candidate independently passed all goal checks.','scope_limit':'This obstruction applies to this scaffold plus the stronger zero-moment objective. General Knill-Laflamme only requires common moments, which may equal+1; n16/n17 codes and other scaffolds are not proved impossible. Removing an obstruction is not by itself construction success or a generic discovery-policy/business claim.','exposure':'Post-construction engineering adjudication; candidate and outcomes already exposed. No fresh statistical confirmation claim and no candidate/source/spec/threshold edits.','scaffold_results':results,'development_records':records,'native_encoder_recount':recount_encoder(15,num['color_masks']),'candidate_source_identities':identities,'cpu_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-start}
    out=a.output/'ADJUDICATION.json';out.write_text(json.dumps(report,indent=2)+'\n')
    receipt={'script_sha256':digest(__file__),'report_sha256':digest(out),'candidate_freeze_sha256':digest(fpath),'no_frozen_core_edits':True,'original_deadline_changed':False,'fresh_statistical_claim':False}
    (a.output/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'status':report['status'],'report_sha256':receipt['report_sha256'],'cpu_seconds':report['cpu_seconds'],'native_gate_total':report['native_encoder_recount']['native_gate_total']}))
if __name__=='__main__':main()
