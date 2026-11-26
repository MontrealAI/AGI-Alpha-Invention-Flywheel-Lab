// Grid recourse 297 — preregistered finite illustrative DC model, not an interconnection study.
// Input: exact PGLib v23.07 cases at dc6be4b2f85ca0e776952ec22cbd4c22396ea5a3.
// Select first two distinct positive-Pmax generator buses and largest-demand other bus.
// Zero background, no losses, voltage/reactive/security dynamics or existing dispatch.
// Use Pmax as hypothetical available incremental generation; rateA as DC MW proxy.
// Every single line outage and intact case, including islands. Fixed shares, joint fixed
// dispatch, contingency-observed adaptive dispatch, no entry. No seed or case replacement.
// Acceptance: all unit-flow KCL checks <=1e-7; independent interval/bisection LP matches
// vertex enumeration <=1e-5 MW for every case; adaptive >= static >= equal >= 0.
// Stop after 3 files, all cases retained. No claim of novel optimization or market demand.
function run(inputs) {
 const tol=1e-8; let checks=0, failures=[];
 function check(ok,msg){checks++;if(!ok)failures.push(msg)}
 function matrix(s,k){return s.match(new RegExp("mpc\\."+k+"\\s*=\\s*\\[([\\s\\S]*?)\\];"))[1].split("\n").map(l=>l.split("%")[0].trim().replace(/;$/,"")).filter(Boolean).map(l=>l.split(/\s+/).map(Number))}
 function solve(A,b){let n=b.length,M=A.map((r,i)=>[...r,b[i]]);for(let i=0;i<n;i++){let p=i;for(let j=i+1;j<n;j++)if(Math.abs(M[j][i])>Math.abs(M[p][i]))p=j;[M[i],M[p]]=[M[p],M[i]];if(Math.abs(M[i][i])<1e-12)throw Error("singular");let d=M[i][i];for(let k=i;k<=n;k++)M[i][k]/=d;for(let j=0;j<n;j++)if(i!==j){let z=M[j][i];for(let k=i;k<=n;k++)M[j][k]-=z*M[i][k]}}return M.map(r=>r[n])}
 function vertices(C){let best={sum:0,x:0,y:0};for(let i=0;i<C.length;i++)for(let j=i+1;j<C.length;j++){let [a,b,c]=C[i],[d,e,f]=C[j],det=a*e-b*d;if(Math.abs(det)<1e-12)continue;let x=(c*e-b*f)/det,y=(a*f-c*d)/det;if(C.every(([p,q,r])=>p*x+q*y<=r+tol)&&x+y>best.sum)best={sum:x+y,x,y}}return best}
 function feasible(C,z){let lo=0,hi=z;for(let [a,b,c] of C){let d=a-b,r=c-b*z;if(Math.abs(d)<1e-12){if(r < -1e-10)return false}else if(d>0)hi=Math.min(hi,r/d);else lo=Math.max(lo,r/d)}return lo<=hi+1e-10}
 function ref(C,cap){let lo=0,hi=cap;for(let i=0;i<70;i++){let m=(lo+hi)/2;if(feasible(C,m))lo=m;else hi=m}return lo}
 function equal(C,cap){let z=cap;for(let [a,b,c] of C)if(a+b>tol)z=Math.min(z,2*c/(a+b));return z}
 const results=[];
 for(let input of inputs){
 const buses=matrix(input.content,"bus"),gen=matrix(input.content,"gen"),raw=matrix(input.content,"branch").filter(e=>e[10]===1),base=Number(input.content.match(/mpc.baseMVA\s*=\s*([\d.]+)/)[1]);
 const caps=new Map();for(let g of gen)if(g[7]===1&&g[8]>0)caps.set(g[0],(caps.get(g[0])||0)+g[8]);
 const src=[...caps.keys()].slice(0,2),lim=src.map(k=>caps.get(k)),sink=buses.filter(r=>!src.includes(r[0])).sort((a,b)=>b[2]-a[2]||a[0]-b[0])[0][0],cap=lim[0]+lim[1];
 const initial=[[-1,0,0],[0,-1,0],[1,0,lim[0]],[0,1,lim[1]]], all=[...initial],scenarios=[];
 for(let out=-1;out<raw.length;out++){
 let edges=raw.filter((_,i)=>i!==out),component=new Set([sink]);let change=true;while(change){change=false;for(let e of edges)if(component.has(e[0])!==component.has(e[1])){component.add(e[0]);component.add(e[1]);change=true}}
 let nodes=[...component].filter(n=>n!==sink),ix=new Map(nodes.map((n,i)=>[n,i])),A=nodes.map(()=>nodes.map(()=>0));
 for(let e of edges){let [u,v]=e;if(!component.has(u))continue;if(e[9]!==0)throw Error("nonzero phase");let k=base/(e[3]*(e[8]||1)),i=ix.get(u),j=ix.get(v);if(i!==undefined)A[i][i]+=k;if(j!==undefined)A[j][j]+=k;if(i!==undefined&&j!==undefined){A[i][j]-=k;A[j][i]-=k}}
 let C=[...initial],flows=[];
 for(let h=0;h<2;h++){let source=src[h];if(!component.has(source)){C.push(h===0?[1,0,0]:[0,1,0]);flows.push(edges.map(()=>0));continue}
 let angles=solve(A,nodes.map(n=>n===source?1:0)),theta=n=>ix.has(n)?angles[ix.get(n)]:0;
 let f=edges.map(e=>component.has(e[0])?base*(theta(e[0])-theta(e[1]))/(e[3]*(e[8]||1)):0);
 for(let n of component){let net=edges.reduce((s,e,i)=>s+(e[0]===n?f[i]:e[1]===n?-f[i]:0),0);check(Math.abs(net-(n===source?1:n===sink?-1:0))<1e-7,input.path+" KCL "+out+" "+n)}
 flows.push(f)}
 edges.forEach((e,i)=>{let a=flows[0][i],b=flows[1][i],k=base/(e[3]*(e[8]||1)),p=Math.min(e[5],k*e[12]*Math.PI/180),m=Math.min(e[5],-k*e[11]*Math.PI/180);C.push([a,b,p],[-a,-b,m])});
 let v=vertices(C),r=ref(C,cap);check(Math.abs(v.sum-r)<1e-5,input.path+" LP "+out);all.push(...C);scenarios.push({outage_index:out,edge:out<0?null:raw[out].slice(0,2),equal_MW:equal(C,cap),adaptive:v,reference_MW:r});
 }
 let fixed=vertices(all),r=ref(all,cap),adaptive=Math.min(...scenarios.map(s=>s.adaptive.sum)),eq=Math.min(...scenarios.map(s=>s.equal_MW));check(Math.abs(fixed.sum-r)<1e-5,input.path+" static LP");check(adaptive+tol>=fixed.sum&&fixed.sum+tol>=eq&&eq>=-tol,input.path+" ordering");
 results.push({path:input.path,blob:input.blob,source_buses:src,source_caps:lim,sink,lines:raw.length,scenarios,robust_equal_MW:eq,robust_fixed:fixed,robust_adaptive_MW:adaptive,robust_fixed_reference_MW:r});
 }
 return {results,checks,failures,accepted:failures.length===0,scope:"authored zero-background DC proxy; no actual transfer rights, demand or money"};
}
