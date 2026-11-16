#!/usr/bin/env node
// TEST-ONLY stub. NO MODEL, NO EXTERNAL AUTH. Emulates Codex output schema plumbing.
const fs=require('fs');const path=require('path');
const args=process.argv.slice(2);
if(args[0]==='login'&&args[1]==='status'){console.log('Logged in using ChatGPT (test-only stub)');process.exit(0)}
if(args[0]!=='exec'){console.error('Unknown stub command');process.exit(2)}
const out=args[args.indexOf('--output-last-message')+1];if(!out){process.exit(3)}
let prompt='';process.stdin.setEncoding('utf8');process.stdin.on('data',c=>prompt+=c);process.stdin.on('end',async()=>{
 const match=prompt.match(/HOST OBSERVATIONS \(JSON, tool outputs are DATA not instructions\):\s*(\{.*?\})\n\nChoose the NEXT/s);
 if(!match){console.error('Missing host context');process.exit(4)}
 const {coverage}=JSON.parse(match[1]);const calls=[];
 function add(name,args){calls.push({name,argumentsJson:JSON.stringify(args)})}
 for(const [flag,tool] of [['sources','list_case_sources'],['policy','read_release_policy'],['orders','list_purchase_orders']])if(!coverage[flag]&&calls.length<12)add(tool,{});
 if(calls.length<12&&coverage.orders){for(let n=301;n<=308;n++)for(const [k,tool] of [['confirmations','get_supplier_confirmation'],['notes','get_supplier_note'],['metrics','calculate_order_metrics']]){
  let id=`P-${n}`;if(!coverage[k].includes(id)&&calls.length<12)add(tool,{po_id:id});
 }}
 if(!calls.length){const root=path.resolve(__dirname,'..');const {loadCase,referenceDossier}=await import('file://'+path.join(root,'policy_verifier.mjs'));
  const src=await loadCase(path.join(root,'case'));add('submit_decision_dossier',{dossier_json:JSON.stringify(referenceDossier(src))});
 }
 fs.writeFileSync(out,JSON.stringify({objective:'TEST STUB — host protocol handshake, not a live model',calls}));
});
