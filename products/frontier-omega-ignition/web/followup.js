"use strict";
const $ = id => document.getElementById(id);
const labels = [...document.querySelectorAll("[data-fr]")].map(node => [node, node.textContent, node.dataset.fr]);
const address = new URL(location.href);
let french = address.searchParams.get("lang") === "fr";
let preset, run, busy = false, changed = false, pendingId = null, message = "", revisions = [];
const t = (en, fr) => french ? fr : en;
const action = (id, suffix = "") => "/api/runs/" + encodeURIComponent(id) + suffix;

async function api(path, data) {
  const options = {cache: "no-store", credentials: "same-origin", redirect: "error"};
  if (data !== undefined) Object.assign(options, {method: "POST", headers: {
    "Content-Type": "application/json", "X-Ignition-Request": "1"}, body: JSON.stringify(data)});
  const response = await fetch(path, options);
  if (!response.ok) throw new Error("HTTP " + response.status);
  return response.json();
}

function render() {
  document.documentElement.lang = french ? "fr" : "en";
  document.title = t("The night worklist", "Le programme de la nuit") + " · FRONTIER Ω";
  for (const [node, en, fr] of labels) node.textContent = french ? fr : en;
  $("language").textContent = t("Français", "English");
  $("language").lang = t("fr", "en");
  $("language").disabled = busy && !preset;
  $("build").textContent = run ? t("Check amended worklist", "Vérifier la révision") : t("Construct worklist", "Construire le programme");
  $("build").disabled = busy || !preset || Boolean(run && !changed && run.status !== "stale");
  $("new").hidden = !run;
  for (const id of ["budget", "cadence", "owner", "new"]) $(id).disabled = busy;
  const result = run?.followup_result;
  const valid = !changed && run?.status === "verified" && result?.dispatch_authorized === false;
  $("receipt").hidden = !valid;
  $("history").hidden = !run;
  $("verdict").textContent = valid
    ? t(result.objective + " fully covered " + (result.objective === 1 ? "target" : "targets"), result.objective + (result.objective === 1 ? " cible couverte" : " cibles couvertes"))
    : changed && run ? t("Criteria changed", "Critères modifiés")
    : busy ? t("Checking the mission…", "Vérification de la mission…")
    : run?.status === "stale" ? t("Source changed", "Source modifiée")
    : run ? t("Worklist unavailable", "Programme indisponible") : t("Awaiting a mission", "En attente d’une mission");
  $("state-note").textContent = message || (changed && run
    ? t("Submit the revision to qualify the new scope.", "Soumettez la révision pour vérifier le nouveau périmètre.")
    : run ? t("Local revision ", "Révision locale ") + run.version
    : t("Construction and independent checking run on this computer.", "La construction et la vérification indépendante s’exécutent sur cet ordinateur."));
  $("revisions").replaceChildren();
  const statuses = {verified: t("verified", "vérifiée"), blocked: t("blocked", "bloquée"), queued: t("queued", "en attente"),
    running: t("in progress", "en cours"), stale: t("source changed", "source modifiée")};
  for (const revision of revisions) {
    const li = document.createElement("li");
    const controls = revision.mission.resources.followup;
    li.textContent = t("Revision ", "Révision ") + revision.version + " · " + (statuses[revision.status] || revision.status)
      + " · " + controls.max_slots + t(" slots", " créneaux") + " / " + controls.visits_per_target + t(" per target", " par cible");
    $("revisions").append(li);
  }
  $("slots").replaceChildren();
  $("proof").textContent = "";
  $("kit").removeAttribute("href");
  if (!valid) return;
  for (const slot of result.slots) {
    const tr = document.createElement("tr");
    for (const value of [slot.utc.replace("T", " ").replace("Z", ""), slot.target_id, slot.ra_deg + " / " + slot.dec_deg]) {
      const cell = document.createElement("td"); cell.textContent = value; tr.append(cell);
    }
    $("slots").append(tr);
  }
  $("comparison").textContent = t("Independent direct optimum", "Optimum de la méthode directe indépendante") + " · " + run.evaluation.verification.direct_objective;
  $("proof").textContent = JSON.stringify({contract_sha256: run.contract_sha256, specialist_sha256: run.specialist_source,
    verification: run.evaluation.verification, plan: result}, null, 2);
  $("kit").href = action(run.id, "/bundle?version=" + run.version);
}

function url() {
  address.hash = run ? run.id : "";
  if (french) address.searchParams.set("lang", "fr"); else address.searchParams.delete("lang");
  window.history.replaceState(null, "", address);
}
$("language").addEventListener("click", () => { french = !french; url(); render(); });
$("plan-form").addEventListener("input", () => { changed = true; pendingId = null; message = ""; render(); });
$("new").addEventListener("click", () => {
  run = null; revisions = []; changed = false; pendingId = null; message = ""; $("plan-form").reset(); $("history").open = false; url(); render();
});
function fail(error) {
  message = t("Could not verify this request. Check the service and current revision.", "La demande n’a pas pu être vérifiée. Vérifiez le service et la révision en cours.") + " " + error.message;
}

async function observe(value) {
  run = value;
  url();
  while (["queued", "running"].includes(run.status)) {
    render();
    await new Promise(resolve => setTimeout(resolve, 180));
    run = await api(action(run.id));
  }
  revisions = (await api(action(run.id, "/history"))).versions;
}

$("plan-form").addEventListener("submit", async event => {
  event.preventDefault();
  if (busy || !preset || !$("plan-form").reportValidity()) return;
  busy = true; message = ""; render();
  try {
    pendingId ||= crypto.randomUUID();
    const mission = structuredClone(preset.mission);
    mission.beneficiary = $("owner").value;
    mission.resources.followup = {max_slots: $("budget").valueAsNumber, visits_per_target: Number($("cadence").value)};
    const body = {mission, sources: [], request_id: pendingId};
    if (run) body.version = run.version;
    const response = await api(run ? action(run.id, "/amend") : "/api/runs", body);
    changed = false; pendingId = null;
    await observe(response);
  } catch (error) { fail(error); }
  finally { busy = false; render(); }
});

async function initialize() {
  busy = true; render();
  try {
    preset = (await api("/api/examples")).examples.find(item => item.id === "followup");
    if (!preset) throw new Error("followup");
    const id = address.hash.slice(1);
    if (id) {
      if (!/^[a-f0-9]{32}$/.test(id)) throw new Error("ID");
      const previous = await api(action(id));
      if (!previous.mission?.resources.followup) throw new Error("ID");
      $("budget").value = previous.mission.resources.followup.max_slots;
      $("cadence").value = previous.mission.resources.followup.visits_per_target;
      $("owner").value = previous.mission.beneficiary;
      await observe(previous);
    }
  } catch (error) { fail(error); }
  finally { busy = false; render(); }
}
initialize();
