'use strict';
const data = JSON.parse(document.querySelector('#dataset').textContent);
const $ = id => document.getElementById(id);
const grid = new Map(), stacks = new Set();
for (const row of data.csv.trimEnd().split('\n').slice(1)) {
  const [task,model,harness,solved,tokens] = row.split(',');
  if (!grid.has(task)) grid.set(task, new Map());
  const stack = model + '/' + harness;
  grid.get(task).set(stack, {solved:Number(solved),tokens:Number(tokens)});
  stacks.add(stack);
}
const ui = {lang:0,budget:2000000,width:2,scope:'main',candidate:0,revealed:false,issue:0,checks:[]};
const t = key => data.copy[key][ui.lang];
const n = value => new Intl.NumberFormat(ui.lang ? 'fr-CA':'en-CA',{maximumFractionDigits:1}).format(value);
const fr = (en,french) => ui.lang ? french : en;
function make(tag,text,attrs={}) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  for (const [key,value] of Object.entries(attrs)) el.setAttribute(key,value);
  return el;
}
function svg(tag,attrs) {
  const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const [k,v] of Object.entries(attrs)) el.setAttribute(k,v);
  return el;
}
function label(stack){
  const models={glm:'GLM-4.7-Flash',qwen:'Qwen3-Coder-Next',devstral:'Devstral'};
  const harnesses={acr:'AutoCodeRover',agentless:'Agentless',openhands:'OpenHands',sweagent:'SWE-agent'};
  const [m,h]=stack.split('/');
  return (models[m] || m)+' / '+(harnesses[h] || h);
}
function measure(tasks,policy,detail=false) {
  const score={tasks:tasks.length,solved:0,tokens:0}, witnesses=[];
  for (const id of tasks) {
    const attempts=policy.map(stack=>({stack,...grid.get(id).get(stack)}));
    const solved=Number(attempts.some(entry=>entry.solved===1));
    const tokens=attempts.reduce((sum,entry)=>sum+entry.tokens,0);
    score.solved+=solved; score.tokens+=tokens;
    if(detail) witnesses.push({id,solved,tokens,attempts});
  }
  return {score,witnesses};
}
function choose(tasks,policies,budget) {
  let best=null;
  for(const policy of policies) {
    const {score}=measure(tasks,policy);
    if(score.tokens>budget*score.tasks) continue;
    const tie=policy.join('\x00');
    if(!best || score.solved>best.score.solved || (score.solved===best.score.solved &&
        (score.tokens<best.score.tokens || (score.tokens===best.score.tokens && tie<best.tie)))) best={policy,score,tie};
  }
  return best;
}
function compute(key) {
  const ref=data.receipt.arms[key], p=ref.parameters;
  const selectTasks=arr=>arr.filter(id=>!p.repository || id.slice(0,id.lastIndexOf('-'))===p.repository);
  const train=selectTasks(data.tasks.slice(0,data.split)), audit=selectTasks(data.tasks.slice(data.split));
  const names=[...stacks].sort().filter(s=>!p.model || s.startsWith(p.model+'/'));
  const singles=names.map(s=>[s]), policies=[...singles];
  if(p.width===2) names.forEach((s,i)=>names.slice(i+1).forEach(u=>policies.push([s,u])));
  const best=choose(train,policies,p.budget);
  if(!best) throw Error('No eligible public configuration');
  const {score,witnesses}=measure(audit,best.policy,true);
  const hindsight=choose(audit,policies,p.budget);
  const uncapped=choose(train,singles,Infinity);
  const unmetered=measure(audit,uncapped.policy).score;
  const pass=score.solved*100>=p.min_percent*score.tasks && score.tokens<=p.budget*score.tasks;
  const same=(a,b)=>a.tasks===b.tasks && a.solved===b.solved && a.tokens===b.tokens;
  const verified=ref.conventional_sql.agreement && JSON.stringify(best.policy)===JSON.stringify(ref.selected) &&
    same(best.score,ref.calibration) && same(score,ref.audit) && pass===ref.qualifies &&
    same(hindsight.score,ref.hindsight_audit) && same(unmetered,ref.uncapped_single.audit) &&
    policies.length===ref.policies_considered;
  return {key,ref,policy:best.policy,train:best.score,score,witnesses,pass,verified,
          theoretical:hindsight.score,uncapped:unmetered};
}
const currentKey=()=>ui.scope==='successor'?'successor':ui.budget+'/'+ui.width;
let current;
function drawPlate(res){
  const field=$('loom'); field.replaceChildren();
  const title=svg('title',{id:'diagram-title'});
  title.textContent=t('issuePath')+' · '+res.score.solved+'/'+res.score.tasks;field.append(title);
  const ordered=[...res.witnesses].sort((a,b)=>b.solved-a.solved || a.id.localeCompare(b.id));
  const order=new Map(ordered.map((row,index)=>[row.id,index]));
  const top=29,bottom=251,scale=(i,length)=>top+(bottom-top)*i/Math.max(1,length-1);
  for(let x=24;x<=480;x+=36) field.append(svg('line',{x1:x,y1:22,x2:x,y2:257,stroke:'#514559','stroke-width':.6}));
  for(let y=28;y<=259;y+=25) field.append(svg('line',{x1:19,y1:y,x2:483,y2:y,stroke:'#514559','stroke-width':.6}));
  // Both endpoints encode actual observations. Distribute the accepted paths
  // across the upper group and leave a visible break before unresolved issues.
  const traces=res.witnesses.map((row,i)=>{
    const x1=26,x2=475,ya=scale(i,res.score.tasks), idx=order.get(row.id);
    const yb=23+idx*205/Math.max(1,res.score.tasks-1)+(row.solved?0:22);
    const pull = (idx/(res.score.tasks-1)-.5)*8;
    const d='M'+x1+' '+ya+' C145 '+ya+',182 '+(ya+pull)+',255 '+((ya+yb)/2)+' S390 '+yb+','+x2+' '+yb;
    return {row,ya,yb,d};
  });
  for(const entry of traces.sort((a,b)=>a.row.solved-b.row.solved)){
    const {row,ya,yb,d}=entry,col=row.solved?'#e6cb91':'#a69abf';
    const path=svg('path',{d,fill:'none',stroke:col,'stroke-width':row.solved?1.38:.96,opacity:row.solved?.95:.68});
    const title=svg('title',{});title.textContent=row.id+' · '+t(row.solved?'solved':'open');path.append(title);
    field.append(path,svg('circle',{cx:26,cy:ya,r:1.5,fill:col}),svg('circle',{cx:475,cy:yb,r:1.7,fill:col}));
  }
  for(const [x,text,anchor] of [[23,t('strandIn'),'start'],[480,t('strandOut'),'end']]){
    const caption=svg('text',{x,y:271,'text-anchor':anchor,fill:'#d7cbd9','font-family':'monospace','font-size':8,'letter-spacing':1.8});
    caption.textContent=text;field.append(caption);
  }
}
function renderWitness() {
  const witness=current.witnesses[ui.issue] || current.witnesses[0];
  const rows=witness.attempts.map(entry=>make('p',label(entry.stack)+' · '+t(entry.solved?'solved':'open')+' · '+n(entry.tokens)+' '+t('tokens')));
  $('witness-rows').replaceChildren(...rows);
}
function renderInstrument(){
  current=compute(currentKey());
  if(!current.verified) throw Error('Public arm differs from the recorded decision: '+current.key);
  const {score,ref,policy}=current;
  $('outcome').textContent=t(current.pass?'pass':'fail');$('outcome').dataset.pass=String(current.pass);
  $('scope-note').textContent=t(ui.scope==='successor'?'scopeSuccessor':'scopeMain');
  $('score').textContent=score.solved+' / '+score.tasks;
  $('volume').textContent=n(score.tokens/score.tasks);
  $('hero-score').textContent=score.solved+' / '+score.tasks;
  $('selected').textContent=policy.map(label).join(' + ');
  $('trade').textContent=n(score.tokens)+' '+t('tokens')+'. '+t('summaryPaid');
  $('budget').value=String(ref.parameters.budget);$('budget').disabled=ui.scope==='successor';$('scope').value=ui.scope;
  document.querySelectorAll('[data-width]').forEach(b=>{b.disabled=ui.scope==='successor';b.setAttribute('aria-pressed',String(Number(b.dataset.width)===ref.parameters.width));});
  const select=$('case');select.replaceChildren(...current.witnesses.map((r,i)=>make('option',r.id,{value:i})));
  if(ui.issue>=score.tasks) ui.issue=0;
  select.value=String(ui.issue);renderWitness();drawPlate(current);
  const scoreOf=s=>s.solved+' / '+s.tasks;
  const comparisons=[['calibration',scoreOf(current.train)],['audit',scoreOf(score)],['sql',t('equal')],
    ['oracle',scoreOf(current.theoretical)],['uncapped',scoreOf(current.uncapped)]];
  $('comparison').replaceChildren(...comparisons.map(([key,value])=>{const row=make('div');row.append(make('dt',t(key)),make('dd',value));return row;}));
}
const translatedRoutes={
 'headline':['Suivre le meilleur taux publié','Désigner rapidement un premier candidat à partir du tableau récapitulatif.','Le tableau regroupe les problèmes de sélection et d’audit. Rien n’y garantit le respect du budget moyen.'],
 'specialist':['Adopter un évaluateur sensible aux coûts','Réutiliser HAL, une infrastructure existante, pour préparer des évaluations locales.','Les résultats publics de HAL ne couvrent pas cette même grille de 18 configurations. Les unités de coût diffèrent.'],
 'local-rerun':['Mesurer toute la grille en contexte privé','Mesurer les résultats sur les propres problèmes de l’établissement avec son évaluateur.','Il faut les droits sur ces données, les modèles, les machines, les vérifications et la mesure de chaque essai.'],
 'failure-review':['Identifier une défaillance réparable','Utiliser les catégories d’échec de l’étude pour proposer une intervention testable.','Le diagnostic seul ne mesure ni l’efficacité d’une réparation ni le coût d’une configuration en service.'],
 'budget-specialist':['Échantillonner les essais décisifs','Économiser des ressources lorsque la mesure d’une grille complète serait coûteuse.','Les coûts préalables et la comparabilité conditionnent la sélection. Les 48 problèmes communs de SWE Mini diffèrent de cet échantillon.'],
 'paired-replay':['Rejouer les configurations sur les mêmes problèmes réservés','Sélectionner sous budget sur 60 problèmes, puis examiner la stratégie verrouillée sur les 40 autres. La même mesure existe pour chaque configuration.','Un évaluateur indépendant doit reconnaître un correctif qui passe en pratique. Une requête SQL exhaustive retrouve le même résultat.']
};
function renderRoutes() {
  const list=ui.revealed?data.options:data.options.slice(0,5);
  const head=item=>ui.lang?translatedRoutes[item.id][0]:item.title;
  $('routes').replaceChildren(...list.map((item,index)=>{
    const button=make('button',head(item),{'aria-pressed':String(index===ui.candidate)});
    button.onclick=()=>{ui.candidate=index;renderRoutes();};return button;
  }));
  const item=list[ui.candidate],trans=translatedRoutes[item.id];
  const url=data.sources[item.source_ids[0]];
  const body=make('p',ui.lang?trans[1]:item.value);
  const limit=make('p',ui.lang?trans[2]:item.tradeoff);
  const link=make('a',t('seeSource'),{href:url,target:'_blank',rel:'noopener noreferrer'});
  const status=item.id===data.winner?'challenger':'proposal';
  $('route-card').replaceChildren(make('div',t(status),{class:'micro'}),make('h3',head(item)),body,document.createElement('br'),limit,link);
  $('challenge').hidden=ui.revealed;
}
function updateChecks() {
  $('events').replaceChildren(...ui.checks.map(row=>make('li',(row.key==='successor'?fr('Django successor','Réutilisation sur Django'):row.key)+' · '+row.solved+'/'+row.tasks+' · '+t(row.verified?'verified':'mismatch'))));
}
function renderLanguage(){
  document.documentElement.lang=ui.lang?'fr-CA':'en';$('language').textContent=ui.lang?'EN':'FR';
  $('language').setAttribute('aria-label',ui.lang?'English':'Français');
  document.querySelectorAll('[data-t]').forEach(node=>node.textContent=t(node.dataset.t));
  document.querySelectorAll('[data-ph]').forEach(node=>node.placeholder=t(node.dataset.ph));
  for(const opt of $('budget').options) opt.textContent=n(Number(opt.value));
  renderInstrument();renderRoutes();updateChecks();
}
function download(bytes,filename,type){
  const url=URL.createObjectURL(new Blob([bytes],{type}));
  const a=make('a',undefined,{href:url,download:filename});document.body.append(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1500);
}
$('scope').onchange=e=>{ui.scope=e.target.value;ui.issue=0;renderInstrument();};
$('budget').onchange=e=>{ui.budget=Number(e.target.value);ui.issue=0;renderInstrument();};
document.querySelectorAll('[data-width]').forEach(button=>button.onclick=()=>{ui.width=Number(button.dataset.width);ui.issue=0;renderInstrument();});
$('case').onchange=e=>{ui.issue=Number(e.target.value);renderWitness();};
$('challenge').onclick=()=>{ui.revealed=true;ui.candidate=data.options.findIndex(x=>x.id===data.winner);renderRoutes();$('routes').lastElementChild.focus();};
$('language').onclick=()=>{ui.lang=1-ui.lang;renderLanguage();};
$('replay').onclick=()=>{
  ui.checks=Object.keys(data.receipt.arms).map(key=>{const result=compute(key);return {key,verified:result.verified,...result.score};});
  updateChecks();
};
$('download').onclick=()=>download(Uint8Array.from(atob(data.archive),c=>c.charCodeAt(0)),'FRONTIER_OMEGA_Pairing_Lab.zip','application/zip');
$('receipt').onclick=()=>download(JSON.stringify({schema:'frontier-showcase-reproduction/1',arm:current.key,recorded:current.ref,
  reproduced:{selected:current.policy,calibration:current.train,audit:current.score,qualifies:current.pass,witnesses:current.witnesses},
  matches_recorded:current.verified},null,2),'pairing-lab-audit.json','application/json');
$('purpose').oninput=()=>{$('savebrief').disabled=!$('purpose').value.trim();};
$('savebrief').onclick=()=>download(JSON.stringify({schema:'frontier-omega-mission-brief/1',purpose:$('purpose').value.trim(),status:'unsubmitted'},null,2),'frontier-mission-brief.json','application/json');
$('datahash').textContent=data.receipt.study.data_sha256;$('archivehash').textContent=data.archive_sha256;
$('source-commit').href=data.receipt.study.source;
renderLanguage();
