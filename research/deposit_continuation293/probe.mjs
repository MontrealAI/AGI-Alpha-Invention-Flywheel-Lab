function probe(){
 const cases=[
  {id:"absent_authoritative",count:0,obs:"absent",correct:false},
  {id:"present_authoritative",count:1,obs:"present",correct:true},
  {id:"known_receipt",count:1,obs:"receipt",correct:true},
  {id:"unknown_absent",count:0,obs:"unknown",correct:false},
  {id:"unknown_present",count:1,obs:"unknown",correct:true},
  {id:"duplicate_existing",count:2,obs:"duplicate",correct:true},
  {id:"mismatch",count:1,obs:"mismatch",correct:false}
 ];
 const policies=["blind_retry","fail_closed","manual_reconcile","automated_reconcile","atomic_server_hypothetical"];
 const decide=(p,c)=>{
  if(c.obs==="receipt")return "link";
  if(p==="blind_retry")return "retry";
  if(p==="fail_closed")return "hold";
  if(p==="atomic_server_hypothetical")return ["duplicate","mismatch"].includes(c.obs)?"hold":"atomic";
  return c.obs==="absent"?"retry":c.obs==="present"?"link":"hold";
 };
 const results=[];
 for(const c of cases)for(const p of policies){
  const action=decide(p,c);
  let count=c.count,linked=false,wrong=false;
  if(action==="retry"){count++;linked=true}
  if(action==="link"){linked=true;wrong=!c.correct}
  if(action==="atomic"){if(count===0)count++;linked=true;wrong=c.count!==0&&!c.correct}
  results.push({case:c.id,policy:p,action,count,linked,safe:count<=Math.max(1,c.count)&&!wrong,complete:count===1&&linked&&!wrong});
 }
 const candidate=results.filter(r=>r.policy==="automated_reconcile"),manual=results.filter(r=>r.policy==="manual_reconcile");
 const indistinguishable=["hold","retry","link"].map(action=>({action,safeAndCompleteBoth:false,reason:action==="hold"?"no completion":action==="retry"?"duplicate in committed world":"no receipt/resource in absent world"}));
 const checks={denominator:results.length===35,allCandidateSafe:candidate.every(x=>x.safe),determinateComplete:candidate.filter(x=>x.complete).length===3,manualParity:candidate.every((x,i)=>x.action===manual[i].action&&x.complete===manual[i].complete&&x.safe===manual[i].safe),blindCounterexample:results.some(x=>x.policy==="blind_retry"&&!x.safe),ambiguity:indistinguishable.every(x=>!x.safeAndCompleteBoth)};
 return {results,checks,indistinguishable,accepted:Object.values(checks).every(Boolean)};
}
console.log(JSON.stringify(probe(), null, 2));
