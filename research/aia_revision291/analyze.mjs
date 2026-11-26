// AIA291: read-only structural reassessment worklist; no compliance decision.
// Input: four objects {ref,doc} in protocol order. Pure ES module.
export function analyze(sources) {
  const response=new Set(["text","dropdown","radiogroup","comment","checkbox"]);
  const canon=x=>x===null||typeof x!=="object"?JSON.stringify(x):Array.isArray(x)?"["+x.map(canon).join(",")+"]":"{"+Object.keys(x).sort().map(k=>JSON.stringify(k)+":"+canon(x[k])).join(",")+"}";
  const omit=(x,k)=>Object.fromEntries(Object.entries(x).filter(([a])=>a!==k));
  const eq=(a,b)=>canon(a)===canon(b);
  function index(doc){
    const m=new Map();
    function walk(parent,ctx) {
      if(!Array.isArray(parent.elements))throw Error("ELEMENTS_NOT_ARRAY");
      for(const e of parent.elements){
        if(typeof e.name!=="string"||!e.name)throw Error("MISSING_NAME");
        if(e.type==="panel"){walk(e,[...ctx,omit(e,"elements")]);continue;}
        if(e.type==="html")continue;
        if(!response.has(e.type))throw Error("UNREGISTERED_TYPE:"+e.type);
        if(m.has(e.name))throw Error("DUPLICATE_RESPONSE:"+e.name);
        m.set(e.name,{own:e,ctx});
      }
    }
    if(!Array.isArray(doc.pages))throw Error("PAGES_NOT_ARRAY");
    for(const page of doc.pages)walk(page,[omit(doc,"pages"),omit(page,"elements")]);
    return m;
  }
  function independent(doc){
    const m=new Map();
    function visit(x){
      if(!x||typeof x!=="object")return;
      if(response.has(x.type)&&typeof x.name==="string"){
        if(m.has(x.name))throw Error("BASELINE_DUPLICATE:"+x.name);
        m.set(x.name,x);
      }
      Object.values(x).forEach(visit);
    }
    visit(doc);return m;
  }
  const out=[];
  for(let i=1;i<sources.length;i++){
    const a=sources[i-1],b=sources[i],m=index(a.doc),n=index(b.doc),u=independent(a.doc),v=independent(b.doc);
    const keys=[...new Set([...m.keys(),...n.keys()])].sort();
    const groups={added:[],removed:[],own_changed:[],context_only:[],structurally_unchanged:[]};
    for(const k of keys){
      if(!m.has(k))groups.added.push(k);
      else if(!n.has(k))groups.removed.push(k);
      else if(!eq(m.get(k).own,n.get(k).own)){
        const x=m.get(k).own,y=n.get(k).own;
        const fields=[...new Set([...Object.keys(x),...Object.keys(y)])].sort().filter(f=>!Object.hasOwn(x,f)||!Object.hasOwn(y,f)||!eq(x[f],y[f]));
        groups.own_changed.push({id:k,fields});
      } else if(!eq(m.get(k).ctx,n.get(k).ctx))groups.context_only.push(k);
      else groups.structurally_unchanged.push(k);
    }
    const ukeys=[...new Set([...u.keys(),...v.keys()])].sort();
    const expected=ukeys.filter(k=>u.has(k)&&v.has(k)&&!eq(u.get(k),v.get(k)));
    if(!eq([...m.keys()].sort(),[...u.keys()].sort())||!eq([...n.keys()].sort(),[...v.keys()].sort())||!eq(expected,groups.own_changed.map(x=>x.id)))throw Error("INDEPENDENT_OWN_DELTA_DISAGREEMENT");
    const counts=Object.fromEntries(Object.entries(groups).map(([k,x])=>[k,x.length]));
    if(Object.values(counts).reduce((a,b)=>a+b,0)!==keys.length||m.size+counts.added!==n.size+counts.removed)throw Error("PARTITION_FAILURE");
    out.push({before:a.ref,after:b.ref,before_count:m.size,after_count:n.size,counts,added:groups.added,removed:groups.removed,own_changed:groups.own_changed,context_only:groups.context_only,unchanged_structural_candidates:groups.structurally_unchanged.length,independent_own_delta_agrees:true,automatic_carry_forward_authorized:false});
  }
  return out;
}
