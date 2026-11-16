// SPDX-License-Identifier: MIT
// Synthetic "what if" construction layer, separately calculated from agent language output.
// No actual supplier change, purchasing, payment or message is executed.
import {loadCase,evaluateCase} from '../engine/policy_verifier.mjs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
export const STAGE=path.dirname(fileURLToPath(import.meta.url));
export const CASE=path.resolve(STAGE,'../engine/case');
export const SCENARIOS=Object.freeze([
 {id:'baseline',label:'Today’s documented evidence',short:'Current',description:'Evidence as currently supplied; no new commitments or assumed vendor responses.',assumptions:[]},
 {id:'supplier',label:'Recover supply & delivery',short:'Supply recovery',description:'Explore what changes if the missing supply response arrives, shortages are covered and the late shipment is brought forward.',assumptions:['P-303 supplier confirms full units','P-304 delivery meets the approved need-by date','P-307 confirmation and quality evidence are obtained']},
 {id:'controls',label:'Resolve price, status & quality',short:'Control recovery',description:'Explore what changes if commercial negotiations and quality checks produce acceptable new evidence.',assumptions:['P-302 price is revised to 5,000 cents per unit','P-305 supplier resumes and confirms','P-306 independently obtains CLEAR quality status']},
 {id:'combined',label:'Coordinate both recovery paths',short:'Combined',description:'Explore the upper-bound hypothetical where both sets of evidence changes are achieved.',assumptions:['All supply recovery assumptions become true','All commercial and quality recovery assumptions become true']},
]);
const clone=x=>JSON.parse(JSON.stringify(x));
export function applyScenario(source,id){
 if(!SCENARIOS.some(s=>s.id===id))throw Error('Unknown scenario: '+id);
 const o={policy:clone(source.policy),orders:clone(source.orders),confirmations:new Map([...source.confirmations].map(([k,v])=>[k,clone(v)])),notes:new Map([...source.notes].map(([k,v])=>[k,clone(v)])),sourceSHA256:clone(source.sourceSHA256)};
 if(['supplier','combined'].includes(id)){
  o.confirmations.get('P-303').confirmed_units='100';
  o.confirmations.get('P-304').promised_by='2026-12-06';
  o.confirmations.set('P-307',{po_id:'P-307',sku:'GX-70',confirmed_units:'200',quoted_unit_price_cents:'650',promised_by:'2026-12-10',status:'CONFIRMED'});
  o.notes.set('P-307',{po_id:'P-307',quality_status:'CLEAR',notes:'Hypothetical documented quality clearance — not an actual vendor record.'});
 }
 if(['controls','combined'].includes(id)){
  o.confirmations.get('P-302').quoted_unit_price_cents='5000';
  o.confirmations.get('P-305').status='CONFIRMED';
  o.notes.set('P-306',{po_id:'P-306',quality_status:'CLEAR',notes:'Hypothetical verified quality clearance — not an actual vendor record.'});
 }
 return o;
}
export async function buildScenarios(caseDir=CASE){
 const src=await loadCase(caseDir);const baseline=evaluateCase(src);
 return {caseLabel:'Northstar Launch — fictional procurement',sourceSHA256:src.sourceSHA256,sourcePolicy:src.policy,scenarios:SCENARIOS.map(s=>{
  const x=evaluateCase(applyScenario(src,s.id));const readyDelta=x.totals.readyCount-baseline.totals.readyCount;
  const exposureDeltaCents=baseline.totals.atRiskApprovedCommitmentCents-x.totals.atRiskApprovedCommitmentCents;
  return {...s,totals:x.totals,lines:x.lines,readyDelta,exposureDeltaCents,
   changedFromBaseline:x.lines.filter(l=>baseline.lines.find(b=>b.poId===l.poId)?.status!==l.status).map(l=>l.poId)};
 })};
}
