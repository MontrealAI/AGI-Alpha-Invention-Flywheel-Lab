import {downloadJSON} from './frontier-goals.mjs';
import {browserModelAvailability, runBrowserStarter} from './frontier-browser-model.mjs';
import {setupExecution} from './frontier-execution.mjs';
import {
  createMission, reviseMission, prepareMission, beginMission, recordMission, interruptMission,
  cancelMission, continueMission, exportMission, importMission, missionPacket, bindMissionRequest,
} from './frontier-mission.mjs';
import {
  createMissionRequest, createMissionPrompt, missionRouteResult, parseMissionResponse, runLocalMission, validateLocalMissionConfig,
} from './frontier-mission-router.mjs';

const messages = {
  en: {
    ready: 'Mission opened on this device.', waiting: 'Assisted mission prepared. No model request has run.',
    running: 'Waiting for your local model…', review: 'Work returned for your review.',
    paused: 'Mission paused. Its ambition and completed work are still here.', canceled: 'Mission canceled.',
    choose: 'Choose intelligence to start work on this ambition. You can also use a qualified capability or continue with an assistant.',
    assisted: 'Review the exact prepared prompt, then bring the answer back here.',
    localNext: 'Review the local result and its assumptions before using it.',
    error: 'The local model did not return a usable response. Check the running service, model name and connection, or continue with an assisted mission.',
    config: 'Local settings saved for this tab. The first mission request will check the connection.', invalidConfig: 'Enter the exact model name and choose a supported runtime.',
    invalid: 'This response does not match the prepared mission or its format.',
    plainInvalid: 'Enter a response or choose a UTF-8 text file of up to 32 KiB.',
    workReview: 'Check the returned work’s sources, calculations and claims before using it.',
    prepareFirst: 'Enter your ambition. Then you can review a brief for ChatGPT.',
    cancelSetupFailed: 'The companion could not confirm cancellation. Reconnect and cancel the pending approval before replacing this mission.',
    browserSource: 'Browser model draft', browserFirst: 'Enter an ambition to try the browser model.',
    browserStarting: 'Preparing the browser’s model…', browserDownloading: value => `Downloading the browser’s model · ${value}`,
    browserRunning: 'The browser’s model is working on your ambition…', browserCanceled: 'The browser model was canceled. Your ambition is still here.',
    browserUnavailable: 'The browser could not complete this request. Try again or continue with another intelligence option.',
    browserWait: 'Finish or cancel the current run and provider setup before starting the browser model.',
    pausedNext: 'Continue when you have the right intelligence or the missing information.',
    canceledNext: 'Open a new mission or resume this one.',
    invalidMission: 'Enter an ambition of up to 24 KiB. Use text you are authorized to process.',
    saved: 'Mission downloaded. It contains your ambition and work.',
    reopened: 'Mission restored. Review its current status before continuing.',
    fileInvalid: 'This file is unreadable, changed or outside the mission format.',
    copy: 'Reviewed prompt copied.', select: 'The reviewed prompt is selected for copying.',
    localSource: 'Local model result', manualSource: 'Assisted result', restoredSource: 'Restored work record', unpublished: 'Verification pending',
    publicReport: 'Read the completed study', publicArtifact: 'Download the verified research tool',
    contextRun: 'Current mission run reference', contextAtlas: 'Public Atlas lead with unverified applicability',
    contextObjective: 'Previous unverified objective', contextAction: 'Previous unverified next action',
    contextWork: 'Excerpt from previous unverified work',
    routes: {direct:'Direct answer',capability:'Existing capability',composition:'Capability composition',adaptation:'Adaptation',
      research:'Frontier research',invention:'New invention',continuing:'Continuing investigation',clarification:'Clarification or abstention'},
  },
  fr: {
    ready: 'Mission ouverte sur cet appareil.', waiting: 'Mission assistée préparée. Aucun modèle n’a été sollicité.',
    running: 'En attente de votre modèle local…', review: 'Travail reçu pour examen.',
    paused: 'Mission en pause. Son ambition et le travail accompli sont conservés.', canceled: 'Mission annulée.',
    choose: 'Choisissez une intelligence pour commencer le travail. Vous pouvez aussi utiliser une capacité qualifiée ou poursuivre avec un assistant.',
    assisted: 'Relisez la consigne préparée, puis rapportez la réponse ici.',
    localNext: 'Examinez le résultat local et ses hypothèses avant de l’utiliser.',
    error: 'Le modèle local n’a pas fourni de réponse exploitable. Vérifiez le service, le nom du modèle et la connexion, ou poursuivez avec une mission assistée.',
    config: 'Paramètres locaux conservés pour cet onglet. La première requête vérifiera la connexion.', invalidConfig: 'Indiquez le nom exact du modèle et choisissez un environnement pris en charge.',
    invalid: 'Cette réponse ne correspond pas à la mission préparée ou au format demandé.',
    plainInvalid: 'Saisissez une réponse ou choisissez un fichier texte UTF-8 d’au plus 32 Kio.',
    workReview: 'Vérifiez les sources, les calculs et les conclusions du travail rapporté avant de l’utiliser.',
    prepareFirst: 'Saisissez votre ambition, puis relisez la consigne à préparer pour ChatGPT.',
    cancelSetupFailed: 'Le compagnon n’a pas pu confirmer l’annulation. Reconnectez-vous et annulez l’approbation en attente avant de remplacer la mission.',
    browserSource: 'Ébauche du modèle du navigateur', browserFirst: 'Saisissez une ambition pour essayer le modèle du navigateur.',
    browserStarting: 'Préparation du modèle du navigateur…', browserDownloading: value => `Téléchargement du modèle du navigateur · ${value}`,
    browserRunning: 'Le modèle du navigateur travaille sur votre ambition…', browserCanceled: 'Le modèle du navigateur a été arrêté. Votre ambition est toujours ici.',
    browserUnavailable: 'Le navigateur n’a pas pu terminer cette demande. Réessayez ou choisissez une autre intelligence.',
    browserWait: 'Terminez ou annulez l’exécution et la configuration du fournisseur avant de lancer le modèle du navigateur.',
    pausedNext: 'Poursuivez lorsque l’intelligence ou les renseignements nécessaires sont disponibles.',
    canceledNext: 'Ouvrez une nouvelle mission ou reprenez celle-ci.',
    invalidMission: 'Saisissez une ambition d’au plus 24 Kio. Utilisez du texte que vous êtes autorisé à traiter.',
    saved: 'Mission téléchargée. Le fichier contient votre ambition et votre travail.',
    reopened: 'Mission rétablie. Examinez son état avant de poursuivre.',
    fileInvalid: 'Ce fichier est illisible, a été modifié ou ne respecte pas le format de mission.',
    copy: 'Consigne relue copiée.', select: 'La consigne relue est sélectionnée pour la copier.',
    localSource: 'Résultat du modèle local', manualSource: 'Résultat assisté', restoredSource: 'Travail rétabli', unpublished: 'Vérification à venir',
    publicReport: 'Lire l’étude terminée', publicArtifact: 'Télécharger l’outil de recherche vérifié',
    contextRun: 'Identifiant de l’exécution en cours', contextAtlas: 'Piste publique de l’Atlas dont l’applicabilité reste à vérifier',
    contextObjective: 'Objectif précédent à vérifier', contextAction: 'Prochaine action précédente à vérifier',
    contextWork: 'Extrait du travail précédent à vérifier',
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
const encoder = new TextEncoder();
const maxReturnedBytes = 32 * 1024;
const browserModelId = 'browser-gemini-nano';

function downloadText(value, filename) {
  const url = URL.createObjectURL(new Blob([value], {type:'text/plain;charset=utf-8'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function structuredReply(raw) {
  const candidate = raw.trim().replace(/^\x60{3}(?:json)?\s*([\s\S]*?)\s*\x60{3}$/iu, '$1');
  try {
    const envelope = JSON.parse(candidate);
    if (typeof envelope?.text === 'string' && !envelope.schema && envelope.text.includes(missionRouteResult)) return envelope.text;
    if (envelope?.schema === missionRouteResult || (envelope?.requestId && envelope?.route)) return candidate;
  } catch {
    if (candidate.startsWith('{') && candidate.includes(missionRouteResult)) return candidate;
  }
  return undefined;
}

function publicRuns() {
  try {
    const entries = JSON.parse(node('mission-public-runs').content.textContent);
    return entries.filter(row => typeof row.ambition === 'string' && typeof row.en === 'string' && typeof row.fr === 'string'
      && /^frontier-[a-z0-9.-]+\.zip$/u.test(row.download)
      && /^https:\/\/github\.com\/MontrealAI\/AGI-Alpha-Invention-Flywheel-Lab\/blob\/[0-9a-f]{40}\/publication\/(universal|mission-executor)\/[a-zA-Z0-9/._-]+\.md$/u.test(row.report)
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
  let browserCheck = 0;
  const active = () => !member.hidden;
  const execution = setupExecution(member, language, {
    currentAmbition: () => mission?.ambition,
    currentMission: () => ['canceled','running'].includes(mission?.status) ? undefined : mission,
    returnToMission: () => shell.show(node('frontier-mission-panel'), {remember:true}),
    showSetup() {
      node('mission-intelligence').open = true;
      shell.show(node('mission-intelligence'), {remember:true});
    },
    onOpen({ambition, original_ambition: originalAmbition = ambition, language: missionLanguage}) {
      if (mission?.ambition === ambition && mission.originalAmbition === originalAmbition && mission.language === missionLanguage) {
        shell.show(node('frontier-mission-panel'), {remember:true});
        return;
      }
      stopRequest();
      resetHandoff();
      mission = createMission(originalAmbition, {language:missionLanguage === 'fr' ? 'fr' : missionLanguage === 'en' ? 'en' : language});
      if (originalAmbition !== ambition) mission = reviseMission(mission, ambition);
      atlas = undefined;
      input.value = ambition;
      input.dispatchEvent(new Event('input'));
      render();
      shell.show(node('frontier-mission-panel'), {remember:true});
    },
  });

  function currentReport() {
    return mission?.reports.findLast(report => report.revision === mission.revision);
  }

  function resetHandoff() {
    request = undefined;
    for (const id of ['mission-prompt','mission-reply','mission-import-artifact']) node(id).value = '';
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
    show('mission-checkpoint', Boolean(mission));
    execution.updateControls();
    if (!mission) {
      delete panel.dataset.state;
      delete panel.dataset.route;
      for (const key of ['mission-ambition','mission-next','mission-status','mission-original','mission-objective','mission-route','mission-work','mission-published-summary']) text(key, '');
      for (const key of ['mission-published-links','mission-capabilities','mission-assumptions']) node(key).replaceChildren();
      node('mission-returned-files').replaceChildren();
      show('mission-returned-files', false);
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
    const observed = localRuns.has(report?.runId);
    const browserReport = observed && report.model === browserModelId;
    const source = report?.provider === 'assisted' ? words.manualSource
      : browserReport ? words.browserSource : observed ? words.localSource : words.restoredSource;
    const labels = [source, observed && !browserReport ? report.model : null, words.unpublished].filter(Boolean);
    const running = state === 'running' && mission.run.model === browserModelId;
    text('mission-status', message ?? (report && state === 'review' ? labels.join(' · ') : running ? words.browserRunning : words[state]));
    text('mission-next', state === 'canceled' ? words.canceledNext : state === 'paused' ? words.pausedNext
      : state === 'waiting' ? words.assisted : state === 'running' ? words.localNext : report?.nextAction ?? words.choose);
    show('mission-understanding', Boolean(report));
    text('mission-route', words.routes[route]);
    text('mission-objective', report?.objective);
    text('mission-work', report?.work);
    show('mission-work-panel', Boolean(report?.work));
    const files = mission.reports.filter(item => item.revision === mission.revision)
      .flatMap(item => item.artifacts ?? []).filter(item => ['assisted-text','browser-text'].includes(item?.kind) && typeof item.content === 'string');
    show('mission-returned-files', files.length > 0);
    node('mission-returned-files').replaceChildren(...files.map(file => {
      const row = document.createElement('li');
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      const preview = document.createElement('pre');
      const download = document.createElement('button');
      summary.textContent = file.label;
      preview.textContent = file.content;
      download.type = 'button';
      download.className = 'quiet';
      download.textContent = node('mission-work-download').textContent;
      download.addEventListener('click', () => {
        if (active()) downloadText(file.content, 'frontier-assisted-work.txt');
      });
      details.append(summary, preview, download);
      row.append(details);
      return row;
    }));
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
    const published = priorRuns.filter(row => row.ambition === mission.ambition.trim());
    show('mission-published', published.length > 0);
    text('mission-published-summary', published.map(row => row[language]).join(' '));
    node('mission-published-links').replaceChildren();
    for (const row of published) {
      const label = row.capability[language];
      for (const [href, title] of [[row.report, words.publicReport], [row.download, words.publicArtifact]]) {
        const link = document.createElement('a');
        link.href = href;
        link.textContent = `${title} · ${label}`;
        if (href === row.download) link.download = '';
        node('mission-published-links').append(link);
      }
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
    browserBusy(false);
  }

  function afterPendingSetup(action) {
    if (!execution.hasPendingSetup()) { action(); return; }
    const token = ++serial;
    void execution.cancelPendingSetup().then(canceled => {
      if (token !== serial || !active()) return;
      if (canceled) action();
      else render(words.cancelSetupFailed);
    });
  }

  function start(ambition, {execute = false} = {}) {
    if (!active()) return false;
    try {
      const updated = mission ? (mission.ambition !== ambition ? reviseMission(mission, ambition) : mission)
        : createMission(ambition, {language});
      atlas = undefined;
      const open = () => {
        if (updated !== mission) {
          stopRequest();
          resetHandoff();
          execution.clearView({preservePrevious:true});
          mission = updated;
        }
        render();
        shell.show(node('frontier-mission-panel'), {remember:true});
        if (execute) execution.activate(ambition);
        else execution.clearView();
      };
      if (updated !== mission) afterPendingSetup(open);
      else open();
      return true;
    } catch {
      text('goal-status', words.invalidMission);
      return false;
    }
  }

  async function requestForMission() {
    const packet = missionPacket(mission);
    const context = [`${words.contextRun}: ${packet.runId}`];
    if (atlas) context.push(`${words.contextAtlas}: ${atlas.title} · ${atlas.evidence} · ${atlas.url}`);
    if (packet.previousReport) {
      const previous = packet.previousReport;
      context.push(`${words.contextObjective}: ${previous.objective.slice(0,450)}`);
      context.push(`${words.contextAction}: ${previous.nextAction.slice(0,450)}`);
      if (previous.work) context.push(`${words.contextWork}: ${previous.work.slice(0,450)}`);
    }
    const {missionId, revision, language, originalAmbition, ambition} = packet;
    return createMissionRequest({missionId, revision, language, originalAmbition, ambition, context, capabilities});
  }

  function accept(receipt, runId) {
    const route = receipt.route === 'clarify' ? 'clarification' : receipt.route;
    const {objective, nextAction, assumptions, work, capabilityIds, artifacts} = receipt;
    mission = recordMission(mission, runId, {route, objective, nextAction,
      ...(assumptions && {assumptions}), ...(work && {work}), ...(capabilityIds && {capabilityIds}), ...(artifacts && {artifacts})});
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

  async function prepareAssistance() {
    if (!active()) return;
    if (!mission) {
      shell.show(input, {remember:true});
      text('goal-status', words.prepareFirst);
      input.focus();
      return;
    }
    if (node('mission-prepare').disabled) {
      shell.show(node('frontier-mission-panel'), {remember:true});
      return;
    }
    const previous = mission;
    if (execution.hasPendingSetup() && !await execution.cancelPendingSetup()) {
      if (active() && previous === mission) render(words.cancelSetupFailed);
      return;
    }
    if (!active() || previous !== mission) return;
    shell.show(node('frontier-mission-panel'), {remember:true});
    execution.clearWaiting();
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
  }
  node('mission-prepare').addEventListener('click', prepareAssistance);
  for (const button of member.querySelectorAll('[data-frontier-assisted]')) button.addEventListener('click', prepareAssistance);

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
    const raw = node('mission-reply').value;
    const claimed = structuredReply(raw);
    try {
      const result = claimed === undefined ? await returnedText(raw) : await parseMissionResponse(claimed, request, {mode:'manual'});
      if (token === serial && active()) accept(result, run);
    } catch { if (token === serial && active()) render(claimed === undefined ? words.plainInvalid : words.invalid); }
  });

  async function returnedText(content, filename, kind = 'assisted-text') {
    const bytes = encoder.encode(content);
    if (!content.trim() || bytes.length > maxReturnedBytes) throw new Error('ASSISTED_TEXT');
    const report = {route:'continuing', objective:mission.ambition, nextAction:words.workReview};
    if (!filename && bytes.length <= 12 * 1024) return {...report, work:content};
    const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), value => value.toString(16).padStart(2, '0')).join('');
    const label = filename?.replace(/[\u0000-\u001f\u007f]/gu, '').slice(0, 120).trim()
      || (kind === 'browser-text' ? words.browserSource : words.manualSource);
    return {...report, artifacts:[{label, kind, sha256, content}]};
  }

  node('mission-import-artifact').addEventListener('change', async event => {
    const control = event.target;
    const file = control.files[0];
    control.value = '';
    if (!file || !active() || !request || !mission?.run) return;
    const token = ++serial;
    const run = mission.run.id;
    try {
      if (file.size > maxReturnedBytes) throw new Error('ASSISTED_FILE_SIZE');
      const content = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(await file.arrayBuffer());
      if (token !== serial || !active()) return;
      const result = await returnedText(content, file.name);
      if (token === serial && active()) accept(result, run);
    } catch { if (token === serial && active()) render(words.plainInvalid); }
  });

  async function checkBrowserStarter() {
    const check = ++browserCheck;
    const state = await browserModelAvailability(mission?.language ?? language);
    if (check === browserCheck && active()) show('intelligence-browser', state !== 'unavailable');
  }

  function browserBusy(busy) {
    node('intelligence-browser-start').disabled = busy;
    show('intelligence-browser-cancel', busy);
  }

  node('intelligence-browser-start').addEventListener('click', async () => {
    if (!active()) return;
    if (!mission) {
      shell.show(input, {remember:true});
      text('goal-status', words.browserFirst);
      input.focus();
      return;
    }
    if (['canceled','running'].includes(mission.status) || execution.hasActiveWork() || execution.hasPendingSetup()) {
      text('intelligence-browser-status', words.browserWait);
      return;
    }
    execution.clearWaiting();
    resetHandoff();
    const controller = new AbortController();
    const token = ++serial;
    const snapshot = mission;
    activeRequest = controller;
    browserBusy(true);
    text('intelligence-browser-status', words.browserStarting);
    let run;
    try {
      mission = beginMission(mission, {provider:'local', model:browserModelId});
      run = mission.run.id;
      render();
      const result = await runBrowserStarter({ambition:snapshot.ambition, language:snapshot.language, signal:controller.signal,
        onProgress(value) {
          if (token !== serial || !active()) return;
          const message = value < 1 ? words.browserDownloading(new Intl.NumberFormat(language, {style:'percent'}).format(value)) : words.browserRunning;
          if (node('intelligence-browser-status').textContent !== message) text('intelligence-browser-status', message);
        }});
      if (token !== serial || !active()) return;
      const report = await returnedText(result, undefined, 'browser-text');
      if (token !== serial || !active()) return;
      localRuns.add(run);
      accept(report, run);
      text('intelligence-browser-status', words.review);
      shell.show(node('frontier-mission-panel'), {remember:true});
    } catch {
      if (token !== serial || !active()) return;
      if (run) mission = interruptMission(mission, run, 'BROWSER_MODEL_FAILED');
      render(words.browserUnavailable);
      text('intelligence-browser-status', words.browserUnavailable);
    } finally {
      if (token === serial) { activeRequest = undefined; browserBusy(false); }
    }
  });

  node('intelligence-browser-cancel').addEventListener('click', () => {
    if (!active() || mission?.status !== 'running' || mission.run.model !== browserModelId) return;
    stopRequest();
    mission = interruptMission(mission, mission.run.id, 'USER_PAUSED');
    render(words.browserCanceled);
    text('intelligence-browser-status', words.browserCanceled);
  });
  window.addEventListener('frontier:member-enter', checkBrowserStarter);
  node('mission-intelligence').addEventListener('toggle', () => {
    if (active() && node('mission-intelligence').open) void checkBrowserStarter();
  });

  node('mission-configure').addEventListener('click', () => {
    node('mission-intelligence').open = true;
    void checkBrowserStarter();
  });
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
    execution.clearWaiting();
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
    afterPendingSetup(() => {
      execution.clearWaiting();
      resetRequest();
      mission = cancelMission(mission);
      render();
    });
  });
  node('mission-revise').addEventListener('click', () => input.focus());
  node('mission-new').addEventListener('click', () => {
    if (!active()) return;
    afterPendingSetup(() => {
      resetRequest();
      mission = atlas = undefined;
      execution.clearView();
      localRuns.clear();
      input.value = '';
      input.dispatchEvent(new Event('input'));
      render();
      input.focus();
    });
  });
  node('mission-work-download').addEventListener('click', () => {
    const report = currentReport();
    if (active() && report?.work) downloadText(report.work, 'frontier-work-for-review.txt');
  });
  async function downloadMission(feedback) {
    if (!active() || !mission) return;
    const snapshot = mission;
    const token = serial;
    try {
      const exported = await exportMission(snapshot);
      if (token !== serial || !active()) return;
      downloadJSON(typeof exported === 'string' ? JSON.parse(exported) : exported, 'frontier-mission.json');
      text(feedback, words.saved);
    } catch { if (token === serial && active()) text(feedback, words.fileInvalid); }
  }
  node('mission-export').addEventListener('click', () => downloadMission('mission-file-status'));
  node('mission-checkpoint').addEventListener('click', () => downloadMission('mission-checkpoint-status'));
  node('mission-restore').addEventListener('click', () => {
    if (active()) node('mission-keeper').open = true;
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
      afterPendingSetup(() => {
        resetRequest();
        localRuns.clear();
        mission = restored;
        execution.clearView();
        atlas = undefined;
        input.value = mission.ambition;
        input.dispatchEvent(new Event('input'));
        if (mission.status === 'waiting' && mission.request) revealHandoff(mission.request);
        render(words.reopened);
        text('mission-file-status', words.reopened);
        shell.show(node('frontier-mission-panel'), {remember:true});
        void checkBrowserStarter();
      });
    } catch { if (attempt === serial && active()) text('mission-file-status', words.fileInvalid); }
  });
  window.addEventListener('frontier:member-lock', () => {
    resetRequest();
    mission = atlas = connection = undefined;
    localRuns.clear();
    browserCheck++;
    show('intelligence-browser', false);
    node('mission-connection-form').reset();
    node('mission-keeper').open = node('mission-intelligence').open = false;
    text('mission-file-status', '');
    text('mission-connection-status', '');
    text('mission-checkpoint-status', '');
    text('intelligence-browser-status', '');
    render();
  });
  render();
  return {start, setAtlas(record) { atlas = record; }};
}
