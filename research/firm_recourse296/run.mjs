export function run(){
 const job=(site,work,deadline,portable=true)=>({site,work,release:0,deadline,portable});
 // Each observation is [site0 available, site1 available, backup available].
 const cases=[
 {id:"diverse",jobs:[job(0,4,4),job(1,4,4)],worlds:[[[0,1,1],[1,0,1],[0,1,1],[1,0,1]],[[1,0,1],[0,1,1],[1,0,1],[0,1,1]],[[1,1,1],[1,1,1],[1,1,1],[1,1,1]]]},
 {id:"correlated",jobs:[job(0,4,4),job(1,4,4)],worlds:[[[0,0,1],[1,1,1],[1,1,1],[1,1,1]],[[1,1,1],[1,1,1],[1,1,1],[0,0,1]]]},
 {id:"slack",jobs:[job(0,2,4),job(1,2,4)],worlds:[[[0,0,1],[0,0,1],[1,1,1],[1,1,1]],[[1,1,1],[1,1,1],[0,0,1],[0,0,1]]]},
 {id:"causal_trap",jobs:[job(0,1,2),job(1,1,2)],worlds:[[[0,0,1],[1,0,0]],[[0,0,1],[0,1,0]]]},
 {id:"nonportable",jobs:[job(0,2,2,false),job(1,2,2)],worlds:[[[0,1,1],[1,0,1]],[[1,1,1],[1,1,1]]]}
 ];
 const key=x=>JSON.stringify(x);
 const groups=(worlds,t)=>{let g=new Map(); for(const w of worlds){let k=key(w[t]);if(!g.has(k))g.set(k,[]);g.get(k).push(w)} return [...g.values()]};
 function feasible(c,mode,cap,clair=false){
   let T=c.worlds[0].length,J=c.jobs.length,cache=new Map();
   function solve(t,left,worlds){
     if(t===T)return left.every(x=>x===0)?[]:null;
     if(left.some((x,i)=>x>Math.max(0,c.jobs[i].deadline-t)))return null;
     const k=key([t,left,worlds]);if(cache.has(k))return cache.get(k);
     let branches=[];
     for(const group of groups(worlds,t)){
       const o=group[0][t],local=mode==="firm"?[0,0]:o.slice(0,2);
       let chosen=null;
       for(let mask=0;mask<(1<<J);mask++){
         let used=[0,0],np=[0,0],next=left.slice(),ok=true;
         for(let i=0;i<J;i++)if(mask&(1<<i)){let j=c.jobs[i];if(!left[i]||t<j.release||t>=j.deadline){ok=false;break}used[j.site]++;if(!j.portable)np[j.site]++;next[i]--}
         if(!ok||np.some((v,s)=>v>local[s]))continue;
         const deficit=used.map((v,s)=>Math.max(0,v-local[s]));
         if(mode==="dedicated"?deficit.some((v,s)=>v>cap[s]*o[2]):deficit[0]+deficit[1]>cap*o[2])continue;
         let sub=solve(t+1,next,group);if(sub!==null){chosen={observation:o,mask,children:sub};break}
       }
       if(chosen===null){cache.set(k,null);return null} branches.push(chosen)
     }
     cache.set(k,branches);return branches
   }
   const left=c.jobs.map(j=>j.work);
   return clair?c.worlds.map(w=>solve(0,left,[w])):solve(0,left,c.worlds)
 }
 // Independent reference: enumerate per-world schedules with explicit assignments,
 // then join whole schedules only when every shared observation prefix has identical executed job set.
 function reference(c,mode,cap,clair=false){
   const T=c.worlds[0].length,J=c.jobs.length;
   const sets=c.worlds.map(w=>{
     const solutions=[];
     function rec(t,left,history){
       if(t===T){if(left.every(v=>v===0))solutions.push(history);return}
       const o=w[t],local=mode==="firm"?[0,0]:o.slice(0,2);
       for(let a=0;a<3**J;a++){
         let n=a,l=[0,0],b=[0,0],next=left.slice(),mask=0,ok=true;
         for(let i=0;i<J;i++){const x=n%3;n=Math.floor(n/3);if(!x)continue;let j=c.jobs[i];if(!left[i]||t<j.release||t>=j.deadline||(x===2&&!j.portable)){ok=false;break}
           (x===1?l:b)[j.site]++;next[i]--;mask|=1<<i;
         }
         if(!ok||l.some((v,s)=>v>local[s])||(mode==="dedicated"?b.some((v,s)=>v>cap[s]*o[2]):b[0]+b[1]>cap*o[2]))continue;
         rec(t+1,next,[...history,mask])
       }
     }rec(0,c.jobs.map(j=>j.work),[]);return [...new Map(solutions.map(s=>[key(s),s])).values()]
   });
   if(clair)return sets.every(s=>s.length>0);
   function join(i,chosen){
     if(i===sets.length)return true;
     return sets[i].some(s=>chosen.every((prev,k)=>{for(let t=0;t<T;t++){if(key(c.worlds[k].slice(0,t+1))!==key(c.worlds[i].slice(0,t+1)))break;if(prev[t]!==s[t])return false}return true})&&join(i+1,[...chosen,s]))
   }return join(0,[])
 }
 // Replay every feasible causal policy against every scenario and explicit resource capacities.
 function replay(c,mode,cap,tree){
   let checked=0;
   for(const w of c.worlds){let left=c.jobs.map(j=>j.work),nodes=tree;
     for(let t=0;t<w.length;t++){let o=w[t],node=nodes.find(x=>key(x.observation)===key(o));if(!node)throw Error("missing branch");
       let available=mode==="firm"?[0,0]:o.slice(0,2),counts=[0,0],fixed=[0,0];
       for(let i=0;i<c.jobs.length;i++)if(node.mask&(1<<i)){let j=c.jobs[i];if(left[i]===0||t<j.release||t>=j.deadline)throw Error("invalid work");left[i]--;counts[j.site]++;if(!j.portable)fixed[j.site]++}
       if(fixed.some((v,s)=>v>available[s]))throw Error("nonportable");let need=counts.map((v,s)=>Math.max(0,v-available[s]));
       if(mode==="dedicated"?need.some((v,s)=>v>cap[s]*o[2]):need[0]+need[1]>cap*o[2])throw Error("capacity");
       nodes=node.children;checked++;
     }if(left.some(v=>v!==0))throw Error("incomplete")
   }return checked
 }
 let results=[],checks=0,replaySlots=0;
 for(const c of cases){
   const arms=[];
   for(const mode of ["pooled","dedicated","firm","clairvoyant"]){
     const caps=mode==="dedicated"?[[0,0],[0,1],[1,0],[0,2],[1,1],[2,0],[1,2],[2,1],[2,2]]:[0,1,2];
     for(const cap of caps){
       const clair=mode==="clairvoyant",m=clair?"pooled":mode;
       const witness=feasible(c,m,cap,clair),pass=clair?witness.every(x=>x!==null):witness!==null;
       const ref=reference(c,m,cap,clair);checks++;
       if(pass!==ref)throw Error("reference disagreement "+c.id+" "+mode+" "+key(cap));
       if(pass&&!clair)replaySlots+=replay(c,m,cap,witness);
       arms.push({mode,cap,pass,witness:pass?witness:null});
     }
   }
   let minimum={};
   for(const m of ["pooled","dedicated","firm","clairvoyant"]){const vals=arms.filter(x=>x.mode===m&&x.pass).map(x=>Array.isArray(x.cap)?x.cap.reduce((a,b)=>a+b,0):x.cap);minimum[m]=vals.length?Math.min(...vals):null}
   results.push({id:c.id,slots:c.worlds[0].length,worlds:c.worlds.length,minimum,arms})
 }
 return {cases:results,referenceChecks:checks,replaySlots};
}
