/* FRONTIER Ω: purpose-bound handoff. Authored finite construction, not live AI. */
(function () {
  'use strict';
  const C = window.FRONTIER_CONSTRUCTION;
  const W = window.FRONTIER_WORLD_LAB;
  const $ = id => document.getElementById(id);
  const state = {current: null, historical: []};
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const json = x => JSON.stringify(C.serial(x), null, 2);
  function save(text, name, type) {
    const url = URL.createObjectURL(new Blob([text], {type}));
    const a = document.createElement('a'); a.href = url; a.download = name; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function contract() {
    const mission = $('ignition-purpose').value.trim();
    const name = $('ignition-name').value.trim();
    if (!mission || mission.length > 4000) throw Error('Describe the purpose in 1–4,000 characters.');
    if (!name || name.length > 120) throw Error('Name the capability in 1–120 characters.');
    const raw = $('ignition-domain').value.split(',').map(x => x.trim());
    if (raw.some(x => !/^[-+]?\d+$/.test(x))) throw Error('Use distinct comma-separated integers; empty fields are not allowed.');
    const values = C.domain(raw.map(Number));
    const scope = $('ignition-scope').value;
    if (!['upper','interval'].includes(scope)) throw Error('Unsupported question family.');
    return {mission, name, values, scope};
  }
  function invalidate() {
    if (state.current) {
      state.historical.push({contract: state.current.contract, status: 'historical-not-current', check: state.current.check});
      // A local UI history, not a lossless evidence archive or financial ledger.
      if (state.historical.length > 20) state.historical.shift();
    }
    state.current = null;
    $('ignition-export').disabled = $('ignition-record').disabled = true;
    $('ignition-status').textContent = 'Contract changed. Rebuild before exporting a current capability.';
    $('ignition-result').textContent = 'No result is accepted for this edited contract.';
  }
  function run() {
    invalidate();
    try {
      const c = contract();
      const parent = C.compile(c.values, 'upper');
      const artifact = c.scope === 'upper' ? parent : C.compile(c.values, 'interval');
      const check = C.verify(artifact);
      if (!check.pass) throw Error(check.error);
      const witness = C.collide(c.values, row => (row[0]+row[1])/2, C.queriesOf(c.values, 'upper'));
      const successorWitness = c.scope === 'interval' ? C.collide(c.values, row => Math.max(...row), artifact.queries) : null;
      const altered = C.serial(artifact); altered.decoders[0][0] = 1 - altered.decoders[0][0];
      const tamper = C.verify(altered);
      if (tamper.pass) throw Error('The deliberately corrupted decoder passed. Do not export.');
      state.current = {
        schema: 'frontier/ignition-capability-v1', contract: c, artifact, check,
        parent_check: C.verify(parent), witness, successor_witness: successorWitness,
        negative_control: {rejected: !tamper.pass, reason: tamper.error},
        selected_research_lead: W.S.selected ? W.brief() : null,
        source_observed_on: '2026-11-17',
        comparison: 'Direct maximum or minimum/maximum gives identical answers. No superiority claim.',
        construction: 'Author-supplied answer-signature compiler; parameters and declared purpose are user-supplied.',
        authority: [], model_calls: 0, commercial_acceptance: false,
        frontier_crossing: 'not-established',
        caveat: 'This is a bounded decision instrument, not implementation of the whole business ambition. The prose purpose is recorded, not semantically verified.'
      };
      $('ignition-result').innerHTML = `<strong>${esc(c.name)}</strong><div class="ignition-metrics"><span><b>${check.labels}</b> constructed labels</span><span><b>${check.checks}</b> exact checks passed</span><span><b>REJECTED</b> corrupted decoder</span></div><p>${witness ? 'A real mean-collision witness was found in your declared domain.' : 'No mean-collision witness exists in this domain. No defect is invented.'} ${successorWitness ? 'The upper-bound representation fails the new interval purpose; a new representation was constructed.' : ''}</p><p class="micro">Ordinary direct methods tie. Verification covers this finite question family—not the truth of your business assumptions or the meaning of the prose purpose.</p>`;
      $('ignition-status').textContent = 'Constructed and checked. Export an executable tool, then try new records inside its declared domain.';
      $('ignition-export').disabled = $('ignition-record').disabled = false;
      return state.current;
    } catch (e) {
      $('ignition-status').textContent = 'NOT CONSTRUCTED · ' + e.message;
      return null;
    }
  }
  function current() {
    if (!state.current || JSON.stringify(contract()) !== JSON.stringify(state.current.contract)) {
      invalidate(); throw Error('The contract is no longer current. Rebuild first.');
    }
    const v = C.verify(state.current.artifact);
    if (!v.pass) throw Error('Current artifact failed revalidation: ' + v.error);
    return state.current;
  }
  function instrumentHTML(record) {
    if (!record || !C.verify(record.artifact).pass) throw Error('A checked artifact is required.');
    const c = record.contract;
    let html = window.FRONTIER_STUDIO.instrumentHTML(record.artifact);
    const intro = `<section id="purpose"><h2>${esc(c.name)}</h2><p>${esc(c.mission)}</p><p><strong>Executable contract:</strong> two original integer readings from {${c.values.join(', ')}}, evaluated against the selected ${c.scope === 'upper' ? 'upper-bound' : 'interval'} questions.</p><small>Recorded prose purpose is not independently validated. No model discovery, commercial acceptance, external authority or new frontier crossing is implied.</small></section>`;
    html = html.replace('<section>', intro + '<section>');
    const batch = '<section id="batch"><h2>Try a batch of your own readings</h2><p>One pair per line, separated by a comma. Every row must be inside the declared domain. The question selected above applies to every row. Invalid data rejects the entire batch.</p><textarea id="batch-rows" rows="5" aria-label="Pairs of readings" style="width:100%;box-sizing:border-box;background:#24152f;color:#fff;padding:12px">'+c.values[0]+','+c.values[c.values.length-1]+'\n'+c.values[0]+','+c.values[0]+'</textarea><button id="batch-run">Evaluate this batch</button><output id="batch-result" aria-live="polite"></output><pre id="batch-detail"></pre></section>';
    const script = `
(function(){'use strict';const rows=document.getElementById('batch-rows'),out=document.getElementById('batch-result'),detail=document.getElementById('batch-detail');function clear(){out.textContent='Inputs changed — evaluate again.';detail.textContent='No current batch acceptance.';}for(const id of ['batch-rows','query'])document.getElementById(id).addEventListener('input',clear);document.getElementById('batch-run').addEventListener('click',()=>{try{if(rows.value.length>200000)throw Error('Batch exceeds this browser tool’s 200,000-character input limit. Split the batch; no impossibility claim.');const lines=rows.value.trim().split(/\\r?\\n/);if(!rows.value.trim())throw Error('Provide at least one pair.');const q=SPEC.queries[Number(document.getElementById('query').value)];if(!q)throw Error('Unsupported question.');const results=lines.map((line,i)=>{const p=line.split(',').map(s=>s.trim());if(p.length!==2||p.some(s=>!/^[-+]?\\d+$/.test(s)))throw Error('Row '+(i+1)+': expected exactly two integers.');const r=p.map(Number);if(r.some(v=>!Number.isSafeInteger(v)||!SPEC.values.includes(v)))throw Error('Row '+(i+1)+': outside the declared domain.');const e=SPEC.encoder.find(e=>e.input[0]===r[0]&&e.input[1]===r[1]);if(!e)throw Error('Missing encoded row.');const answer=SPEC.decoders[e.label][SPEC.queries.indexOf(q)]===1;const direct=r.every(v=>v<=q.hi&&(q.kind==='upper'||v>=q.lo));if(answer!==direct)throw Error('Decoder/reference disagreement.');return{row:i+1,input:r,condition_satisfied:answer,raw_input_check:true};});out.textContent=results.length+' records checked · '+results.filter(r=>r.condition_satisfied).length+' satisfy the selected condition';detail.textContent=JSON.stringify(results,null,2);}catch(e){out.textContent='BATCH REFUSED · '+e.message;detail.textContent='No partial batch acceptance.';}});})();`;
    return html.replace('<script>const SPEC=', batch+'<script>const SPEC=').replace('</body>', '<script>'+script+'<\/script></body>');
  }
  function exportCurrent(kind) {
    try { const r = current(); save(kind === 'html' ? instrumentHTML(r) : json(r), kind === 'html' ? 'FRONTIER_OMEGA_MY_CAPABILITY.html' : 'FRONTIER_OMEGA_MY_CAPABILITY.json', kind === 'html' ? 'text/html' : 'application/json'); }
    catch(e) { $('ignition-status').textContent = 'EXPORT REFUSED · '+e.message; }
  }
  for (const id of ['ignition-purpose','ignition-name','ignition-domain','ignition-scope']) $(id).addEventListener('input',invalidate);
  $('ignition-run').addEventListener('click',run);
  $('ignition-export').addEventListener('click',()=>exportCurrent('html'));
  $('ignition-record').addEventListener('click',()=>exportCurrent('json'));
  const carry = document.createElement('button'); carry.id='ignition-carry';carry.className='btn primary';carry.type='button';carry.textContent='Build a first decision instrument →';
  $('panel-4').append(carry);
  carry.addEventListener('click',()=>{
    invalidate(); $('ignition-purpose').value=W.S.mission;
    $('ignition-status').textContent='Ambition carried forward. Define the measurable contract below; this finite instrument does not build the entire proposed business.';
    $('ignition').scrollIntoView({behavior:'smooth',block:'start'});
  });
  // Editing a selected ambition invalidates its dossier rather than preserving stale approval.
  for(const id of ['ambition','sector','value','constraints']) $(id).addEventListener('input',()=>{W.S.mission='';W.S.selected=null;W.S.ranked=[];});
  document.querySelectorAll('[data-sample]').forEach(b=>b.addEventListener('click',()=>{W.S.mission='';W.S.selected=null;W.S.ranked=[];}));
  // Preserve a single session export, including only current purpose-bound evidence.
  $('download-session').addEventListener('click',e=>{
    e.stopImmediatePropagation();
    let accepted=null;try{accepted=state.current?current():null;}catch(_){}
    save(json({schema:'frontier/ignition-session-v1',user_mission:W.S.mission||null,selected_opportunity:W.S.selected?W.brief():null,construction_studio:{parent:window.FRONTIER_STUDIO.state.parent,successor:window.FRONTIER_STUDIO.state.child,measurement:window.FRONTIER_STUDIO.state.measurement},ignition:accepted,historical_contracts:state.historical,causal_study:W.S.causal,market_study:W.S.market,construction_study:W.S.builder,strategy_study:W.S.strategy||null,authority:[],model_calls:0,commercial_acceptance:false,limits:['No live model inference','No verified new 35-day economic crossing','No real customer commitments or revenue','Public mathematical demonstrations only; not validation of commercial hypotheses']}),'FRONTIER_OMEGA_RESEARCH_SESSION.json','application/json');
  },true);
  window.FRONTIER_IGNITION={state,contract,run,current,instrumentHTML};
})();
