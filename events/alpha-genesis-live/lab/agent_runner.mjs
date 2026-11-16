#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Bounded educational orchestration. No filesystem writes except explicit evidence report.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {compareCSV,verifyClaim,canonicalClaim,CORE_VERSION} from './proof_core.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
function parseArgs(args) {
  const out={mode:'fixture-wrong',model:'',output:path.join(here,'run-evidence.json')};
  for(let i=0;i<args.length;i++){
    const [k,v]=[args[i],args[i+1]];
    if(k==='--mode'&&v){out.mode=v;i++;}
    else if(k==='--model'&&v){out.model=v;i++;}
    else if(k==='--output'&&v){out.output=path.resolve(v);i++;}
    else if(k==='--help'){console.log('node agent_runner.mjs --mode fixture-wrong|fixture-reference|ollama [--model EXISTING_OLLAMA_MODEL] [--output PATH]');process.exit(0);}
    else throw new Error('Unsupported CLI argument: '+k);
  }
  if(!['fixture-wrong','fixture-reference','ollama'].includes(out.mode))throw new Error('Unsupported mode.');
  if(out.mode==='ollama'&&!out.model)throw new Error('Set --model to an actual locally installed Ollama model.');
  return out;
}
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
async function ollama(model,prompt){
  const controller=new AbortController(); const timeout=setTimeout(()=>controller.abort(),60000);
  try {
    const r=await fetch('http://127.0.0.1:11434/api/generate',{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({model,prompt,stream:false,format:'json',options:{temperature:0,num_predict:1000}})});
    if(!r.ok)throw new Error(`Ollama returned HTTP ${r.status}; check that your approved model is installed.`);
    const data=await r.json();if(!data||typeof data.response!=='string')throw new Error('Invalid Ollama response.');
    return {text:data.response,done_reason:data.done_reason,model:data.model};
  }finally{clearTimeout(timeout);}
}
function parseStrictJson(s,stage){try{const v=JSON.parse(s); if(typeof v!=='object'||!v||Array.isArray(v))throw Error();return v;}catch{throw new Error(stage+' did not produce one JSON object; fail closed.')}}
function safeModelView(x){return String(x).slice(0,20000)}
async function run(){
 const cfg=parseArgs(process.argv.slice(2));
 const left=await fs.readFile(path.join(here,'data/supply_a.csv'),'utf8');
 const right=await fs.readFile(path.join(here,'data/supply_b.csv'),'utf8');
 let toolDecision=null,modelAnswer=null,claim=null;
 const comparison=compareCSV(left,right);
 if(comparison.status==='BLOCKED')throw Error('The deterministic comparison is blocked.');
 if(cfg.mode==='ollama'){
  const first=await ollama(cfg.model,`You are a constrained AI analyst in a training exercise. You may request ONLY one named tool, compare_catalogs. You cannot read files or take external actions. Decide whether to use the deterministic comparison tool before making factual claims. Output exactly JSON: {"tool":"compare_catalogs","reason":"..."}. A file has ${comparison.stats.leftRows} Source A records and another has ${comparison.stats.rightRows} Source B records. Task: find stock/price/status discrepancies with verifiable source identity. Never claim approval.`);
  toolDecision=parseStrictJson(first.text,'Tool selection');
  if(toolDecision.tool!=='compare_catalogs')throw Error('Model did not select the only authorized read-only tool. Execution refused.');
  const second=await ollama(cfg.model,`You requested the read-only compare_catalogs tool. The ACTUAL TOOL RESULT is below (JSON). Produce a plain JSON object with exactly the following fields: "summary": brief descriptive sentence, "unmatchedLeft": array of exact identifiers found only in A, "unmatchedRight": array of exact identifiers found only in B, "conflicts": array of {"sku":identifier,"field":shared_field_name}. Use only tool evidence. Do not invent remedies or claim human approval. Source A and B have no established authority. TOOL RESULT:\n${JSON.stringify(comparison)}\nReturn ONLY JSON.`);
  modelAnswer={model:second.model,text:safeModelView(second.text)};
  claim=parseStrictJson(second.text,'AI synthesis');
 }else if(cfg.mode==='fixture-wrong'){
  toolDecision={tool:'compare_catalogs',reason:'Scripted choice for deterministic rehearsal; no model was called.'};
  claim=JSON.parse(await fs.readFile(path.join(here,'data/claim_wrong.json'),'utf8'));
 }else{
  toolDecision={tool:'compare_catalogs',reason:'Scripted choice for deterministic rehearsal; no model was called.'};
  claim=canonicalClaim(comparison);
 }
 const verification=verifyClaim(comparison,claim);
 const receipt={schema:'montrealai-event-proof-receipt/v1',generatedAt:new Date().toISOString(),mode:cfg.mode,actuallyUsedModel:cfg.mode==='ollama',model:cfg.mode==='ollama'?cfg.model:null,coreVersion:CORE_VERSION,sourceSHA256:{A:sha(left),B:sha(right)},toolDecision,modelAnswer,claim,comparison,verification,humanAcceptance:null,claimBoundary:'Structured comparison checked; no authoritative truth about either source, customer acceptance, ROI, production or general autonomy.'};
 await fs.mkdir(path.dirname(cfg.output),{recursive:true});await fs.writeFile(cfg.output,JSON.stringify(receipt,null,2)+'\n','utf8');
 console.log('MODE:',cfg.mode,'MODEL CALLED:',receipt.actuallyUsedModel);
 console.log('DETERMINISTIC CHECK:',comparison.status,JSON.stringify(comparison.stats));
 console.log('AI CLAIM CHECK:',verification.status);
 console.log('EVIDENCE:',cfg.output);
 console.log('HUMAN ACCEPTANCE: NOT GIVEN');
}
run().catch(e=>{console.error('FAIL CLOSED:',String(e.message||e));process.exitCode=1});
