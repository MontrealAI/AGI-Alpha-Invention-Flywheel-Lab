"use strict";
// BEGIN SHARED READ-ONLY EVIDENCE VIEW
const $ = id => document.getElementById(id);
const json = value => JSON.stringify(value, null, 2);
function lineText(v) {return typeof v === "string" ? v : json(v);}
function elem(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
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
    if ($("public-preview-data")) return elem("code",u.href);
    const a=elem("a","Inspect primary source →"); a.href=u.href; a.rel="noreferrer noopener"; a.target="_blank"; return a;
  } catch {return null;}
}
function commercialEvidence(e) {
  if(!e || typeof e!=="object") return;
  const s=section("Commercial evidence"), observed=elem("dl");
  for (const [key,label] of [["verified_demand","Verified demand"],["booked_revenue","Booked revenue"],["collected_revenue","Collected revenue"]]) {
    if(Object.hasOwn(e,key)) observed.append(elem("dt",label),elem("dd",e[key]===null?"Unmeasured":lineText(e[key])));
  }
  if(observed.childElementCount) s.append(observed);
  if(e.usage) {
    const terms=[];
    for (const [key,label] of [["recorded_application_model_calls","application model calls"],["assisted_exchanges","operator-assisted exchanges"]]) {
      if(Number.isSafeInteger(e.usage[key])) terms.push(e.usage[key]+" "+label);
    }
    if(terms.length) s.append(elem("p","Provider receipts · "+terms.join(" · "),"muted"));
  }
  if(e.scenario) {
    const caseData=e.scenario, scope=caseData.scope || {};
    s.append(elem("h4","Operator-supplied scenario"));
    const unit=[scope.currency,scope.unit,scope.horizon].filter(Boolean).join(" · ");
    if(unit) s.append(elem("small",unit));
    const values=elem("dl");
    for(const [key,label] of [["projected_gross_revenue","Projected revenue"],["modeled_total_economic_cost","Modeled total cost"],["modeled_economic_contribution","Modeled contribution"]]) {
      const value=caseData[key];
      if(value && value.low!==undefined && value.high!==undefined) {
        const range=value.low===value.high?value.low:value.low+" – "+value.high;
        values.append(elem("dt",label),elem("dd",[range,scope.currency].filter(x=>x!==undefined).join(" ")));
      }
    }
    if(values.childElementCount) s.append(values);
    if(caseData.unpriced_categories?.length) s.append(elem("p",caseData.unpriced_categories.length+(caseData.unpriced_categories.length===1?" cost category has":" cost categories have")+" no supplied estimate.","muted"));
    detail(s,"Scenario assumptions and participant outside options",{scenario:caseData,operator_evidence:e.operator_evidence,participants:e.participants});
  }
  if(e.error) s.append(elem("p",lineText(e.error),"notice"));
}
function results(run) {
  $("results").replaceChildren();
  const r=run.research || {};
  if (run.error) entry($("results"),"Run obstruction",lineText(run.error));
  if (Array.isArray(run.source_result?.failures) && run.source_result.failures.length) {
    detail($("results"),"Source retrieval failures",run.source_result.failures);
  }
  if (r.candidates?.length) {
    const s=section("Opportunities");
    for (const c of r.candidates) {
      const a=entry(s,c.title,c.outcome);
      if (c.standing) a.append(elem("small",[c.id,c.standing].filter(Boolean).join(" · ")));
      const d=elem("details"); d.append(elem("summary","Evidence, alternatives and next test"));
      const grid=elem("dl");
      for (const [label,value] of [["Reported change",c.change],["Obstruction",c.obstruction],
          ["Construction",c.route],["Strong alternative",c.alternative],["Economic hypothesis",c.value],["Decisive test",c.test]]) {
        if (value) grid.append(elem("dt",label),elem("dd",value));
      }
      d.append(grid);a.append(d);
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
    if (Array.isArray(ev.cases) && ev.cases.every(c=>c && typeof c==="object")) {
      const table=elem("table");const head=elem("tr");
      for (const name of ["Check","Artifact","Comparator"]) {const th=elem("th",name);th.scope="col";head.append(th);}
      const thead=elem("thead"); thead.append(head);table.append(thead);
      const tbody=elem("tbody"); const outcome=v=>v===true?"Pass":v===false?"Fail":"Unavailable";
      for (const c of ev.cases) {
        const row=elem("tr"),th=elem("th",c.name);th.scope="row";
        row.append(th,elem("td",outcome(c.candidate_pass)),elem("td",outcome(c.reference_pass)));tbody.append(row);
      }
      table.append(tbody);s.append(table);
    }
    if (ev.scope) s.append(elem("p",ev.scope,"muted"));
    detail(s,"Full evaluation receipt",ev);
  }
  commercialEvidence(run.economics);
}
// END SHARED READ-ONLY EVIDENCE VIEW
const authorityKeys = ["local_model", "assisted_model", "public_sources", "allow_program_reuse"];
const detailKeys = ["construction_spec", "resources", "time"];
const transient = new Set(["queued", "running"]);
let replay = false, providerLabel = "", liveView=null;
let current, examples = [], timer, dirty = false, busy = false, online = false;
let renderedAttempts = null, renderedStudy = null, renderedChoice = null;
let extraMission = {}, requestId, lastHandoff, lastTrial, lastProposal, generation = 0, editNumber = 0;

function remember(id) {
  try { if (id) sessionStorage.setItem("ignition-run", id); else sessionStorage.removeItem("ignition-run"); } catch {}
}
function earlierRun() {try {return sessionStorage.getItem("ignition-run");} catch {return null;}}
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
  if (!r.ok) {
    const error=Error(lineText(data.error || data.message || `Request failed (HTTP ${r.status})`));
    error.status=r.status; throw error;
  }
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
const routeDescriptions = {
  adaptive: "A specified mission can compile locally, request an authorized model, or ask you to resolve competing mappings. An open ambition can enter frontier research.",
  direct: "Attempt the supplied construction specification. If the checker cannot accept it, the run can request clarification.",
  research: "Investigate opportunities and challenge the candidates before choosing whether to build."
};
function updateStrategyHelp() {
  $("strategy-help").textContent = routeDescriptions[$("strategy").value];
  $("fallback-option").hidden = $("strategy").value === "direct";
}
$("strategy").addEventListener("change", updateStrategyHelp);

function wholeNumber(id) {
  const field = $(id);
  if (field.value.trim() === "" || !Number.isSafeInteger(field.valueAsNumber) || !field.checkValidity()) {
    throw Error("Enter a valid whole number for " + document.querySelector('label[for="' + id + '"]').textContent + ".");
  }
  return field.valueAsNumber;
}
function loadPairing(params) {
  $("pairing-controls").hidden = !params;
  $("pairing-controls").disabled = !params;
  if (!params) return;
  $("pairing-budget").value = params.budget;
  $("pairing-width").value = String(params.width);
  $("pairing-percent").value = params.min_percent;
  $("pairing-model").value = params.model || "";
  $("pairing-repository").value = params.repository || "";
}
const endpointFields = {
  model: "ep-model", dataset: "ep-dataset", max_ttft_p90_ms: "ep-ttft", min_tps_per_user: "ep-rate",
  min_concurrency: "ep-concurrency", load_mode: "ep-load", rate_metric: "ep-metric",
  require_point_accuracy: "ep-accuracy", require_price: "ep-price", require_access: "ep-access"
};
function loadEndpoint(params) {
  const controls = $("endpoint-controls");
  controls.hidden = controls.disabled = !params;
  if (!params) return;
  for (const [key, id] of Object.entries(endpointFields)) {
    const field = $(id);
    if (field.type === "checkbox") field.checked = params[key] === true;
    else field.value = params[key] ?? "";
  }
}
function readEndpoint() {
  const contract = {...extraMission.resources?.endpoint_lab};
  for (const [key, id] of Object.entries(endpointFields)) {
    const field = $(id);
    if (field.type === "checkbox") contract[key] = field.checked;
    else if (key === "min_concurrency") contract[key] = wholeNumber(id);
    else contract[key] = field.value.trim();
  }
  for (const key of ["max_ttft_p90_ms", "min_tps_per_user"]) {
    if (!/^[0-9]+(?:\.[0-9]+)?$/.test(contract[key]) || !/[1-9]/.test(contract[key])) {
      throw Error("Enter a positive decimal for " + document.querySelector('label[for="' + endpointFields[key] + '"]').textContent + ".");
    }
  }
  return contract;
}
function readMission() {
  const mission = {...extraMission, purpose:$("purpose").value.trim(), beneficiary:$("beneficiary").value.trim(),
    requirements:$("requirements").value.split("\n").map(s=>s.trim()).filter(Boolean),
    authority:Object.fromEntries(authorityKeys.map(k=>[k,$(k).checked]))};
  for (const k of detailKeys) mission[k] = parseField(k, false);
  if (!$("endpoint-controls").hidden) {
    if (Object.hasOwn(mission.resources, "endpoint_lab")) throw Error("Edit the interactive inference requirements above and remove endpoint_lab from Other resources.");
    mission.resources.endpoint_lab = readEndpoint();
  }
  if (!$("pairing-controls").hidden) {
    if (Object.hasOwn(mission.resources, "pairing_lab")) throw Error("Use the coding-stack pilot criteria above to change the public study.");
    mission.resources.pairing_lab = {
      budget: wholeNumber("pairing-budget"), width: Number($("pairing-width").value),
      min_percent: wholeNumber("pairing-percent"), model: $("pairing-model").value || null,
      repository: $("pairing-repository").value.trim() || null
    };
  }
  if (Object.hasOwn(mission.resources, "execution_strategy") || Object.hasOwn(mission.resources, "direct_method") || Object.hasOwn(mission.resources, "direct_after_research")) {
    throw Error("Use the route controls above. Remove their execution_strategy, direct_method or direct_after_research keys from Other resources.");
  }
  mission.resources.execution_strategy = $("strategy").value;
  if ($("direct-method").value) mission.resources.direct_method = $("direct-method").value;
  if (!$("fallback-option").hidden && $("direct-after").checked) mission.resources.direct_after_research = true;
  return {mission,sources:parseField("sources",true)};
}
function loadBrief(mission = {}, sources = [], useSavedPermissions = true) {
  extraMission = {...mission};
  $("purpose").value = mission.purpose || "";
  $("beneficiary").value = mission.beneficiary || "";
  $("requirements").value = (mission.requirements || []).join("\n");
  for (const k of detailKeys) $(k).value = json(mission[k] || {});
  const {execution_strategy: strategy, direct_method: method, direct_after_research: fallback, pairing_lab: pairing, endpoint_lab: endpoint, ...resources} = mission.resources || {};
  loadEndpoint(endpoint);
  loadPairing(pairing);
  $("resources").value = json(resources);
  $("strategy").value = Object.hasOwn(routeDescriptions, strategy) ? strategy : "adaptive";
  $("direct-method").value = ["model", "specialist", "operator_choice", "model_choice"].includes(method) ? method : "";
  $("direct-after").checked = fallback === true;
  updateStrategyHelp();
  for (const k of authorityKeys) $(k).checked = useSavedPermissions && mission.authority?.[k] === true;
  $("sources").value = json(sources);
}
function buttons() {
  $("snapshot").hidden = replay || !current || ["queued","running","awaiting_model","awaiting_contract","awaiting_choice"].includes(current.status) || dirty;
  $("close-replay").hidden = !replay;
  $("recorded-bundle").hidden = true;
  $("history").hidden = replay;
  $("mission").hidden = replay;
  if (replay) {
    $("bundle").removeAttribute("href");
    for (const key of ["resume","review","handoff","mapping-choice","actions"]) $(key).hidden=true;
    return;
  }
  $("fresh").hidden = !current;
  $("start").textContent = current ? "Submit amended mission →" : "Start mission →";
  $("start").disabled = !online || busy || Boolean(current && !dirty);
  $("resume").hidden = !current || current.status !== "blocked" || dirty;
  $("review").hidden = !current?.proposed_contract || current.status !== "awaiting_contract" || dirty;
  $("mapping-choice").hidden = !current?.mapping_choice || current.status !== "awaiting_choice" || dirty;
  $("choice-options").disabled = busy || $("mapping-choice").hidden;
  $("apply-choice").disabled = busy || $("mapping-choice").hidden || !$("choice-options").querySelector("input:checked");
  $("abstain-choice").disabled = busy || $("mapping-choice").hidden;
  $("handoff").hidden = !current?.handoff || current.status !== "awaiting_model" || dirty;
  $("actions").hidden = current?.status !== "verified" || dirty;
  if ($("actions").hidden) $("bundle").removeAttribute("href");
  for (const id of ["resume","respond","approve","try"]) $(id).disabled = busy;
}
function edited() {
  editNumber++;
  $("run-status").dataset.tone = "";
  requestId = null;
  if (current) {
    dirty = true;
    $("run-status").textContent="Historical record · " + current.status.replaceAll("_"," ");
    runNotice("Edited brief. The record below belongs to the submitted revision. Submit the amendment to run fresh checks.");
    $("output").textContent = "";
  }
  buttons();
}
$("brief").addEventListener("input", edited);
$("example").addEventListener("change", () => {
  const selected = examples.find(x => x.id === $("example").value);
  loadBrief(selected?.mission, selected?.sources, false); edited();
});
const routeNames = {direct: "Direct ignition", research: "Frontier investigation", clarify: "Clarification needed"};
function stageLabel(stage) {
  const text = String(stage || "").replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
function studyView(study) {
  $("opportunity-study").hidden = !study;
  if (!study) return;
  const identity = json(study);
  if (identity === renderedStudy) return;
  renderedStudy = identity;
  const candidates = Array.isArray(study.candidates) ? study.candidates : [];
  const challengers = Array.isArray(study.challengers) ? study.challengers : [];
  const sources = new Map((Array.isArray(study.sources) ? study.sources : []).map(s => [s.id, s]));
  const selected = study.decision?.candidate_id;
  const winner = [...candidates, ...challengers].find(c => c.id === selected);
  $("study-choice").textContent = winner?.title || stageLabel(study.decision?.status || "Opportunity study");
  $("study-basis").textContent = study.decision?.reason || "";
  const host = $("study-candidates");
  host.replaceChildren();
  for (const [group, label] of [[candidates, "Opportunity"], [challengers, "Challenger"]]) {
    for (const candidate of group) {
      const item = elem("details");
      const chosen = selected === candidate.id;
      item.open = chosen;
      item.append(elem("summary", label + (chosen ? " selected · " : " · ") + candidate.title));
      const grid = elem("dl");
      for (const [key, text] of [["value", "Potential value"], ["method", "Construction"],
        ["tradeoff", "Limitation"], ["test", "Decisive test"]]) {
        if (candidate[key]) grid.append(elem("dt", text), elem("dd", candidate[key]));
      }
      item.append(grid);
      const sourceList = elem("ul");
      for (const id of candidate.source_ids || []) {
        const source = sources.get(id), li = elem("li");
        const link = source && urlLink(source.url);
        if (link) {
          link.textContent = source.title || id;
          li.append(link, elem("small", source.published ? " · " + source.published : ""));
        } else li.textContent = "Source record · " + id;
        sourceList.append(li);
      }
      if (sourceList.childElementCount) item.append(sourceList);
      host.append(item);
    }
  }
}
function pairingView(run) {
  const study = run.pairing_result;
  const decision = study || run.endpoint_result || run.followup_result || run.change_result || run.evidence_result;
  $("pairing-result").hidden = !study;
  $("pilot-next").hidden = study?.qualifies !== true;
  $("trial-label").hidden = Boolean(decision);
  $("trial").hidden = Boolean(decision);
  $("try").textContent = decision ? "Reproduce decision" : "Run input";
  $("actions-title").textContent = decision ? "Take the decision with you" : "Operate the artifact";
  $("evidence-result").hidden = !run.evidence_result;
  if (run.evidence_result) {
    const receipt = run.evidence_result;
    const labels = {
      retain_shadow_review: ["Retain the shadow review", "Maintenir l’examen en parallèle"],
      withdraw_shadow_review: ["Withdraw the shadow review", "Retirer le dossier de la file parallèle"],
      qualify_A_next: ["Qualify configuration A next", "Évaluer ensuite la configuration A"],
      qualify_B_next: ["Qualify configuration B next", "Évaluer ensuite la configuration B"],
      defer_tied_qualification: ["Defer the tied choice", "Reporter le choix entre les configurations ex æquo"],
      deliver_persistence_measurement: ["Deliver the persistence measurement", "Livrer la mesure de persistance"],
      escalate_reversal: ["Review the reversal", "Examiner l’inversion"],
      close_unconfirmed_change: ["Close the unconfirmed change", "Clore la variation non confirmée"],
      request_missing_evidence: ["Obtain the missing evidence", "Obtenir les éléments manquants"],
      continue_monitoring: ["Continue monitoring", "Poursuivre le suivi"],
      defer_until_access: ["Defer until access is available", "Reporter jusqu’à l’obtention de l’accès"],
      escalate_to_review: ["Refer conflicting records for review", "Soumettre les données contradictoires à un examen"],
      close_covered_search: ["Close the covered search", "Clore la recherche dans le périmètre couvert"]
    };
    const pair = labels[receipt.decision.action];
    $("evidence-verdict").textContent = pair[0];
    $("evidence-verdict-fr").textContent = pair[1];
    $("evidence-attempts").replaceChildren(...receipt.attempts.map(a => elem("li", a.route + " · " + a.reason)));
    $("evidence-sha").textContent = receipt.sha256;
  }
  $("recipient-command").textContent = run.evidence_result ? "python3 -IB action_study/desk.py verify decision.json --mission mission.json" :
    run.change_result ? "python3 -IB review_change.py" :
    run.followup_result ? "python3 -IB review_followup.py" :
    run.endpoint_result ? "python3 -B endpoint_lab/replay_delivery.py" :
    study ? "python3 -B verify_decision.py" : "python3 -I run.py verify";
  if (!study) return;
  const verdicts = {audit_pass:"Pilot criteria met", audit_failed:"Pilot criteria missed",
    no_feasible_calibration_policy:"No policy fits the calibration budget"};
  $("pairing-verdict").textContent = verdicts[study.verdict] || "Inspect the study verdict";
  $("pairing-result").dataset.tone = study.qualifies === true ? "pass" : "fail";
  $("pairing-stacks").textContent = Array.isArray(study.selected) && study.selected.length
    ? "Selected on calibration issues · " + study.selected.join(" + ") : "No stack selected.";
  const metrics = $("pairing-metrics");
  metrics.replaceChildren();
  if (study.audit) {
    const {solved, tasks, tokens} = study.audit;
    for (const [label, value] of [
      ["Held-out issues resolved", solved + " of " + tasks],
      ["Total tokens charged", Number(tokens).toLocaleString("en-US")],
      ["Mean tokens per held-out issue", (tokens / tasks).toLocaleString("en-US", {maximumFractionDigits: 1})]
    ]) metrics.append(elem("dt", label), elem("dd", value));
  }
  const agreement = replay ? "The recording reports independent SQL agreement. " : "Independent SQL reproduced the decision. ";
  $("pairing-qualification").textContent = (study.sql_agreement ? agreement : "") +
    "These are historical grader outcomes. A fresh pilot requires new issues and separately obtained grades.";
}
const endpointReasons = {
  unverified_report: "Report is provisional",
  outside_standardized_scope: "Report falls outside the standardized division",
  outside_reported_deployment: "Deployment type differs",
  unavailable_system_category: "System availability category differs",
  different_model: "Model differs",
  different_dataset: "Workload dataset differs",
  price_evidence_unavailable: "Price evidence is missing",
  lab_access_unproven: "Lab access is unconfirmed",
  turn_end_to_end_unmeasured: "End-to-end agent turns were unmeasured",
  incomplete_run: "Run is incomplete",
  failed_or_unreported_queries: "Queries failed or completion evidence is missing",
  offline_or_unknown_load: "Load is offline or unknown",
  online_label_unavailable: "Explicit online label is missing",
  point_accuracy_unreported: "Accuracy at this load is missing",
  below_minimum_load: "Concurrency falls below the minimum",
  missing_first_token: "First-token latency is missing",
  first_token_too_slow: "P90 first-token latency exceeds the ceiling",
  missing_token_rate: "Token rate is missing",
  token_rate_too_low: "Token rate falls below the floor"
};
function endpointPoint(host, point) {
  const a = elem("article", undefined, "endpoint-point");
  const link = urlLink("https://results.mlcommons.org/endpoints/report?source=phase2&submission=" + encodeURIComponent(point.source));
  if (link) {
    link.textContent = "Official report · run " + point.run + " ↗";
    a.append(link);
  }
  const metrics = elem("dl");
  const fields = [["Concurrency", point.concurrency], ["P90 time to first token (ms)", point.ttft_p90_ms],
    ["Reported tokens/s per user", point.tps_per_user], ["P90 time per output token (ms)", point.tpot_p90_ms],
    ["System output (tokens/s)", point.system_tps], ["Load configuration", point.config_type],
    ["Failed queries", point.failed]];
  for (const [label, value] of fields) metrics.append(elem("dt", label), elem("dd", value ?? "Unreported"));
  a.append(metrics);
  if (point.reasons?.length) a.append(elem("p", point.reasons.map(code => endpointReasons[code] || code).join(" · ")));
  host.append(a);
}
function endpointView(run) {
  const result = run.endpoint_result, area = $("endpoint-result");
  area.hidden = !result;
  if (!result) return;
  const contract = result.contract;
  const selected = result.selected, supported = result.decision === "supported" && selected.length > 0;
  area.dataset.tone = supported ? "pass" : "fail";
  $("endpoint-verdict").textContent = supported ? selected[0].concurrency + " concurrent requests supported" : "Capacity decision withheld";
  const metric = {reported_tps_per_user: "reported tokens/s per user", inverse_p90_tpot: "tokens/s from inverse P90 time per token", agentic_e2e: "tokens/s over a complete agent turn"};
  $("endpoint-scope").textContent = contract.model + " · " + contract.dataset + " · P90 first token ≤ " + contract.max_ttft_p90_ms +
    " ms · ≥ " + contract.min_tps_per_user + " " + metric[contract.rate_metric] + " · minimum load " + contract.min_concurrency +
    " · " + (contract.load_mode === "online" ? "online only" : "reported submission or online");
  const witnesses = $("endpoint-witnesses"), next = $("endpoint-next");
  witnesses.replaceChildren();
  next.replaceChildren();
  witnesses.append(elem("p", result.eligible.length + " of " + (result.eligible.length + result.excluded.length) +
    " measured configurations meet the full requirement."));
  for (const point of selected) endpointPoint(witnesses, point);
  if (!supported) {
    const matching = result.excluded.filter(p =>
      !p.reasons.some(reason => ["different_model", "different_dataset", "unverified_report"].includes(reason)));
    if (matching.length) {
      const details = elem("details");
      details.append(elem("summary", "Inspect " + matching.length + " measured configurations on the matching workload"));
      for (const p of matching) endpointPoint(details, p);
      witnesses.append(details);
    }
  }
  const test = result.next_test;
  if (test.action === "measure_matching_workload") {
    next.append(elem("p", "Run the specified model and dataset together. The evidence pack has no verified matching workload."));
  } else if (test.action === "collect_missing_evidence") {
    next.append(elem("p", "Resolve these conditions on a matching workload. A configuration can appear under several conditions."));
    const list = elem("ul");
    for (const [reason, count] of Object.entries(test.obstacles)) {
      list.append(elem("li", (endpointReasons[reason] || reason) + " · " + count + (count === 1 ? " configuration" : " configurations")));
    }
    next.append(list);
  } else {
    const repeat = test.action === "verify_selected_point_on_intended_traffic";
    next.append(elem("p", repeat ? "Repeat the selected load on the intended traffic and measure the same latency and rate." :
      "Retest the next higher recorded load on the intended traffic. Its published result missed at least one threshold."));
    if (!repeat) for (const point of test.targets) endpointPoint(next, point);
  }
  const verified = run.evaluation?.verification?.checked === true;
  $("endpoint-verification").textContent = (verified ? (replay ? "The recording reports independent replay agreement. " : "Independent SQL replay agrees on the decision and selected measurements. ") : "") +
    "The evidence covers the reported benchmark workload. Access, pricing and deployment require separate evidence.";
}
function mappingChoiceView(run) {
  const choice = !replay && run.status === "awaiting_choice" ? run.mapping_choice : null;
  if (!choice) {
    renderedChoice = null;
    return;
  }
  const identity = json([run.id, run.version, choice.sha256]);
  if (renderedChoice === identity) return;
  renderedChoice = identity;
  $("choice-question").textContent = choice.question;
  const examples = run.mission?.construction_spec?.definition?.demonstrations || [];
  $("choice-examples").hidden = examples.length === 0;
  $("choice-examples").open = false;
  $("choice-examples-content").textContent = json(examples);
  const legend = elem("legend", "Candidate rules");
  $("choice-options").replaceChildren(legend);
  for (const candidate of choice.candidates) {
    const row = elem("div", undefined, "rule-option");
    const label = elem("label");
    const radio = elem("input");
    radio.type = "radio";
    radio.name = "mapping-rule";
    radio.value = candidate.id;
    label.append(radio, elem("strong", candidate.description));
    row.append(label);
    detail(row, "Inspect exact operations", candidate.operations.map(op => op.column));
    $("choice-options").append(row);
  }
  const fixed = choice.fixed_operations || [];
  $("fixed-rules").hidden = !fixed.length;
  $("fixed-rules").open = false;
  $("fixed-list").replaceChildren(...fixed.map(op => elem("li", op.description)));
}
$("choice-options").addEventListener("change", buttons);
function chooseRule(abstain) {
  if (!current?.mapping_choice || current.status !== "awaiting_choice" || dirty || replay || busy) return;
  const request = current.mapping_choice;
  if (renderedChoice !== json([current.id, current.version, request.sha256])) return;
  const choice = abstain ? "abstain" : $("choice-options").querySelector("input:checked")?.value;
  if (choice) action("choose", {sha256:request.sha256, choice});
}
$("apply-choice").addEventListener("click", () => chooseRule(false));
$("abstain-choice").addEventListener("click", () => chooseRule(true));
function executionView(run) {
  const routing = run.routing;
  $("route-receipt").hidden = !routing;
  if (routing) {
    $("route-title").textContent = routeNames[routing.route] || stageLabel(routing.route);
    const method = {specialist:"Built-in specialist", model:"Configured model",
      operator_choice:"Operator clarification", model_choice:"Model selection among fitting rules"}[routing.method];
    $("route-method").hidden = !method;
    $("route-method").textContent = method || "";
    $("route-reason").textContent = routing.reason || "";
    const resolution = run.mapping_resolution;
    $("mapping-resolution").hidden = !resolution;
    if (resolution) {
      const options = run.mapping_choice?.candidates;
      const candidate = Array.isArray(options) ? options.find(c => c?.id === resolution.choice) : null;
      const actor = resolution.origin === "operator" ? "Operator" : resolution.origin === "model" ? "Model" : "Specialist";
      $("mapping-resolution").textContent = resolution.choice === "abstain" ? actor + " abstained." :
        actor + " selected · " + (candidate?.description || resolution.choice);
    }
    $("route-fallback").hidden = !routing.fallback;
    if (routing.fallback) {
      const outcome = run.status === "verified" ? "The direct construction passed verification." :
        (run.status === "failed" ? "The direct construction failed verification." : "A separately authorized direct attempt follows.");
      $("route-fallback").textContent = "Research verdict · " + stageLabel(run.research?.decision) + ". " + outcome;
    }
    $("route-detail").textContent = json(routing);
  }
  const checkpoints = (run.events || []).slice(-3);
  $("forge").hidden = !checkpoints.length;
  $("checkpoints").replaceChildren(...checkpoints.map(ev => {
    const li = elem("li");
    const time = elem("time", ev.at);
    time.dateTime = ev.at;
    li.append(elem("strong", stageLabel(ev.stage)), elem("p", ev.message), time);
    return li;
  }));
  const attempts = Array.isArray(run.construction_attempts) ? run.construction_attempts : [];
  $("attempts").hidden = !attempts.length;
  const list = $("attempt-list");
  const attemptIdentity = json(attempts);
  if (renderedAttempts !== attemptIdentity) {
    renderedAttempts = attemptIdentity;
    list.replaceChildren();
    for (const attempt of attempts) {
      const article = elem("article", undefined, "attempt");
      article.dataset.status = attempt.status;
      article.append(elem("h4", "Attempt " + attempt.attempt + " · " + stageLabel(attempt.status)));
      if (attempt.feedback) {
        if (typeof attempt.feedback === "string") article.append(elem("p", attempt.feedback));
        else detail(article, "Evaluator feedback", attempt.feedback);
      }
      detail(article, "Attempt receipt", attempt);
      list.append(article);
    }
  }
  const handoffTitles = {repair:"Repair the rejected construction", choose_hypothesis:"Review the model’s mapping choice"};
  $("handoff-title").textContent = handoffTitles[run.handoff?.stage] || "Operator-assisted execution";
}
function show(run, open = false) {
  if (!run?.id) throw Error("The service returned an incomplete run record.");
  if (current && current.id !== run.id) {dirty=false;lastHandoff=null;lastTrial=null;}
  current=run; if (!replay) remember(run.id); $("record").hidden=false; $("empty").hidden=true;
  $("record-title").textContent=run.mission?.purpose || "Execution & evidence";
  $("run-status").textContent=[run.status,run.stage].filter(Boolean).join(" · ").replaceAll("_"," ");
  if (dirty && !replay) $("run-status").textContent="Historical record · " + $("run-status").textContent;
  if (replay) $("run-status").textContent="RECORDED REPLAY · " + $("run-status").textContent;
  $("run-id").textContent=`Revision ${run.version} · ${run.id}`;
  $("raw").textContent=json(run);
  if (!dirty && !replay && run.status==="stale") runNotice("The execution source or provider changed. Amend the mission to run it against the current configuration.");
  $("run-status").dataset.tone = dirty ? "" : ({verified:"pass", failed:"fail"})[run.status] || "";
  executionView(run);
  mappingChoiceView(run);
  pairingView(run);
  endpointView(run);
  studyView(run.opportunity_study);
  $("events").replaceChildren(...(run.events||[]).map(ev=>{
    const li=elem("li");li.append(elem("strong",ev.stage),elem("p",ev.message),elem("small",ev.at));return li;
  }));
  results(run);
  $("proposal").textContent=json(run.proposed_contract || {});
  if(lastProposal!==run.contract_sha256) {lastProposal=run.contract_sha256; $("confirmations").value="";}
  if (lastHandoff !== run.handoff?.sha256) { $("response").value=""; lastHandoff=run.handoff?.sha256; }
  $("prompt").textContent=lineText(run.handoff?.prompt || "");
  const trialKey=run.id + "/" + run.version + "/" + (run.contract?.sha256 || run.contract_sha256 || "pending");
  if (lastTrial !== trialKey) {
    $("trial").value=json(run.contract?.spec?.cases?.find(c=>Object.hasOwn(c,"expected"))?.input ?? run.mission?.construction_spec?.cases?.find(c=>Object.hasOwn(c,"expected"))?.input ?? {});
    $("output").textContent=""; lastTrial=trialKey;
  }
  $("bundle").href=apiPath(run.id,"/bundle")+"?version="+encodeURIComponent(run.version);
  buttons();
  if (open) {
    $("record-title").focus({preventScroll:true});
    $("investigation").scrollIntoView({block:"start"});
  }
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
    busy=true; clearTimeout(timer); const token=++generation, submittedEdit=editNumber;buttons(); message("Saving mission…");
    const res=await api(path,{...payload,request_id:requestId});
    const run=res.mission ? res : await api(apiPath(res.id));
    if(token!==generation)return;
    dirty=submittedEdit!==editNumber;
    runNotice(dirty?"The brief changed while this revision was saving. Submit the amendment to check your current edits.":"");
    message("");show(run,true);
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
    if(token!==generation || dirty || replay)return;
    if (name==="try") $("output").textContent=json(result);
    else {const run=result.mission ? result : await api(apiPath(id)); if(token===generation)show(run);}
  } catch(e){if(token===generation){
    if(e.status===409) await refresh(id,token);
    runNotice(e.message); if(name==="try") $("output").textContent="Input refused. " + e.message;
  }}
  finally {busy=false;buttons();}
}
$("resume").addEventListener("click",()=>action("resume",{}));
$("approve").addEventListener("click",()=>{
  try {
    const confirmations=parseField("confirmations",true);
    if(!confirmations.some(c=>c && typeof c==="object" && Object.hasOwn(c,"expected"))) throw Error("Add at least one fresh successful acceptance case.");
    action("approve",{contract_sha256:current.contract_sha256,confirmations});
  } catch(e) {runNotice(e.message);}
});
$("respond").addEventListener("click",()=>{
  try { const response=parseField("response",false); action("respond",{sha256:current.handoff.sha256,response}); } catch(e){runNotice(e.message);}
});
$("copy-prompt").addEventListener("click",async()=>{
  try {await navigator.clipboard.writeText($("prompt").textContent); runNotice("Prompt copied.");}
  catch { $("prompt").parentElement.open=true; const range=document.createRange();range.selectNodeContents($("prompt"));getSelection().removeAllRanges();getSelection().addRange(range);runNotice("Prompt selected. Use your browser’s copy command."); }
});
$("try").addEventListener("click",()=>{
  try {const input=current?.pairing_result || current?.endpoint_result || current?.followup_result || current?.change_result || current?.evidence_result ? {} : JSON.parse($("trial").value); action("try",{input});}
  catch { $("output").textContent="Enter a valid JSON input."; }
});
$("trial").addEventListener("input",()=>{$("output").textContent="";});
$("history").addEventListener("toggle",async()=>{
  if (replay || !$("history").open || !current) return;
  const id=current.id, token=generation;
  try {const h=await api(apiPath(id,"/history"));if(token===generation)$("versions").textContent=json(h);}
  catch(e){if(token===generation)$("versions").textContent=e.message;}
});
function openReplay(data, label, packagedId) {
  if(!data || typeof data!=="object" || typeof data.id!=="string" || typeof data.status!=="string" ||
     !Number.isSafeInteger(data.version) || typeof data.mission?.purpose!=="string" ||
     !Array.isArray(data.events) || data.events.some(e=>!e || typeof e!=="object"))
    throw Error("Choose a saved IGNITION run record.");
  if (data.routing && (!Object.hasOwn(routeNames, data.routing.route) ||
      typeof data.routing.reason !== "string")) throw Error("Invalid route decision in this record.");
  if (data.construction_attempts && (!Array.isArray(data.construction_attempts) ||
      data.construction_attempts.some(attempt => !attempt || !Number.isInteger(attempt.attempt) ||
        !["rejected", "accepted"].includes(attempt.status)))) throw Error("Invalid construction attempts in this record.");
  if (data.opportunity_study) {
    const study = data.opportunity_study;
    const invalidCandidate = c => !c || typeof c.id !== "string" || typeof c.title !== "string" ||
      !Array.isArray(c.source_ids) || c.source_ids.some(id => typeof id !== "string");
    if (![study.candidates, study.challengers].every(group => Array.isArray(group) && group.every(c => !invalidCandidate(c))) ||
        (study.sources && (!Array.isArray(study.sources) || study.sources.some(s => !s || typeof s.id !== "string")))) {
      throw Error("Invalid opportunity study in this record.");
    }
  }
  if (data.endpoint_result) {
    const e = data.endpoint_result;
    const numeric = n => typeof n === "number" || typeof n === "string" || n === null;
    const point = p => p && typeof p.source === "string" && Number.isInteger(p.run) && Number.isInteger(p.concurrency) &&
      [p.ttft_p90_ms, p.tps_per_user, p.tpot_p90_ms, p.system_tps, p.failed].every(numeric) &&
      (p.reasons === undefined || Array.isArray(p.reasons) && p.reasons.every(r => typeof r === "string"));
    if (e.schema !== "frontier-endpoints/decision/v1" || !["supported","withheld"].includes(e.decision) ||
        !e.contract || typeof e.contract !== "object" || !Array.isArray(e.selected) || !e.selected.every(point) ||
        !Array.isArray(e.eligible) || !Array.isArray(e.excluded) || !e.excluded.every(p => point(p) && Array.isArray(p.reasons)) || !e.next_test ||
        (e.decision === "supported") !== Boolean(e.selected.length) ||
        !["measure_matching_workload","collect_missing_evidence","verify_selected_point_on_intended_traffic","measure_next_recorded_load_on_intended_traffic"].includes(e.next_test.action) ||
        (e.next_test.action === "collect_missing_evidence" && (!e.next_test.obstacles || typeof e.next_test.obstacles !== "object")) ||
        (e.next_test.action === "measure_next_recorded_load_on_intended_traffic" && (!Array.isArray(e.next_test.targets) || !e.next_test.targets.every(point)))) {
      throw Error("Invalid endpoint decision in this record.");
    }
  }
  const r=data.research || {};
  for (const k of ["signals","candidates","objections","mechanisms"])
    if (r[k] && (!Array.isArray(r[k]) || r[k].some(o=>!o || typeof o!=="object"))) throw Error("Invalid research records.");
  if (!replay) liveView={current,dirty,requestId,message:$("form-message").textContent,note:$("amend-note").textContent};
  replay=true;dirty=false;runNotice("");$("mode").textContent="Recorded replay · "+label;
  $("replay-message").textContent="Opened "+label+".";
  // Never import a pending request as an actionable handoff.
  show({...data,handoff:null},true);
  const bundle=$("recorded-bundle");
  if (["integrity","migration"].includes(packagedId) && data.status==="verified") {
    bundle.href="/api/replays/"+packagedId+"/bundle";bundle.hidden=false;
  } else bundle.removeAttribute("href");
}
function replayFailure(error,token) {
  $("replay-message").textContent=error.message;
  if (!replay && current && transient.has(current.status)) refresh(current.id,token);
}
$("replay-file").addEventListener("change",async()=>{
  const file=$("replay-file").files[0]; if (!file || busy) return;
  const token=++generation;clearTimeout(timer);
  try {
    if (file.size>4*1024*1024) throw Error("This viewer accepts run files up to 4 MiB.");
    const data=JSON.parse(await file.text());if(token===generation)openReplay(data,file.name);
  } catch(e) {if(token===generation)replayFailure(e,token);}
  $("replay-file").value="";
});
function publicReplayButton(rec) {
  const b=elem("button",rec.title || rec.id);b.type="button";b.dataset.publicReplay=rec.id;
  b.addEventListener("click",async()=>{
    if(busy)return;
    const token=++generation; clearTimeout(timer);
    try {const data=await api("/api/replays/"+encodeURIComponent(rec.id));
      if(token===generation) openReplay(data,rec.title || rec.id,rec.id);
    } catch(e){if(token===generation)replayFailure(e,token);}
  });return b;
}
$("close-replay").addEventListener("click",async()=>{
  const token=++generation;
  const previous=liveView;liveView=null;replay=false;current=previous?.current || null;dirty=previous?.dirty || false;
  requestId=previous?.requestId || null;
  $("mode").textContent=providerLabel || "Execution service unavailable";
  $("replay-message").textContent="";$("recorded-bundle").removeAttribute("href");
  if(current){
    show(current);runNotice(previous.note);
    if (online) try {const latest=await api(apiPath(current.id));if(token===generation)show(latest);} catch(e){message(e.message);}
  } else {
    $("record").hidden=true;$("empty").hidden=false;$("record-title").textContent="Execution & evidence";runNotice("");
    $("raw").textContent="";$("results").replaceChildren();
  }
  message(previous?.message);buttons();
});
$("snapshot").addEventListener("click",()=>{
  if (replay || dirty || !current || $("snapshot").hidden) return;
  const url=URL.createObjectURL(new Blob([json({...current,handoff:null})+"\n"],{type:"application/json"}));
  const a=elem("a");a.href=url;a.download="ignition-"+current.id+"-v"+current.version+".json";
  document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
document.addEventListener("visibilitychange",()=>{
  if(!document.hidden && online && current && !replay && !busy && !dirty) {
    clearTimeout(timer); refresh(current.id,++generation);
  }
});
async function init() {
  updateStrategyHelp();
  try {
    if (location.protocol === "file:") {
      $("public-showcase").hidden = true;
      throw Error("Open a saved record, or start the loopback service to run a mission.");
    }
    const status=await api("/api/status");online=true;
    const modeLabels={manual:"Operator-assisted model execution",local:"Live local model configured",unavailable:"Local tools available · Model unavailable"};
    providerLabel=[modeLabels[status.mode] || status.mode || "Execution service",status.provider?.provider,status.provider?.model].filter(Boolean).join(" · ");
    if(!replay) $("mode").textContent=providerLabel;
    const data=await api("/api/examples");examples=data.examples || [];
    for(const x of examples){const opt=elem("option",x.title || x.id); opt.value=x.id; $("example").append(opt);}
    $("presets").hidden=!examples.length;
    try {const pub=await api("/api/replays");
      $("public-replays").replaceChildren(...(pub.examples || []).map(publicReplayButton));

    } catch(e) {$("replay-message").textContent="Packaged recordings are unavailable. " + e.message;}
    const restored=earlierRun();
    if(restored && !replay) {try {const r=await api(apiPath(restored));loadBrief(r.mission,r.sources || []);show(r);}
      catch(e){remember(null);message("Previous run could not be reopened. " + e.message);}}
  } catch(e){if(!online)$("mode").textContent="Execution service unavailable";message(e.message);}
  buttons();
}
init();
