#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Separate process. Recomputes against source, never trusts agent's metrics or verdict.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {loadCase,verifyDossier,VERIFIER_VERSION} from './policy_verifier.mjs';
const here=path.dirname(fileURLToPath(import.meta.url));
const sha=x=>crypto.createHash('sha256').update(x).digest('hex');
const p=process.argv[2];let caseDir=path.join(here,'case');if(process.argv[3]==='--case-dir'&&process.argv[4])caseDir=path.resolve(process.argv[4]);else if(process.argv.length>3)throw Error('Unknown arguments; use --case-dir PATH');
if(!p){console.error('Usage: node verify_receipt.mjs PATH_TO_AGENT_RECEIPT.json');process.exit(1)}
try{
 const receiptBytes=await fs.readFile(path.resolve(p));
 const receipt=JSON.parse(receiptBytes.toString('utf8'));
 const input=await loadCase(caseDir);
 const issues=[];
 if(receipt.schema!=='montrealai-agentic-mission-receipt/v1')issues.push('Wrong receipt schema');
 for(const [f,d] of Object.entries(input.sourceSHA256)){if(receipt.sourceSHA256?.[f]!==d)issues.push('Source changed: '+f)}
 if(sha(JSON.stringify(receipt.toolCalls))!==receipt.traceSHA256)issues.push('Tool-trace self-consistency failed');
 const cov=receipt.requiredToolCoverage||{};
 const ids=input.orders.map(x=>x.po_id);
 if(!(cov.sources&&cov.policy&&cov.orders))issues.push('Required source/policy/plan inspection missing');
 for(const id of ids){for(const f of ['confirmations','notes','metrics'])if(!cov[f]?.includes(id))issues.push(`Missing ${f} coverage for ${id}`)}
 if(receipt.humanApproval!==null||receipt.actionExecuted!==false)issues.push('Receipt falsely claims authorization');
 const verdict=verifyDossier(input,receipt.submittedDossier);
 if(verdict.status!=='CHECKS_PASS')issues.push(...verdict.issues);
 const result={schema:'montrealai-independent-verification/v1',verifierVersion:VERIFIER_VERSION,runId:receipt.runId,receiptSHA256:sha(receiptBytes),traceSHA256:receipt.traceSHA256,verdict:issues.length?'REJECT':'CHECKS_PASS',sourceSHA256:input.sourceSHA256,issues,checkedLineCount:verdict.checkedLineCount,expectedTotals:verdict.expectedTotals,agentMode:receipt.mode,actuallyUsedModel:receipt.actuallyUsedModel,observedModelCalls:receipt.actualModelCalls,scope:'Independent process against exact four input files and approved synthetic policy; no external auditor or human approval. Self-consistent hashes do not authenticate the producer.'};
 console.log(JSON.stringify(result,null,2));
 if(issues.length)process.exitCode=2;
}catch(e){console.error('VERIFICATION FAILED CLOSED:',e.message||e);process.exitCode=1}
