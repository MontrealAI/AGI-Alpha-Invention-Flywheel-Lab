# Spectral transfer 298 — frozen development comparison

Base b35f937fcb77199334e267360e9a0c9e438a74ad. Independent research only; no account, protected runtime or deployment. Compare (1) accepted molecular identification through public spectral evidence and a future measurement partner, (2) energy-efficient compute instrument development under NSF X-Labs, (3) hybrid AI application construction, (4) no entry. Select (1) only for a bounded falsification of reference transfer, not commercial admission. Primary opportunity: https://www.kaggle.com/competitions/enveda-CASMI26-molecule-id-mass-spectra/ (entry Dec 7, final Dec 14 2026). Alternatives: https://www.nsf.gov/tip/updates/nsf-releases-final-x-labs-funding-opportunity-2026 and https://buildhybridai.devpost.com/ (not verified beyond third-party listing). No prize entry or outreach. Established SIRIUS/CSI:FingerID, GNPS and modified-cosine library matching remain strong alternatives; this test does not claim to beat them.

Source: MassBank/MassBank-data at 72980b3af504cfd1e89ac54d7698d3da45d85a58, directory CASMI_2012, every .txt record except SMI00001 (inspected schema development record). Retrieve each pinned record, record blob SHA and license; do not publish raw spectra. No post-result filtering beyond declared criteria. CC BY records only, parse all peaks and require count agreement, positive precursor, known connectivity and MS2, same ion mode. Leave one spectrum out at a time; reference identities grouped by connectivity, not tautomer canonicalization. Compare mass-only nearest precursor, maximum spectral similarity across reference records, mean spectral similarity across same reference groups. Fixed 0.1 Da bins and square-root intensity cosine, alphabetical key tie break. No target labels in ranking except library reference identities. Cases with no same-mode reference are reported not scored. Report all eligible and ineligible cases, top1 and MRR. Sparse cosine independently arithmetic-checked against union vector dot products. Stop after one pass. No optimization or repeated sampling; no inference about unseen structures, competition performance, customer value, physical acceptance, human time, or commercial profit. Prototype adoption requires later source-independent instruments/measurements and matched strong methods; this is exposed historical development, not holdout. No paid calls, actual billing unknown.

Source retrieval and analysis code are separated. The connector run uses the exact analyze function below, also executable with Node on JSON input records {id,sha,content}. Input IDs from pinned directory list. Local runtime DNS failure before registration is retained as retrieval limitation; connector reads are the authorized alternative.

```js
function analyze(records){
  const parsed=records.map(r=>{
    const s=r.content, line=(regex)=>s.match(regex)?.[1]?.trim()??null;
    const key=line(/^CH\$LINK: INCHIKEY ([^\s]+)/m)?.split("-")[0], mode=line(/^AC\$MASS_SPECTROMETRY: ION_MODE (.+)$/m), mz=Number(line(/^MS\$FOCUSED_ION: PRECURSOR_M\/Z (.+)$/m)), type=line(/^AC\$MASS_SPECTROMETRY: MS_TYPE (.+)$/m), license=line(/^LICENSE: (.+)$/m);
    const segment=s.split(/^PK\$PEAK:.*$/m)[1]?.split(/^\/\//m)[0]??"";
    const bins=new Map();let count=0;
    for(const l of segment.split("\n")){const m=l.trim().match(/^(\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\s+(\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)\s+(\d+(?:\.\d+)?)$/);if(!m)continue;const b=Math.round(Number(m[1])*10),v=Number(m[2]);if(v<0||!Number.isFinite(v))continue;bins.set(b,(bins.get(b)||0)+v);count++;}
    const expected=Number(line(/^PK\$NUM_PEAK: (.+)$/m));
    const norm=Math.sqrt([...bins.values()].reduce((a,b)=>a+b,0));
    const vector=new Map([...bins].map(([b,v])=>[b,Math.sqrt(v)/norm]));
    return {id:r.id,sha:r.sha,key,mode,mz,type,license,count,expected,vector,eligible:!!key&&!!mode&&mz>0&&type==="MS2"&&count===expected&&norm>0&&!!license&&/^CC BY(?:$| [0-9])/.test(license)};
  });
  const cases=[];let comparisons=0,checks=0;
  for(const q of parsed){
    if(!q.eligible){cases.push({id:q.id,status:"INELIGIBLE",parsed_peaks:q.count,declared_peaks:q.expected,license:q.license});continue;}
    const groups=new Map();
    for(const r of parsed){if(!r.eligible||r.id===q.id||r.mode!==q.mode)continue;
      let score=0;for(const [b,v] of q.vector)score+=v*(r.vector.get(b)||0);
      const dense=[...new Set([...q.vector.keys(),...r.vector.keys()])].map(b=>(q.vector.get(b)||0)*(r.vector.get(b)||0)).reduce((a,b)=>a+b,0);
      if(Math.abs(score-dense)>1e-12||score< -1e-12||score>1+1e-12)throw Error("cosine verification");
      checks++;comparisons++;
      const g=groups.get(r.key)||{key:r.key,scores:[],mass:Infinity};
      g.scores.push(score);g.mass=Math.min(g.mass,Math.abs(q.mz-r.mz));groups.set(r.key,g);
    }
    if(!groups.has(q.key)){cases.push({id:q.id,status:"NO_SAME_MODE_REFERENCE",candidate_groups:groups.size});continue;}
    const gs=[...groups.values()].map(g=>({key:g.key,mass:g.mass,best:Math.max(...g.scores),mean:g.scores.reduce((a,b)=>a+b,0)/g.scores.length}));
    const rank=(metric,ascending)=>gs.slice().sort((a,b)=>(ascending?a[metric]-b[metric]:b[metric]-a[metric])||a.key.localeCompare(b.key)).findIndex(x=>x.key===q.key)+1;
    cases.push({id:q.id,status:"EVALUATED",candidate_groups:gs.length,reference_count:groups.get(q.key).scores.length,mass:rank("mass",true),best:rank("best",false),mean:rank("mean",false)});
  }
  const evaluated=cases.filter(x=>x.status==="EVALUATED"),metrics={};
  for(const k of ["mass","best","mean"])metrics[k]={top1:evaluated.filter(x=>x[k]===1).length,mrr:evaluated.length?evaluated.reduce((a,b)=>a+1/b[k],0)/evaluated.length:null};
  return {registered:records.length,eligible:parsed.filter(x=>x.eligible).length,evaluated:evaluated.length,comparisons,checks,metrics,cases,inputs:parsed.map(x=>({id:x.id,sha:x.sha,license:x.license}))};
}
```
