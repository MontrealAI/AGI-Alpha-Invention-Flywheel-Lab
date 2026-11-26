/* 290: frozen observational fixed-schedule reserve envelope, not power or SLA.
 * Node: node experiment.js < publisher.csv
 * Inputs: alibaba/clusterdata@3858992ca41bf92082e6d6522ddf0bebd14e838b
 * cluster-trace-gpu-v2023/csv/openb_pod_list_default.csv
 * Git blob bd82505791c723c5b11486ef457fb338529912c0.
 */
function analyze(csv) {
  const lines=csv.trimEnd().split(/\r?\n/);
  if(lines.shift()!=="name,cpu_milli,memory_mib,num_gpu,gpu_milli,gpu_spec,qos,pod_phase,creation_time,deletion_time,scheduled_time") throw Error("HEADER");
  const seen=new Set(), rows=[], excluded={}, qos={}, phase={};
  function inc(o,k){o[k]=(o[k]||0)+1;}
  for(const line of lines){
    const a=line.split(",");
    if(a.length!==11 || !a[0] || seen.has(a[0])) throw Error("ROW_OR_DUPLICATE");
    seen.add(a[0]);inc(qos,a[6]);inc(phase,a[7]);
    const [n,m,s,e]=[a[3],a[4],a[10],a[9]].map(x=>x===""?NaN:Number(x));
    if(![n,m,s,e].every(Number.isSafeInteger)||n<0||m<0||s<0||e<=s||n>8||m>1000||(n>1&&m!==1000)||(n>0&&m===0)){inc(excluded,"invalid_or_nonpositive_interval");continue;}
    if(n===0){inc(excluded,"cpu_only");continue;}
    // Requested GPU-equivalent, not measured utilization or physically fungible GPU count.
    rows.push({s,e,g:n*m,q:a[6]});
  }
  if(lines.length!==8152||!rows.length) throw Error("PUBLISHER_DENOMINATOR");
  const start=Math.min(...rows.map(r=>r.s)),end=Math.max(...rows.map(r=>r.e));
  const scopes=[["all",()=>true],["non_BE",r=>r.q!=="BE"],["LS_only",r=>r.q==="LS"]];
  const out={rows:lines.length,qos,phase,excluded,eligible:rows.length,start,end,scopes:{}};
  for(const [name,select] of scopes){
    const chosen=rows.filter(select), events=new Map([[start,0],[end,0]]);
    let work=0;
    for(const {s,e,g} of chosen){events.set(s,(events.get(s)||0)+g);events.set(e,(events.get(e)||0)-g);work+=g*(e-s);}
    const points=[...events.keys()].sort((a,b)=>a-b);
    let active=0,peak=0,peak_t=start,area=0, checks=0;
    for(let i=0;i<points.length;i++){
      const t=points[i];active+=events.get(t);
      if(active<0)throw Error("NEGATIVE");
      // Independent interval-membership recomputation, including simultaneous boundaries.
      let direct=0;for(const r of chosen){if(r.s<=t&&t<r.e)direct+=r.g;}
      if(direct!==active)throw Error("DIRECT_MISMATCH"); checks++;
      if(active>peak){peak=active;peak_t=t;}
      if(i+1<points.length)area+=active*(points[i+1]-t);
    }
    if(active!==0||area!==work||!Number.isSafeInteger(area))throw Error("CONSERVATION");
    out.scopes[name]={jobs:chosen.length,peak_milli_gpu:peak,peak_t,requested_milli_gpu_seconds:work,mean_milli_gpu:work/(end-start),direct_checks:checks};
  }
  if(out.scopes.all.peak_milli_gpu<out.scopes.non_BE.peak_milli_gpu||out.scopes.non_BE.peak_milli_gpu<out.scopes.LS_only.peak_milli_gpu)throw Error("NESTING");
  return out;
}
if(typeof require!=="undefined"&&typeof module!=="undefined"&&require.main===module){
  const fs=require("fs"),crypto=require("crypto"),b=fs.readFileSync(0);
  const h=crypto.createHash("sha1").update("blob "+b.length+"\\0".replace("\\0","\0")).update(b).digest("hex");
  if(h!=="bd82505791c723c5b11486ef457fb338529912c0")throw Error("BLOB_MISMATCH");
  console.log(JSON.stringify(analyze(b.toString("utf8")),null,2));
}
