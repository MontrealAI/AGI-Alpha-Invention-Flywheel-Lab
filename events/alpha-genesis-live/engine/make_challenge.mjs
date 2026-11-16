#!/usr/bin/env node
// Create an immutable-looking COPY for a second mission; original remains untouched.
// The supplier amended two fictional records. Changes are recorded explicitly.
import fs from 'node:fs/promises';import path from 'node:path';import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url));const target=process.argv[2]?path.resolve(process.argv[2]):path.join(here,'challenge_case');
try{
 await fs.mkdir(target,{recursive:false});
 for(const file of ['orders.csv','supplier_notes.csv','policy.json','confirmations.csv']){
  let s=await fs.readFile(path.join(here,'case',file),'utf8');
  if(file==='confirmations.csv'){
   if(!s.includes('P-302,BX-20,80,5250,2026-12-06,CONFIRMED')||!s.includes('P-304,DX-40,30,8400,2026-12-10,CONFIRMED'))throw Error('Source version changed: cannot create challenge blindly');
   s=s.replace('P-302,BX-20,80,5250,2026-12-06,CONFIRMED','P-302,BX-20,80,4950,2026-12-06,CONFIRMED').replace('P-304,DX-40,30,8400,2026-12-10,CONFIRMED','P-304,DX-40,30,8400,2026-12-06,CONFIRMED');
  }
  await fs.writeFile(path.join(target,file),s);
 }
 console.log('Changed supplier quote for P-302 and date for P-304 only; new case at '+target);
}catch(e){console.error('CHALLENGE CREATION ABORTED:',e.message);process.exitCode=1}
