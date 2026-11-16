#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Auditable end-to-end orchestrator: model-backed tool-using agent -> independent gate
// -> competing pathways -> tested reusable browser instrument.
import fs from 'node:fs/promises';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {propose} from './strategy_agent.mjs';
import {build} from './build_live_studio.mjs';
const dir=path.dirname(fileURLToPath(import.meta.url));
const get=(a,key,def)=>{const i=a.indexOf(key);return i<0?def:a[i+1]};
async function main(){
 const a=process.argv.slice(2),mode=get(a,'--mode','preview'),focus=get(a,'--focus','confidence'),model=get(a,'--model',''),out=path.resolve(get(a,'--out',path.join(dir,'output'))),caseDir=path.resolve(get(a,'--case-dir',path.join(dir,'../engine/case')));
 if(!['preview','codex-pro'].includes(mode))throw Error('Use --mode preview or codex-pro');if(!['confidence','time','cost'].includes(focus))throw Error('Use --focus confidence|time|cost');
 await fs.mkdir(out,{recursive:true});
 const receiptPath=path.join(out,'agent-receipt.json'),strategyPath=path.join(out,'strategy.json'),studioPath=path.join(out,'ALPHA_GENESIS_MISSION_STUDIO.html');
 const provider=mode==='preview'?'scripted-good':'codex-pro';
 const run=spawnSync(process.execPath,[path.resolve(dir,'../engine/mission_agent.mjs'),'--provider',provider,'--case-dir',caseDir,'--output',receiptPath,...(model?['--model',model]:[])],{stdio:'inherit',timeout:1500000});
 if(run.error)throw run.error;
 if(run.status!==0)throw Error('Agent mission did not complete with a verified dossier. No instrument was labelled complete.');
 const verification=spawnSync(process.execPath,[path.resolve(dir,'../engine/verify_receipt.mjs'),receiptPath,'--case-dir',caseDir],{encoding:'utf8',timeout:15000});
 if(verification.status!==0)throw Error('Independent baseline verifier did not pass: '+(verification.stderr||verification.stdout).slice(0,800));
 const receipt=JSON.parse(await fs.readFile(receiptPath,'utf8'));
 const strat=await propose({mode:mode==='preview'?'preview':'codex-pro',focus,model,receipt,caseDir});
 await fs.writeFile(strategyPath,JSON.stringify(strat,null,2)+'\n');
 const result=await build({receiptPath,strategyPath,outputPath:studioPath,caseDir});
 const handoff=`# HARNESS handoff · ${new Date().toISOString().slice(0,10)}\n\n## AMBITION\n${strat.strategy.ambition}\n\n## FOCUS\n${strat.strategy.frame}\n\n## STRATEGIES TESTED\n${strat.strategy.alternatives.map(a=>`- **${a.scenarioId}:** ${a.hypothesis} Test: ${a.test} Tradeoff: ${a.tradeoff}`).join('\n')}\n\n## CONSTRUCTED RESULT\nA standalone interactive mission instrument was generated: ALPHA_GENESIS_MISSION_STUDIO.html. The frozen eight-order baseline was independently rechecked, while new supplier and control paths are explicitly assumed hypothetical scenarios.\n\n## EVIDENCE\nModel/run mode: ${receipt.mode}; model-planning rounds: ${receipt.actualModelCalls}; tool events: ${receipt.toolCalls.length}; independent baseline checker: ${result.manifest.independentVerifier}.\n\n## LEARNING\n${strat.strategy.newLearning}\n\n## NEXT MOVE\n${strat.strategy.nextMove}\n\n## HARNESS OPERATOR NOTES\nUse the official ALPHA GENESIS FLYWHEEL Ω HARNESS manual mission path. Enter the ambition and constraints; attach this document and the exported JSON as independently inspectable references. The separate Codex agent is not an embedded HARNESS model connection, and this is a manual handoff rather than a verified HARNESS project import.\n`;
 await fs.writeFile(path.join(out,'HARNESS_HANDOFF.md'),handoff);
 const status={mode,focus,agentMode:receipt.mode,liveModel:receipt.mode==='LIVE_MODEL'&&receipt.actuallyUsedModel===true,modelCalls:receipt.actualModelCalls,toolEvents:receipt.toolCalls.length,verified:result.manifest.independentVerifier,selectedStrategy:strat.strategy.chosen,instrument:path.basename(studioPath),handOff:'HARNESS_HANDOFF.md'};
 await fs.writeFile(path.join(out,'RUN_SUMMARY.json'),JSON.stringify(status,null,2)+'\n');
 console.log('\n=== ALPHA GENESIS FLYWHEEL Ω · CONSTRUCTED INSTRUMENT ===\n'+JSON.stringify(status,null,2));
}
main().catch(e=>{console.error('RUN STOPPED: '+(e.stack||e));process.exitCode=1});
