// OD identifiability 289. Frozen before reading input payloads.
// Academic research ONLY; source README restricts data to academic research. No raw data republication or commercial rights asserted.
// Upstream bstabler/TransportationNetworks @ d1639b4ef218c17928ba573e806ddf8ba5e7ae6d; registered Git blob identifiers:
// [{"folder":"SiouxFalls","stem":"SiouxFalls","net":"66d0eca4ddcfb82f861bea040060deab7a741b2f","trips":"db70eda57738877811e9ac07c25a567973d3b6a0"},{"folder":"Anaheim","stem":"Anaheim","net":"1a5600ffb343b9b391dab59a28b39d2a2869b645","trips":"59146d9224872e06c00acee90bf25f7eed9c6fe3"},{"folder":"Eastern-Massachusetts","stem":"EMA","net":"8290ca8be024a94bd7f7eee30652bb8c720cac5a","trips":"ef2362c41e81aad3959f8eb91dc243f568ff0fe3"}]
// Three fixed instances, all retained, one pass each. No parameter/seed changes.
// Fixed free-flow shortest routes, respecting first thru node; OD positive off-diagonal support.
// Challenger: exact path-difference signature yields four-cell feasible ambiguity with preserved link and OD marginals.
// Strong ordinary control: dimension bound rank <= number of links + 2*number of zones; no new mathematics claimed.
// Independent calculation: aggregate full original and modified OD across every fixed path; require all three max differences <= 1e-7, nonnegative, nonzero change, no unreachable positive OD.
// Stop after 3 cases, any failure stays failure. No inference of observed traffic, congestion equilibrium, actual city OD, superior estimation, or commerce.
// Compare: OpenCity reproducible transport model (IEEE $3500 pool, Nov 30 deadline); GEMS geologic mapping ($300k, Dec 3; gated test data); NIH SPARK ($250k, Jan 15 code; eligibility/data boundaries); no entry. Select research-only transport identifiability because exact benchmark inputs are accessible and a concrete missing observation constraint can be tested. No entry is the commercial incumbent.
// References: https://bigdataieee.org/BigData2026/cup/ ; https://www.drivendata.org/competitions/306/ ; https://www.nih.gov/challenges/semantic-precision-ai-retrieval-knowledge-spark-dbgap-challenge
function experiment(net,trip) {
  const meta=(s,key)=>{const m=s.match(new RegExp("<"+key+">\\s*(\\d+)","i"));if(!m)throw Error("missing "+key);return Number(m[1])};
  const N=meta(net,"NUMBER OF NODES"),Z=meta(net,"NUMBER OF ZONES"),E=meta(net,"NUMBER OF LINKS"),first=meta(net,"FIRST THRU NODE");
  const edges=[],adj=Array.from({length:N+1},()=>[]);
  for(const line of net.split(/\r?\n/)){const s=line.trim();if(!/^\d/.test(s))continue;const a=s.replace(/;/g," ").trim().split(/\s+/).map(Number);if(a.length!==10||!a.every(Number.isFinite))throw Error("invalid edge");const [u,v,,,w]=a;if(u<1||u>N||v<1||v>N||w<0)throw Error("edge range");adj[u].push(edges.length);edges.push({u,v,w});}
  if(edges.length!==E||meta(trip,"NUMBER OF ZONES")!==Z)throw Error("metadata mismatch");
  const q=Array.from({length:Z+1},()=>new Float64Array(Z+1)),seen=new Set();
  const sections=trip.split(/\bOrigin\s+(\d+)/i);if(sections.length!==2*Z+1)throw Error("origin count");
  for(let i=1;i<sections.length;i+=2){const o=Number(sections[i]);if(o<1||o>Z)throw Error("origin range");for(const m of sections[i+1].matchAll(/(\d+)\s*:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)\s*;/gi)){const d=Number(m[1]),v=Number(m[2]),k=o+","+d;if(d<1||d>Z||v<0||!Number.isFinite(v)||seen.has(k))throw Error("trip range or duplicate");seen.add(k);q[o][d]=v;}}
  const paths=Array.from({length:Z+1},()=>Array(Z+1).fill(null));
  let positive=0,unreachable=0,total=0;
  for(let o=1;o<=Z;o++){const dist=Array(N+1).fill(Infinity),pred=Array(N+1).fill(-1),done=new Uint8Array(N+1);dist[o]=0;
    for(let k=0;k<N;k++){let u=-1,least=Infinity;for(let j=1;j<=N;j++)if(!done[j]&&dist[j]<least){least=dist[j];u=j}if(u<0)break;done[u]=1;if(u!==o&&u<first)continue;for(const e of adj[u]){const {v,w}=edges[e];if(!done[v]&&least+w<dist[v]){dist[v]=least+w;pred[v]=e}}}
    for(let d=1;d<=Z;d++){if(o===d||q[o][d]<=0)continue;positive++;total+=q[o][d];if(!Number.isFinite(dist[d])){unreachable++;continue}let v=d,ids=[];while(v!==o){const e=pred[v];if(e<0||ids.length>N)throw Error("broken path");ids.push(e);v=edges[e].u;}paths[o][d]=ids.reverse();}
  }
  const sig=(a,b)=>{const m=new Map();for(const e of a)m.set(e,(m.get(e)||0)+1);for(const e of b)m.set(e,(m.get(e)||0)-1);return [...m].filter(x=>x[1]).sort((x,y)=>x[0]-y[0]).map(x=>x.join(":")).join(",")};
  let witness=null;
  outer:for(let a=1;a<=Z;a++)for(let b=a+1;b<=Z;b++){const map=new Map();for(let d=1;d<=Z;d++){if(!paths[a][d]||!paths[b][d])continue;const k=sig(paths[a][d],paths[b][d]);if(map.has(k)){const c=map.get(k),delta=Math.min(q[a][d],q[b][c])/2;if(delta>0){witness={a,b,c,d,delta};break outer}}else map.set(k,d)}}
  // Independent check: traverse all original routes, calculate complete before/after link totals and OD marginals.
  const out={nodes:N,zones:Z,links:E,first_thru_node:first,positive_offdiagonal_pairs:positive,unreachable_positive_pairs:unreachable,od_total:total,dimension_lower_bound:Math.max(0,positive-unreachable-E-2*Z),witness_found:!!witness};
  if(!witness)return {...out,passed:false};
  const {a,b,c,d,delta}=witness;
  const change=new Map([[a+","+c,delta],[b+","+d,delta],[a+","+d,-delta],[b+","+c,-delta]]);
  const calc=modified=>{const L=new Float64Array(E),O=new Float64Array(Z+1),D=new Float64Array(Z+1);let nonnegative=true;for(let i=1;i<=Z;i++)for(let j=1;j<=Z;j++){const f=q[i][j]+(modified?(change.get(i+","+j)||0):0);if(f<0)nonnegative=false;O[i]+=f;D[j]+=f;if(i===j||f===0)continue;const path=paths[i][j];if(!path)continue;let u=i;for(const k of path){if(edges[k].u!==u)throw Error("route discontinuity");u=edges[k].v;L[k]+=f}if(u!==j)throw Error("route endpoint");}return {L,O,D,nonnegative}};
  const x=calc(false),y=calc(true),maxdiff=(u,v)=>u.reduce((m,t,i)=>Math.max(m,Math.abs(t-v[i])),0);
  const errors=[maxdiff(x.L,y.L),maxdiff(x.O,y.O),maxdiff(x.D,y.D)];
  return {...out,changed_od_cells:4,l1_od_change:4*delta,max_link_flow_change:errors[0],max_origin_total_change:errors[1],max_destination_total_change:errors[2],nonnegative:y.nonnegative,passed:unreachable===0&&y.nonnegative&&delta>0&&errors.every(e=>e<=1e-7)};
}
if(typeof module!=="undefined")module.exports=experiment;
