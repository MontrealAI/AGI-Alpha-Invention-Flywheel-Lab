'use strict';

// Each selectable midnight comes from the source-bound Python producer.
// The browser displays the exact dated queue, including decisions to defer.
function createChangeDesk(series, {el, t, num, fill, element, svg, options, setBlob, locale}) {
  const key = row => row.target_id + '/' + row.band;
  const stamp = at => new Intl.DateTimeFormat(locale()==='fr'?'fr-CA':'en-GB',
    {day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(at));
  const signed = (value,precision=6) => new Intl.NumberFormat(locale(),{signDisplay:'always',maximumFractionDigits:precision}).format(value);
  const head = window => window.days[window.days.length-1];
  const counter = row => [row.status,row.eligible_detections,row.comparisons].join('/');
  function illustrative(window) {
    const archive = head(window);
    const later = [...archive.alerts].sort((a,b)=>a.issued_utc.localeCompare(b.issued_utc)||key(a).localeCompare(key(b)));
    if (later.length) return {target:key(later[0]),issued:later[0].issued_utc,hasAlert:true,weight:0};
    const measured = archive.coverage.filter(r=>r.strongest_comparison)
      .sort((a,b)=>Math.abs(b.strongest_comparison.delta_mag)-Math.abs(a.strongest_comparison.delta_mag)||key(a).localeCompare(key(b)));
    const first = measured[0] || archive.coverage[0];
    return {target:key(first),issued:first.strongest_comparison?.issued_utc||window.start,
      hasAlert:false,weight:Math.abs(first.strongest_comparison?.delta_mag||0)};
  }
  const presets = series.map(illustrative);
  const index = presets.findIndex(s=>s.hasAlert);
  let active = index<0?series[presets.findIndex(p=>p.weight===Math.max(...presets.map(x=>x.weight)))]:series[index];
  let checkpoint, selected;
  function choose(window) {
    active=window;
    const preset=presets[series.indexOf(window)];
    selected=preset.target;
    checkpoint=window.days.find(s=>s.as_of_utc>=preset.issued) || head(window);
  }
  const requested = new URLSearchParams(location.search);
  choose(series.find(s=>s.id===requested.get('window'))||active);
  checkpoint=active.days.find(s=>s.as_of_utc===requested.get('date')+'T00:00:00Z')||checkpoint;
  const requestedFocus=requested.get('target')+'/'+requested.get('band');
  if (checkpoint.coverage.some(r=>key(r)===requestedFocus)) selected=requestedFocus;
  let useSecond=requested.get('source')==='alerce'||!requested.has('source')&&!requested.has('date');
  if (useSecond && active.second_archive && !requested.has('date')) {
    checkpoint=active.days.find(s=>active.second_archive[s.as_of_utc].witnesses.some(v=>key(v)===selected))||checkpoint;
  }
  function extras(s=checkpoint) {return useSecond?active.second_archive?.[s.as_of_utc]:null;}
  function external(keyToFind,s=checkpoint) {return extras(s)?.witnesses.find(r=>key(r)===keyToFind);}
  function statusText(status) { return t('status_'+status); }
  function plate(row, witness, alert) {
    const root=el('trace-drawing');root.replaceChildren();
    el('trace').setAttribute('viewBox','0 0 564 240');
    el('trace-title').textContent=t('traceTitle');
    el('trace-target').textContent=row.target_id;
    el('trace-band').textContent=fill(t('bandName'),{band:row.band});
    el('trace-state').textContent=statusText(row.status);
    el('trace-source').textContent=alert?.cross?'FINK + ALeRCE / ZTF':'FINK / ZTF';
    el('trace-date').textContent=stamp(checkpoint.as_of_utc)+' · 00:00 UTC';
    el('trace-delta').textContent=witness?fill(t(alert?.followup?'traceLaterDelta':'traceIssueDelta'),{
      delta:signed(alert?.followup?alert.followup_delta_mag:witness.delta_mag,4),error:num(alert?.followup?alert.followup_formal_error_mag:witness.formal_error_mag,4)}):'';
    if (!witness) {
      el('trace-desc').textContent=t('noPair');
      svg('text',{x:282,y:124,'text-anchor':'middle',class:'chart-axis'},root,t('noPair'));
      return;
    }
    const compact=matchMedia('(max-width: 540px)').matches;
    const width=compact?390:564;
    const left=compact?64:78, right=width-(compact?42:73), edge=width-22;
    el('trace').setAttribute('viewBox','0 0 '+width+' 240');
    const points=[{p:witness.baseline,role:'baseline'},{p:witness.trigger,role:'current'}];
    if (alert?.followup) points.push({p:alert.followup,role:'followup'});
    const times=points.map(({p})=>Date.parse(p.utc));
    const low=Math.min(...points.map(({p})=>p.mag-p.error_mag));
    const high=Math.max(...points.map(({p})=>p.mag+p.error_mag));
    const span=Math.max(high-low,0.04);
    const min=low-span*.20,max=high+span*.23;
    const x=i=>left+(right-left)*(times[i]-times[0])/Math.max(1,times.at(-1)-times[0]);
    // Smaller magnitudes are brighter and appear higher on the page.
    const y=m=>30+145*(m-min)/(max-min);
    svg('text',{x:14,y:16,class:'chart-title'},root,t('axisMag'));
    for(let i=0;i<4;i++) {
      const m=min+(max-min)*i/3;
      svg('line',{x1:left-11,x2:edge,y1:y(m),y2:y(m),class:'chart-guide'},root);
      svg('text',{x:left-18,y:y(m)+4,'text-anchor':'end',class:'chart-axis'},root,num(m,2));
    }
    svg('path',{d:points.map((point,i)=>(i?'L':'M')+x(i)+' '+y(point.p.mag)).join(' '),class:'chart-join'},root);
    const fmt=new Intl.DateTimeFormat(locale()==='fr'?'fr-CA':'en-GB',{month:'short',day:'numeric',timeZone:'UTC'});
    points.forEach(({p,role},i)=>{
      const cx=x(i), cy=y(p.mag), u=y(p.mag-p.error_mag), l=y(p.mag+p.error_mag);
      svg('line',{x1:cx,x2:cx,y1:30,y2:180,class:'chart-guide chart-guide-vert'},root);
      svg('path',{d:'M'+cx+' '+u+'V'+l+' M'+(cx-5)+' '+u+'h10 M'+(cx-5)+' '+l+'h10',class:'chart-error'},root);
      if(role==='followup') svg('path',{d:'M'+cx+' '+(cy-7)+'l7 7 -7 7 -7 -7Z',class:'trace-observation trace-repeat'},root);
      else svg('circle',{cx,cy,r:5.5,class:'trace-observation '+(role==='current'?'trace-trigger':'')},root);
      // End labels anchor away from a middle point even with irregular cadence.
      if(i===0 || i===points.length-1) svg('text',{x:cx,y:202,'text-anchor':i===0?'start':'end',class:'chart-axis'},root,fmt.format(new Date(p.utc)));
    });
    svg('text',{x:edge,y:227,'text-anchor':'end',class:'chart-title'},root,t('axisUTC'));
    el('trace-desc').textContent=points.map(({p,role})=>t('point_'+role)+' '+p.utc+', '+num(p.mag,6)+' ± '+num(p.error_mag,6)+' mag').join('. ');
  }
  function windowLabel(window) {
    const f=new Intl.DateTimeFormat(locale()==='fr'?'fr-CA':'en-GB',{day:'numeric',month:'short',timeZone:'UTC'});
    const start=new Date(window.start), end=new Date(Date.parse(window.end)-1);
    return t('series_'+window.id)+' · '+f.formatRange(start,end);
  }
  function timeline(row, witness, alert) {
    const list=el('signal-points');list.replaceChildren();
    for (const [role,p] of [['baseline',witness?.baseline],['current',witness?.trigger],['followup',alert?.followup]]) {
      const li=element('li');
      li.append(element('span',t('point_'+role)+(role==='followup'&&alert?.cross?' · ALeRCE':'')));li.firstChild.className='step-label';
      if(p) {
        const when=element('time',p.utc.replace('T',' ').replace('Z',' UTC'));when.dateTime=p.utc;
        li.append(element('strong',num(p.mag,6)+' ± '+num(p.error_mag,6)+' mag'),when,element('small','ID '+p.candid));
      } else {
        const state=element('span',role==='followup' ? t('next_'+row.status) : t('pairPending'));
        state.className='awaiting';li.append(state);
      }
      list.append(li);
    }
  }
  function toCsv() {
    const fields=['target_id','band','as_of_utc','eligible_detections','comparisons','status','baseline_candid','baseline_utc','current_candid','current_utc','delta_mag','formal_error_mag','rate_mag_per_day','alert_issued_utc','repeat_deadline_utc','direction','followup_candid','followup_utc','followup_delta_mag','reference_status','additional_broker','additional_status','additional_candid','additional_utc','additional_delta_mag','additional_formal_error_mag'];
    function quote(v) { return '"'+String(v??'').replaceAll('"','""')+'"'; }
    const rows=checkpoint.coverage.map(r=>{
      const a=checkpoint.alerts.find(v=>key(v)===key(r)), w=a||r.strongest_comparison, extra=external(key(r));
      return [r.target_id,r.band,checkpoint.as_of_utc,r.eligible_detections,r.comparisons,r.status,w?.baseline?.candid,w?.baseline?.utc,
        w?.trigger?.candid,w?.trigger?.utc,w?.delta_mag,w?.formal_error_mag,w?.rate_mag_per_day,a?.issued_utc,a?.deadline_utc,a?.direction,a?.followup?.candid,a?.followup?.utc,a?.followup_delta_mag,a?.reference_image?.status,extra?.source,extra?.status,extra?.witness?.candid,extra?.witness?.utc,extra?.delta_from_baseline_mag,extra?.formal_error_mag];
    });
    return [fields,...rows].map(r=>r.map(quote).join(',')).join('\r\n')+'\r\n';
  }
  function display() {
    const primary=checkpoint.coverage.find(r=>key(r)===selected);
    const original=checkpoint.alerts.find(r=>key(r)===selected);
    const extra=external(selected);
    const row=extra?{...primary,status:extra.status}:primary;
    const alert=extra?{...original,status:extra.status,followup:extra.witness,
      followup_delta_mag:extra.delta_from_baseline_mag,followup_formal_error_mag:extra.formal_error_mag,cross:true}:original;
    const witness=alert || row.strongest_comparison;
    el('signal-window').value=active.id;el('signal-date').value=checkpoint.as_of_utc;el('signal-choice').value=selected;
    el('decision-seal').textContent=statusText(row.status)+(extra?' · ALeRCE':' · Fink');
    const result=witness ? fill(t('measuredChange'),{delta:signed(witness.delta_mag),error:num(witness.formal_error_mag,6),days:num(witness.gap_days,3)}) : t('noPair');
    el('signal-outcome').textContent=result;
    let interpretation=t('next_'+row.status);
    if (witness && !alert) {
      const failed=Object.entries(witness.gates).filter(([_,passed])=>!passed).map(([gate])=>t('gate_'+gate));
      interpretation=fill(t('failedGates'),{gates:new Intl.ListFormat(locale(),{style:'long',type:'conjunction'}).format(failed)});
    } else if (alert?.followup) {
      interpretation=fill(t('laterDelta'),{delta:signed(alert.followup_delta_mag,4),error:num(alert.followup_formal_error_mag,4)})+' '+interpretation;
    } else if (alert) {
      interpretation+=' '+t('deadline')+' '+stamp(alert.deadline_utc)+' · 00:00 UTC.';
    }
    el('signal-next').textContent=interpretation;
    const ref=el('signal-reference');ref.hidden=!alert?.reference_image;
    ref.textContent=alert?.reference_image?fill(t('reference_'+alert.reference_image.status),{ids:alert.reference_image.rfids.filter(Boolean).join(' / ')}):'';
    if(alert?.broker_at_trigger?.rate_mag_per_day!=null) {
      ref.textContent+=' '+fill(t('brokerRate'),{broker:signed(alert.broker_at_trigger.rate_mag_per_day),own:signed(alert.rate_mag_per_day)});
    }
    const available=!!active.second_archive;
    el('archive-switch').hidden=!available;
    if(available) {
      el('compare-archive').setAttribute('aria-pressed',String(useSecond));
      el('compare-archive').textContent=t(useSecond?'useFink':'useAlerce');
      el('archive-reading').textContent=fill(t('originalStatus'),{status:statusText(primary.status)})+' '+
        (extra?fill(t('otherConfirmed'),{id:extra.witness.candid}):t(useSecond?'nothingYet':'secondClosed'));
      if(extra?.aperture) el('archive-reading').textContent+=' '+fill(t('apertureCheck'),{delta:signed(extra.aperture.delta_from_baseline_mag,4),error:num(extra.aperture.formal_error_mag,4)});
      if(extra?.forced_photometry) el('archive-reading').textContent+=' '+fill(t('forcedCheck'),{delta:signed(extra.forced_photometry.delta_mag,4),error:num(extra.forced_photometry.formal_error_mag,4)});
      if(extra?.witness.rfid!=null) ref.textContent+=' '+fill(t('laterReference'),{id:extra.witness.rfid});
      const link=el('al-source');
      link.hidden=!extra; if(extra) link.href=extras().source_url;
    }
    const paired=otherHistory();
    el('history-switch').hidden=!paired;
    if(paired) {
      const other=paired.days.find(s=>s.as_of_utc===checkpoint.as_of_utc).coverage.find(r=>key(r)===selected);
      el('history-reading').textContent=fill(t('parallelCondition'),{name:t('series_'+paired.id),state:statusText(other.status)});
      el('compare-history').textContent=t(active.id==='early_warm'?'useCold':'useWarm');
    }
    timeline(row,witness,alert);
    plate(row,witness,alert);
    const body=el('signal-coverage');body.replaceChildren();
    checkpoint.coverage.forEach(r=>{
      const tr=element('tr');tr.append(element('td',r.target_id),element('td',r.band),element('td',String(r.eligible_detections)),element('td',statusText(external(key(r))?.status||r.status)+(external(key(r))?' · ALeRCE':'')));
      body.append(tr);
    });
    const comparisons=checkpoint.coverage.reduce((n,r)=>n+r.comparisons,0);
    el('signal-total').textContent=fill(t('queueTotal'),{alerts:num(checkpoint.alerts.length),pairs:num(comparisons),bands:num(checkpoint.coverage.length)});
    const name=active.id+'-'+checkpoint.as_of_utc.slice(0,10)+(extras()?'-alerce':'');
    const receipt=extras()?{...checkpoint,second_archive:extras()}:checkpoint;
    setBlob('signal-download',JSON.stringify(receipt,null,2)+'\n','application/json','change-queue-'+name+'.json');
    setBlob('signal-csv',toCsv(),'text/csv;charset=utf-8','change-queue-'+name+'.csv');
    el('signal-step').textContent=t(checkpoint===head(active)?'rewind':'advance');
  }
  function render() {
    options('signal-window',series.map(s=>s.id),id=>windowLabel(series.find(s=>s.id===id)),active.id);
    options('signal-date',active.days.map(s=>s.as_of_utc),at=>stamp(at)+' · 00:00 UTC',checkpoint.as_of_utc);
    options('signal-choice',checkpoint.coverage.map(key),v=>v.replace('/',' · '),selected);
    display();
  }
  function otherHistory() {
    const id={early_warm:'early_cold',early_cold:'early_warm'}[active.id];
    return series.find(s=>s.id===id);
  }
  function setWindow(window) {
    if (window===otherHistory()) {
      const at=checkpoint.as_of_utc;
      active=window;checkpoint=active.days.find(s=>s.as_of_utc===at);
    } else choose(window);
    render();
  }
  el('signal-window').addEventListener('change',()=>setWindow(series.find(s=>s.id===el('signal-window').value)));
  el('compare-archive').addEventListener('click',()=>{useSecond=!useSecond;display();});
  el('compare-history').addEventListener('click',()=>setWindow(otherHistory()));
  el('signal-choice').addEventListener('change',()=>{selected=el('signal-choice').value;display();});
  el('signal-date').addEventListener('change',()=>{checkpoint=active.days.find(s=>s.as_of_utc===el('signal-date').value);display();});
  el('signal-step').addEventListener('click',()=>{
    const i=active.days.indexOf(checkpoint);
    const visible=s=>counter(s.coverage.find(r=>key(r)===selected))+'/'+(external(selected,s)?.witness.candid||'');
    const last=visible(checkpoint);
    checkpoint=i===active.days.length-1?active.days[0]:
      active.days.slice(i+1).find(s=>visible(s)!==last)||head(active);
    display();
  });
  matchMedia('(max-width: 540px)').addEventListener('change',display);
  return {render};
}
