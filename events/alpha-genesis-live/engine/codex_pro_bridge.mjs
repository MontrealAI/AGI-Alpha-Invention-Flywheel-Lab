// SPDX-License-Identifier: MIT
// Official OpenAI Codex CLI adapter. Auth is handled ONLY by Codex's first-party
// ChatGPT sign-in. This module never reads, copies or distributes account tokens.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import crypto from 'node:crypto';

export const PLAN_SCHEMA = Object.freeze({
  type:'object', additionalProperties:false,
  required:['objective','calls'],
  properties:{
    objective:{type:'string',description:'One short description of why these tool calls are next.'},
    calls:{type:'array',minItems:1,maxItems:12,items:{
      type:'object',additionalProperties:false,required:['name','argumentsJson'],
      properties:{
        name:{type:'string',enum:['list_case_sources','read_release_policy','list_purchase_orders','get_supplier_confirmation','get_supplier_note','calculate_order_metrics','submit_decision_dossier']},
        argumentsJson:{type:'string',description:'JSON-encoded arguments object; for empty args use {}. For submission include a JSON-encoded dossier_json string.'}
      }
    }}
  }
});
const isTestBridge=()=>Boolean(process.env.PROOF_LAB_TEST_CODEX_BIN && process.env.PROOF_LAB_TEST_MODE==='1');
const cliPath=()=>isTestBridge()?process.env.PROOF_LAB_TEST_CODEX_BIN:'codex';
function envWithoutApiKeys(){const e={...process.env};delete e.OPENAI_API_KEY;delete e.CODEX_API_KEY;return e;}
export async function runCli(args,{cwd,stdin='',timeoutMs=250000,limit=250000}={}){
 const executable=cliPath();
 return await new Promise((resolve,reject)=>{
  const cp=spawn(executable,args,{cwd:cwd||process.cwd(),env:envWithoutApiKeys(),stdio:['pipe','pipe','pipe'],windowsHide:true});
  let out='',err='',closed=false;const timer=setTimeout(()=>{cp.kill('SIGTERM');},timeoutMs);
  cp.stdout.on('data',b=>{out+=b.toString('utf8');if(out.length>limit)cp.kill('SIGTERM');});
  cp.stderr.on('data',b=>{err+=b.toString('utf8');if(err.length>limit)cp.kill('SIGTERM');});
  cp.on('error',e=>{if(!closed){closed=true;clearTimeout(timer);reject(new Error(`Codex CLI unavailable: ${e.code||e.message}. Install official Codex CLI: npm install -g @openai/codex`))}});
  cp.on('close',(code,signal)=>{clearTimeout(timer);if(closed)return;closed=true;
   if(code!==0)reject(new Error(`Codex CLI ended without a completed response (code ${code}, signal ${signal||'none'}). ${err.slice(-700).replace(/sk-[A-Za-z0-9_-]+/g,'[redacted]')}`));
   else resolve({stdout:out,stderr:err});});
  cp.stdin.on('error',()=>{});cp.stdin.end(stdin);
 });
}
export async function ensureChatGPTSignIn(){
 if(isTestBridge())return {status:'MOCK_ONLY_NO_REAL_AUTH'};
 const out=await runCli(['login','status'],{timeoutMs:16000,limit:20000});
 const msg=(out.stdout+' '+out.stderr).toLowerCase();
 if(!msg.includes('using chatgpt'))throw Error('Official Codex CLI is not signed in with ChatGPT. In Terminal run: codex login; choose Sign in with ChatGPT. A website session cannot be imported silently.');
 return {status:'CODEX_CHATGPT_AUTHENTICATED_METHOD',planTier:'NOT_ASSERTED'};
}
export async function codexPlan({model,prompt}){
 const temp=await fs.mkdtemp(path.join(os.tmpdir(),'montrealai-agent-planner-'));
 try{
  const schemaFile=path.join(temp,'plan.schema.json'),outFile=path.join(temp,'plan.json');
  await fs.writeFile(schemaFile,JSON.stringify(PLAN_SCHEMA,null,2),{mode:0o600});
  const args=['exec','--sandbox','read-only','--skip-git-repo-check','--ephemeral',
    '--output-schema',schemaFile,'--output-last-message',outFile,'-C',temp];
  if(model)args.push('--model',model);
  args.push('-');
  await runCli(args,{cwd:temp,stdin:prompt,timeoutMs:250000});
  const raw=await fs.readFile(outFile,'utf8');if(raw.length>80000)throw Error('Codex plan too large');
  const plan=JSON.parse(raw);
  if(!plan||typeof plan.objective!=='string'||!Array.isArray(plan.calls)||plan.calls.length<1||plan.calls.length>12)throw Error('Codex response not a valid bounded plan');
  for(const c of plan.calls){if(!c||!PLAN_SCHEMA.properties.calls.items.properties.name.enum.includes(c.name)||typeof c.argumentsJson!=='string'||c.argumentsJson.length>30000)throw Error('Codex attempted a malformed/unapproved tool');}
  return plan;
 }finally{await fs.rm(temp,{recursive:true,force:true})}
}
export function parsePlannedArgs(call){
 let x;try{x=JSON.parse(call.argumentsJson)}catch{throw Error('Codex tool arguments were not valid JSON')}
 if(!x||typeof x!=='object'||Array.isArray(x))throw Error('Codex tool arguments must be a JSON object');
 return x;
}
export function testBridgeUsed(){return isTestBridge()}
