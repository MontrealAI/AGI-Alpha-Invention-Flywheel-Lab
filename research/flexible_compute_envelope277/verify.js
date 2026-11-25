// Independent cumulative-service adjudicator; run with node verify.js RESULT.json
const fs=require('node:fs');
function independentReplay(j){
  const called=new Set(j.dates), start=Date.UTC(2026,4,16);
  function accepted(D,F,stress){let served=0,offered=0,firstMiss=null;for(let h=0;h<j.H;h++){let d=Math.floor(h/24),time=h%24,day=new Date(start+d*86400000).toISOString().slice(5,10);let cut=(stress?d<j.K:called.has(day))&&time>=14&&time<21;if(h<=j.H-D)offered+=j.A;served=Math.min(offered,served+(cut?F:j.C));let due=j.A*Math.max(0,h-D+2);if(served<due&&firstMiss===null)firstMiss=h+1;}return firstMiss===null;}
  let thresholds=j.thresholds.map(t=>({D:t.D,observed:Array.from({length:25},(_,i)=>i).find(F=>accepted(t.D,F,false)),stress:Array.from({length:25},(_,i)=>i).find(F=>accepted(t.D,F,true))}));return {thresholds,allThresholdsMatch:thresholds.every((t,i)=>t.observed===j.thresholds[i].exactIntegerObserved&&t.stress===j.thresholds[i].exactIntegerRobust),allGridArmsMatch:j.arms.every(a=>accepted(a.D,a.F,false)===a.observed.accepted&&accepted(a.D,a.F,true)===a.robust.accepted)};
}
const result=independentReplay(JSON.parse(fs.readFileSync(process.argv[2],'utf8')));console.log(JSON.stringify(result,null,2));if(!result.allThresholdsMatch||!result.allGridArmsMatch)process.exitCode=1;
