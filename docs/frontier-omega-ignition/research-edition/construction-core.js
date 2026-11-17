/* FRONTIER Ω research construction core. Supplied finite semantics, not live LLM discovery.
   Sources: Surf the Exponential (1.2.0), §6; Out-Learn (21 October revision), §§2–8. */
(function(root){
'use strict';
const assert=(ok,msg)=>{if(!ok)throw new Error(msg);};
const gcd=(a,b)=>{a=a<0n?-a:a;b=b<0n?-b:b;while(b){const r=a%b;a=b;b=r;}return a||1n;};
class Q {
 constructor(n,d=1n){n=BigInt(n);d=BigInt(d);assert(d!==0n,'Zero denominator');if(d<0n){n=-n;d=-d;}const g=gcd(n,d);this.n=n/g;this.d=d/g;}
 add(x){x=q(x);return new Q(this.n*x.d+x.n*this.d,this.d*x.d);}
 sub(x){x=q(x);return new Q(this.n*x.d-x.n*this.d,this.d*x.d);}
 mul(x){x=q(x);return new Q(this.n*x.n,this.d*x.d);}
 div(x){x=q(x);return new Q(this.n*x.d,this.d*x.n);}
 abs(){return new Q(this.n<0n?-this.n:this.n,this.d);}
 cmp(x){x=q(x);const v=this.n*x.d-x.n*this.d;return v<0n?-1:v>0n?1:0;}
 num(){return Number(this.n)/Number(this.d);}
 toString(){return this.d===1n?String(this.n):`${this.n}/${this.d}`;}
 toJSON(){return this.toString();}
}
function q(x){if(x instanceof Q)return x;if(typeof x==='string'&&x.includes('/')){const [n,d]=x.split('/');return new Q(n,d);}return new Q(x);}
function sum(xs){return xs.reduce((a,b)=>a.add(b),q(0));}
function domain(values){assert(Array.isArray(values)&&values.length>=2&&values.length<=6,'Use 2–6 distinct integer values');assert(values.every(x=>Number.isSafeInteger(x)&&Math.abs(x)<=1000000),'Values must be integers between -1,000,000 and 1,000,000');const v=[...new Set(values)].sort((a,b)=>a-b);assert(v.length===values.length,'Domain values must be unique');return v;}
function statesOf(values){return values.flatMap(a=>values.map(b=>[a,b]));}
function queriesOf(values,scope){assert(['upper','interval'].includes(scope),'Unsupported scope');if(scope==='upper'){const ts=[...new Set([...values,90])].sort((a,b)=>a-b);return ts.map(hi=>({kind:'upper',hi}));}return values.flatMap((lo,i)=>values.slice(i).map(hi=>({kind:'interval',lo,hi})));}
function truth(state,query){return state.every(x=>x<=query.hi&&(query.kind==='upper'||x>=query.lo));}
function signature(state,queries){return queries.map(v=>truth(state,v)?1:0);}
function collide(values,summary,queries){const states=statesOf(domain(values));for(let i=0;i<states.length;i++)for(let j=i+1;j<states.length;j++){if(JSON.stringify(summary(states[i]))!==JSON.stringify(summary(states[j])))continue;for(const query of queries){if(truth(states[i],query)!==truth(states[j],query))return {left:states[i],right:states[j],shared:summary(states[i]),query,left_answer:truth(states[i],query),right_answer:truth(states[j],query)};}}return null;}
function compile(values=[60,80,100],scope='upper'){
 values=domain(values);const queries=queriesOf(values,scope),states=statesOf(values),keys=new Map(),decoders=[],encoder=[];
 for(const row of states){const sig=signature(row,queries),key=sig.join('');if(!keys.has(key)){keys.set(key,keys.size);decoders.push(sig);}encoder.push({input:row,label:keys.get(key)});}
 const witnesses=[];for(let a=0;a<decoders.length;a++)for(let b=a+1;b<decoders.length;b++){const qi=decoders[a].findIndex((v,i)=>v!==decoders[b][i]);witnesses.push({a,b,query:qi});}
 return {schema:'frontier/missing-move-v1',scope,values,queries,encoder,decoders,witnesses,source:'Surf the Exponential 1.2.0, section 6',authority:[],claim:'Exact finite representation construction; not learned construction or a new commercial frontier.'};
}
function verify(a){
 try{
  assert(a&&a.schema==='frontier/missing-move-v1','Unknown artifact schema');const values=domain(a.values),queries=queriesOf(values,a.scope),states=statesOf(values);
  assert(JSON.stringify(a.queries)===JSON.stringify(queries),'Changed query contract');assert(Array.isArray(a.encoder)&&a.encoder.length===states.length,'Incomplete source domain');assert(Array.isArray(a.decoders),'Missing decoder');
  let checks=0;const observed=new Set();
  for(let i=0;i<states.length;i++){const item=a.encoder[i];assert(JSON.stringify(item.input)===JSON.stringify(states[i]),'Source identity mismatch');assert(Number.isInteger(item.label)&&item.label>=0&&item.label<a.decoders.length,'Invalid label');observed.add(item.label);for(let j=0;j<queries.length;j++){const raw=states[i],v=queries[j];const expected=raw[0]<=v.hi&&raw[1]<=v.hi&&(v.kind==='upper'||(raw[0]>=v.lo&&raw[1]>=v.lo));assert(a.decoders[item.label][j]===(expected?1:0),'Wrong decoded result');checks++;}}
  const signatures=new Set(states.map(row=>queries.map(v=>(row[0]<=v.hi&&row[1]<=v.hi&&(v.kind==='upper'||(row[0]>=v.lo&&row[1]>=v.lo)))?'Y':'N').join('')));
  assert(observed.size===a.decoders.length&&a.decoders.length===signatures.size,'Nonminimal or unused labels');assert(Array.isArray(a.witnesses)&&a.witnesses.length===a.decoders.length*(a.decoders.length-1)/2,'Missing separation witnesses');
  const pairs=new Set();for(const w of a.witnesses){assert(Number.isInteger(w.a)&&Number.isInteger(w.b)&&w.a>=0&&w.b<a.decoders.length&&w.a<w.b,'Invalid witness labels');assert(Number.isInteger(w.query)&&w.query>=0&&w.query<queries.length,'Invalid witness query');assert(a.decoders[w.a][w.query]!==a.decoders[w.b][w.query],'False separation witness');pairs.add(`${w.a}:${w.b}`);}assert(pairs.size===a.witnesses.length,'Duplicate witness');
  assert(Array.isArray(a.authority)&&a.authority.length===0,'Artifact cannot grant authority');return {pass:true,checks,labels:a.decoders.length,minimum_labels:signatures.size,scope:a.scope};
 }catch(e){return {pass:false,error:e.message};}
}
function evaluate(a,raw,query){const v=verify(a);assert(v.pass,v.error);assert(Array.isArray(raw)&&raw.length===2&&raw.every(x=>Number.isSafeInteger(x)&&a.values.includes(x)),'Input is outside the declared finite domain');const qi=a.queries.findIndex(x=>JSON.stringify(x)===JSON.stringify(query));assert(qi>=0,'Question is outside the declared scope');const item=a.encoder.find(x=>x.input[0]===raw[0]&&x.input[1]===raw[1]);return Boolean(a.decoders[item.label][qi]);}
function missingRun(values=[60,80,100]){const parent=compile(values,'upper'),child=compile(values,'interval');const v1=verify(parent),v2=verify(child);return {parent,child,parent_check:v1,child_check:v2,mean_collision:collide(values,s=>(s[0]+s[1])/2,parent.queries),stale_collision:collide(values,s=>Math.max(...s),child.queries),conventional:'max for upper queries; min/max for interval queries. Same answers and minimum label counts.',model_calls:0};}
function combinations(xs,k){if(k===0)return [[]];if(xs.length<k)return [];const out=[];for(let i=0;i<=xs.length-k;i++)for(const tail of combinations(xs.slice(i+1),k-1))out.push([xs[i],...tail]);return out;}
function signs(n){const out=[];for(let m=0;m<2**(n-1);m++)out.push([1,...Array.from({length:n-1},(_,i)=>(m&(1<<i))?-1:1)]);return out;}
function makePlan(times,sig,degree=2){
 assert(times.length===degree+2&&times.length===sig.length,'Sparse schedule length mismatch');assert(new Set(times).size===times.length,'Duplicate time slot');
 const v=times.map((t,i)=>{let d=1n;for(let j=0;j<times.length;j++)if(i!==j)d*=BigInt(t-times[j]);return new Q(1n,d);});
 const norm=sum(v.map((w,i)=>w.mul(sig[i])));if(norm.n===0n)return null;const weights=v.map(w=>w.div(norm)),A=sum(weights.map(w=>w.abs()));const switches=sig.slice(1).filter((s,i)=>s!==sig[i]).length;
 return {times,signs:sig,weights,A,cost10:10*times.length+20*switches+times[times.length-1],degree};
}
function validatePlan(p){try{assert(p&&Array.isArray(p.times),'Missing plan');assert(p.times.length===p.degree+2&&p.signs.length===p.times.length&&p.weights.length===p.times.length,'Shape mismatch');assert(new Set(p.times).size===p.times.length&&p.times.every((x,i)=>Number.isInteger(x)&&x>=0&&(i===0||x>p.times[i-1])),'Invalid times');assert(p.signs.every(s=>s===1||s===-1),'Invalid polarity');for(let d=0;d<=p.degree;d++)assert(sum(p.weights.map((w,i)=>q(w).mul(BigInt(p.times[i])**BigInt(d)))).n===0n,'Drift cancellation failed');assert(sum(p.weights.map((w,i)=>q(w).mul(p.signs[i]))).cmp(1)===0,'Signal normalization failed');const A=sum(p.weights.map(w=>q(w).abs()));assert(A.cmp(p.A)===0,'Wrong amplification');const c=10*p.times.length+20*p.signs.slice(1).filter((s,i)=>s!==p.signs[i]).length+p.times.at(-1);assert(c===p.cost10,'Wrong cost');return {pass:true,moment_checks:p.degree+1};}catch(e){return {pass:false,error:e.message};}}
let CACHE=null;
function plans(){if(CACHE)return CACHE;let count=0,aliases=0;const valid=[];for(const tail of combinations([1,2,3,4,5,6,7,8],3))for(const sig of signs(4)){count++;const p=makePlan([0,...tail],sig);if(p)valid.push(p);else aliases++;}const unique=[];for(const p of valid)if(!unique.some(v=>v.cost10===p.cost10&&v.A.cmp(p.A)===0))unique.push(p);const pareto=unique.filter(p=>!unique.some(v=>v.cost10<=p.cost10&&v.A.cmp(p.A)<=0&&(v.cost10<p.cost10||v.A.cmp(p.A)<0)));CACHE={count,aliases,valid,pareto};return CACHE;}
function radius(c,o){const ec=q(c.A).div(1000),eo=q(o.A).div(1000);const r1=ec.add(eo).div(q(1).add(ec.mul(2)));return r1.cmp(eo)>=0?r1:eo;}
function selectPair(uses=1,tolerance='3/1000',full=false){assert(Number.isInteger(uses)&&uses>=1&&uses<=1000,'Uses must be an integer from 1 to 1,000');const bank=plans(),pool=full?bank.valid:bank.pareto;let best=null,feasible=0,compared=0;for(const c of pool)for(const o of pool){compared++;const r=radius(c,o);if(r.cmp(tolerance)>0)continue;feasible++;const total10=c.cost10+uses*o.cost10;if(!best||total10<best.total10||(total10===best.total10&&r.cmp(best.radius)<0))best={reference:c,query:o,total10,radius:r,uses};}return {best,feasible,compared,candidates:bank.count,informative:bank.valid.length,aliases:bank.aliases,pareto:bank.pareto.length,claim:'Minimum over the specified fixed sparse reference/query design class; supplied acquisition cost units, not currency or elapsed time.'};}
function readings(p,gain,signal,drift,errors){assert(drift.length>=1&&drift.length<=5,'Drift must contain 1–5 coefficients');return p.times.map((t,i)=>q(gain).mul(p.signs[i]).mul(signal).add(sum(drift.map((c,k)=>q(c).mul(BigInt(t)**BigInt(k))))).add(errors?q(errors[i]):0));}
function contrast(p,raw){assert(raw.length===p.times.length,'Reading count mismatch');return sum(raw.map((v,i)=>q(v).mul(p.weights[i])));}
function decode(p,c,raw,{gainFloor='1',signalBound='1',noise='1/1000',calNoise='1/1000'}={}){
 const ec=q(c.plan.A).mul(calNoise),eo=q(p.A).mul(noise),cv=contrast(c.plan,c.raw),z=contrast(p,raw);let a=cv.sub(ec),b=cv.add(ec);if(a.cmp(gainFloor)<0)a=q(gainFloor);assert(a.cmp(b)<=0&&a.cmp(0)>0,'Reference conflicts with gain bounds');const endpoints=[z.sub(eo).div(a),z.sub(eo).div(b),z.add(eo).div(a),z.add(eo).div(b)].sort((x,y)=>x.cmp(y));let lo=endpoints[0],hi=endpoints.at(-1),S=q(signalBound);if(lo.cmp(S.mul(-1))<0)lo=S.mul(-1);if(hi.cmp(S)>0)hi=S;assert(lo.cmp(hi)<=0,'Observations conflict with signal bound');return {gain_interval:[a,b],product:z,interval:[lo,hi],midpoint:lo.add(hi).div(2)};
}
function measurementRun(uses=1,cubic=false){const result=selectPair(uses),p=result.best;assert(p,'No supported pair');const gain=q('7/5'),signal=q('2/7'),calRaw=readings(p.reference,gain,1,[11,1,2]);const drift=cubic?[3,-2,1,'1/100']:[3,-2,1];const raw=readings(p.query,gain,signal,drift),decoded=decode(p.query,{plan:p.reference,raw:calRaw},raw);return {...result,gain,signal,reference_readings:calRaw,query_readings:raw,decoded,contains_truth:decoded.interval[0].cmp(signal)<=0&&decoded.interval[1].cmp(signal)>=0,scope_supported:!cubic,known_scope_violation:cubic?'Injected cubic drift exceeds this quadratic programme. Nominal interval is not a valid guarantee.':null,model_calls:0};}
function serial(x){return JSON.parse(JSON.stringify(x));}
const api={Q,q,domain,queriesOf,compile,verify,evaluate,collide,missingRun,makePlan,validatePlan,plans,radius,selectPair,readings,contrast,decode,measurementRun,serial};
if(typeof module!=='undefined'&&module.exports)module.exports=api;root.FRONTIER_CONSTRUCTION=api;
})(typeof window==='undefined'?globalThis:window);
