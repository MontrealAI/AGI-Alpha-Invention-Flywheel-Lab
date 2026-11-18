'use strict';

function createActionDesk(study, ui) {
  const {el, t, num, fill, element, svg, options, setBlob, locale} = ui;
  const cases = new Map(Object.entries(study.cases).map(([purpose, editions]) =>
    [purpose, new Map(editions.map(e => [e.id, {text:e.receipt, receipt:JSON.parse(e.receipt)}]))]));
  const defaults = {'gw-status':'withdraw', 'ztf-persistence':'g-repeat',
    'engineering-qualification':Array.from(cases.get('engineering-qualification').keys()).at(-1)};
  const query = new URLSearchParams(location.search);
  let purpose = cases.has(query.get('purpose')) ? query.get('purpose') : 'gw-status';
  const selection = {...defaults};
  if (cases.get(purpose).has(query.get('edition'))) selection[purpose] = query.get('edition');
  let heroEdition = ['before','withdraw'].includes(selection['gw-status']) ? selection['gw-status'] : 'withdraw';
  let reference = 'archive';

  function utc(s) {
    const date = new Intl.DateTimeFormat(locale()==='fr'?'fr-CA':'en-GB',
      {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(s));
    return date + ' · ' + s.slice(11).replace(/Z$/, '') + ' UTC';
  }
  function frac(value) {
    const [numerator, denominator = '1'] = String(value).split('/');
    return Number(numerator)/Number(denominator);
  }
  function signed(x, places) {
    return new Intl.NumberFormat(locale(), {minimumFractionDigits:places, maximumFractionDigits:places,
      signDisplay:'exceptZero'}).format(x).replace(/^-/, '−');
  }
  function latest(receipt) {
    const evidence=receipt.attempts.at(-1)?.evidence;
    return receipt.mission.profile==='engineering-qualification' ? evidence?.[0] : evidence?.at(-1);
  }
  function reportEdition(value) {
    if (purpose === 'ztf-persistence') {
      const [band, route] = value.split('-');
      return band + ' · ' + t('ztf_'+route);
    }
    if (purpose === 'engineering-qualification') {
      return value === 'pooled' ? t('engineeringPooled') : fill(t('engineeringCap'),{n:value});
    }
    return t('gw_'+value);
  }
  function sourceLink(receipt) {
    for (const step of [...receipt.attempts].reverse()) {
      const row = receipt.mission.profile==='engineering-qualification' ? step.evidence[0] : step.evidence.at(-1);
      if (!row) continue;
      const url = row.source_url || row.url || (row.sources || []).find(s=>s.url)?.url;
      if (url && /^https:\/\//.test(url)) return url;
    }
    return null;
  }
  function referenceDesk() {
    options('reference-control',Object.keys(study.references),v=>t('ref_'+v),reference);
    const row=study.references[reference];
    el('reference-origin').textContent=t(row.kind==='record'?'archiveOrigin':'controlOrigin');
    el('reference-verdict').textContent=t(row.witness?'witnessRetained':'witnessWithheld');
    el('reference-verdict').dataset.accepted=String(Boolean(row.witness));
    const detail=el('reference-evidence');
    const prefix=fill(t('referenceCondition'),{ref:row.required_reference});
    let text=prefix+' ';
    if(reference==='other-reference') text+=fill(t('differentCandidate'),{ref:row.candidate_reference})+' ';
    if(row.witness) {
      text+=fill(t('referenceMeasurement'),{id:row.witness,utc:utc(row.utc),delta:signed(row.delta,4),error:num(row.uncertainty,4)});
    } else {
      text+=t('missingOriginal');
    }
    detail.textContent=text;
  }
  function chronicle() {
    const all=cases.get('gw-status').get('withdraw').receipt;
    const selected=cases.get('gw-status').get(heroEdition).receipt;
    const records=selected.attempts.find(a=>a.route==='status_history').evidence;
    const full=all.attempts.find(a=>a.route==='status_history').evidence;
    const left=76, right=468, upper=63, lower=112;
    const start=Date.parse(full[0].issued_utc), end=Date.parse(full.at(-1).issued_utc);
    const x=stamp=>left+(right-left)*(Date.parse(stamp)-start)/(end-start);
    const y=row=>row.notice_type==='Retraction'?lower:upper;
    const g=el('chronogram-plot');g.replaceChildren();
    for(const [height,key] of [[upper,'trackActive'],[lower,'trackRetracted']]){
      svg('line',{x1:left,x2:right+10,y1:height,y2:height,class:'time-rule'},g);
      svg('text',{x:left-9,y:height+4,'text-anchor':'end',class:'track-label'},g,t(key));
    }
    const cutoff=selected.mission.scope.as_of, mark=x(cutoff);
    let d='M'+x(records[0].issued_utc)+' '+y(records[0]);
    for(const row of records.slice(1)) d+=' H'+x(row.issued_utc)+' V'+y(row);
    d+=' H'+mark;
    svg('path',{d,class:'notice-course'},g);
    svg('line',{x1:mark,x2:mark,y1:24,y2:127,class:'decision-edge'},g);
    for(const row of records){
      const dot=svg('circle',{cx:x(row.issued_utc),cy:y(row),r:row===records.at(-1)?6:3.5,class:'notice-dot',
        'data-record':row.record_id},g);
      svg('title',{},dot, row.record_id+' · '+row.issued_utc);
    }
    svg('text',{x:left,y:151,class:'track-label'},g,full[0].issued_utc.slice(11,19));
    svg('text',{x:right,y:151,'text-anchor':'end',class:'track-label'},g,cutoff.slice(11,19)+' UTC');
    el('chronicle-id').textContent=selected.mission.scope.event;
    el('chronicle-sub').textContent=fill(t('chronicleCaption'),{day:utc(cutoff).split(' · ')[0]});
    el('chronicle-decision').textContent=t('act_'+selected.decision.action);
    el('chronicle-flip').textContent=t(heroEdition==='withdraw'?'oneSecondBack':'oneSecondAhead');
    el('chronogram-title').textContent=t('chronicleTitle');
    el('chronogram-desc').textContent=records.map(r=>r.issued_utc.slice(11,19)+' '+t('type_'+r.notice_type)).join(', ')+'. '+t('act_'+selected.decision.action);
  }
  function facts(receipt) {
    const d=receipt.decision, row=latest(receipt);
    if(purpose==='engineering-qualification' && row?.lower!==undefined) {
      const bounds=signed(frac(row.lower)*100,3)+' … '+signed(frac(row.upper)*100,3);
      return fill(t('engineeringCounts'),{a:num(row.pooled.A),b:num(row.pooled.B),n:num(row.cases),
        lo:bounds,revealed:num(row.revealed.length),total:num(row.repository_count)});
    }
    if(purpose==='gw-status' && row) {
      return fill(t('noticeFact'),{serial:num(row.serial),type:t('type_'+row.notice_type),utc:utc(row.issued_utc),id:row.record_id});
    }
    if(purpose==='ztf-persistence' && row?.delta_from_baseline_mag!==undefined) {
      return fill(t('witnessFact'),{band:row.band,id:row.record_id,delta:signed(row.delta_from_baseline_mag,4),
        error:num(row.formal_error_mag,4),utc:utc(row.event_utc)});
    }
    return t('state_'+d.state)+'.';
  }
  function uncertainty(receipt) {
    const scope=receipt.mission.scope;
    if(scope.clock==='received') return t(purpose==='gw-status'?'gwDeliveryLimit':'ztfDeliveryLimit');
    if(purpose==='gw-status') return t(receipt.decision.state==='observed'?'gwActionScope':'gwFirstLimit');
    if(purpose==='ztf-persistence') return t(receipt.decision.state==='observed'?'ztfActionScope':'ztfFirstLimit');
    return t('engineeringScope');
  }
  function ledger(receipt) {
    const box=el('action-attempts');box.replaceChildren();
    for(const attempt of receipt.attempts) {
      const li=element('li');
      li.dataset.route=attempt.route;
      const row=element('div'); row.append(element('strong',t('route_'+attempt.route)),element('span',t('state_'+attempt.state)));
      li.append(row);
      const note=purpose==='engineering-qualification' ? attempt.evidence[0] : attempt.evidence.at(-1);
      if(note?.record_id) li.append(element('small',note.record_id));
      else if(attempt.route==='pooled' || attempt.route==='repository_outcomes') {
        if(note?.pooled) li.append(element('small',fill(t('pooledLine'),{a:num(note.pooled.A),b:num(note.pooled.B),n:num(note.cases)})));
      }
      box.append(li);
    }
    const source=el('action-citation'),url=sourceLink(receipt);
    source.hidden=!url;
    if(url) {source.href=url;source.textContent=t('originalSource');}
    else source.removeAttribute('href');
  }
  function bounds(receipt) {
    const figure=el('engineering-band');
    figure.hidden=purpose!=='engineering-qualification';
    if(figure.hidden) return;
    const current=latest(receipt), root=el('bound-plot');
    root.replaceChildren();
    if(!current || current.lower===undefined) {figure.hidden=true;return;}
    const observed=new Map();
    for(const edition of cases.get(purpose).values()) {
      const scope=edition.receipt.mission.scope;
      if(scope.max_repositories>receipt.mission.scope.max_repositories) continue;
      const row=latest(edition.receipt);
      if(row && row.lower!==undefined) observed.set(row.revealed.length,row);
    }
    const rows=[...observed.values()].sort((a,b)=>a.revealed.length-b.revealed.length);
    const max=Math.max(...rows.flatMap(r=>[Math.abs(frac(r.upper)), Math.abs(frac(r.lower))]),0.00001);
    const x=n=>46+318*n/current.repository_count, y=n=>48-n*37/max;
    const points=(sorted,key)=>sorted.map(r=>x(r.revealed.length)+','+y(frac(r[key])));
    svg('line',{x1:46,x2:364,y1:48,y2:48,class:'time-rule'},root);
    svg('text',{x:38,y:52,'text-anchor':'end',class:'bounds-label'},root,'0');
    if(rows.length>1) svg('polygon',{points:[...points(rows,'upper'),...points([...rows].reverse(),'lower')].join(' '),class:'bounds-area'},root);
    const end=x(current.revealed.length), bottom=y(frac(current.lower)), top=y(frac(current.upper));
    svg('line',{x1:end,x2:end,y1:bottom,y2:top,class:'bounds-end'},root);
    for(const value of new Set([top,bottom])) svg('circle',{cx:end,cy:value,r:4,class:'notice-dot'},root);
    svg('text',{x:46,y:109,class:'bounds-label'},root,'0');
    svg('text',{x:364,y:109,'text-anchor':'end',class:'bounds-label'},root,num(current.repository_count)+' '+t('repositoryAxis'));
    el('bound-title').textContent=t('boundTitle');el('bound-desc').textContent=facts(receipt);
  }
  function decision() {
    const edition=selection[purpose];
    options('action-purpose',[...cases.keys()],v=>t('purpose_'+v),purpose);
    options('action-edition',[...cases.get(purpose).keys()],reportEdition,edition);
    el('action-edition-label').textContent=t(purpose==='engineering-qualification'?'scopeRepository':'scopeArchive');
    const {receipt,text}=cases.get(purpose).get(edition);
    const d=receipt.decision;
    el('action-contract').textContent=receipt.mission.scope.event || (purpose==='ztf-persistence'?'ZTF26acbezdh':'SWE-bench Verified');
    el('action-question').textContent=t('question_'+purpose);
    el('action-state').textContent=t('state_'+d.state);
    el('action-state').parentElement.dataset.state=d.state;
    el('action-verdict').textContent=t('act_'+d.action);
    el('action-verdict').dataset.action=d.action;
    el('action-fact').textContent=facts(receipt);
    el('action-limit').textContent=uncertainty(receipt);
    ledger(receipt);bounds(receipt);
    el('photometry-link').hidden=purpose!=='ztf-persistence' || receipt.mission.scope.clock!=='event';
    const trial=el('trial-download');
    trial.hidden=purpose!=='engineering-qualification' || d.state!=='observed' ||
      JSON.parse(study.trial).first_submission!==latest(receipt)?.[d.finding];
    if(trial.hidden) trial.removeAttribute('href');
    else setBlob('trial-download',study.trial,'application/json;charset=utf-8','qualification_input.json');
    setBlob('action-download',text,'application/json;charset=utf-8','decision.json');
    if(purpose==='gw-status' && (edition==='before'||edition==='withdraw')) heroEdition=edition;
    chronicle();
  }
  el('action-purpose').addEventListener('change',e=>{purpose=e.target.value;decision();});
  el('action-edition').addEventListener('change',e=>{selection[purpose]=e.target.value;decision();});
  el('photometry-link').addEventListener('click',()=>{
    const {mission}=cases.get(purpose).get(selection[purpose]).receipt;
    if (purpose==='ztf-persistence') ui.openNotice(mission.scope,mission.sources);
  });
  el('chronicle-flip').addEventListener('click',()=>{
    purpose='gw-status';
    selection[purpose]=heroEdition==='before'?'withdraw':'before';
    decision();
  });
  el('reference-control').addEventListener('change',e=>{reference=e.target.value;referenceDesk();});
  return {render(){decision();referenceDesk();}};
}
