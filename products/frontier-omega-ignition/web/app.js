"use strict";
const $ = id => document.getElementById(id);
const json = value => JSON.stringify(value, null, 2);
const authorityKeys = ["local_model", "assisted_model", "public_sources"];
const detailKeys = ["construction_spec", "resources", "time"];
const transient = new Set(["queued", "running"]);
let replay = false, providerLabel = "";
let current, examples = [], timer, dirty = false, busy = false, online = false;
let extraMission = {}, requestId, lastHandoff, lastTrial, generation = 0;

function elem(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function remember(id) {
  try { if (id) sessionStorage.setItem("ignition-run", id); else sessionStorage.removeItem("ignition-run"); } catch {}
}
function earlierRun() {try {return sessionStorage.getItem("ignition-run");} catch {return null;}}
function lineText(v) {return typeof v === "string" ? v : json(v);}
function message(text) { $("form-message").textContent = text || ""; }
function runNotice(text) { $("amend-note").textContent = text || ""; }
const apiPath = (id, action = "") => "/api/runs/" + encodeURIComponent(id) + action;

async function api(path, body) {
  const init = {cache: "no-store", credentials: "same-origin", redirect: "error"};
  if (body !== undefined) Object.assign(init, {method: "POST", headers: {
    "Content-Type": "application/json", "X-Ignition-Request": "1"
  }, body: JSON.stringify(body)});
  const r = await fetch(path, init);
  if (!r.headers.get("content-type")?.includes("application/json")) throw Error("The execution service did not return JSON.");
  const data = await r.json();
  if (!r.ok) throw Error(lineText(data.error || data.message || `Request failed (HTTP ${r.status})`));
  return data;
}
function parseField(id, array) {
  let value;
  try { value = JSON.parse($(id).value); }
  catch { throw Error("Enter valid JSON in " + id.replaceAll("_"," ") + "."); }
  if (array ? !Array.isArray(value) : !value || typeof value !== "object" || Array.isArray(value))
    throw Error(id.replaceAll("_"," ") + (array ? " must be an array." : " must be an object."));
  return value;
}
function readMission() {
  const mission = {...extraMission, purpose:$("purpose").value.trim(), beneficiary:$("beneficiary").value.trim(),
    requirements:$("requirements").value.split("\n").map(s=>s.trim()).filter(Boolean),
    authority:Object.fromEntries(authorityKeys.map(k=>[k,$(k).checked]))};
  for (const k of detailKeys) mission[k] = parseField(k, false);
  return {mission,sources:parseField("sources",true)};
}
function loadBrief(mission = {}, sources = []) {
  extraMission = {...mission};
  $("purpose").value = mission.purpose || "";
  $("beneficiary").value = mission.beneficiary || "";
  $("requirements").value = (mission.requirements || []).join("\n");
  for (const k of detailKeys) $(k).value = json(mission[k] || {});
  for (const k of authorityKeys) $(k).checked = mission.authority?.[k] === true;
  $("sources").value = json(sources);
}
function buttons() {
  $("snapshot").hidden = replay || !current || ["queued","running","awaiting_model","awaiting_contract"].includes(current.status) || dirty;
  $("close-replay").hidden = !replay;
  $("history").hidden = replay;
  $("mission").hidden = replay;
  if (replay) {
    for (const key of ["resume","review","handoff","actions"]) $(key).hidden=true;
    return;
  }
  $("fresh").hidden = !current;
  $("start").textContent = current ? "Submit amended mission →" : "Start investigation →";
  $("start").disabled = !online || busy || Boolean(current && !dirty);
  $("resume").hidden = !current || current.status !== "blocked" || dirty;
  $("review").hidden = !current?.proposed_contract || current.status !== "awaiting_contract" || dirty;
  $("handoff").hidden = !current?.handoff || current.status !== "awaiting_model" || dirty;
  $("actions").hidden = current?.status !== "verified" || dirty;
  for (const id of ["resume","respond","approve","try"]) $(id).disabled = busy;
}
function edited() {
  requestId = null;
  if (current) {
    dirty = true;
    runNotice("Edited brief. The record below belongs to the submitted revision. Submit the amendment to run fresh checks.");
    $("output").textContent = "";
  }
  buttons();
}
$("brief").addEventListener("input", edited);
$("example").addEventListener("change", () => {
  const selected = examples.find(x => x.id === $("example").value);
  loadBrief(selected?.mission, selected?.sources); edited();
});
function section(title) {
  const s = elem("section"); s.append(elem("h3",title)); $("results").append(s); return s;
}
function entry(host,title,body) {
  const a=elem("article",undefined,"entry"); a.append(elem("h4",title));
  if (body) a.append(elem("p",body));
  host.append(a); return a;
}
function detail(host,title,value) {
  const d=elem("details"); d.append(elem("summary",title),elem("pre",json(value))); host.append(d);
}
function urlLink(url) {
  try { const u = new URL(url); if (u.protocol !== "https:" || u.username || u.password) return null;
    const a=elem("a","Inspect primary source →"); a.href=u.href; a.rel="noreferrer noopener"; a.target="_blank"; return a;
  } catch {return null;}
}
function results(run) {
  $("results").replaceChildren();
  const r=run.research || {};
  if (run.error) entry($("results"),"Run obstruction",lineText(run.error));
  if (r.candidates?.length) {
    const s=section("Opportunities");
    for (const c of r.candidates) {
      const a=entry(s,c.title,c.outcome); detail(a,"Evidence, alternatives and next test",c);
    }
  }
  if (r.objections?.length || r.selected || r.decision) {
    const s=section("Challenge & selection");
    if (r.decision) entry(s,r.selected?.title || r.decision,r.decision_reason);
    for (const o of r.objections || []) {const a=entry(s,o.status || "Challenge",o.claim);detail(a,"Inspect witness",o);}
  }
  if (r.signals?.length || r.frontier) {
    const s=section("Frontier evidence");
    if (r.frontier) entry(s,`Crossing · ${r.frontier.status}`,r.frontier.reason);
    for (const sig of r.signals || []) {
      const a=entry(s,sig.title || sig.id,[sig.publisher,sig.published_at,sig.status].filter(Boolean).join(" · "));
      const link=urlLink(sig.url); if (link) a.append(link); detail(a,"Provenance and limitations",sig);
    }
  }
  if (r.mechanisms?.length) detail($("results"),"Mechanism decisions",r.mechanisms);
  if (run.contract) detail($("results"),"Frozen mission contract",run.contract);
  if (run.artifact) detail($("results"),"Constructed artifact",run.artifact);
  if (run.evaluation) {
    const s=section("Independent evaluation");
    const ev=run.evaluation;
    if (ev.status || ev.verdict) s.append(elem("p",lineText(ev.status || ev.verdict)));
    if (ev.comparison?.outcome) s.append(elem("p","Conventional comparison · " + ev.comparison.outcome.replaceAll("_"," ")));
    detail(s,"Comparison and check results",ev);
  }
}
function show(run, open = false) {
  if (!run?.id) throw Error("The service returned an incomplete run record.");
  if (current && current.id !== run.id) {dirty=false;lastHandoff=null;lastTrial=null;}
  current=run; if (!replay) remember(run.id); $("record").hidden=false; $("empty").hidden=true;
  $("record-title").textContent=run.mission?.purpose || "Execution & evidence";
  $("run-status").textContent=[run.status,run.stage].filter(Boolean).join(" · ").replaceAll("_"," ");
  if (replay) $("run-status").textContent="RECORDED REPLAY · " + $("run-status").textContent;
  $("run-id").textContent=`Revision ${run.version} · ${run.id}`;
  $("raw").textContent=json(run);
  $("events").replaceChildren(...(run.events||[]).map(ev=>{
    const li=elem("li");li.append(elem("strong",ev.stage),elem("p",ev.message),elem("small",ev.at));return li;
  }));
  results(run);
  $("proposal").textContent=json(run.proposed_contract || {});
  if (lastHandoff !== run.handoff?.sha256) { $("response").value=""; lastHandoff=run.handoff?.sha256; }
  $("prompt").textContent=lineText(run.handoff?.prompt || "");
  const trialKey=run.id + "/" + run.version + "/" + (run.contract?.sha256 || run.contract_sha256 || "pending");
  if (lastTrial !== trialKey) {
    $("trial").value=json(run.contract?.spec?.cases?.find(c=>Object.hasOwn(c,"expected"))?.input ?? run.mission?.construction_spec?.cases?.find(c=>Object.hasOwn(c,"expected"))?.input ?? {});
    $("output").textContent=""; lastTrial=trialKey;
  }
  $("bundle").href=apiPath(run.id,"/bundle")+"?version="+encodeURIComponent(run.version);
  buttons();
  if (open) $("investigation").scrollIntoView({block:"start"});
  clearTimeout(timer);
  if (!replay && transient.has(run.status)) timer=setTimeout(()=>refresh(run.id,generation),950);
}
async function refresh(id,token) {
  try {const run=await api(apiPath(id)); if(token===generation) show(run);}
  catch(e){if(token!==generation)return;runNotice("Connection interrupted. Retrying. " + e.message);
    timer=setTimeout(()=>refresh(id,token),3500);}
}
async function submit(ev) {
  ev.preventDefault(); if (replay || busy || !online) return;
  try {
    const payload=readMission(); if (!payload.mission.purpose) throw Error("Describe the mission first.");
    requestId ||= crypto.randomUUID();
    const path=current?apiPath(current.id,"/amend"):"/api/runs";
    if (current) payload.version=current.version;
    busy=true; clearTimeout(timer); const token=++generation;buttons(); message("Saving mission…");
    const res=await api(path,{...payload,request_id:requestId});
    const run=res.mission ? res : await api(apiPath(res.id));
    if(token!==generation)return; dirty=false;runNotice("");message("");show(run,true);
  } catch(e){message(e.message);if(current && transient.has(current.status)) timer=setTimeout(()=>refresh(current.id,generation),950);}
  finally {busy=false;buttons();}
}
$("brief").addEventListener("submit",submit);
$("fresh").addEventListener("click",()=>{
  ++generation;clearTimeout(timer);current=null;remember(null);dirty=false; requestId=null;lastHandoff=null;lastTrial=null;
  $("example").value="";loadBrief();$("record").hidden=true;$("empty").hidden=false;$("record-title").textContent="Execution & evidence";runNotice("");message("");buttons();$("purpose").focus();
});
async function action(name,data) {
  if (replay || busy || dirty || !current) return;
  const id=current.id, version=current.version, token=++generation;
  busy=true;clearTimeout(timer);buttons();runNotice("");
  try {
    const result=await api(apiPath(id,"/"+name),{...data,version});
    if(token!==generation || dirty)return;
    if (name==="try") $("output").textContent=json(result);
    else {const run=result.mission ? result : await api(apiPath(id)); if(token===generation)show(run);}
  } catch(e){if(token===generation){runNotice(e.message); if(name==="try") $("output").textContent="Input refused. " + e.message;}}
  finally {busy=false;buttons();}
}
$("resume").addEventListener("click",()=>action("resume",{}));
$("approve").addEventListener("click",()=>action("approve",{contract_sha256:current.proposed_contract_sha256 || current.contract_sha256 || current.proposed_contract?.sha256}));
$("respond").addEventListener("click",()=>{
  try { const response=parseField("response",false); action("respond",{sha256:current.handoff.sha256,response}); } catch(e){runNotice(e.message);}
});
$("copy-prompt").addEventListener("click",async()=>{
  try {await navigator.clipboard.writeText($("prompt").textContent); runNotice("Prompt copied.");}
  catch { $("prompt").parentElement.open=true; const range=document.createRange();range.selectNodeContents($("prompt"));getSelection().removeAllRanges();getSelection().addRange(range);runNotice("Prompt selected. Use your browser’s copy command."); }
});
$("try").addEventListener("click",()=>{
  try {const input=JSON.parse($("trial").value); action("try",{input});}
  catch { $("output").textContent="Enter a valid JSON input."; }
});
$("trial").addEventListener("input",()=>{$("output").textContent="";});
$("history").addEventListener("toggle",async()=>{
  if (replay || !$("history").open || !current) return;
  const id=current.id, token=generation;
  try {const h=await api(apiPath(id,"/history"));if(token===generation)$("versions").textContent=json(h);}
  catch(e){if(token===generation)$("versions").textContent=e.message;}
});
function resetRecord() {
  current=null; dirty=false; requestId=null; lastHandoff=null; lastTrial=null;
  $("record").hidden=true; $("empty").hidden=false; $("record-title").textContent="Execution & evidence";
  $("results").replaceChildren(); $("raw").textContent=""; $("versions").textContent=""; $("response").value="";
  runNotice(""); message(""); loadBrief(); buttons();
}
$("replay-file").addEventListener("change",async()=>{
  const file=$("replay-file").files[0]; if (!file) return;
  const token=++generation;clearTimeout(timer);
  try {
    if (file.size>4*1024*1024) throw Error("This viewer accepts run files up to 4 MiB.");
    const data=JSON.parse(await file.text());
    if(!data || typeof data!=="object" || typeof data.id!=="string" || typeof data.status!=="string" ||
       !Number.isSafeInteger(data.version) || typeof data.mission?.purpose!=="string" ||
       !Array.isArray(data.events) || data.events.some(e=>!e || typeof e!=="object"))
      throw Error("Choose a saved IGNITION run record.");
    const r=data.research || {};
    for (const k of ["signals","candidates","objections","mechanisms"])
      if (r[k] && (!Array.isArray(r[k]) || r[k].some(o=>!o || typeof o!=="object"))) throw Error("Invalid research records.");
    if (token!==generation) return;
    replay=true;dirty=false;runNotice("");$("mode").textContent="Recorded replay · local file";
    $("replay-message").textContent="Opened "+file.name+".";
    // Never import a pending request as an actionable handoff.
    show({...data,handoff:null},true);
  } catch(e){
    $("replay-message").textContent=e.message;
    if (!replay && current && transient.has(current.status)) refresh(current.id,token);
  }
  $("replay-file").value="";
});
$("close-replay").addEventListener("click",async()=>{
  const token=++generation;replay=false;resetRecord();$("mode").textContent=providerLabel || "Execution service unavailable";
  $("replay-message").textContent="";const id=earlierRun();
  if(id && online) try {const run=await api(apiPath(id));if (token===generation) {loadBrief(run.mission,run.sources);show(run);}} catch(e){message(e.message);}
});
$("snapshot").addEventListener("click",()=>{
  if (replay || dirty || !current || $("snapshot").hidden) return;
  const url=URL.createObjectURL(new Blob([json({...current,handoff:null})+"\n"],{type:"application/json"}));
  const a=elem("a");a.href=url;a.download="ignition-"+current.id+"-v"+current.version+".json";
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
async function init() {
  try {
    if(location.protocol==="file:") throw Error("Open a saved record, or start the loopback service to run an investigation.");
    const status=await api("/api/status");online=true;
    const modeLabels={manual:"Operator-assisted model execution",local:"Live local model configured",unavailable:"Model unavailable"};
    providerLabel=[modeLabels[status.mode] || status.mode || "Execution service",status.provider?.provider,status.provider?.model].filter(Boolean).join(" · ");
    if(!replay) $("mode").textContent=providerLabel;
    const data=await api("/api/examples");examples=data.examples || [];
    for(const x of examples){const opt=elem("option",x.title || x.id); opt.value=x.id; $("example").append(opt);}
    $("presets").hidden=!examples.length;
    const restored=earlierRun();
    if(restored && !replay) {try {const r=await api(apiPath(restored));loadBrief(r.mission,r.sources || []);show(r);}
      catch(e){remember(null);message("Previous run could not be reopened. " + e.message);}}
  } catch(e){if(!online)$("mode").textContent="Execution service unavailable";message(e.message);}
  buttons();
}
init();
