// Diagnostic for 278 failed FCFS expectation. This is a new finite diagnostic,
// not a replacement for the original result. Freeze before execution.
// Compare fixed per-pool occupancy ceilings, total occupancy ceilings with
// arbitrary concentration, explicit dual-pool minimum, unlimited FCFS, and
// guaranteed admission. Two simultaneous eligible tasks, capacity pairs 0..10.
// Occupancy is physically feasible only if <= reserved capacity per pool.
// No assumption that AWS supplies an occupancy bound; current documented
// first-come-first-served behavior motivates the unrestricted counterexample.
// No new source or financial account, no cloud requests, no actual cost.
(()=>{
const t0=Date.now(),cases=[
 {id:"per_pool_cap_two",min:0,occ:(a,b)=>a<=2&&b<=2,formula:(x,y)=>Math.max(0,x-2)+Math.max(0,y-2),expected:4},
 {id:"per_pool_cap_two_dual_min",min:2,occ:(a,b)=>a<=2&&b<=2,formula:(x,y)=>Math.max(0,x-2)+Math.max(0,y-2),expected:6},
 {id:"total_cap_four_arbitrary_concentration",min:0,occ:(a,b)=>a+b<=4,formula:(x,y)=>Math.max(0,x+y-4),expected:6},
 {id:"unbounded_fcfs",min:0,occ:()=>true,formula:()=>0,expected:null},
 {id:"enforceable_zero_occupancy",min:0,occ:(a,b)=>a+b===0,formula:(x,y)=>x+y,expected:2}
];
let mismatches=0,pairs=0,occupancyChecks=0;
const arms=cases.map(q=>{let best=null,checked=0;
for(let x=q.min;x<=10;x++)for(let y=q.min;y<=10;y++){
 pairs++;let worst=Infinity;
 for(let a=0;a<=x;a++)for(let b=0;b<=y;b++)if(q.occ(a,b)){occupancyChecks++;worst=Math.min(worst,x+y-a-b)}
 if(worst!==q.formula(x,y))mismatches++;
 if(worst>=2){checked++;if(!best||x+y<best[0]+best[1])best=[x,y]}
}
const total=best?best[0]+best[1]:null;return {id:q.id,best,total,expected:q.expected,pass:total===q.expected,qualifyingPairs:checked};
});
return {schema:"reserve-rights278/fcfs-diagnostic-v1",parentFailureCommit:"2f5704970ad96afc1e206d2fc14498757ad31394",pairs,occupancyChecks,mismatches,arms,pass:mismatches===0&&arms.every(a=>a.pass),original278EngineeringPass:false,wallMs:Date.now()-t0,actualBilling:null};
})()
