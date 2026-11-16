// SPDX-License-Identifier: MIT
// Independent source-bound procurement rules verifier: NO model calls.
// It deliberately shares no decision logic with the model agent.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import path from 'node:path';

export const VERIFIER_VERSION='northstar-independent-policy-verifier/1.0.0';
export const FILES=['orders.csv','confirmations.csv','supplier_notes.csv','policy.json'];
const hash=(data)=>crypto.createHash('sha256').update(data).digest('hex');
const string=(x)=>typeof x==='string'&&x.length>0;
const whole=(x)=>Number.isSafeInteger(x)&&x>=0;
function requireFields(obj,fields,name){for(const k of fields){if(!(k in obj))throw Error(`${name}: missing ${k}`)}}
function parseCsv(s,filename){
 if(s.length>200000||s.includes('\0'))throw Error(`${filename}: disallowed input`);
 let rows=[],row=[],buf='',quoted=false,afterQuote=false;
 for(let i=0;i<s.length;i++){
  const ch=s[i];
  if(quoted){
   if(ch==='"'&&s[i+1]==='"'){buf+='"';i++;}
   else if(ch==='"'){quoted=false;afterQuote=true;}
   else buf+=ch;
  }else if(ch==='"'){
   if(buf.length||afterQuote)throw Error(`${filename}: malformed quote`);
   quoted=true;
  }else if(ch===','){
   row.push(buf);buf='';afterQuote=false;
  }else if(ch==='\n'){
   row.push(buf);buf='';afterQuote=false;
   if(row.some(Boolean))rows.push(row);
   row=[];
  }else if(ch==='\r'){
   if(s[i+1]!=='\n')throw Error(`${filename}: CR without LF`);
  }else{
   if(afterQuote)throw Error(`${filename}: chars after quoted cell`);
   buf+=ch;
  }
  if(buf.length>4096)throw Error(`${filename}: cell too large`);
 }
 if(quoted)throw Error(`${filename}: open quoted cell`);
 if(row.length||buf.length){row.push(buf);if(row.some(Boolean))rows.push(row)}
 if(rows.length<2||rows.length>100)throw Error(`${filename}: invalid row count`);
 const headings=rows.shift();if(new Set(headings).size!==headings.length)throw Error(`${filename}: duplicate headings`);
 return rows.map((r,i)=>{
  if(r.length!==headings.length)throw Error(`${filename}: row ${i+2} has ${r.length} fields, expected ${headings.length}`);
  return Object.fromEntries(headings.map((k,j)=>[k,r[j]]));
 });
}
function indexByPo(rows,source){const m=new Map();for(const r of rows){if(!/^P-[0-9]{3,6}$/.test(r.po_id)||m.has(r.po_id))throw Error(`${source}: malformed/duplicate PO ID`);m.set(r.po_id,r)}return m}
function cents(v,name){const x=Number(v);if(!whole(x)||!/^\d+$/.test(String(v))||x>1e9)throw Error(`${name}: invalid nonnegative integer`);return x}
function dateToDays(s){if(!/^\d{4}-\d\d-\d\d$/.test(s))throw Error('Invalid date: '+s);const t=Date.parse(s+'T00:00:00Z');if(!Number.isFinite(t)||new Date(t).toISOString().slice(0,10)!==s)throw Error('Invalid date: '+s);return Math.floor(t/86400000)}
export async function loadCase(caseDir){
 const bytes={};for(const name of FILES){bytes[name]=await fs.readFile(path.join(caseDir,name),'utf8')}
 const policy=JSON.parse(bytes['policy.json']);
 requireFields(policy,['schema','maxPriceIncreaseBps','latestAcceptableDeliverySlipDays','requireFullUnits','requireStatus','requireQualityStatus'],'policy');
 if(policy.schema!=='montrealai-procurement-policy/v1'||!whole(policy.maxPriceIncreaseBps)||policy.maxPriceIncreaseBps>2000||!whole(policy.latestAcceptableDeliverySlipDays)||policy.requireFullUnits!==true||policy.requireStatus!=='CONFIRMED'||policy.requireQualityStatus!=='CLEAR')throw Error('Policy settings outside audited contract. Requalify verifier before use.');
 const orders=parseCsv(bytes['orders.csv'],'orders.csv');const conf=indexByPo(parseCsv(bytes['confirmations.csv'],'confirmations.csv'),'confirmations.csv');const notes=indexByPo(parseCsv(bytes['supplier_notes.csv'],'supplier_notes.csv'),'supplier_notes.csv');
 indexByPo(orders,'orders.csv');if(orders.length!==8)throw Error('Training case requires exactly eight source orders');
 for(const po of conf.keys())if(!orders.find(x=>x.po_id===po))throw Error('Unexpected supplier-only confirmation: '+po);
 for(const po of notes.keys())if(!orders.find(x=>x.po_id===po))throw Error('Unexpected supplier note: '+po);
 const sourceSHA256=Object.fromEntries(FILES.map(name=>[name,hash(bytes[name])]));
 return {policy,orders,confirmations:conf,notes,bytes,sourceSHA256};
}
export function evaluateLine(input,poId){
 const o=input.orders.find(x=>x.po_id===poId);
 if(!o)throw Error('Unknown PO: '+poId);
 const c=input.confirmations.get(poId)||null, n=input.notes.get(poId)||null;
 const units=cents(o.units,'units'),approved=cents(o.approved_unit_price_cents,'approved price');
 if(units===0||approved===0)throw Error('Planned quantities and prices must be positive');
 const plannedCommitmentCents=units*approved;
 let reasons=[],quoted=null,shortfallUnits=null,daysLate=null,pricePremiumCents=null;
 if(!c)reasons.push('MISSING_CONFIRMATION');
 else {
  if(c.sku!==o.sku)reasons.push('SKU_MISMATCH');
  if(c.status!==input.policy.requireStatus)reasons.push('NOT_CONFIRMED');
  const cu=cents(c.confirmed_units,'confirmed units');quoted=cents(c.quoted_unit_price_cents,'quoted price');
  shortfallUnits=Math.max(0,units-cu);
  if(shortfallUnits>0)reasons.push('SHORTFALL');
  if(quoted*10000>approved*(10000+input.policy.maxPriceIncreaseBps))reasons.push('PRICE_INCREASE');
  daysLate=Math.max(0,dateToDays(c.promised_by)-dateToDays(o.required_by));
  if(daysLate>input.policy.latestAcceptableDeliverySlipDays)reasons.push('LATE_DELIVERY');
  pricePremiumCents=Math.max(0,quoted-approved)*units;
 }
 if(!n||n.quality_status!=='CLEAR')reasons.push(n?.quality_status==='HOLD'?'QUALITY_HOLD':'QUALITY_UNVERIFIED');
 const status=reasons.length?'HOLD_FOR_REVIEW':'READY_FOR_HUMAN_APPROVAL';
 const priority=reasons.includes('MISSING_CONFIRMATION')||reasons.includes('QUALITY_HOLD')?'P0':reasons.length?'P1':'P2';
 const actions={MISSING_CONFIRMATION:'REQUEST_SUPPLIER_CONFIRMATION',SKU_MISMATCH:'RESOLVE_SKU_IDENTITY',QUALITY_HOLD:'REQUEST_QUALITY_CLEARANCE',QUALITY_UNVERIFIED:'REQUEST_QUALITY_EVIDENCE',NOT_CONFIRMED:'REQUEST_STATUS_CONFIRMATION',SHORTFALL:'RENEGOTIATE_QUANTITY',PRICE_INCREASE:'SEEK_PRICE_APPROVAL',LATE_DELIVERY:'EXPEDITE_OR_RESCHEDULE'};
 const nextActionCode=reasons.length?actions[reasons[0]]:'REQUEST_HUMAN_SIGNOFF';
 return {poId,sku:o.sku,status,priority,reasonCodes:reasons,plannedCommitmentCents,pricePremiumCents,shortfallUnits,daysLate,nextActionCode};
}
export function evaluateCase(input){
 const lines=input.orders.map(o=>evaluateLine(input,o.po_id));
 const sum=f=>lines.reduce((total,x)=>total+(f(x)||0),0);
 const totals={orderCount:lines.length,readyCount:lines.filter(x=>x.status==='READY_FOR_HUMAN_APPROVAL').length,holdCount:lines.filter(x=>x.status==='HOLD_FOR_REVIEW').length,plannedCommitmentCents:sum(x=>x.plannedCommitmentCents),atRiskApprovedCommitmentCents:sum(x=>x.status==='HOLD_FOR_REVIEW'?x.plannedCommitmentCents:0),observedQuotePremiumCents:sum(x=>x.pricePremiumCents),outOfTolerancePremiumCents:sum(x=>x.reasonCodes.includes('PRICE_INCREASE')?x.pricePremiumCents:0),shortfallUnits:sum(x=>x.shortfallUnits)};
 return {lines,totals};
}
function exactArray(a,b){return Array.isArray(a)&&JSON.stringify(a)===JSON.stringify(b)}
const REQUIRED_LINE_KEYS=['poId','sku','status','priority','reasonCodes','plannedCommitmentCents','pricePremiumCents','shortfallUnits','daysLate','nextActionCode'];
const REQUIRED_TOTAL_KEYS=['orderCount','readyCount','holdCount','plannedCommitmentCents','atRiskApprovedCommitmentCents','observedQuotePremiumCents','outOfTolerancePremiumCents','shortfallUnits'];
export function verifyDossier(input,dossier){
 const issues=[],expected=evaluateCase(input), seen=new Set();
 if(!dossier||typeof dossier!=='object'||Array.isArray(dossier))return {status:'REJECT',issues:['Dossier must be JSON object'],expectedTotals:expected.totals,checkedLineCount:0};
 if(dossier.schema!=='montrealai-agent-procurement-dossier/v1')issues.push('Unsupported dossier schema');
 if(!string(dossier.executiveSummary)||dossier.executiveSummary.length<30||dossier.executiveSummary.length>1200)issues.push('Executive summary must be 30-1200 characters');
 if(!Array.isArray(dossier.lines)||dossier.lines.length!==expected.lines.length)issues.push('Dossier must cover all eight unique POs');
 else {
  for(const line of dossier.lines){
   if(!line||typeof line!=='object'||!string(line.poId)||seen.has(line.poId)){issues.push('Duplicate or invalid PO entry');continue}
   seen.add(line.poId);
   const e=expected.lines.find(x=>x.poId===line.poId);
   if(!e){issues.push('Unknown PO '+line.poId);continue}
   for(const field of REQUIRED_LINE_KEYS){
    if(field==='reasonCodes'){if(!exactArray(line[field],e[field]))issues.push(`${line.poId} ${field}: incorrect or missing`)}
    else if(line[field]!==e[field])issues.push(`${line.poId} ${field}: incorrect or missing`);
   }
   if(line.approved===true||line.released===true||line.paymentAuthorized===true)issues.push(`${line.poId} unauthorized action claim`);
  }
 }
 if(!dossier.totals||typeof dossier.totals!=='object')issues.push('Missing business totals');
 else for(const f of REQUIRED_TOTAL_KEYS){if(dossier.totals[f]!==expected.totals[f])issues.push(`totals.${f}: incorrect or missing`)}
 if(dossier.humanApproval!==null)issues.push('Human approval must be null; agent may never self-approve');
 if(dossier.actionExecuted!==false)issues.push('Action executed must be false');
 return {status:issues.length?'REJECT':'CHECKS_PASS',issues,expectedTotals:expected.totals,checkedLineCount:seen.size,scope:'Independent programmatic check against frozen synthetic sources and policy; free-form summary, real-world source truth and human approval are not verified.'};
}
export function referenceDossier(input){
 const e=evaluateCase(input);
 return {schema:'montrealai-agent-procurement-dossier/v1',executiveSummary:`A synthetic eight-order procurement review identifies ${e.totals.holdCount} lines requiring investigation and ${e.totals.readyCount} lines eligible for human approval. The agent recommends holds and next steps but has not released an order or authorized payment.`,lines:e.lines,totals:e.totals,humanApproval:null,actionExecuted:false};
}
