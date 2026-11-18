'use strict';
const cfg = JSON.parse(document.querySelector('#task-data').textContent);
const en = document.documentElement.lang==='en', by = id => document.getElementById(id);
const text = (a,b) => en ? a : b;
const key = 'frontier-rr-h1-'+cfg.session;
let record = {session:cfg.session, rows:[], started:null, barrier:'', technology:''};
try {const saved=localStorage.getItem(key); if(saved)record=JSON.parse(saved);} catch(e) { /* Completion can also be downloaded after each task. */ }
function save(){try{localStorage.setItem(key,JSON.stringify(record));}catch(e){by('notice').textContent=text('Keep this tab open and download your work.','Gardez cet onglet ouvert et téléchargez votre travail.');}}
function write(){
  const current=cfg.tasks[record.rows.length];
  by('task').hidden=!current || record.started===null;
  by('start').hidden=!current || record.started!==null;
  by('next').textContent=current ? text('Task ','Tâche ')+(record.rows.length+1)+' / '+cfg.tasks.length : text('Session complete','Séance terminée');
  by('question').textContent=current && record.started!==null ? current.prompt : '';
  by('download').disabled=record.rows.length===0;
  by('barrier').value=record.barrier||''; by('technology').value=record.technology||'';
}
by('start').onclick=()=>{record.started=Date.now();save();write();by('question').focus();};
by('task').onsubmit=e=>{
 e.preventDefault();
 const status=by('outcome').value, page=Number(by('page').value),answer=by('answer').value.trim(),quote=by('quote').value.trim();
 if(status==='answered' && (!answer || !quote || !Number.isInteger(page)||page<1||page>cfg.maxPage)){
  by('notice').textContent=text('Provide the answer, quotation and a physical page.','Saisissez une réponse, une citation et une page physique.');return;
 }
 const end=Date.now(); if(end<record.started){by('notice').textContent=text('Clock changed; tell the coordinator.','L’horloge a changé; avisez la coordination.');return;}
 record.rows.push({task:cfg.tasks[record.rows.length].id,status,answer,quote,page:page||null,elapsed_ms:end-record.started,
                   interruption:by('interruption').value.trim()});
 record.started=null;save();by('task').reset();by('notice').textContent='';write();by('next').focus();
};
['barrier','technology'].forEach(k=>by(k).addEventListener('input',()=>{record[k]=by(k).value;save();}));
by('download').onclick=()=>{
 const {session,rows,barrier,technology}=record;
 const url=URL.createObjectURL(new Blob([JSON.stringify({session,rows,barrier,technology},null,2)],{type:'application/json'}));
 const a=document.createElement('a');a.href=url;a.download='responses-'+session+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),500);
};
write();
