function run281(raws) {
 const obj=x=>x!==null&&typeof x==="object"&&!Array.isArray(x);
 const cut=(x,k)=>Object.fromEntries(Object.entries(x).filter(([a])=>a!==k));
 const canon=x=>Array.isArray(x)?"["+x.map(canon).join(",")+"]":obj(x)?"{"+Object.keys(x).sort().map(k=>JSON.stringify(k)+":"+canon(x[k])).join(",")+"}":JSON.stringify(x);
 function inventory(j) {
   if(!obj(j)||!Array.isArray(j.pages))throw Error("ROOT");
   const root=cut(j,"pages"), entries=new Map(), pages=[], pageNames=new Set();
   const groups=new Map();
   function scan(n){if(!obj(n)||typeof n.name!=="string"||!n.name)throw Error("INVALID_NAME");if(!groups.has(n.name))groups.set(n.name,[]);groups.get(n.name).push(n.type);if("elements"in n){if(!Array.isArray(n.elements))throw Error("ELEMENTS");n.elements.forEach(scan);}}
   j.pages.forEach(p=>{if(!Array.isArray(p.elements))throw Error("PAGE");p.elements.forEach(scan)});
   for(const [name,types] of groups)if(types.length>1&&!types.every(t=>t==="html"))throw Error("DUPLICATE_ANSWER_OR_NONDISPLAY:"+name);
   function visit(n,anc,path) {
     if(!obj(n)||typeof n.name!=="string"||!n.name||typeof n.type!=="string")throw Error("ELEMENT_INVALID_OR_DUPLICATE:"+n?.name);
     if("elements" in n&&!Array.isArray(n.elements))throw Error("ELEMENTS");
     // The published schema uses pages/elements. Detect other nested named typed nodes.
     function unexpected(v){if(Array.isArray(v)){v.forEach(unexpected);return}if(obj(v)){if(typeof v.name==="string"&&typeof v.type==="string")throw Error("UNSUPPORTED_NESTED:"+v.name);Object.values(v).forEach(unexpected)}}
     Object.values(cut(n,"elements")).forEach(unexpected);
     const id=groups.get(n.name).length===1?n.name:JSON.stringify([...anc.map(a=>a.name),n.name]);
     if(entries.has(id)||groups.get(n.name).length>1&&groups.has(id))throw Error("DUPLICATE_QUALIFIED_ID:"+id);
     entries.set(id,{def:n,context:{root,anc,path}});
     if("elements"in n)n.elements.forEach((x,i)=>visit(x,[...anc,cut(n,"elements")],[...path,i]));
   }
   j.pages.forEach((p,i)=>{if(!obj(p)||typeof p.name!=="string"||!p.name||pageNames.has(p.name)||!Array.isArray(p.elements))throw Error("PAGE");pageNames.add(p.name);pages.push(cut(p,"elements"));p.elements.forEach((n,k)=>visit(n,[cut(p,"elements")],[i,k]));});
   return {root,entries,pages};
 }
 function equal(a,b){if(a===b)return true;if(!a||!b||typeof a!=="object"||typeof b!=="object"||Array.isArray(a)!==Array.isArray(b))return false;const ka=Object.keys(a),kb=Object.keys(b);return ka.length===kb.length&&ka.every(k=>Object.prototype.hasOwnProperty.call(b,k)&&equal(a[k],b[k]));}
 function ordinary(j) {
   const root={...j};delete root.pages;
   const result=new Map();const queue=j.pages.flatMap((p,i)=>{const pmeta={...p};delete pmeta.elements;return p.elements.map((n,k)=>({n,anc:[pmeta],path:[i,k]}))});
   for(let i=0;i<queue.length;i++){const {n,anc,path}=queue[i];if(n.elements){const meta={...n};delete meta.elements;n.elements.forEach((v,k)=>queue.push({n:v,anc:anc.concat([meta]),path:path.concat([k])}))}}
   const names=new Map();for(const {n} of queue)names.set(n.name,(names.get(n.name)||0)+1);
   for(const {n,anc,path} of queue){const id=names.get(n.name)===1?n.name:JSON.stringify(anc.map(a=>a.name).concat(n.name));if(result.has(id)||names.get(n.name)>1&&n.type!=="html")throw Error("CONTROL_DUPLICATE");result.set(id,{def:n,context:{root,anc,path}})}
   return result;
 }
 function classify(a,b,eq) {
   const added=[],removed=[],modified=[],context=[],unchanged=[];
   for(const id of [...new Set([...a.keys(),...b.keys()])].sort()){
      if(!a.has(id))added.push(id);else if(!b.has(id))removed.push(id);else{const x=a.get(id),y=b.get(id);const d=!eq(x.def,y.def),c=!eq(x.context,y.context);if(d)modified.push(id);if(c)context.push(id);if(!d&&!c)unchanged.push(id);}
   }
   return {added,removed,modified,context,unchanged};
 }
 function compare(a,b){
   const x=inventory(a),y=inventory(b), result=classify(x.entries,y.entries,(u,v)=>canon(u)===canon(v)), control=classify(ordinary(a),ordinary(b),equal);
   const root_changed=canon(x.root)!==canon(y.root),page_metadata_changed=canon(x.pages)!==canon(y.pages),document_changed=canon(a)!==canon(b);
   const allocated=root_changed||page_metadata_changed||["added","removed","modified","context"].some(k=>result[k].length>0);
   return {before_count:x.entries.size,after_count:y.entries.size,...result,root_changed,page_metadata_changed,document_changed,unallocated:document_changed&&!allocated,ordinary_agrees:equal(result,control)};
 }
 const inputs=raws.map(x=>JSON.parse(x)), snapshot=canon(inputs);
 const pairs=inputs.slice(1).map((x,i)=>compare(inputs[i],x));
 const base=inputs[1],clone=()=>JSON.parse(JSON.stringify(base));
 const def=clone();let changed;for(const p of def.pages){const stack=p.elements.slice();while(stack.length){const q=stack.shift();if(Array.isArray(q.choices)&&q.choices.length){q.choices.push("281-synthetic-sentinel");changed=q.name;break;}if(q.elements)stack.push(...q.elements);}if(changed)break;}if(!changed)throw Error("NO_CHOICE");
 const root=clone();root.showProgressBar="281-synthetic-root";
 const anc=clone();anc.pages[1].title="281-synthetic-ancestor";
 const adversarial={definition:compare(base,def),root:compare(base,root),ancestor:compare(base,anc)};
 const duplicateAnswer=clone(), duplicateHTML=clone();
 function duplicate(j,type){for(const p of j.pages){const q=[p.elements];while(q.length){const arr=q.shift();for(const n of arr){if(n.type===type){arr.push(JSON.parse(JSON.stringify(n)));return;}if(n.elements)q.push(n.elements)}}}throw Error("NO_DUPLICATION_TARGET")}
 duplicate(duplicateAnswer,"radiogroup");duplicate(duplicateHTML,"html");
 function rejects(j){try{inventory(j);return false}catch(e){return String(e).includes("DUPLICATE")}}
 const acceptance={duplicate_answer_rejected:rejects(duplicateAnswer),duplicate_same_ancestry_html_rejected:rejects(duplicateHTML),two_distinct_display_nodes:inventory(base).entries.has(JSON.stringify(["consultationDesign","consultationDesignPanel-MS","consultation-intro"]))&&inventory(base).entries.has(JSON.stringify(["consultationImplementation","consultationImplementationPanel-MS","consultation-intro"])),all_pairs_agree:pairs.every(x=>x.ordinary_agrees),no_unallocated:[...pairs,...Object.values(adversarial)].every(x=>!x.unallocated),mutation_definition:adversarial.definition.modified.includes(changed),mutation_root:adversarial.root.root_changed&&adversarial.root.context.length===adversarial.root.before_count,mutation_ancestor:adversarial.ancestor.page_metadata_changed&&adversarial.ancestor.context.length>0,all_mutations_agree:Object.values(adversarial).every(x=>x.ordinary_agrees),inputs_unchanged:snapshot===canon(inputs)};
 return {pairs,adversarial,changed,acceptance,pass:Object.values(acceptance).every(Boolean),scope:"structural review triage only; no assessment transferred, scored, or approved"};
}

// Offline usage: node instrument.cjs <four downloaded survey JSON files in frozen order>
if (require.main === module) {
 const fs=require('node:fs'); const args=process.argv.slice(2); if(args.length!==4) throw Error('four frozen input paths required');
 const start=process.hrtime.bigint(), cpu=process.cpuUsage(); const result=run281(args.map(p=>fs.readFileSync(p,'utf8'))); result.telemetry={wall_seconds:Number(process.hrtime.bigint()-start)/1e9,cpu_microseconds:process.cpuUsage(cpu)}; console.log(JSON.stringify(result,null,2)); if(!result.pass)process.exitCode=1;
}
module.exports=run281;
