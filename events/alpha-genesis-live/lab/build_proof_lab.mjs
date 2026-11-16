import fs from 'node:fs';import path from 'node:path';import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));
let html=fs.readFileSync(path.join(here,'proof_lab.template.html'),'utf8');
const core=fs.readFileSync(path.join(here,'proof_core.mjs'),'utf8').replace(/^export /gm,'');
let data={
'/*__CORE__*/':core,
'/*__DATA_A__*/':JSON.stringify(fs.readFileSync(path.join(here,'data/supply_a.csv'),'utf8')),
'/*__DATA_B__*/':JSON.stringify(fs.readFileSync(path.join(here,'data/supply_b.csv'),'utf8')),
'/*__CLAIM_WRONG__*/':JSON.stringify(JSON.parse(fs.readFileSync(path.join(here,'data/claim_wrong.json'),'utf8'))),
'/*__CLAIM_REFERENCE__*/':JSON.stringify(JSON.parse(fs.readFileSync(path.join(here,'data/claim_reference.json'),'utf8')))
};
for(const [key,val] of Object.entries(data)){if(!html.includes(key))throw Error('Missing build token '+key);html=html.replace(key,val)}
fs.writeFileSync(path.join(here,'proof_lab.html'),html,'utf8');
console.log('Built proof_lab.html',Buffer.byteLength(html),'bytes');
