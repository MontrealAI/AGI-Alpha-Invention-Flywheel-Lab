"use strict";
const $ = id => document.getElementById(id);
const form = $("mission");
const labels = Array.from(document.querySelectorAll("[data-fr]"), el => [el, el.textContent, el.dataset.fr]);
const address = new URL(location.href);
let french = address.searchParams.get("lang") === "fr";
let preset, run, requestId, errorCode = "", dirty = false, busy = true, historyRows = [];
const t = (en, fr) => french ? fr : en;
const path = (suffix = "") => "/api/runs/" + encodeURIComponent(run.id) + suffix;
const disposition = {
  no_trigger: ["Monitoring", "Surveillance"], awaiting_repeat: ["Awaiting repeat", "En attente d’une nouvelle détection"],
  persisted: ["Change persisted", "Variation persistante"], reversed: ["Direction reversed", "Sens inversé"],
  not_reproduced: ["Change unconfirmed", "Variation non reproduite"], coverage_gap: ["No eligible repeat by deadline", "Aucune nouvelle détection admissible avant l’échéance"],
  right_censored: ["Archive ended before deadline", "Fin de l’archive avant l’échéance"]
};

async function api(url, body) {
  const opts = {cache: "no-store", credentials: "same-origin", redirect: "error"};
  if (body) Object.assign(opts, {method: "POST", headers: {"Content-Type": "application/json", "X-Ignition-Request": "1"},
    body: JSON.stringify(body)});
  const response = await fetch(url, opts);
  if (!response.ok) throw Error("HTTP " + response.status);
  return response.json();
}

function locationState() {
  address.hash = run ? run.id : "";
  if (french) address.searchParams.set("lang", "fr"); else address.searchParams.delete("lang");
  window.history.replaceState(null, "", address);
}

function render() {
  document.documentElement.lang = french ? "fr" : "en";
  document.title = t("Transient review desk", "Suivi des variations") + " · FRONTIER Ω";
  for (const [node, en, fr] of labels) node.textContent = t(en, fr);
  $("language").textContent = t("Français", "English");
  $("language").lang = t("fr", "en");
  for (const node of form.elements) node.disabled = busy;
  $("build").disabled = busy || !preset || Boolean(run && !dirty && run.status !== "stale");
  $("build").textContent = run ? t("Check revised queue", "Vérifier la révision") : t("Build review queue", "Construire la liste");
  $("new").hidden = !run;
  $("late").hidden = !$("second-archive").checked;
  $("history").hidden = !run;
  $("revisions").replaceChildren();
  for (const revision of historyRows) {
    const scope = revision.mission.resources.change_desk;
    if (!scope) continue;
    const li = document.createElement("li");
    li.textContent = t("Revision ", "Révision ") + revision.version + " · " + scope.as_of_utc + " · "
      + (scope.arm === "early_warm" ? t("prior history", "historique inclus") : t("week only", "semaine seulement"));
    $("revisions").append(li);
  }
  const selected = !dirty && run?.status === "verified" && run.change_result?.cohorts[0];
  $("verdict").textContent = selected
    ? selected.alerts.length + (selected.alerts.length === 1 ? t(" notice issued", " avis émis") : t(" notices issued", " avis émis"))
    : dirty && run ? t("Criteria changed", "Critères modifiés")
    : busy ? t("Checking the archive…", "Vérification des archives…")
    : run ? t("Queue unavailable", "Liste indisponible") : t("Awaiting a mission", "En attente d’une mission");
  $("state").textContent = errorCode ? t("The request could not be verified. ", "La demande n’a pas pu être vérifiée. ") + errorCode
    : run?.status === "blocked" ? t("Check the UTC cutoff and registered scope.", "Vérifiez la date UTC et le périmètre de la mission.")
    : dirty && run ? t("Submit the new criteria to verify this revision.", "Soumettez les critères pour vérifier cette révision.")
    : selected ? run.change_result.as_of_utc + " · " + selected.eligible_rows + t(" eligible detections this week", " détections admissibles cette semaine")
    : t("Construction and independent checking run locally.", "La construction et la vérification indépendante s’exécutent localement.");
  $("receipt").hidden = !selected;
  $("decisions").replaceChildren();
  const supplemental = run?.change_result?.archive_recheck;
  $("archive-heading").hidden = !selected || !supplemental;
  $("second-verdict").hidden = !selected || !supplemental;
  $("archive-scope").hidden = !selected || !supplemental;
  if (selected && supplemental) {
    const evidence = Object.values(supplemental);
    const count = evidence.filter(x => x.witness).length;
    const forced = evidence.filter(x => x.forced_photometry).length;
    $("second-verdict").textContent = selected.alerts.length
      ? t("Eligible later detections in the ALeRCE archive", "Détections ultérieures admissibles dans l’archive ALeRCE") + " · " + count
        + t(". Bands checked with forced photometry · ", ". Filtres vérifiés par photométrie forcée · ") + forced
      : t("The selected baseline produced no notice to recheck.", "Aucun avis à vérifier pour l’historique choisi.");
  }
  $("proof").textContent = "";
  $("kit").removeAttribute("href");
  if (!selected) return;
  const format = new Intl.NumberFormat(french ? "fr-CA" : "en-CA", {maximumFractionDigits: 6, signDisplay: "always"});
  const alerts = new Map(selected.alerts.map(a => [a.target_id + a.band, a]));
  for (const row of selected.coverage) {
    const alert = alerts.get(row.target_id + row.band);
    const tr = document.createElement("tr");
    const cells = [row.target_id + " · " + row.band, alert ? format.format(alert.delta_mag) : "—", t(...disposition[row.status])];
    if (supplemental) {
      const other = supplemental[row.band];
      cells.push(other?.target_id === row.target_id ? t(...disposition[other.status]) : "—");
    }
    for (const value of cells) {
      const cell = document.createElement("td"); cell.textContent = value; tr.append(cell);
    }
    $("decisions").append(tr);
  }
  $("kit").href = path("/bundle?version=" + run.version);
  $("verify-command").textContent = "python3 -IB review_change.py --expect-queue " + run.evaluation.verification.queue_sha256;
  $("proof").textContent = JSON.stringify({contract: run.contract, verification: run.evaluation.verification,
    alerts: selected.alerts, archive_recheck: supplemental}, null, 2);
}

function edited() { dirty = true; requestId = null; errorCode = ""; render(); }
form.addEventListener("input", edited);
for (const node of document.querySelectorAll("[data-instant]")) node.addEventListener("click", () => {
  $("cutoff").value = node.dataset.instant; edited();
});
$("language").addEventListener("click", () => { french = !french; locationState(); render(); });
$("new").addEventListener("click", () => {
  run = null; requestId = null; historyRows = []; dirty = false; errorCode = "";
  form.reset(); $("history").open = false; locationState(); render();
});

async function observe(item) {
  run = item; locationState();
  while (["queued", "running"].includes(run.status)) {
    render();
    await new Promise(resolve => setTimeout(resolve, 150));
    run = await api(path());
  }
  historyRows = (await api(path("/history"))).versions;
}

form.addEventListener("submit", async e => {
  e.preventDefault();
  if (busy || !preset || !form.reportValidity()) return;
  const mission = structuredClone(preset.mission);
  mission.resources.change_desk = {as_of_utc: $("cutoff").value, arm: $("arm").value, check_other_archive: $("second-archive").checked};
  mission.beneficiary = $("beneficiary").value;
  busy = true; errorCode = ""; render();
  try {
    requestId ||= crypto.randomUUID();
    const body = {mission, sources: [], request_id: requestId};
    if (run) body.version = run.version;
    const record = await api(run ? path("/amend") : "/api/runs", body);
    dirty = false; requestId = null;
    await observe(record);
  } catch (error) { errorCode = error.message; }
  finally { busy = false; render(); }
});

async function initialize() {
  render();
  try {
    preset = (await api("/api/examples")).examples.find(p => p.id === "change_desk");
    if (!preset) throw Error("change_desk");
    const id = address.hash.slice(1);
    if (id) {
      if (!/^[a-f0-9]{32}$/.test(id)) throw Error("ID");
      const item = await api("/api/runs/" + id);
      const scope = item.mission?.resources.change_desk;
      if (!scope) throw Error("ID");
      $("cutoff").value = scope.as_of_utc; $("arm").value = scope.arm;
      $("second-archive").checked = scope.check_other_archive === true;
      $("beneficiary").value = item.mission.beneficiary;
      await observe(item);
    }
  } catch (error) { errorCode = error.message; }
  finally { busy = false; render(); }
}
initialize();
