#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Distinct model-backed strategy stage: no browser session import, no token handling.
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {runCli,ensureChatGPTSignIn} from '../engine/codex_pro_bridge.mjs';
import {buildScenarios,SCENARIOS} from './scenario_engine.mjs';

const OPTIONS=['supplier','controls','combined'];
const FOCUS=['time','cost','confidence'];
export const STRATEGY_SCHEMA={type:'object',additionalProperties:false,required:['ambition','frame','alternatives','chosen','whyChosen','nextMove','newLearning'],properties:{
 ambition:{type:'string'},frame:{type:'string'},
 alternatives:{type:'array',minItems:3,maxItems:3,items:{type:'object',additionalProperties:false,required:['scenarioId','hypothesis','test','tradeoff'],properties:{scenarioId:{type:'string',enum:OPTIONS},hypothesis:{type:'string'},test:{type:'string'},tradeoff:{type:'string'}}}},
 chosen:{type:'string',enum:OPTIONS},whyChosen:{type:'string'},nextMove:{type:'string'},newLearning:{type:'string'}
}};
const preview=(focus,caseData)=>{
 const f={time:'recover the most launch-critical commitments before their needed dates',cost:'reduce at-risk approved commitment without bypassing any controls',confidence:'make each release decision independently checkable'}[focus];
 return {ambition:'What if we could rescue an at-risk product launch without approving an unsafe order?',frame:f,alternatives:[
  {scenarioId:'supplier',hypothesis:'If delivery and shortage evidence improves, more orders may pass policy review.',test:'Recalculate the eight orders under expressly assumed new supplier evidence.',tradeoff:'Depends on vendors supplying credible responses; no automatic fulfillment.'},
  {scenarioId:'controls',hypothesis:'If price, status and quality evidence improve, additional orders may qualify for human review.',test:'Recalculate price tolerance, quality and supplier status with a frozen policy.',tradeoff:'Depends on a negotiated quote and independently accepted quality clearance.'},
  {scenarioId:'combined',hypothesis:'If both groups of assumptions hold, all eight could qualify for human review.',test:'Recompute all lines and compare with current evidence and the two partial paths.',tradeoff:'An optimistic hypothetical; cost and capacity of interventions have not been measured.'}
 ],chosen:focus==='time'?'supplier':focus==='cost'?'controls':'combined',whyChosen:'The path can be tested against the same approved policy using explicit hypothetical source changes, without authorizing any real action.',nextMove:'Obtain the missing confirmation or independent quality evidence, then rerun the checker against actually received records.',newLearning:'A scenario improvement is a conditional possibility, not an observed supplier recovery.'};
};
export function validateStrategy(z){
 if(!z||typeof z!=='object'||Array.isArray(z))throw Error('Strategy is not an object');
 for(const key of STRATEGY_SCHEMA.required)if(!(key in z))throw Error('Strategy missing: '+key);
 for(const key of ['ambition','frame','whyChosen','nextMove','newLearning'])if(typeof z[key]!=='string'||z[key].trim().length<18||z[key].length>900)throw Error('Strategy field malformed: '+key);
 if(!Array.isArray(z.alternatives)||z.alternatives.length!==3)throw Error('Exactly three alternative paths required');
 const ids=[];for(const a of z.alternatives){if(!a||!OPTIONS.includes(a.scenarioId))throw Error('Unapproved scenario');ids.push(a.scenarioId);for(const k of ['hypothesis','test','tradeoff'])if(typeof a[k]!=='string'||a[k].length<18||a[k].length>850)throw Error('Alternative field malformed '+k)}
 if(new Set(ids).size!==3||!OPTIONS.includes(z.chosen))throw Error('Must compare each of three approved strategies');
 return z;
}
export async function propose({mode='preview',focus='confidence',model='',receipt=null,caseDir}){
 if(!['preview','codex-pro'].includes(mode))throw Error('Unknown mode');if(!FOCUS.includes(focus))throw Error('Choose focus: time, cost or confidence');
 const data=await buildScenarios(caseDir);
 if(mode==='preview')return {strategy:validateStrategy(preview(focus,data)),mode:'SCRIPTED_PREVIEW',modelCalls:0};
 if(!receipt||receipt.mode!=='LIVE_MODEL'||receipt.actuallyUsedModel!==true||receipt.verification?.status!=='CHECKS_PASS'||receipt.provider!=='codex-pro')throw Error('Real strategy stage requires independently checked actual Codex mission receipt');
 await ensureChatGPTSignIn();
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'alpha-genesis-live-strategy-'));
 try{
  const schema=path.join(dir,'schema.json'),output=path.join(dir,'strategy.json');await fs.writeFile(schema,JSON.stringify(STRATEGY_SCHEMA,null,2),{mode:0o600});
  const brief=`You are the second, strategy-building AI agent in a live invention lab. The FIRST agent has completed read-only work and a separate verifier has checked the dossier. Form a compelling, conservative, useful next instrument for an operations leader.\nOur ambition: What if we could rescue an at-risk product launch without approving unsafe orders?\nAudience-chosen focus: ${focus}.\nActual SOURCE-BOUND verified baseline (not an actual customer): ${JSON.stringify(data.scenarios[0].totals)}.\nThe allowed conditional exploration paths and computed, TESTABLE hypothetical results are: ${JSON.stringify(data.scenarios.map(x=>({id:x.id,assumptions:x.assumptions,totals:x.totals,changedFromBaseline:x.changedFromBaseline})))}.\nProduce exactly THREE competing alternative strategies, one per scenario supplier, controls and combined. Select one based on the focus; be candid on dependencies and costs. DO NOT present assumed vendor improvements as observed. Do not claim a payment, approval or transaction. Generate only the JSON structure. A separate trusted builder will construct the runnable scenario desk and a verifier will check all computations. No files, tools, external services or websites are needed for this role.`;
  const args=['exec','--sandbox','read-only','--skip-git-repo-check','--ephemeral','--output-schema',schema,'--output-last-message',output,'-C',dir];if(model)args.push('--model',model);args.push('-');
  await runCli(args,{cwd:dir,stdin:brief,timeoutMs:250000});const s=JSON.parse(await fs.readFile(output,'utf8'));
  return {strategy:validateStrategy(s),mode:'LIVE_CODEX_STRATEGY',modelCalls:1};
 }finally{await fs.rm(dir,{recursive:true,force:true})}
}
if(process.argv[1]&&process.argv[1].endsWith('strategy_agent.mjs')){
 const args=process.argv.slice(2);const get=(name,def)=>{let ix=args.indexOf(name);return ix<0?def:args[ix+1]};
 let receipt=null;const rp=get('--receipt',null);if(rp)receipt=JSON.parse(await fs.readFile(rp,'utf8'));
 const result=await propose({mode:get('--mode','preview'),focus:get('--focus','confidence'),model:get('--model',''),receipt});
 const out=get('--output','');if(out){await fs.mkdir(path.dirname(path.resolve(out)),{recursive:true});await fs.writeFile(out,JSON.stringify(result,null,2)+'\n')};console.log(JSON.stringify({mode:result.mode,chosen:result.strategy.chosen,output:out||null},null,2));
}
