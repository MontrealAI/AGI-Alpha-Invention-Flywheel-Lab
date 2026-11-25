import {downloadJSON} from './frontier-goals.mjs';
import {
  createMission, reviseMission, prepareMission, beginMission, recordMission, interruptMission,
  cancelMission, continueMission, exportMission, importMission, missionPacket, bindMissionRequest,
} from './frontier-mission.mjs';
import {
  createMissionRequest, createMissionPrompt, parseMissionResponse, runLocalMission, validateLocalMissionConfig,
} from './frontier-mission-router.mjs';

const messages = {
  en: {
    ready: 'Mission opened on this device.', waiting: 'Assisted mission prepared. No model request has run.',
    running: 'Waiting for your local model…', review: 'Work returned for your review.',
    paused: 'Mission paused. Its ambition and completed work are still here.', canceled: 'Mission canceled.',
    choose: 'Use an available tool, connect intelligence or open a prepared assisted mission.',
    assisted: 'Review the exact prepared prompt, then bring the answer back here.',
    localNext: 'Review the local result and its assumptions before using it.',
    error: 'The local model did not return a usable response. Check the running service, model name and connection, or continue with an assisted mission.',
    config: 'Local configuration ready. The mission remains open.', invalidConfig: 'Enter the exact model name and choose a supported runtime.',
    invalid: 'This response does not match the prepared mission or its format.',
    pausedNext: 'Continue when you have the right intelligence or the missing information.',
    canceledNext: 'Open a new mission or resume this one.',
    invalidMission: 'Enter an ambition of up to 24 KiB. Use text you are authorized to process.',
    saved: 'Mission downloaded. It contains your ambition and work.',
    reopened: 'Mission restored. Review its current status before continuing.',
    fileInvalid: 'This file is unreadable, changed or outside the mission format.',
    copy: 'Reviewed prompt copied.', select: 'The reviewed prompt is selected for copying.',
    localSource: 'Local model result', manualSource: 'Assisted result', restoredSource: 'Restored work record', unpublished: 'Verification pending',
    publicReport: 'Read the completed study', publicArtifact: 'Download the verified research tool',
    routes: {direct:'Direct answer',capability:'Existing capability',composition:'Capability composition',adaptation:'Adaptation',
      research:'Frontier research',invention:'New invention',continuing:'Continuing investigation',clarification:'Clarification or abstention'},
  },
  fr: {
    ready: 'Mission ouverte sur cet appareil.', waiting: 'Mission assistée préparée. Aucun modèle n’a été sollicité.',
    running: 'En attente de votre modèle local…', review: 'Travail reçu pour examen.',
    paused: 'Mission en pause. Son ambition et le travail accompli sont conservés.', canceled: 'Mission annulée.',
    choose: 'Utilisez un outil disponible, connectez un modèle ou ouvrez une mission assistée.',
    assisted: 'Relisez la consigne préparée, puis rapportez la réponse ici.',
    localNext: 'Examinez le résultat local et ses hypothèses avant de l’utiliser.',
    error: 'Le modèle local n’a pas fourni de réponse exploitable. Vérifiez le service, le nom du modèle et la connexion, ou poursuivez avec une mission assistée.',
    config: 'Configuration locale prête. La mission demeure ouverte.', invalidConfig: 'Indiquez le nom exact du modèle et choisissez un environnement pris en charge.',
    invalid: 'Cette réponse ne correspond pas à la mission préparée ou au format demandé.',
    pausedNext: 'Poursuivez lorsque l’intelligence ou les renseignements nécessaires sont disponibles.',
    canceledNext: 'Ouvrez une nouvelle mission ou reprenez celle-ci.',
    invalidMission: 'Saisissez une ambition d’au plus 24 Kio. Utilisez du texte que vous êtes autorisé à traiter.',
    saved: 'Mission téléchargée. Le fichier contient votre ambition et votre travail.',
    reopened: 'Mission rétablie. Examinez son état avant de poursuivre.',
    fileInvalid: 'Ce fichier est illisible, a été modifié ou ne respecte pas le format de mission.',
    copy: 'Consigne relue copiée.', select: 'La consigne relue est sélectionnée pour la copier.',
    localSource: 'Résultat du modèle local', manualSource: 'Résultat assisté', restoredSource: 'Travail rétabli', unpublished: 'Vérification à venir',
    publicReport: 'Lire l’étude terminée', publicArtifact: 'Télécharger l’outil de recherche vérifié',
    routes: {direct:'Réponse directe',capability:'Capacité existante',composition:'Composition de capacités',adaptation:'Adaptation',
      research:'Recherche de pointe',invention:'Nouvelle invention',continuing:'Enquête à poursuivre',clarification:'Précision ou abstention'},
  },
};

const routes = [
  ['endpoint-screen','#mv-endpoint-run',['Endpoint Evidence Screen','Évaluation Endpoint'],
    ['Select a tested load from authorized same-scope measurements of P90 first-token latency and per-user throughput. Missing results, untested loads and different workload scopes require their own evidence.',
      'Choisir une charge testée selon la latence P90 du premier jeton et le débit par utilisateur, à partir de mesures autorisées et comparables. Les charges non testées et les autres scénarios exigent leurs propres mesures.']],
  ['noaa-archive','#tool-archive',['NOAA Archive Point','Point d’archive NOAA'],
    ['NOAA GFS historical f024 forecast only, with exactly 24 hours from initialization to valid time. It returns 2 m air temperature at an exact native 0.25° grid cell in kelvin. The package runs with Linux, Python 3.12, curl and OpenSSL.',
      'Prévision historique NOAA GFS f024 seulement, avec exactement 24 heures entre l’initialisation et l’heure de validité. Température de l’air à 2 m en kelvins pour une cellule exacte de la grille de 0,25°. Linux, Python 3.12, curl et OpenSSL requis.']],
  ['harness','#foundry-mission',['HARNESS capability construction','Construction d’une capacité HARNESS'],
    ['Define scalar inputs, a deterministic rule and independently held acceptance cases.','Définir des entrées scalaires, une règle déterministe et des cas d’acceptation gardés séparément.']],
  ['scientific-evidence','#foundry-factory-results',['Scientific Truth Engine','Moteur de validation scientifique'],
    ['Inspect qualified source-lineage, scope and historical measurement checks.','Examiner les contrôles qualifiés de provenance, de portée et de mesures historiques.']],
  ['opportunity-capture','#opportunity-capture',['Opportunity Capture','Repérage des possibilités'],
    ['Check verified technology availability and supported productive follow-up.','Vérifier la disponibilité documentée et les suites productives possibles.']],
  ['successor-study','#foundry-study',['Successor comparisons','Comparaison de capacités successeures'],
    ['Inspect independently compared portable capabilities and replay a supported study.','Examiner des capacités portables comparées indépendamment et reproduire une étude prise en charge.']],
];

const node = key => document.getElementById(key);
const text = (key, value) => { node(key).textContent = value ?? ''; };
const show = (key, visible) => { node(key).hidden = !visible; };

function downloadText(value, filename) {
  const url = URL.createObjectURL(new Blob([value], {type:'text/plain;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function publicRuns() {
  try {
    const entries = JSON.parse(node('mission-public-runs').content.textContent);
    return entries.filter(row => typeof row.ambition === 'string' && typeof row.en === 'string' && typeof row.fr === 'string'
      && /^frontier-[a-z0-9.-]+\.zip$/u.test(row.download)
      && /^https:\/\/github\.com\/MontrealAI\/AGI-Alpha-Invention-Flywheel-Lab\/blob\/[0-9a-f]{40}\/publication\/universal\/[a-zA-Z0-9/._-]+\.md$/u.test(row.report)
      && typeof row.capability?.id === 'string' && /^[a-z0-9][a-z0-9-]{1,63}$/u.test(row.capability.id)
      && [row.capability.en, row.capability.fr, row.capability.scopeEn, row.capability.scopeFr]
        .every(value => typeof value === 'string' && value.length > 0 && value.length <= 300));
  } catch { return []; }
}

export function setupMissionConsole(member, shell) {
  const language = document.documentElement.lang === 'fr' ? 'fr' : 'en';
  const words = messages[language];
  const i = language === 'fr' ? 1 : 0;
  const input = node('goal-text');
  const priorRuns = publicRuns();
  const registered = priorRuns.map(({capability, download}) => [capability.id, download,
    [capability.en, capability.fr], [capability.scopeEn, capability.scopeFr]]);
  const available = [...routes, ...registered];
  const capabilities = available.map(([id,, title, scope]) => ({id, title:title[i], scope:scope[i]}));
  const localRuns = new Set();
  let mission, request, connection, activeRequest, atlas, serial = 0;
  const active = () => !member.hidden;

  function currentReport() {
    return mission?.reports.findLast(report => report.revision === mission.revision);
  }

  function resetHandoff() {
    request = undefined;
    for (const id of ['mission-prompt','mission-reply']) node(id).value = '';
    node('mission-share').checked = false;
    node('mission-handoff').open = false;
    show('mission-handoff', false);
    authorizeShare();
  }

  function authorizeShare() {
    const permitted = Boolean(request && node('mission-share').checked && active());
    for (const id of ['mission-copy','mission-prompt-download']) node(id).disabled = !permitted;
    show('mission-assistant', permitted);
  }

  function render(message) {
    const panel = node('frontier-mission-panel');
    panel.hidden = !mission;
    node('mission-export').disabled = !mission;
    show('mission-return', Boolean(mission));
    if (!mission) {
      delete panel.dataset.state;
      delete panel.dataset.route;
      for (const key of ['mission-ambition','mission-next','mission-status','mission-original','mission-objective','mission-route','mission-work','mission-published-summary']) text(key, '');
      for (const key of ['mission-published-links','mission-capabilities','mission-assumptions']) node(key).replaceChildren();
      return;
    }
    const report = currentReport();
    const state = mission.status;
    const route = report?.route;
    panel.dataset.state = state;
    panel.dataset.route = route ?? '';
    text('mission-ambition', mission.ambition);
    text('mission-original', mission.originalAmbition);
    show('mission-history', mission.originalAmbition !== mission.ambition);
    const source = report?.provider === 'assisted' ? words.manualSource
      : localRuns.has(report?.runId) ? words.localSource : words.restoredSource;
    const labels = [source, localRuns.has(report?.runId) ? report.model : null, words.unpublished].filter(Boolean);
    text('mission-status', message ?? (report && state === 'review' ? labels.join(' · ') : words[state]));
    text('mission-next', state === 'canceled' ? words.canceledNext : state === 'paused' ? words.pausedNext
      : state === 'waiting' ? words.assisted : state === 'running' ? words.localNext : report?.nextAction ?? words.choose);
    show('mission-understanding', Boolean(report));
    text('mission-route', words.routes[route]);
    text('mission-objective', report?.objective);
    text('mission-work', report?.work);
    show('mission-work-panel', Boolean(report?.work));
    const assumptions = report?.assumptions ?? [];
    show('mission-assumptions-group', assumptions.length > 0);
    node('mission-assumptions').replaceChildren(...assumptions.map(value => {
      const item = document.createElement('li');
      item.textContent = value;
      return item;
    }));
    const picked = available.filter(([id]) => report?.capabilityIds?.includes(id));
    node('mission-capabilities').replaceChildren(...picked.map(([, href, title, scope]) => {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = href;
      link.textContent = title[i];
      if (href.endsWith('.zip')) link.download = '';
      if (href === '#foundry-mission') link.addEventListener('click', () => {
        const value = report.objective;
        if (value.length <= 360 && !node('foundry-objective').value) node('foundry-objective').value = value;
        node('foundry-mission').open = true;
      });
      item.append(link, document.createTextNode(` · ${scope[i]}`));
      return item;
    }));
    const published = priorRuns.find(row => row.ambition === mission.ambition.trim());
    show('mission-published', Boolean(published));
    text('mission-published-summary', published?.[language]);
    node('mission-published-links').replaceChildren();
    if (published) for (const [href, label] of [[published.report, words.publicReport], [published.download, words.publicArtifact]]) {
      const link = document.createElement('a');
      link.href = href;
      link.textContent = label;
      if (href === published.download) link.download = '';
      node('mission-published-links').append(link);
    }
    show('mission-run-local', Boolean(connection) && state !== 'canceled' && state !== 'running');
    show('mission-pause', state === 'running' || state === 'waiting');
    show('mission-continue', ['paused','canceled','review'].includes(state));
    node('mission-cancel').disabled = state === 'canceled';
    node('mission-prepare').disabled = state === 'running' || state === 'canceled';
  }

  function stopRequest() {
    serial++;
    activeRequest?.abort();
    activeRequest = undefined;
  }

  function start(ambition) {
    if (!active()) return false;
    try {
      const updated = mission ? (mission.ambition !== ambition ? reviseMission(mission, ambition) : mission)
        : createMission(ambition, {language});
      if (updated !== mission) {
        stopRequest();
        resetHandoff();
        mission = updated;
      }
      atlas = undefined;
      render();
      shell.show(node('frontier-mission-panel'), {remember:true});
      return true;
    } catch {
      text('goal-status', words.invalidMission);
      return false;
    }
  }

  async function requestForMission() {
    const packet = missionPacket(mission);
    const context = [`Current mission run reference: ${packet.runId}`];
    if (atlas) context.push(`Public Atlas lead, applicability unverified: ${atlas.title} · ${atlas.evidence} · ${atlas.url}`);
    if (packet.previousReport) {
      const previous = packet.previousReport;
      context.push(`Previous objective, unverified: ${previous.objective.slice(0,450)}`);
      context.push(`Previous next action, unverified: ${previous.nextAction.slice(0,450)}`);
      if (previous.work) context.push(`Previous work excerpt, unverified: ${previous.work.slice(0,450)}`);
    }
    const {missionId, revision, language, originalAmbition, ambition} = packet;
    return createMissionRequest({missionId, revision, language, originalAmbition, ambition, context, capabilities});
  }

  function accept(receipt, runId) {
    const route = receipt.route === 'clarify' ? 'clarification' : receipt.route;
    mission = recordMission(mission, runId, {route, objective:receipt.objective, nextAction:receipt.nextAction,
      assumptions:receipt.assumptions, work:receipt.work, capabilityIds:receipt.capabilityIds});
    resetHandoff();
    render();
    node('mission-work-panel').open = Boolean(receipt.work);
  }

  function revealHandoff(prepared) {
    request = prepared;
    node('mission-prompt').value = createMissionPrompt(request);
    const handoff = node('mission-handoff');
    handoff.hidden = false;
    handoff.open = true;
  }

  node('mission-prepare').addEventListener('click', async () => {
    if (!active() || !mission) return;
    const token = ++serial;
    try {
      if (mission.status !== 'waiting' || mission.run?.provider !== 'assisted' || !mission.request) {
        const queued = prepareMission(mission, {provider:'assisted'});
        mission = queued;
        const prepared = await bindMissionRequest(queued, queued.run.id, await requestForMission());
        if (token !== serial || !active()) return;
        mission = prepared;
      }
      revealHandoff(mission.request);
      render();
      node('mission-handoff').querySelector('summary').focus();
    } catch { if (token === serial && active()) render(words.invalidMission); }
  });

  node('mission-share').addEventListener('change', authorizeShare);
  node('mission-copy').addEventListener('click', async () => {
    if (!active() || !request || !node('mission-share').checked) return;
    const token = serial;
    try {
      await navigator.clipboard.writeText(node('mission-prompt').value);
      if (token === serial && active()) render(words.copy);
    } catch {
      if (token !== serial || !active()) return;
      node('mission-prompt').focus();
      node('mission-prompt').select();
      render(words.select);
    }
  });
  node('mission-prompt-download').addEventListener('click', () => {
    if (active() && request && node('mission-share').checked) downloadText(node('mission-prompt').value, 'frontier-mission-prompt.txt');
  });
  node('mission-import-reply').addEventListener('click', async () => {
    if (!active() || !request || !mission?.run) return;
    const token = ++serial;
    const run = mission.run.id;
    try {
      let raw = node('mission-reply').value;
      try {
        const envelope = JSON.parse(raw);
        if (typeof envelope?.text === 'string' && !envelope.schema) raw = envelope.text;
      } catch { /* Parse and validate the actual reply below. */ }
      const result = await parseMissionResponse(raw, request, {mode:'manual'});
      if (token === serial && active()) accept(result, run);
    } catch { if (token === serial && active()) render(words.invalid); }
  });

  node('mission-configure').addEventListener('click', () => { node('mission-intelligence').open = true; });
  node('mission-connection-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!active()) return;
    try {
      const endpoint = node('mission-endpoint').value;
      connection = validateLocalMissionConfig({endpoint, model:node('mission-model').value.trim(),
        structuredOutput:endpoint.endsWith('/v1/chat/completions')});
      text('mission-connection-status', words.config);
      render();
    } catch { text('mission-connection-status', words.invalidConfig); }
  });
  node('mission-run-local').addEventListener('click', async () => {
    if (!active() || !mission || !connection || mission.status === 'running') return;
    const config = connection;
    const controller = new AbortController();
    const token = ++serial;
    activeRequest = controller;
    resetHandoff();
    let run;
    try {
      mission = beginMission(mission, {provider:'local', model:config.model});
      run = mission.run.id;
      render();
      const localRequest = await requestForMission();
      const attached = await bindMissionRequest(mission, run, localRequest);
      if (token !== serial || !active()) return;
      mission = attached;
      const result = await runLocalMission(localRequest, config, {authorized:true, signal:controller.signal});
      if (token === serial && active()) {
        localRuns.add(run);
        accept(result, run);
      }
    } catch {
      if (token !== serial || !active()) return;
      if (run) mission = interruptMission(mission, run, 'LOCAL_RESPONSE_FAILED');
      render(words.error);
    } finally { if (token === serial) activeRequest = undefined; }
  });

  const resetRequest = () => { stopRequest(); resetHandoff(); };
  node('mission-pause').addEventListener('click', () => {
    if (!active() || !mission?.run) return;
    resetRequest();
    mission = interruptMission(mission, mission.run.id, 'USER_PAUSED');
    render();
  });
  node('mission-continue').addEventListener('click', () => {
    if (!active() || !mission) return;
    resetRequest();
    mission = continueMission(mission);
    render();
  });
  node('mission-cancel').addEventListener('click', () => {
    if (!active() || !mission) return;
    resetRequest();
    mission = cancelMission(mission);
    render();
  });
  node('mission-revise').addEventListener('click', () => input.focus());
  node('mission-new').addEventListener('click', () => {
    if (!active()) return;
    resetRequest();
    mission = atlas = undefined;
    localRuns.clear();
    input.value = '';
    input.dispatchEvent(new Event('input'));
    render();
    input.focus();
  });
  node('mission-work-download').addEventListener('click', () => {
    const report = currentReport();
    if (active() && report?.work) downloadText(report.work, 'frontier-work-for-review.txt');
  });
  node('mission-export').addEventListener('click', async () => {
    if (!active() || !mission) return;
    const snapshot = mission;
    const token = serial;
    try {
      const exported = await exportMission(snapshot);
      if (token !== serial || !active()) return;
      downloadJSON(typeof exported === 'string' ? JSON.parse(exported) : exported, 'frontier-mission.json');
      text('mission-file-status', words.saved);
    } catch { if (token === serial && active()) text('mission-file-status', words.fileInvalid); }
  });
  node('mission-import').addEventListener('change', async event => {
    const control = event.target;
    const file = control.files[0];
    control.value = '';
    if (!file || !active()) return;
    const attempt = serial;
    try {
      if (file.size > 2*1024*1024) throw new Error('FILE_TOO_LARGE');
      const restored = await importMission(await file.text());
      if (attempt !== serial || !active()) return;
      resetRequest();
      localRuns.clear();
      mission = restored;
      atlas = undefined;
      input.value = mission.ambition;
      input.dispatchEvent(new Event('input'));
      if (mission.status === 'waiting' && mission.request) revealHandoff(mission.request);
      render(words.reopened);
      text('mission-file-status', words.reopened);
      shell.show(node('frontier-mission-panel'), {remember:true});
    } catch { if (attempt === serial && active()) text('mission-file-status', words.fileInvalid); }
  });
  window.addEventListener('frontier:member-lock', () => {
    resetRequest();
    mission = atlas = connection = undefined;
    localRuns.clear();
    node('mission-connection-form').reset();
    node('mission-keeper').open = node('mission-intelligence').open = false;
    text('mission-file-status', '');
    text('mission-connection-status', '');
    render();
  });
  render();
  return {start, setAtlas(record) { atlas = record; }};
}
