// Frozen finite construction; see PROTOCOL.md. Stand-alone, no dependencies.
function instrument(){
const dates=["06-11","06-12","06-18","07-01","07-02","07-03","07-04","07-05","07-15","07-16","07-17","08-06","08-07","08-08","08-09","08-10","08-11","08-13","08-17"];
const days=138,H=days*24,C=24,A=20,K=19,ds=[1,8,24,48],fs=[0,8,12,16,20,24];
const start=Date.UTC(2026,4,16);function day(s){let [m,d]=s.split("-").map(Number);return (Date.UTC(2026,m-1,d)-start)/86400000;}
function make(n,calls){const p=new Uint8Array(n*24);for(const d of calls){if(!Number.isInteger(d)||d<0||d>=n)throw Error("invalid day");for(let h=14;h<21;h++)p[d*24+h]=1;}return p;}
const obs=make(days,dates.map(day)),stress=make(days,Array.from({length:K},(_,i)=>i));
function formula(l,k){return Math.min(k*7,Math.floor(l/24)*7+Math.min(l%24,7));}
function maxByLength(p){const h=p.length,pre=new Int32Array(h+1),out=new Int32Array(h+1);for(let i=0;i<h;i++)pre[i+1]=pre[i]+p[i];for(let l=1;l<=h;l++){let m=0;for(let s=0;s+l<=h;s++)m=Math.max(m,pre[s+l]-pre[s]);out[l]=m;}return out;}
const observedMax=maxByLength(obs),stressMax=maxByLength(stress);
let tiny=new Int32Array(121),tinyCalendars=0;for(let mask=0;mask<32;mask++){let c=[];for(let i=0;i<5;i++)if(mask&(1<<i))c.push(i);if(c.length>2)continue;tinyCalendars++;let x=maxByLength(make(5,c));for(let i=1;i<x.length;i++)tiny[i]=Math.max(tiny[i],x[i]);}
const tinyOK=Array.from(tiny).every((m,l)=>m===formula(l,2)),stressEnvelope=Array.from(stressMax).every((m,l)=>m===formula(l,K));
function cert(D,F,mode){let min=Infinity,w=null;for(let l=D;l<=H;l++){const cut=mode==="robust"?formula(l,K):observedMax[l],demand=A*(l-D+1),cap=C*l-(C-F)*cut,slack=cap-demand;if(slack<min){min=slack;w={length:l,curtailedHours:cut,demand,capacity:cap};}}return {accepted:min>=0,minSlack:min,binding:w};}
function edf(D,F,p){let rem=new Int32Array(H),head=0,done=0,miss=0,first=null;for(let t=0;t<H;t++){if(t+D<=H)rem[t]=A;let cap=p[t]?F:C;while(head<=t){if(rem[head]===0){head++;continue;}if(cap===0)break;let x=Math.min(cap,rem[head]);rem[head]-=x;cap-=x;done+=x;}let exp=t-D+1;if(exp>=0&&rem[exp]>0){miss+=rem[exp];if(first===null)first=t+1;rem[exp]=0;}}return {accepted:miss===0,completed:done,missed:miss,firstMissDeadlineHour:first,offered:A*(H-D+1)};}
let arms=[];for(const D of ds)for(const F of fs){let o=cert(D,F,"observed"),r=cert(D,F,"robust"),e=edf(D,F,obs),s=edf(D,F,stress);arms.push({D,F,observed:o,robust:r,edfObserved:e,edfStress:s});}
let thresholds=ds.map(D=>({D,gridObserved:fs.find(F=>cert(D,F,"observed").accepted)??null,gridRobust:fs.find(F=>cert(D,F,"robust").accepted)??null,exactIntegerObserved:Array.from({length:25},(_,i)=>i).find(F=>cert(D,F,"observed").accepted)??null,exactIntegerRobust:Array.from({length:25},(_,i)=>i).find(F=>cert(D,F,"robust").accepted)??null}));
let checks={noticeCount:new Set(dates).size===19,curtailedHours:obs.reduce((a,b)=>a+b,0)===133,miniatureExhaustive:tinyOK,fullStressAttainsEnvelope:stressEnvelope,observedMatchesEDF:arms.every(a=>a.observed.accepted===a.edfObserved.accepted),robustMatchesStressEDF:arms.every(a=>a.robust.accepted===a.edfStress.accepted),robustImpliesObserved:arms.every(a=>!a.robust.accepted||a.observed.accepted),workConservation:arms.every(a=>[a.edfObserved,a.edfStress].every(e=>e.completed+e.missed===e.offered))};
return {schema:"flexible-compute-envelope277/v1",scope:"historical notice timing plus authored workloads; not measured compute or power",dates,days,H,C,A,K,tinyCalendars,checks,accepted:Object.values(checks).every(Boolean),thresholds,arms,commerce:{nativeAccount:false,realContracts:0,realRevenue:0,completeCostProfit:null,actualBilling:"UNKNOWN",targetAchieved:false},decision:"NO_DEPLOY_PENDING_BENEFICIARY_AND_COMPLETE_COST_EVIDENCE"};
}
console.log(JSON.stringify(instrument(),null,2));
