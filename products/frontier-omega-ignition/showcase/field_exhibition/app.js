'use strict';
(() => {
  const data = JSON.parse(document.getElementById('public-evidence').textContent);
  const el = id => document.getElementById(id);
  const query = new URLSearchParams(location.search);
  const pilot = JSON.parse(data.pilotReport);
  const secondWeek = JSON.parse(data.secondWeekReport);
  let lang = query.get('lang') === 'fr' ? 'fr' : 'en';
  let candidate = 'sky';
  const cases = data.sky.cases;
  const chosen = cases.find(row => String(row.budget) === query.get('budget') && String(row.visits) === query.get('visits'));
  let current = chosen || cases.find(row => row.id === data.sky.primary);
  const urls = new Map();
  const t = key => data.copy[lang][key];
  const num = (value, maximumFractionDigits = 3) => value === null ? t('unmeasured') : new Intl.NumberFormat(lang, {maximumFractionDigits}).format(value);
  function element(tag, text) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function term(list, label, description, wrap = false) {
    const group = wrap ? element('div') : list;
    group.append(element('dt', label), element('dd', description));
    if (wrap) list.append(group);
  }
  function setBlob(id, value, type, filename) {
    if (urls.has(id)) URL.revokeObjectURL(urls.get(id));
    const url = URL.createObjectURL(new Blob([value], {type}));
    urls.set(id, url);
    el(id).href = url;
    el(id).download = filename;
  }
  function svg(tag, attrs, parent, text) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    parent.append(node);
    return node;
  }
  function skyChart(selected) {
    const points = data.sky.targets;
    const radians = Math.PI / 180;
    // Gnomonic tangent plane centred on the catalog's mean sky direction. The
    // catalogue is a compact field. East (increasing right ascension) is left.
    const mean = points.reduce(([x,y,z], p) => {
      const a = p.ra_deg*radians, d = p.dec_deg*radians;
      return [x+Math.cos(d)*Math.cos(a), y+Math.cos(d)*Math.sin(a), z+Math.sin(d)];
    }, [0,0,0]);
    const a0 = Math.atan2(mean[1], mean[0]), d0 = Math.atan2(mean[2], Math.hypot(mean[0], mean[1]));
    function plane(ra, dec) {
      const da = ra*radians - a0, d = dec*radians;
      const c = Math.sin(d0)*Math.sin(d) + Math.cos(d0)*Math.cos(d)*Math.cos(da);
      if (c <= 0) return null;
      return [-Math.cos(d)*Math.sin(da)/c, -(Math.cos(d0)*Math.sin(d)-Math.sin(d0)*Math.cos(d)*Math.cos(da))/c];
    }
    const xy = points.map(p => plane(p.ra_deg,p.dec_deg));
    const scale = Math.min(212 / Math.max(.05, ...xy.map(p => Math.abs(p[0]))), 108 / Math.max(.05, ...xy.map(p => Math.abs(p[1]))));
    const project = (ra,dec) => { const v = plane(ra,dec); return v && [310 + scale*v[0],177 + scale*v[1]]; };
    const root = el('drawing'); root.replaceChildren();
    el('sky-title').textContent = t('plate'); el('sky-desc').textContent = t('skyDescription');
    const clip = svg('clipPath', {id:'window'},root);
    svg('rect',{x:31,y:28,width:558,height:298},clip);
    svg('rect',{x:31,y:28,width:558,height:298,fill:'url(#ink)',stroke:'#71617a','stroke-width':.8},root);
    const layer = svg('g',{'clip-path':'url(#window)'},root);
    function grid(pairs, axis) {
      let open = false;
      const d = [], vertices = [];
      for (const [ra,dec] of pairs) {
        const v = project(ra,dec);
        if (!v || Math.abs(v[0]) > 2000 || Math.abs(v[1]) > 1600) { open = false; vertices.push(null); continue; }
        d.push((open?'L':'M') + v.map(n => n.toFixed(2)).join(' ')); vertices.push(v); open=true;
      }
      svg('path',{d:d.join(' '),class:axis?'gridline axis':'gridline'},layer);
      return vertices;
    }
    function intersection(vertices, coordinate, edge) {
      for (let i=1;i<vertices.length;i++) {
        const p=vertices[i-1], q=vertices[i];
        if (!p || !q || q[coordinate]===p[coordinate]) continue;
        const part=(edge-p[coordinate])/(q[coordinate]-p[coordinate]);
        if (part>=0 && part<=1) return p[1-coordinate]+part*(q[1-coordinate]-p[1-coordinate]);
      }
      return null;
    }
    for (let ra=0;ra<360;ra+=15) {
      const meridian=grid(Array.from({length:179},(_,i)=>[ra,i-89]),false);
      const x=intersection(meridian,1,326);
      if (x!==null && x>46 && x<575) svg('text',{x,y:347,class:'map-label','text-anchor':'middle'},root,`${ra/15}h`);
    }
    for (let dec=-80;dec<=80;dec+=10) {
      const center = a0/radians;
      const parallel=grid(Array.from({length:179},(_,i)=>[center+i-89,dec]),dec===0);
      const y=intersection(parallel,0,31);
      if(y!==null && y>35 && y<317) svg('text',{x:26,y:y+4,class:'map-label','text-anchor':'end'},root,`${dec}°`);
    }
    const labels = [];
    for (const p of [...points].sort((a,b)=>a.ra_deg-b.ra_deg)) {
      const [x,y] = project(p.ra_deg,p.dec_deg);
      const marked = selected.has(p.id);
      const group = svg('g', {'data-target':p.id,'data-scheduled':String(marked)}, layer);
      svg('title',{},group,`${p.id} · ${num(p.ra_deg,5)}°, ${num(p.dec_deg,5)}°`);
      if (marked) svg('circle',{cx:x,cy:y,r:9.3,class:'halo'},group);
      svg('circle',{cx:x,cy:y,r:4.2,class:marked?'visit':'unused'},group);
      // Each tabulated object is labelled with its actual catalogue suffix.
      const label = p.id.slice(-5), end=x>500?-1:1;
      const position = [ -17, 24, -35, 41, -51, 58 ].map(dy=>({x:x+end*14,y:y+dy})).find(v=>v.y>39 && v.y<318 && labels.every(l=>Math.abs(v.y-l.y)>14 || Math.abs(v.x-l.x)>61));
      if (position) {
        labels.push(position);
        svg('path',{d:`M${x+end*6} ${y+(position.y>y?6:-6)} L${position.x} ${position.y-3}`,class:'leader'},group);
        svg('text',{x:position.x+end*3,y:position.y,class:'star-id','text-anchor':end===1?'start':'end'},group,label);
      }
    }
    svg('text',{x:588,y:370,'text-anchor':'end',class:'map-foot'},root,t('orientation'));
    el('sky-count').textContent=`Fink/ZTF · ${selected.size}/${points.length} ${t('marked')}`;
    el('sky-legend').textContent=t('goldMarks');
  }
  function opportunity() {
    const c = data.opportunities.find(row => row.id===candidate);
    const [short,title,claim,limit,test] = c.translations[lang];
    document.querySelectorAll('#choices button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === candidate)));
    el('opp-state').textContent=t(c.id==='sky'?'chosen':'hypothesis');
    el('opp-title').textContent=title; el('opp-claim').textContent=claim;
    const details=el('opp-detail');details.replaceChildren();
    term(details,t('limitLabel'),limit);term(details,t('testLabel'),test);
    el('opp-source').textContent=t('sourceLink');el('opp-source').href=c.publication;
  }
  function options(id, values, fn, selected) {
    const select=el(id);select.replaceChildren();
    values.forEach(value=>{const o=element('option',fn(value));o.value=String(value);select.append(o);});
    select.value=String(selected);
  }
  function worklist() {
    el('budget').value=String(current.budget); el('coverage').value=String(current.visits);
    el('plan-state').textContent=t(current.accepted?'verified':'unverified');
    el('plan-number').textContent=`${num(current.objective)} ${t(current.objective===1?'targetSingle':'targetsPlural')}`;
    el('plan-summary').textContent=`${num(current.slots.length)} ${t('visitsUsed')} / ${num(current.budget)} ${t('available')}. ${t('directScore')} ${num(current.direct_objective)} ${t('targetsNoun')}.`;
    const body=el('worklist');body.replaceChildren();
    const fmt=new Intl.DateTimeFormat(lang==='en'?'en-GB':'fr-CA',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23',timeZone:'UTC'});
    for (const s of current.slots) {
      const row=element('tr'), cell=element('td'), time=element('time',fmt.format(new Date(s.utc)));
      time.dateTime=s.utc;cell.append(time);
      row.append(cell,element('td',s.target_id),element('td',num(s.ra_deg,5)),element('td',num(s.dec_deg,5)));
      body.append(row);
    }
    el('empty-plan').textContent=t('zero');el('empty-plan').hidden=current.slots.length!==0;
    skyChart(new Set(current.slots.map(s=>s.target_id)));
    setBlob('csv',current.csv,'text/csv;charset=utf-8',current.id+'.csv');
    setBlob('receipt',current.receipt_text,'application/json',current.id+'.json');
  }
  let gap = 120;
  function datedWindow(startUTC, endUTC) {
    const date = new Intl.DateTimeFormat(lang === 'en' ? 'en-GB' : 'fr-CA',
      {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'});
    const lastDay = new Date(Date.parse(endUTC) - 1);
    return `${date.formatRange(new Date(startUTC), lastDay)} UTC`;
  }
  function fill(template, values) {
    return template.replace(/\{([a-z]+)\}/g, (_, key) => values[key]);
  }
  function secondWeekFinding() {
    const s = secondWeek;
    el('second-window').textContent=`${t('repeatTitle')} · ${datedWindow(s.cutoff_utc,s.observation_end_utc)}. `;
    el('second-outcome').textContent=fill(t('repeatCount'), {overlap:s.overlap_with_first.length, rows:s.holdout_rows,
      wide:s.pairs_120.length, tight:s.pairs_10.length, targets:s.targets});
    const paired=s.pairs_120.find(row=>s.overlap_with_first.includes(row.target_id) && data.sky.photometry.missing_pair.includes(row.target_id));
    if (paired) {
      const signed=new Intl.NumberFormat(lang,{maximumFractionDigits:6,signDisplay:'always'});
      el('second-example').textContent=fill(t('repeatExample'), {id:paired.target_id, color:signed.format(paired.g_minus_r_diff_mag),
        error:num(paired.formal_error_mag,6), minutes:num(paired.separation_minutes,5)});
    }
  }
  function photometry() {
    const source=data.sky.photometry;
    const kept=source.pairs.filter(p=>Math.abs(p.g_jd-p.r_jd)*1440<=gap);
    const missing=data.sky.targets.map(t=>t.id).filter(id=>!kept.some(p=>p.target_id===id));
    const body=el('photometry');body.replaceChildren();
    for(const p of kept) {
      const row=element('tr');
      row.append(element('td',p.target_id),element('td',num(p.g_minus_r_diff_mag,6)),element('td',num(p.formal_error_mag,6)),element('td',num(p.separation_minutes,5)));
      body.append(row);
    }
    el('photo-count').textContent=`${datedWindow(...source.window_utc)} · ${kept.length}/${source.targets} ${t('photoCount')}`;
    el('withheld').textContent=`${t('withheld')} · ${missing.join(', ')}`;
    // Every field is a numeric value, a source ID or an ISO time from the verified projection.
    const csv=[source.columns.join(','),...kept.map(row=>source.columns.map(k=>String(row[k])).join(','))].join('\r\n')+'\r\n';
    setBlob('colors',csv,'text/csv;charset=utf-8','difference-photometry-'+gap+'min.csv');
    el('colors').textContent=t('colors');
    el('archive-source').href=source.source_url;
  }
  function proof() {
    const list=el('verdicts');list.replaceChildren();
    const agreement=cases.filter(c=>c.accepted&&c.objective===c.direct_objective).length;
    term(list,t('solverLabel'),`${agreement}/${cases.length} ${t('casesAgree')}`,true);
    term(list,t('holdoutLabel'),data.sky.holdout?`${data.sky.holdout.detected}/${data.sky.holdout.total} ${t('archiveWith')} ${data.sky.holdout.note[lang]}`:t('archiveUnknown'),true);
    term(list,t('actionLabel'),t('actionProof'),true);
    const passed=pilot.arms.filter(arm=>arm.meets_interactive_performance).length;
    term(list,t('pilotLabel'),`${passed}/${pilot.arms.length} ${t('pilotSummary')}`,true);
    term(list,t('economicsLabel'),t('economicsProof'),true);
    el('pilot-identity').textContent=`${pilot.model} · ${pilot.hardware.processor} · ${num(pilot.hardware.threads)} ${t('pilotThreads')}`;
    const liveRows=el('model-results');
    liveRows.replaceChildren();
    for(const arm of pilot.arms.filter(a=>a.concurrency===Number(el('service-load').value))) {
      const card=element('article');
      card.dataset.route=arm.route;
      card.dataset.concurrency=String(arm.concurrency);
      card.append(element('h4',`${t(arm.route==='field'?'fieldRoute':'directRoute')} · ${t(arm.decision==='withhold'?'pilotWithhold':'pilotPass')}`));
      card.append(element('p',`${arm.transport_complete}/${arm.requests} ${t('pilotStreams')} · ${arm.quality_accepted}/${arm.requests} ${t('pilotQuality')}`));
      card.append(element('p',`${t('fieldLatency')} · ${num(arm.p90_first_visible_ms===null?null:arm.p90_first_visible_ms/1000)} s (${arm.visible_count}/${arm.requests}) / ${num(arm.p90_turn_ms===null?null:arm.p90_turn_ms/1000)} s (${arm.transport_complete}/${arm.requests})`));
      card.append(element('p',`${t('pilotSpeed')} · ${num(arm.p10_delivered_tokens_per_turn_second)} (${arm.rate_count}/${arm.requests})`));
      liveRows.append(card);
    }
    const fields=el('field-results');fields.replaceChildren();
    for(const arm of data.field.arms.filter(arm=>arm.concurrency===Number(el('service-load').value))) {
      const article=element('article');
      article.append(element('h3',t(arm.target==='nominal'?'fieldNominal':'fieldAdverse')));
      article.append(element('p',`${t(arm.route==='field'?'fieldRoute':'directRoute')} · ${num(arm.concurrency)} ${t('load')}`));
      article.append(element('p',`${num(arm.quality_accepted)}/${num(arm.requests)} ${t('fieldAccepted')} · ${num(arm.attempts)} ${t('attempts')} · ${num(arm.transport_complete)} ${t('transport')}.`));
      article.append(element('p',`${t('fieldLatency')} · ${num(arm.p90_first_visible_ms)} ms (${arm.visible_count}/${arm.requests}) / ${num(arm.p90_turn_ms)} ms (${arm.transport_complete}/${arm.requests})`));
      fields.append(article);
    }
    const s=data.successor;
    el('successor-description').textContent=`${s.dates} ${t('queue')} · ${[ 'reprocess', 'retain', 'review', 'defer' ].map(k=>`${num(s[k])} ${t(k)}`).join(' / ')}.`;
  }
  function render() {
    document.documentElement.lang=lang;
    document.title='FRONTIER Ω IGNITION · '+(lang==='fr'?'Nuit d’observation':'Observing night');
    document.querySelectorAll('[data-i]').forEach(n=>{n.textContent=t(n.dataset.i);});
    el('navigation').setAttribute('aria-label',t('nav'));
    const toggle=el('lang');toggle.textContent=lang==='fr'?'EN':'FR';toggle.lang=lang==='fr'?'en':'fr';toggle.setAttribute('aria-label',lang==='fr'?'English':'Français');
    el('mission-scope').textContent=t('scope');
    el('choices').replaceChildren();el('choices').setAttribute('aria-label',t('oppGroup'));
    for(const c of data.opportunities){
      const button=element('button'); button.type='button';button.dataset.id=c.id;button.setAttribute('aria-controls','opportunity');
      const arrow=element('span','↗');arrow.setAttribute('aria-hidden','true');button.append(element('span',c.translations[lang][0]),arrow);
      button.addEventListener('click',()=>{candidate=c.id;opportunity();});el('choices').append(button);
    }
    el('research-source').href=data.opportunities.find(o=>o.id==='sky').publication;
    options('budget',[...new Set(cases.map(c=>c.budget))].sort((a,b)=>a-b),n=>`${num(n)} ${t('budgetOption')}`,current.budget);
    options('coverage',[...new Set(cases.map(c=>c.visits))].sort((a,b)=>a-b),n=>t(n===1?'coverageOne':'coverageTwo'),current.visits);
    el('csv').textContent=t('csv');el('receipt').textContent=t('receipt');
    el('command').textContent=data.command;el('kit-hash').textContent=data.archive.sha256;
    const related=el('related');related.replaceChildren();
    for(const row of data.related){const link=element('a',t(row.label)+' ↗');link.href=row.url;link.target='_blank';link.rel='noopener noreferrer';const item=element('li');item.append(link);related.append(item);}
    options('gap',data.sky.exploratory_color_counts.map(x=>x.max_gap_minutes),n=>`${num(n)} min`,gap);
    const loads=[...new Set(data.field.arms.map(a=>a.concurrency))].sort((a,b)=>a-b);
    options('service-load',loads,num,Number(el('service-load').value)||loads[0]);
    opportunity();worklist();photometry();secondWeekFinding();proof();
  }
  for(const id of ['budget','coverage']) el(id).addEventListener('change',()=>{
    current=cases.find(c=>c.budget===Number(el('budget').value)&&c.visits===Number(el('coverage').value));worklist();
  });
  el('service-load').addEventListener('change',proof);
  el('gap').addEventListener('change',()=>{gap=Number(el('gap').value);photometry();});
  el('lang').addEventListener('click',()=>{lang=lang==='en'?'fr':'en';render();});
  setBlob('second-source',data.secondWeekReport,'application/json','fink-second-week.json');
  setBlob('pilot-summary',data.pilotReport,'application/json','qwen-cpu-pilot.json');
  setBlob('download',Uint8Array.from(atob(data.archive.bytes),v=>v.charCodeAt(0)),'application/zip','FRONTIER_OMEGA_Observing_Night.zip');
  render();
})();
