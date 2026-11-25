import {downloadJSON} from './frontier-goals.mjs';
import {browserModelAvailability, runBrowserStarter} from './frontier-browser-model.mjs';
import {setupExecution} from './frontier-execution.mjs';
import {
  createMission, reviseMission, prepareMission, beginMission, recordMission, interruptMission,
  cancelMission, continueMission, exportMission, importMission, missionPacket, bindMissionRequest,
  addMissionInstruction, checkMissionDocuments, setMissionDocuments, maxDocuments, maxDocumentBytes,
} from './frontier-mission.mjs';
import {
  createMissionRequest, createMissionPrompt, runLocalMission, validateLocalMissionConfig,
} from './frontier-mission-router.mjs';
import {createAssistedBrief, maximumReturnedBytes, readAssistedReply, renderAssistedWork, workPreview} from './frontier-assisted-work.mjs';

const messages = {
  en: {
    ready: 'Mission opened on this device.', waiting: 'Assisted mission prepared. No model request has run.',
    running: 'Waiting for your local model…', review: 'Work returned for your review.',
    paused: 'Mission paused. Its ambition and completed work are still here.', canceled: 'Mission canceled.',
    choose: 'Choose intelligence to start work on this ambition. You can also use a qualified capability or continue with an assistant.',
    assisted: 'Review your brief, then bring the work back here.',
    localNext: 'Review the local result and its assumptions before using it.',
    error: 'The local model did not return a usable response. Check the running service, model name and connection, or continue with an assisted mission.',
    config: 'Local settings saved for this tab. The first mission request will check the connection.', invalidConfig: 'Enter the exact model name and choose a supported runtime.',
    invalid: 'This structured response does not match the prepared mission or is incomplete. You can keep its content here as unverified work.',
    plainInvalid: 'Paste a response or choose a readable UTF-8 text file of up to 32 KiB.',
    workReview: 'Review the work, then continue from the next useful calculation, source check or test.',
    originalResponse: 'Original assistant response', fileDownload: 'Download original text',
    prepareFirst: 'Enter your ambition. Then you can review a brief for ChatGPT.',
    cancelSetupFailed: 'The companion could not confirm cancellation. Reconnect and cancel the pending approval before replacing this mission.',
    browserSource: 'Browser model draft', browserFirst: 'Enter an ambition to try the browser model.',
    browserStarting: 'Preparing the browser’s model…', browserDownloading: value => `Downloading the browser’s model · ${value}`,
    browserRunning: 'The browser’s model is working on your ambition…', browserCanceled: 'The browser model was canceled. Your ambition is still here.',
    browserUnavailable: 'The browser could not complete this request. Try again or continue with another intelligence option.',
    browserUnsupported: 'This browser has no supported on-device model available here.',
    browserContext: 'This mission exceeds the browser model’s context. Choose a companion model or review an assisted brief.',
    browserUnverified: 'This browser did not pass the on-device model check. Your ambition is ready for another intelligence option.',
    browserWait: 'Finish or cancel the current run and provider setup before starting the browser model.',
    pausedNext: 'Continue when you have the right intelligence or the missing information.',
    canceledNext: 'Open a new mission or resume this one.',
    invalidMission: 'Enter an ambition of up to 24 KiB. Use text you are authorized to process.',
    saved: 'Mission downloaded. It contains your ambition and work.',
    reopened: 'Mission restored. Review its current status before continuing.',
    fileInvalid: 'This file is unreadable, changed or outside the mission format.',
    copy: 'Reviewed brief copied.', select: 'The reviewed brief is selected for copying.',
    localSource: 'Local model result', manualSource: 'Assisted result', restoredSource: 'Restored work record', unpublished: 'Verification pending',
    publicReport: 'Read the completed study', publicArtifact: 'Download the verified research tool',
    contextRun: 'Current mission run reference', contextAtlas: 'Public Atlas lead with unverified applicability',
    contextObjective: 'Previous unverified objective', contextAction: 'Previous unverified next action',
    contextWork: 'Excerpt from previous unverified work',
    contextInstruction: 'Member’s latest instruction',
    nextInstruction: 'Choose how to continue with this instruction.',
    invalidInstruction: 'Enter an instruction of up to 2 KiB.',
    fileInput: 'Use up to eight nonempty UTF-8 text files. The total limit is 96 KiB.',
    localFiles: 'Use these files with your private companion, or remove them to use another intelligence option.',
    fileReady: 'Source files ready. Confirm below to share them with the private companion.',
    fileChanged: 'Continue the mission to use your updated sources.',
    restoreFiles: 'The companion holds these source files for this mission.',
    continueBusy: 'The current operation is still being stopped. Try again after it settles.',
    routes: {direct:'Direct answer',capability:'Existing capability',composition:'Capability composition',adaptation:'Adaptation',
      research:'Frontier research',invention:'New invention',continuing:'Continuing investigation',clarification:'Clarification or abstention'},
  },
  fr: {
    ready: 'Mission ouverte sur cet appareil.', waiting: 'Mission assistée préparée. Aucun modèle n’a été sollicité.',
    running: 'En attente de votre modèle local…', review: 'Travail reçu pour examen.',
    paused: 'Mission en pause. Son ambition et le travail accompli sont conservés.', canceled: 'Mission annulée.',
    choose: 'Choisissez une intelligence pour commencer le travail. Vous pouvez aussi utiliser une capacité qualifiée ou poursuivre avec un assistant.',
    assisted: 'Relisez le résumé de mission, puis rapportez le travail ici.',
    localNext: 'Examinez le résultat local et ses hypothèses avant de l’utiliser.',
    error: 'Le modèle local n’a pas fourni de réponse exploitable. Vérifiez le service, le nom du modèle et la connexion, ou poursuivez avec une mission assistée.',
    config: 'Paramètres locaux conservés pour cet onglet. La première requête vérifiera la connexion.', invalidConfig: 'Indiquez le nom exact du modèle et choisissez un environnement pris en charge.',
    invalid: 'Cette réponse structurée ne correspond pas à la mission préparée ou elle est incomplète. Vous pouvez en conserver le contenu ici comme travail à vérifier.',
    plainInvalid: 'Collez une réponse ou choisissez un fichier texte UTF-8 lisible d’au plus 32 Kio.',
    workReview: 'Examinez le travail, puis poursuivez avec le prochain calcul, la prochaine vérification de source ou le prochain essai utile.',
    originalResponse: 'Réponse originale de l’assistant', fileDownload: 'Télécharger le texte original',
    prepareFirst: 'Saisissez votre ambition, puis relisez la consigne à préparer pour ChatGPT.',
    cancelSetupFailed: 'Le compagnon n’a pas pu confirmer l’annulation. Reconnectez-vous et annulez l’approbation en attente avant de remplacer la mission.',
    browserSource: 'Ébauche du modèle du navigateur', browserFirst: 'Saisissez une ambition pour essayer le modèle du navigateur.',
    browserStarting: 'Préparation du modèle du navigateur…', browserDownloading: value => `Téléchargement du modèle du navigateur · ${value}`,
    browserRunning: 'Le modèle du navigateur travaille sur votre ambition…', browserCanceled: 'Le modèle du navigateur a été arrêté. Votre ambition est toujours ici.',
    browserUnavailable: 'Le navigateur n’a pas pu terminer cette demande. Réessayez ou choisissez une autre intelligence.',
    browserUnsupported: 'Ce navigateur ne dispose pas d’un modèle intégré pris en charge ici.',
    browserContext: 'Cette mission dépasse le contexte du modèle intégré. Choisissez un modèle du compagnon ou préparez une mission assistée.',
    browserUnverified: 'Le navigateur n’a pas réussi le test du modèle local. Votre ambition est prête pour une autre intelligence.',
    browserWait: 'Terminez ou annulez l’exécution et la configuration du fournisseur avant de lancer le modèle du navigateur.',
    pausedNext: 'Poursuivez lorsque l’intelligence ou les renseignements nécessaires sont disponibles.',
    canceledNext: 'Ouvrez une nouvelle mission ou reprenez celle-ci.',
    invalidMission: 'Saisissez une ambition d’au plus 24 Kio. Utilisez du texte que vous êtes autorisé à traiter.',
    saved: 'Mission téléchargée. Le fichier contient votre ambition et votre travail.',
    reopened: 'Mission rétablie. Examinez son état avant de poursuivre.',
    fileInvalid: 'Ce fichier est illisible, a été modifié ou ne respecte pas le format de mission.',
    copy: 'Résumé relu copié.', select: 'Le résumé relu est sélectionné pour la copie.',
    localSource: 'Résultat du modèle local', manualSource: 'Résultat assisté', restoredSource: 'Travail rétabli', unpublished: 'Vérification à venir',
    publicReport: 'Lire l’étude terminée', publicArtifact: 'Télécharger l’outil de recherche vérifié',
    contextRun: 'Identifiant de l’exécution en cours', contextAtlas: 'Piste publique de l’Atlas dont l’applicabilité reste à vérifier',
    contextObjective: 'Objectif précédent à vérifier', contextAction: 'Prochaine action précédente à vérifier',
    contextWork: 'Extrait du travail précédent à vérifier',
    contextInstruction: 'Dernière consigne du membre',
    nextInstruction: 'Choisissez comment poursuivre avec cette consigne.',
    invalidInstruction: 'Saisissez une consigne d’au plus 2 Kio.',
    fileInput: 'Utilisez au plus huit fichiers texte UTF-8 non vides (96 Kio au total).',
    localFiles: 'Utilisez ces fichiers avec votre compagnon privé ou retirez-les pour choisir une autre intelligence.',
    fileReady: 'Les fichiers sources sont prêts. Confirmez leur transmission au compagnon privé ci-dessous.',
    fileChanged: 'Poursuivez la mission pour utiliser les sources mises à jour.',
    restoreFiles: 'Le compagnon conserve ces fichiers sources pour la mission.',
    continueBusy: 'L’opération en cours s’arrête. Réessayez une fois l’arrêt confirmé.',
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
const browserModelId = 'browser-gemini-nano';

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
  let mission, request, connection, activeRequest, atlas, unmatchedWork, serial = 0;
  let entryDocuments, recoveredDocuments, fileSerial = 0, editingAmbition = false;
  let browserCheck = 0;
  const active = () => !member.hidden;
  const files = () => mission ? mission.documents ?? recoveredDocuments ?? [] : entryDocuments ?? [];
  const settings = node('mission-intelligence');

  function showSetup() {
    if (mission) {
      const slot = node('mission-inline-intelligence');
      if (settings.parentElement !== slot) slot.append(settings);
      settings.open = true;
      shell.show(node('frontier-mission-panel'), {remember:true,focus:false});
    } else {
      if (settings.parentElement !== node('intelligence-settings-slot')) node('intelligence-settings-slot').append(settings);
      settings.open = true;
      shell.show(settings, {remember:true});
    }
  }

  window.addEventListener('frontier:member-view', ({detail}) => {
    if (detail === 'my-intelligence' && settings.parentElement !== node('intelligence-settings-slot')) {
      node('intelligence-settings-slot').append(settings);
      settings.open = true;
    }
  });
  const execution = setupExecution(member, language, {
    currentAmbition: () => mission?.ambition,
    currentMission: () => ['canceled','running'].includes(mission?.status) ? undefined : mission,
    localFilesConsent: () => !files().length || node('mission-document-consent').checked,
    filesAttached: () => files().length > 0,
    returnToMission: () => shell.show(node('frontier-mission-panel'), {remember:true}),
    showSetup,
    onOpen({ambition, original_ambition: originalAmbition = ambition, language: missionLanguage, instruction, documents}) {
      stopRequest();
      resetHandoff();
      mission = createMission(originalAmbition, {language:missionLanguage === 'fr' ? 'fr' : missionLanguage === 'en' ? 'en' : language});
      if (originalAmbition !== ambition) mission = reviseMission(mission, ambition);
      if (instruction) mission = addMissionInstruction(mission, instruction);
      recoveredDocuments = Array.isArray(documents) ? documents : undefined;
      entryDocuments = undefined;
      fileSerial++;
      node('mission-document-consent').checked = false;
      node('mission-follow-up').value = '';
      editingAmbition = false;
      atlas = undefined;
      input.value = ambition;
      input.dispatchEvent(new Event('input'));
      render();
      text('mission-document-status', recoveredDocuments?.length ? words.restoreFiles : '');
      shell.show(node('frontier-mission-panel'), {remember:true});
    },
  });

  function currentReport() {
    return mission?.reports.findLast(report => report.revision === mission.revision);
  }

  function renderFiles() {
    const documents = files();
    const reports = documents.map(source => {
      const row = document.createElement('li');
      row.textContent = source.name;
      return row;
    });
    node('mission-document-list').replaceChildren(...reports);
    show('mission-document-scope', documents.length > 0);
    show('mission-documents-remove', documents.length > 0);
    const report = currentReport();
    show('mission-use-returned', Boolean(report?.provider === 'assisted' && report.work && !documents.length));
  }

  function changeFiles(documents) {
    const next = mission ? setMissionDocuments(mission, documents) : undefined;
    afterPendingSetup(() => {
      if (next && ['running','waiting'].includes(next.status)) {
        stopRequest();
        resetHandoff();
        mission = continueMission(interruptMission(next, next.run.id, 'SOURCE_CHANGED'));
      } else if (next) mission = next;
      else entryDocuments = documents;
      recoveredDocuments = undefined;
      node('mission-document-consent').checked = false;
      render();
      text('mission-document-status', documents.length ? words.fileReady : mission ? words.fileChanged : '');
    });
  }

  node('mission-documents').addEventListener('change', async event => {
    const selected = Array.from(event.target.files);
    event.target.value = '';
    if (!active() || !selected.length) return;
    const ticket = ++fileSerial;
    const id = mission?.id;
    try {
      if (selected.length > maxDocuments || selected.reduce((total, file) => total + file.size, 0) > maxDocumentBytes
        || selected.some(file => !/\.(txt|md|csv|tsv|json)$/iu.test(file.name))) throw new Error('MISSION_DOCUMENTS');
      const decoder = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true});
      const documents = await Promise.all(selected.map(async file => ({name:file.name, text:decoder.decode(await file.arrayBuffer())})));
      if (ticket !== fileSerial || !active() || mission?.id !== id) return;
      // Apply the same validation to files picked before and after activating a mission.
      checkMissionDocuments(documents);
      changeFiles(documents);
    } catch {
      if (ticket === fileSerial && active()) text('mission-document-status', words.fileInput);
    }
  });

  node('mission-documents-remove').addEventListener('click', () => {
    if (!active()) return;
    fileSerial++;
    changeFiles([]);
    node('mission-documents').focus();
  });

  node('mission-use-returned').addEventListener('click', () => {
    const report = currentReport();
    if (!active() || report?.provider !== 'assisted' || !report.work || files().length) return;
    try {
      changeFiles([{name:'returned-assisted-work.md',text:report.work}]);
      node('mission-files').open = true;
      node('mission-document-consent').focus();
    } catch { text('mission-document-status', words.fileInput); }
  });

  function activateWork({preferred, continuation = false} = {}) {
    if (!mission || mission.status === 'running' || mission.status === 'canceled') return;
    if (files().length && !node('mission-document-consent').checked) {
      node('mission-files').open = true;
      showSetup();
      render(words.localFiles);
      return;
    }
    if (!files().length && preferred === 'assisted') { void prepareAssistance(); return; }
    if (!files().length && preferred === browserModelId) { node('intelligence-browser-start').click(); return; }
    if (!files().length && connection && !execution.hasPreferredRoute()) { void runConfiguredModel(); return; }
    if (!execution.hasPreferredRoute()) showSetup();
    void execution.activate(mission.ambition, {continuation});
  }

  function resetHandoff() {
    request = undefined;
    for (const id of ['mission-prompt','mission-reply','mission-import-artifact']) node(id).value = '';
    node('mission-share').checked = false;
    node('mission-technical').checked = false;
    resetAssistedImport();
    node('mission-handoff').open = false;
    show('mission-handoff', false);
    authorizeShare();
  }

  function authorizeShare() {
    const permitted = Boolean(request && node('mission-share').checked && active());
    for (const id of ['mission-copy','mission-prompt-download']) node(id).disabled = !permitted;
    show('mission-assistant', permitted);
    show('mission-codex', permitted);
  }

  function render(message) {
    const panel = node('frontier-mission-panel');
    panel.hidden = !mission;
    node('mission-export').disabled = !mission;
    show('mission-return', Boolean(mission));
    show('mission-reopen-current', Boolean(mission));
    show('mission-checkpoint', Boolean(mission));
    show('mission-entry', !mission || editingAmbition);
    const filesSlot = node(mission && !editingAmbition ? 'mission-inline-files' : 'mission-entry-files');
    if (node('mission-files').parentElement !== filesSlot) filesSlot.append(node('mission-files'));
    renderFiles();
    show('mission-follow-up-form', Boolean(mission && mission.status !== 'canceled'));
    show('mission-dialogue', Boolean(mission?.turns?.length));
    node('mission-dialogue-list').replaceChildren(...(mission?.turns ?? []).map(turn => {
      const item = document.createElement('li');
      item.textContent = turn.instruction;
      return item;
    }));
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
      : state === 'waiting' ? words.assisted : state === 'running' ? words.localNext
      : state === 'ready' && missionPacket(mission).instruction ? words.nextInstruction : report?.nextAction ?? words.choose);
    show('mission-understanding', Boolean(report));
    text('mission-route', words.routes[route]);
    text('mission-objective', report?.objective);
    renderAssistedWork(node('mission-work'), report?.work);
    show('mission-work-panel', Boolean(report?.work));
    show('mission-continue-assisted', report?.provider === 'assisted' && state === 'review');
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
      download.textContent = words.fileDownload;
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

  function afterPendingSetup(action, {stopWork = false} = {}) {
    const stopping = stopWork === 'cancel' ? 'cancel' : 'pause';
    if (!execution.hasPendingSetup() && (!stopWork || !execution.hasActiveWork(stopping))) { action(); return; }
    const token = ++serial;
    void (async () => await execution.cancelPendingSetup() && (!stopWork || await execution.pauseActive(stopping)))().then(canceled => {
      if (token !== serial || !active()) return;
      if (canceled) action();
      else render(words.continueBusy);
    });
  }

  function start(ambition, {execute = false, atlasLead} = {}) {
    if (!active()) return false;
    try {
      let updated = mission ? (mission.ambition !== ambition ? reviseMission(mission, ambition) : mission)
        : createMission(ambition, {language});
      if (!mission && entryDocuments) updated = setMissionDocuments(updated, entryDocuments);
      const open = () => {
        if (updated !== mission) {
          stopRequest();
          resetHandoff();
          execution.clearView({preservePrevious:true});
          mission = updated;
        }
        editingAmbition = false;
        entryDocuments = undefined;
        atlas = atlasLead;
        render();
        shell.show(node('frontier-mission-panel'), {remember:true});
        if (execute) activateWork();
        else execution.clearView();
      };
      if (updated !== mission) afterPendingSetup(open, {stopWork:true});
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
    const {missionId, revision, language, originalAmbition, ambition, instruction} = packet;
    if (instruction) context.push(words.contextInstruction, instruction);
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
    if (request?.requestId !== prepared.requestId) {
      resetHandoff();
      request = prepared;
      updateAssistedBrief();
    }
    const handoff = node('mission-handoff');
    handoff.hidden = false;
    handoff.open = true;
  }

  function updateAssistedBrief() {
    if (!request) return;
    const context = request.context.filter(value => !value.startsWith(`${words.contextRun}: `));
    node('mission-prompt').value = node('mission-technical').checked ? createMissionPrompt(request)
      : createAssistedBrief(request, context, Boolean(mission.reports.length));
    node('mission-share').checked = false;
    authorizeShare();
  }

  async function prepareAssistance() {
    if (!active()) return;
    if (!mission) {
      shell.show(input, {remember:true});
      text('goal-status', words.prepareFirst);
      input.focus();
      return;
    }
    if (files().length) { render(words.localFiles); return; }
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
  node('mission-continue-assisted').addEventListener('click', prepareAssistance);
  for (const button of member.querySelectorAll('[data-frontier-assisted]')) button.addEventListener('click', prepareAssistance);

  node('mission-technical').addEventListener('change', updateAssistedBrief);
  node('mission-share').addEventListener('change', authorizeShare);
  node('mission-copy').addEventListener('click', async () => {
    if (!active() || !request || !node('mission-share').checked) return;
    const token = serial;
    try {
      await navigator.clipboard.writeText(node('mission-prompt').value);
      if (token === serial && active()) text('mission-handoff-status', words.copy);
    } catch {
      if (token !== serial || !active()) return;
      node('mission-prompt').focus();
      node('mission-prompt').select();
      text('mission-handoff-status', words.select);
    }
  });
  node('mission-prompt-download').addEventListener('click', () => {
    if (active() && request && node('mission-share').checked) downloadText(node('mission-prompt').value, 'frontier-mission-brief.txt');
  });

  function resetAssistedImport() {
    unmatchedWork = undefined;
    show('mission-keep-unverified', false);
    text('mission-handoff-status', '');
  }

  const canImportAssisted = () => active() && request && mission?.request?.requestId === request.requestId
    && mission.status === 'waiting' && mission.run?.provider === 'assisted';

  async function textArtifact(content, kind, label) {
    const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(content))),
      value => value.toString(16).padStart(2, '0')).join('');
    return {label, kind, sha256, content};
  }

  async function keepAssisted(result, filename, token) {
    const label = filename?.replace(/[\u0000-\u001f\u007f]/gu, '').slice(0, 120).trim() || words.originalResponse;
    const artifact = await textArtifact(result.raw, filename ? 'assisted-text' : 'assisted-original', label);
    if (token !== serial || !canImportAssisted()) return;
    const receipt = result.receipt ?? {route:'continuing', objective:mission.ambition, nextAction:words.workReview};
    const work = workPreview(result.work.trim() ? result.work : result.raw);
    accept({...receipt, work, artifacts:[artifact]}, mission.run.id);
    const workPanel = node('mission-work-panel');
    if (workPanel.getClientRects().length) {
      workPanel.querySelector('summary').focus({preventScroll:true});
      workPanel.scrollIntoView({block:'start', behavior:'instant'});
    }
  }

  async function importAssisted(raw, filename, token) {
    const result = await readAssistedReply(raw, request);
    if (token !== serial || !canImportAssisted()) return;
    if (result.kind === 'unmatched') {
      unmatchedWork = {result, filename};
      text('mission-handoff-status', words.invalid);
      show('mission-keep-unverified', true);
      node('mission-keep-unverified').focus();
      return;
    }
    await keepAssisted(result, filename, token);
  }

  node('mission-reply').addEventListener('input', () => { serial++; resetAssistedImport(); });
  node('mission-import-reply').addEventListener('click', async () => {
    if (!canImportAssisted()) return;
    const token = ++serial;
    resetAssistedImport();
    try { await importAssisted(node('mission-reply').value, undefined, token); }
    catch { if (token === serial && active()) text('mission-handoff-status', words.plainInvalid); }
  });
  node('mission-keep-unverified').addEventListener('click', async () => {
    if (!canImportAssisted() || !unmatchedWork) return;
    const token = ++serial;
    const {result, filename} = unmatchedWork;
    try { await keepAssisted(result, filename, token); }
    catch { if (token === serial && active()) text('mission-handoff-status', words.plainInvalid); }
  });

  async function returnedText(content) {
    const bytes = encoder.encode(content);
    if (!content.trim() || bytes.length > maximumReturnedBytes) throw new Error('ASSISTED_TEXT');
    const report = {route:'continuing', objective:mission.ambition, nextAction:words.workReview};
    if (bytes.length <= 12 * 1024) return {...report, work:content};
    return {...report, artifacts:[await textArtifact(content, 'browser-text', words.browserSource)]};
  }

  node('mission-import-artifact').addEventListener('change', async event => {
    const control = event.target;
    const file = control.files[0];
    control.value = '';
    if (!file || !canImportAssisted()) return;
    const token = ++serial;
    resetAssistedImport();
    try {
      if (file.size > maximumReturnedBytes) throw new Error('ASSISTED_FILE_SIZE');
      const content = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(await file.arrayBuffer());
      if (token === serial && canImportAssisted()) await importAssisted(content, file.name, token);
    } catch { if (token === serial && active()) text('mission-handoff-status', words.plainInvalid); }
  });

  async function checkBrowserStarter() {
    const check = ++browserCheck;
    const state = await browserModelAvailability(mission?.language ?? language);
    if (check !== browserCheck || !active()) return;
    show('intelligence-browser', true);
    show('intelligence-browser-start', state !== 'unavailable');
    if (state === 'unavailable') text('intelligence-browser-status', words.browserUnsupported);
    else if (node('intelligence-browser-status').textContent === words.browserUnsupported) text('intelligence-browser-status', '');
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
    if (files().length) { render(words.localFiles); return; }
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
      const packet = missionPacket(snapshot);
      const result = await runBrowserStarter({ambition:snapshot.ambition, language:snapshot.language, signal:controller.signal,
        instruction:packet.instruction, previousWork:packet.previousReport?.work,
        onProgress(value) {
          if (token !== serial || !active()) return;
          const message = value < 1 ? words.browserDownloading(new Intl.NumberFormat(language, {style:'percent'}).format(value)) : words.browserStarting;
          if (node('intelligence-browser-status').textContent !== message) text('intelligence-browser-status', message);
        },
        onReady() {
          if (token === serial && active()) text('intelligence-browser-status', words.browserRunning);
        }});
      if (token !== serial || !active()) return;
      const report = await returnedText(result);
      if (token !== serial || !active()) return;
      localRuns.add(run);
      accept(report, run);
      text('intelligence-browser-status', words.review);
      shell.show(node('frontier-mission-panel'), {remember:true});
    } catch (error) {
      if (token !== serial || !active()) return;
      if (run) mission = interruptMission(mission, run, 'BROWSER_MODEL_FAILED');
      const message = error?.message === 'BROWSER_MODEL_UNVERIFIED' ? words.browserUnverified
        : error?.message === 'BROWSER_MODEL_CONTEXT' ? words.browserContext : words.browserUnavailable;
      render(message);
      text('intelligence-browser-status', message);
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
    if (!active()) return;
    showSetup();
    settings.querySelector('summary').focus();
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
  async function runConfiguredModel() {
    if (!active() || !mission || !connection || ['running','canceled'].includes(mission.status)) return;
    if (files().length) { render(words.localFiles); return; }
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
  }
  node('mission-run-local').addEventListener('click', runConfiguredModel);

  const resetRequest = () => { stopRequest(); resetHandoff(); };
  node('mission-pause').addEventListener('click', () => {
    if (!active() || !mission?.run) return;
    resetRequest();
    mission = interruptMission(mission, mission.run.id, 'USER_PAUSED');
    render();
  });
  function continueFromHere(instruction) {
    if (!active() || !mission) return;
    try {
      const next = instruction ? addMissionInstruction(mission, instruction) : continueMission(mission);
      const last = currentReport();
      const preferred = mission.run?.provider === 'assisted' || last?.provider === 'assisted' ? 'assisted' : last?.model;
      afterPendingSetup(() => {
        resetRequest();
        if (next.status === 'running') {
          const stopped = interruptMission(next, next.run.id, 'USER_CONTINUED');
          mission = continueMission(stopped);
        } else mission = next;
        node('mission-follow-up').value = '';
        render();
        activateWork({preferred,continuation:true});
      }, {stopWork:true});
    } catch { render(words.invalidInstruction); }
  }
  node('mission-continue').addEventListener('click', () => continueFromHere());
  node('mission-follow-up-form').addEventListener('submit', event => {
    event.preventDefault();
    const instruction = node('mission-follow-up').value;
    if (instruction.trim()) continueFromHere(instruction);
  });
  node('mission-cancel').addEventListener('click', () => {
    if (!active() || !mission) return;
    afterPendingSetup(() => {
      execution.clearWaiting();
      resetRequest();
      mission = cancelMission(mission);
      render();
    }, {stopWork:'cancel'});
  });
  node('mission-revise').addEventListener('click', () => {
    if (!active() || !mission) return;
    editingAmbition = true;
    render();
    input.focus();
  });
  node('mission-new').addEventListener('click', () => {
    if (!active()) return;
    afterPendingSetup(() => {
      resetRequest();
      mission = atlas = undefined;
      entryDocuments = recoveredDocuments = undefined;
      editingAmbition = false;
      fileSerial++;
      node('mission-follow-up').value = '';
      node('mission-document-status').textContent = '';
      node('mission-document-consent').checked = false;
      node('mission-files').open = false;
      execution.clearView();
      localRuns.clear();
      input.value = '';
      input.dispatchEvent(new Event('input'));
      render();
      input.focus();
    }, {stopWork:true});
  });
  node('mission-work-download').addEventListener('click', () => {
    const report = currentReport();
    const original = report?.artifacts?.find(file => ['assisted-original','assisted-text'].includes(file.kind));
    const work = original?.content ?? report?.work;
    if (active() && work) downloadText(work, 'frontier-work-for-review.txt');
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
        recoveredDocuments = entryDocuments = undefined;
        editingAmbition = false;
        fileSerial++;
        node('mission-document-consent').checked = false;
        node('mission-follow-up').value = '';
        execution.clearView();
        atlas = undefined;
        input.value = mission.ambition;
        input.dispatchEvent(new Event('input'));
        if (mission.status === 'waiting' && mission.request) revealHandoff(mission.request);
        render(words.reopened);
        text('mission-file-status', words.reopened);
        shell.show(node('frontier-mission-panel'), {remember:true});
        void checkBrowserStarter();
      }, {stopWork:true});
    } catch { if (attempt === serial && active()) text('mission-file-status', words.fileInvalid); }
  });
  window.addEventListener('frontier:member-lock', () => {
    resetRequest();
    mission = atlas = connection = undefined;
    entryDocuments = recoveredDocuments = undefined;
    editingAmbition = false;
    fileSerial++;
    node('mission-follow-up').value = '';
    node('mission-document-status').textContent = '';
    node('mission-document-consent').checked = false;
    node('mission-files').open = false;
    if (settings.parentElement !== node('intelligence-settings-slot')) node('intelligence-settings-slot').append(settings);
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
  return {start};
}
