// Contingent reserve rights 278 — preregistered finite simulation, 2026-11-25.
// Run: node instrument.js (or evaluate this single expression and serialize result).
// No cloud API, physical control, native account, actual customer, or spend.
// Input: four authored sites with two interchangeable single-H100 tasks each.
// Each outage demand requires two remote GPU slots concurrently for one hour;
// input already staged; transfer/startup/remaining block time must be established
// separately. 48 booked hours, 47 usable hours assumed. No measured job trace.
// AWS p5.4xlarge US East Ohio/Oregon price observed on 2026-11-25: USD 5.970/h.
// Source https://aws.amazon.com/ec2/capacityblocks/pricing/
// Rights: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/capacity-blocks-share.html
// Same-org only, shared capacity first-come first-served; no right to evict.
// Source: FERC 195 FERC paragraph 61,196, 2026-06-05 paras 99-101:
// https://spp.org/documents/76880/20260605_order%20-%20revisions%20to%20add%20the%20conditional%20high%20impact%20large%20load%20service_er26-1323.pdf
// October 26 compliance order listed at https://www.spp.org/spp-documents-filings/?id=576876
// but PDF retrieval forbidden; no claim of full current tariff interpretation.
// SPP service conditional; do not assume max outage or independence.
// Alternatives: (1) on-site firm power or independent generation, costs/rights unknown;
// (2) direct 8-slot remote reservation, (3) contingent shared reserve with verified
// rights and coordinated admission, (4) no deploy. Direct is a competent comparison;
// ordinary maximum matching/Hall certificate is allowed and expected to tie.
// No actual rights, demand, cost or buyer acceptance asserted. Price-only component,
// no resale or customer organization enrollment, no real transfer. Bound 0..8 per
// pool because at most eight simultaneous tasks, except occupied slots (bound 10).
// Freeze all eight cases below and retain failure arms, no retries or tuning.
// Compare augmenting matching with separate exhaustive Hall inequalities on every
// candidate capacity pair and scenario. Check no access = refusal, correlated
// outages defeat single-outage savings, independent pool loss requires redundancy.
// A passing engineering check is not commercial qualification. Stop after one run.
(()=>{
const t0=Date.now(), n=4, need=2, horizon=48, rateMills=5970;
const all=Array.from({length:15},(_,i)=>i+1);
const pop=m=>{let z=0;for(;m;m>>=1)z+=m&1;return z};
const scenario=(k,fail=false,occupied=false)=>all.filter(m=>pop(m)<=k).flatMap(mask=>[
 {mask,down:-1,occ:[0,0]},
 ...(fail?[{mask,down:0,occ:[0,0]},{mask,down:1,occ:[0,0]}]:[]),
 ...(occupied?[{mask,down:-1,occ:[2,2]}]:[])
]);
const cases=[
 {id:"one_independent",rights:[3,3,3,3],sc:scenario(1)},
 {id:"two_concurrent",rights:[3,3,3,3],sc:scenario(2)},
 {id:"all_correlated",rights:[3,3,3,3],sc:scenario(4)},
 {id:"one_pool_loss",rights:[3,3,3,3],sc:scenario(1,true)},
 {id:"all_plus_pool_loss",rights:[3,3,3,3],sc:scenario(4,true)},
 {id:"restricted_same_org_routes",rights:[1,1,2,2],sc:scenario(1)},
 {id:"uncontrolled_fcfs",rights:[3,3,3,3],sc:scenario(1,false,true)},
 {id:"external_org_no_right",rights:[0,3,3,3],sc:scenario(4)}
];
const available=(c,s)=>c.map((x,j)=>s.down===j?0:Math.max(0,x-s.occ[j]));
function match(c,s,r){
 const a=available(c,s),slots=[];
 a.forEach((z,j)=>{for(let i=0;i<z;i++)slots.push(j)});
 const tasks=[];for(let i=0;i<n;i++)if(s.mask&(1<<i))for(let k=0;k<need;k++)tasks.push(i);
 const owners=slots.map(()=>-1);
 function add(t,seen){for(let j=0;j<slots.length;j++)if(!seen[j]&&(r[tasks[t]]&(1<<slots[j]))){seen[j]=true;if(owners[j]<0||add(owners[j],seen)){owners[j]=t;return true}}return false}
 let done=0;for(let i=0;i<tasks.length;i++)if(add(i,[]))done++;
 return {ok:done===tasks.length,done,demand:tasks.length};
}
function hall(c,s,r){
 const a=available(c,s);
 for(let sub=s.mask;sub;sub=(sub-1)&s.mask){let m=0;for(let i=0;i<n;i++)if(sub&(1<<i))m|=r[i];const count=(m&1?a[0]:0)+(m&2?a[1]:0);if(count<need*pop(sub))return false}
 return true;
}
let comparisons=0,mismatches=0;
const arms=cases.map(q=>{
 let best=null,valid=0;
 for(let x=0;x<=10;x++)for(let y=0;y<=10;y++){
  let pass=true;for(const s of q.sc){const a=match([x,y],s,q.rights).ok,b=hall([x,y],s,q.rights);comparisons++;if(a!==b)mismatches++;if(!a)pass=false}
  if(pass){valid++;if(best===null||x+y<best[0]+best[1])best=[x,y]}
 }
 const total=best?best[0]+best[1]:null;
 // Direct 8 slot alternative in an independent region with rights, before
 // reserve-domain failure and migration overhead; not equivalent under all shocks.
 return {id:q.id,scenarios:q.sc.length,pairs:121,valid,best,total,usdMills:total===null?null:total*horizon*rateMills,
 directReferenceMills:8*horizon*rateMills,
 directReferenceEquivalentUnderDeclaredShocks:!q.sc.some(s=>s.down>=0||s.occ.some(Boolean))&&q.rights.every(x=>x===3),
 witnessAtZero:match([0,0],q.sc[0],q.rights)};
});
const expected=[2,4,8,4,16,4,6,null];
const invariants={allHallAgree:mismatches===0,registeredMinima:arms.every((a,i)=>a.total===expected[i]),noRightsRefused:arms[7].total===null,allCorrelatedEliminatesSavings:arms[2].total===8,commonReserveFailureNeedsDuplication:arms[4].total===16,fcfsOccupationCosted:arms[6].total===6,sourcePriceInteger:arms[2].usdMills===2292480};
return {schema:"reserve-rights278/v1",registeredCases:8,comparisons,mismatches,arms,invariants,engineeringPass:Object.values(invariants).every(Boolean),commercial:"NO_DEPLOY",actualContracts:0,actualRevenueUSD:0,nativeAccount:null,nativeProfit:null,actualBilling:null,wallMs:Date.now()-t0};
})()
