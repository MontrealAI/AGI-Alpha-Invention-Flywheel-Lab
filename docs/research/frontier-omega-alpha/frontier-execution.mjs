import {connectCompanion} from './frontier-companion-link.mjs';
import {missionPacket} from './frontier-mission.mjs';

const base = 'http://127.0.0.1:38463/api/frontier-missions/';
const node = id => document.getElementById(id);
const text = (id, value) => { if (node(id).textContent !== value) node(id).textContent = value; };
const activeStates = new Set(['running','ready']);
const resumable = new Set(['paused','interrupted','ready']);
const approvalStates = new Set(['awaiting_consent','approval_required']);
const localDevice = () => !(navigator.userAgentData?.mobile || /Android|iPad|iPhone|iPod/u.test(navigator.userAgent)
  || (navigator.maxTouchPoints > 1 && /Macintosh/u.test(navigator.userAgent)));

function download(blob, name) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function ambitionBody(mission, previous, {local = false} = {}) {
  const body = {ambition:mission.ambition,language:mission.language};
  if (previous) body.previous = previous;
  else if (mission.originalAmbition !== mission.ambition) body.original_ambition = mission.originalAmbition;
  const {instruction} = missionPacket(mission);
  if (instruction) body.instruction = instruction;
  if (local && mission.documents) body.documents = mission.documents;
  return body;
}

function checkAmbition(result, mission, id = result.id) {
  const {instruction} = missionPacket(mission);
  if (result.id !== id || result.ambition !== mission.ambition || result.language !== mission.language
      || result.original_ambition !== mission.originalAmbition || (instruction && result.instruction !== instruction)) {
    throw new Error('MISSION_BINDING');
  }
}
const copy = {
  en: {
    paired: 'Paired with the local executor', unpaired: 'Pair with the local executor again to reopen its records.',
    unreachable: 'The local executor could not confirm the request. Check its connection before retrying.',
    refused: 'The local executor paused or refused this request. Check its authorization and the run record.',
    expired: 'The local authorization has ended. Reconnect with a current pairing code.',
    freshScope: 'This mission started under different limits. Activate the ambition again to use your current authorization.',
    pairing: 'Checking the one-use code on this device…', pairInvalid: 'Use the current one-use code printed by your local executor.',
    starting: 'Submitting the ambition to the local executor…', disconnected: 'The local executor was disconnected.',
    chooseModel: 'Choose and check a model to resume your mission.',
    checkingModel: 'Checking the selected model with a local request…',
    findingModels: 'Looking for supported models on this computer…',
    noModel: 'No supported running model was found. Start an installed runtime and try again.',
    modelsFound: 'Choose a detected model to check it.',
    verifiedModel: 'Model checked on this computer',
    savedModel: 'Reconnect to check your saved model before resuming.',
    configuredModel: 'Local model configured',
    memory: value => `${value} GiB of available memory`,
    installed: value => `${value} GiB of installed memory`,
    storage: value => `${value} GiB of free workspace storage`,
    modelUnavailable: 'The selected model could not complete the connection check. Make sure it is loaded and try again.',
    settingsBusy: 'Finish checking the model before starting more work.',
    missionActive: 'Pause the active mission before changing models.',
    companion: 'Connect the desktop companion to continue with this ambition.',
    companionFallback: 'Open the companion, then try again or use a pairing code.',
    approveCompanion: 'Approve the connection in your desktop companion.',
    chooseFiles: 'Confirm which source files the private companion can use.',
    changedSources: 'The sources changed after submission. Reconnect and reopen the saved run to check its status before sending new sources.',
    localFiles: 'This mission has local source files. Remove them before preparing a provider request.',
    fileUnavailable: 'The companion could not verify this file. Try downloading the run record.',
    downloadFile: name => `Download ${name}`,
    dimensions: {technical_correctness:'Technical correctness',semantic_correctness:'Answers the registered question',
      objective_relevance:'Relevance to your ambition',frontier_advantage:'Advantage over alternatives'},
    verdicts: {PROVEN:'Proven',PARTIAL:'Partial',EXPERIMENTAL:'Experimental','NOT TESTED':'Pending evaluation',NOT_TESTED:'Pending evaluation',
      BLOCKED:'Blocked',FAIL:'Failed',ABSTAIN:'Insufficient evidence'},
    criteria: {milestone:'Milestone',beneficiary:'Who benefits',deliverable:'Deliverable',acceptance:'How to evaluate it',alternative:'Alternative',assumptions:'Assumptions'},
    desktopOnly: 'Continue on a desktop computer for local or provider setup, or use an assistant on this device.',
    staging: 'Saving the current ambition in the private companion for review…',
    nativeSetup: 'Choose or connect a provider in private setup. The companion will ask you to approve the exact mission and usage limits.',
    nativeWaiting: 'Waiting for your decision in private setup. Return here to follow this mission.',
    nativeRequired: 'Open private setup again to review this mission’s provider permission.',
    nativeConfiguration: 'Set up your provider in the private companion. Activate an ambition when you’re ready to review a mission.',
    nativeCanceled: 'Setup canceled. Your ambition is still here.', nativeReturned: 'Provider permission recorded. Open the mission to follow its execution.',
    nativeNotSaved: 'The companion could not confirm setup. Pair again or use an assistant.',
    nativeCancelFailed: 'The companion could not confirm cancellation. Reconnect to cancel this setup.',
    chooseFound: 'Choose the local model you want to check.',
    localReady: 'Your local model is ready for this mission.', hybridReady: 'Your local model is ready. Verified tools are preferred when they fit the mission.',
    evidenceStates: {VERIFIED:'Checked against the registered reference', SOURCE_BOUND:'Result from bound inputs, awaiting verification',
      UNVERIFIED:'Unverified', EXECUTED:'Executed', PROPOSED:'Proposed', REJECTED:'Rejected', ABSTAIN:'Evidence unavailable'},
    origins: {AUTHORIZED_MISSION_INPUT:'Authorized mission input', AUTHORIZED_MEMBER_DOCUMENT:'Authorized private source file',
      OPERATOR_SUPPLIED_OBSERVATION:'Operator observation',
      OPERATOR_APPROVED_DATASET:'Approved dataset', VERIFIED_EXTERNAL_SOURCE:'Verified external source',
      OPERATOR_PINNED_SOURCE_CAPTURE:'Operator-approved source capture',
      MODEL_DEVELOPMENT_FIXTURE:'Generated development fixture', DEVELOPMENT_FIXTURE:'Development fixture',
      SYNTHETIC_EXAMPLE:'Synthetic example', SIMULATION_OUTPUT:'Simulation output', DERIVED_DATA:'Derived data'},
    rawOutput: 'Tool output without claim acceptance',
    empty: 'This workspace has no saved missions.', actions: 'Actions', model: 'Model calls', checked: 'Scope or prior result checked',
    statuses: {ready:'Ready to execute',running:'Running',paused:'Paused',interrupted:'Interrupted',cancelled:'Canceled',
      complete:'Completed within the registered checks',needs_review:'Awaiting independent evaluation',
      exhausted:'Authorized resources exhausted',revoked:'Authority revoked',expired:'Authority expired',failed:'Execution failed',
      awaiting_consent:'Waiting for provider approval',approval_required:'Provider approval required',superseded:'Replaced by a new revision'},
    next: {ready:'The companion is preparing the run.', running:'Follow the work in Mission execution.',
      paused:'Resume the saved run or add an instruction to change the approach.',
      interrupted:'Review the run activity, then resume or add an instruction.',
      awaiting_consent:'Review the mission and provider permission in the private companion.',
      approval_required:'Review current provider permission to continue this mission.',
      exhausted:'Review what was attempted and add an instruction for the next run.',
      cancelled:'Open a new mission or add an instruction to start a new run.',
      expired:'Review the expired permission and choose how to continue.',
      revoked:'Choose an authorized model to continue.',
      failed:'Review the run activity and choose how to continue.'},
    nextReview: 'Review the evidence, work files and remaining checks below.',
    events: {created:'Mission recorded',model_started:'Model request sent',model_completed:'Model result received',
      remote_mission_approved:'Provider permission approved',authority_stopped:'Authority ended',
      tool_completed:'Tool operation recorded',tool_refused:'Tool refused',response_refused:'Model response refused',
      paused:'Paused',resumed:'Resumed',cancelled:'Canceled',stopped:'Stopped',model_error:'Model request failed',
      interruption_recovered:'Interruption recorded',model_not_dispatched:'Model request not sent'},
  },
  fr: {
    paired: 'Jumelé avec l’exécuteur local', unpaired: 'Jumelez de nouveau l’exécuteur local pour rouvrir ses dossiers.',
    unreachable: 'L’exécuteur local n’a pas pu confirmer la demande. Vérifiez la connexion avant de réessayer.',
    refused: 'L’exécuteur local a suspendu ou refusé la demande. Consultez l’autorisation et le dossier de la mission.',
    expired: 'L’autorisation locale est terminée. Reconnectez-vous avec un code de jumelage valide.',
    freshScope: 'Cette mission a démarré avec d’autres limites. Activez de nouveau l’ambition pour utiliser l’autorisation actuelle.',
    pairing: 'Vérification du code à usage unique sur cet appareil…', pairInvalid: 'Utilisez le code à usage unique affiché par votre exécuteur local.',
    starting: 'Transmission de l’ambition à l’exécuteur local…', disconnected: 'L’exécuteur local a été déconnecté.',
    chooseModel: 'Choisissez et vérifiez un modèle pour reprendre votre mission.',
    checkingModel: 'Vérification du modèle choisi par une requête locale…',
    findingModels: 'Recherche de modèles compatibles sur cet ordinateur…',
    noModel: 'Aucun modèle compatible en cours d’exécution. Démarrez un environnement installé, puis réessayez.',
    modelsFound: 'Choisissez un modèle détecté pour le vérifier.',
    verifiedModel: 'Modèle vérifié sur cet ordinateur',
    savedModel: 'Reconnectez le modèle enregistré pour le vérifier avant de reprendre.',
    configuredModel: 'Modèle local configuré',
    memory: value => `${value} Gio de mémoire disponible`,
    installed: value => `${value} Gio de mémoire installée`,
    storage: value => `${value} Gio d’espace de travail libre`,
    modelUnavailable: 'Le modèle sélectionné n’a pas terminé la vérification. Assurez-vous qu’il est chargé et réessayez.',
    settingsBusy: 'Attendez la fin de la vérification du modèle avant de lancer un autre travail.',
    missionActive: 'Suspendez la mission en cours avant de changer de modèle.',
    companion: 'Jumelez le compagnon de bureau pour poursuivre cette ambition.',
    companionFallback: 'Ouvrez le compagnon, puis réessayez ou utilisez un code de jumelage.',
    approveCompanion: 'Approuvez le jumelage dans votre compagnon de bureau.',
    chooseFiles: 'Confirmez les fichiers sources que le compagnon privé peut utiliser.',
    changedSources: 'Les sources ont changé après l’envoi. Reconnectez le compagnon et rouvrez l’exécution sauvegardée pour vérifier son état avant de transmettre les nouvelles sources.',
    localFiles: 'La mission contient des sources locales. Retirez-les avant de préparer une demande au fournisseur.',
    fileUnavailable: 'Le compagnon n’a pas pu vérifier ce fichier. Essayez de télécharger le dossier d’exécution.',
    downloadFile: name => `Télécharger ${name}`,
    dimensions: {technical_correctness:'Exactitude technique',semantic_correctness:'Réponse à la question déclarée',
      objective_relevance:'Pertinence pour votre ambition',frontier_advantage:'Avantage sur les autres options'},
    verdicts: {PROVEN:'Démontré',PARTIAL:'Partiel',EXPERIMENTAL:'Expérimental','NOT TESTED':'À évaluer',NOT_TESTED:'À évaluer',
      BLOCKED:'Bloqué',FAIL:'Échec',ABSTAIN:'Preuves insuffisantes'},
    criteria: {milestone:'Étape',beneficiary:'Pour qui',deliverable:'Livrable',acceptance:'Comment l’évaluer',alternative:'Autre approche',assumptions:'Hypothèses'},
    desktopOnly: 'Poursuivez sur un ordinateur pour configurer un modèle local ou un fournisseur, ou utilisez un assistant sur cet appareil.',
    staging: 'Enregistrement de l’ambition dans le compagnon privé pour examen…',
    nativeSetup: 'Choisissez ou connectez un fournisseur dans la configuration privée. Vous devrez approuver la mission précise et ses limites d’utilisation.',
    nativeWaiting: 'Votre décision est attendue dans la configuration privée. Revenez ici pour suivre la mission.',
    nativeRequired: 'Rouvrez la configuration privée pour examiner l’autorisation du fournisseur pour cette mission.',
    nativeConfiguration: 'Configurez votre fournisseur dans le compagnon privé. Activez une ambition quand vous souhaitez examiner une mission.',
    nativeCanceled: 'Configuration annulée. Votre ambition est toujours ici.', nativeReturned: 'Autorisation du fournisseur enregistrée. Ouvrez la mission pour suivre son exécution.',
    nativeNotSaved: 'Le compagnon n’a pas pu confirmer la configuration. Jumelez de nouveau ou utilisez un assistant.',
    nativeCancelFailed: 'Le compagnon n’a pas pu confirmer l’annulation. Reconnectez-vous pour annuler cette configuration.',
    chooseFound: 'Choisissez le modèle local à vérifier.',
    localReady: 'Votre modèle local est prêt pour cette mission.', hybridReady: 'Votre modèle local est prêt. Les outils vérifiés sont privilégiés quand ils conviennent à la mission.',
    evidenceStates: {VERIFIED:'Vérifié selon la référence déclarée', SOURCE_BOUND:'Résultat issu des données liées, en attente de vérification',
      UNVERIFIED:'Non vérifié', EXECUTED:'Exécuté', PROPOSED:'Proposé', REJECTED:'Rejeté', ABSTAIN:'Preuves indisponibles'},
    origins: {AUTHORIZED_MISSION_INPUT:'Données de mission autorisées', AUTHORIZED_MEMBER_DOCUMENT:'Fichier source privé autorisé',
      OPERATOR_SUPPLIED_OBSERVATION:'Observation de l’opérateur',
      OPERATOR_APPROVED_DATASET:'Jeu de données approuvé', VERIFIED_EXTERNAL_SOURCE:'Source externe vérifiée',
      OPERATOR_PINNED_SOURCE_CAPTURE:'Source archivée et approuvée par l’opérateur',
      MODEL_DEVELOPMENT_FIXTURE:'Données d’essai générées', DEVELOPMENT_FIXTURE:'Données d’essai',
      SYNTHETIC_EXAMPLE:'Exemple synthétique', SIMULATION_OUTPUT:'Résultat d’une simulation', DERIVED_DATA:'Données dérivées'},
    rawOutput: 'Sortie de l’outil dont la conclusion reste à valider',
    empty: 'Cet espace ne contient aucune mission enregistrée.', actions: 'Actions', model: 'Appels au modèle', checked: 'Périmètre ou résultat antérieur vérifié',
    statuses: {ready:'Prête à démarrer',running:'En cours',paused:'En pause',interrupted:'Interrompue',cancelled:'Annulée',
      complete:'Terminée selon les contrôles enregistrés',needs_review:'En attente d’une évaluation indépendante',
      exhausted:'Ressources autorisées épuisées',revoked:'Autorisation révoquée',expired:'Autorisation expirée',failed:'Échec de l’exécution',
      awaiting_consent:'En attente de l’approbation du fournisseur',approval_required:'Approbation du fournisseur requise',superseded:'Remplacée par une nouvelle révision'},
    next: {ready:'Le compagnon prépare l’exécution.', running:'Suivez le travail dans la section Exécution de la mission.',
      paused:'Reprenez l’exécution sauvegardée ou ajoutez une consigne pour changer d’approche.',
      interrupted:'Consultez le journal, puis reprenez ou ajoutez une consigne.',
      awaiting_consent:'Examinez la mission et l’autorisation du fournisseur dans le compagnon privé.',
      approval_required:'Examinez l’autorisation du fournisseur pour poursuivre cette mission.',
      exhausted:'Examinez les tentatives et ajoutez une consigne pour la prochaine exécution.',
      cancelled:'Ouvrez une nouvelle mission ou ajoutez une consigne pour relancer le travail.',
      expired:'Vérifiez l’autorisation expirée et choisissez comment poursuivre.',
      revoked:'Choisissez un modèle autorisé pour poursuivre.',
      failed:'Consultez le journal et choisissez comment poursuivre.'},
    nextReview: 'Examinez ci-dessous les preuves, les fichiers et les contrôles restants.',
    events: {created:'Mission enregistrée',model_started:'Demande envoyée au modèle',model_completed:'Résultat du modèle reçu',
      remote_mission_approved:'Autorisation du fournisseur accordée',authority_stopped:'Autorisation terminée',
      tool_completed:'Opération de l’outil enregistrée',tool_refused:'Opération refusée',response_refused:'Réponse du modèle refusée',
      paused:'Mise en pause',resumed:'Reprise',cancelled:'Annulation',stopped:'Arrêt',model_error:'Échec de la demande au modèle',
      interruption_recovered:'Interruption enregistrée',model_not_dispatched:'Demande au modèle non envoyée'},
  },
};

export function setupExecution(member, language, {onOpen, currentAmbition, currentMission, returnToMission, showSetup,
  localFilesConsent, filesAttached, updateSummary, onChooseRoute}) {
  const words = copy[language];
  const available = () => !member.hidden;
  let session, commandScope, view, pending, busyEpoch, serial = 0, timer;
  let queuedAmbition, ready = false, setupBusy = false;
  let selectedRoute, localSelection, nativeSetup, previousRun, viewMissionKey;
  let pairingRequest;
  const desktop = localDevice();
  const pairingPanel = member.querySelector('.mission-execution-connection');
  const status = message => {
    text('execution-status', message);
    updateSummary();
  };
  const missionKey = (mission = currentMission()) => mission ? `${mission.id}:${mission.revision}` : undefined;

  async function request(action, body = {}, command, authorizedSession = session, authorizedCommands = commandScope) {
    const headers = {'Content-Type':'application/json'};
    if (action !== 'pair') headers['X-Frontier-Session'] = authorizedSession;
    if (command) headers['X-Frontier-Command'] = `${authorizedCommands}.${command}`;
    const response = await fetch(base + action, {method:'POST', headers, body:JSON.stringify(body),
      credentials:'omit', redirect:'error', cache:'no-store', referrerPolicy:'no-referrer', keepalive:action === 'release'});
    if (action === 'export' && response.ok) return response.blob();
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.code ?? 'MISSION_EXECUTION');
    return data;
  }

  function errorMessage(error) {
    if (['MISSION_LEASE_EXPIRED','MISSION_SESSION'].includes(error.message)) return words.expired;
    if (error.message === 'MISSION_FRESH_SCOPE') return words.freshScope;
    if (error.message === 'MISSION_INTELLIGENCE_REQUIRED') return words.chooseModel;
    if (error.message === 'MISSION_INTELLIGENCE_UNAVAILABLE') return words.nativeNotSaved;
    if (error.message === 'MISSION_DOCUMENT_LOCAL_ONLY') return words.localFiles;
    if (error.message === 'MISSION_INTELLIGENCE_CONSENT') return words.nativeRequired;
    if (error.message === 'MISSION_INTELLIGENCE_BUSY') return words.settingsBusy;
    if (error.message === 'MISSION_ACTIVE') return words.missionActive;
    if (error.message === 'MISSION_ORIGIN') return words.nativeNotSaved;
    if (error.message === 'INTELLIGENCE_BUSY') return words.settingsBusy;
    if (error.message.startsWith('INTELLIGENCE_')) return words.modelUnavailable;
    return error instanceof TypeError ? words.unreachable : words.refused;
  }

  function updateControls() {
    node('execution-code-form').hidden = !desktop || Boolean(session);
    node('execution-manual-code').hidden = !desktop || Boolean(session);
    node('execution-connect-companion').hidden = !desktop || Boolean(session);
    node('execution-connect-companion').disabled = Boolean(pairingRequest);
    node('execution-open-saved').disabled = !session;
    node('execution-recover').hidden = !session;
    node('execution-disconnect').hidden = !session;
    node('execution-send-current').hidden = !session || !ready || !currentMission() || selectedRoute === 'api' || Boolean(view || pending);
    node('execution-retry').hidden = !session || !ready || !pending;
    node('intelligence-discover').disabled = setupBusy;
    node('intelligence-reconnect').disabled = setupBusy;
    node('intelligence-select-form').querySelector('button').disabled = setupBusy;
    for (const id of ['execution-pause','execution-resume','execution-cancel','execution-disconnect']) node(id).disabled = busyEpoch === serial;
  }

  function requirePairing(error) {
    if (!['MISSION_LEASE_EXPIRED','MISSION_SESSION'].includes(error.message)) return;
    session = commandScope = localSelection = undefined;
    ready = false;
    clearTimeout(timer);
    displayNativeLink();
    node('intelligence-local-controls').hidden = true;
    node('intelligence-select-form').hidden = true;
    if (desktop) pairingPanel.open = true;
    text('execution-connection', words.expired);
    updateControls();
  }

  function showRoute(message, {assist = true, check = false, cancel = false} = {}) {
    node('intelligence-next').hidden = false;
    text('intelligence-route-status', message);
    node('intelligence-assist').hidden = !assist;
    node('intelligence-check-native').hidden = !check;
    node('intelligence-cancel-native').hidden = !cancel;
  }

  function nativeLink(ticket) {
    if (ticket !== undefined && !/^[A-Za-z0-9_-]{43}$/u.test(ticket)) return;
    const url = new URL('/', base);
    url.search = new URLSearchParams({setup:'intelligence',route:'api',lang:language});
    if (ticket) url.hash = `ticket=${ticket}`;
    return url.href;
  }

  function displayNativeLink(url) {
    const link = node('intelligence-open-native');
    link.hidden = !url;
    if (url) link.href = url;
    else link.removeAttribute('href');
  }

  function clearOnboarding() {
    selectedRoute = localSelection?.mode;
    node('intelligence-next').hidden = true;
    node('intelligence-mobile').hidden = desktop;
    displayNativeLink();
    text('intelligence-route-status', '');
  }

  function renderEvidence(evidence, outcome) {
    const contract = node('execution-contract');
    if (contract) {
      const deliverable = outcome?.schema === 'frontier/mission-outcome/v1' ? outcome.contract?.deliverable : null;
      contract.hidden = !deliverable;
      text('execution-deliverable', deliverable ?? '');
    }
    if (outcome?.schema === 'frontier/mission-outcome/v1') {
      const conclusions = (outcome.conclusions ?? []).filter(item => item.status === 'VERIFIED');
      const unresolved = (outcome.unresolved ?? []).map(item => ({
        ...item, value: null, note: [item.message, ...(item.missing ?? []).map(field => field.label)].filter(Boolean).join(' · '),
      }));
      node('execution-evidence').hidden = false;
      text('execution-evidence-status', outcome.message);
      node('execution-claims').replaceChildren(...[...conclusions, ...unresolved].map(item => {
        const li = document.createElement('li');
        const detail = item.value == null ? item.note || words.evidenceStates[item.status] : [item.value, item.unit].filter(Boolean).join(' ');
        li.textContent = [item.id, detail].filter(Boolean).join(' · ');
        return li;
      }));
      return;
    }
    const claims = Array.isArray(evidence?.claims) ? evidence.claims : [];
    node('execution-evidence').hidden = !claims.length;
    text('execution-evidence-status', claims.length ? (words.evidenceStates[evidence.status] ?? evidence.status) : '');
    node('execution-claims').replaceChildren(...claims.map(claim => {
      const li = document.createElement('li');
      const state = words.evidenceStates[claim.status] ?? claim.status;
      const value = ['VERIFIED','SOURCE_BOUND'].includes(claim.status) ? claim.value : null;
      li.textContent = [claim.id, value == null ? '' : [value,claim.unit].filter(x => x != null && x !== '').join(' '), state].filter(Boolean).join(' · ');
      return li;
    }));
  }

  function renderQualification(result) {
    const rows = Object.entries(words.dimensions);
    const values = result?.qualification_dimensions;
    node('execution-dimensions').hidden = !values;
    node('execution-dimensions-list').replaceChildren(...(values ? rows.map(([key,label]) => {
      const row = document.createElement('div');
      const heading = document.createElement('dt');
      const status = document.createElement('dd');
      heading.textContent = label;
      status.textContent = words.verdicts[values[key]] ?? words.verdicts.ABSTAIN;
      row.append(heading,status);
      return row;
    }) : []));
    const contract = result?.proposed_contract;
    node('execution-proposed-contract').hidden = !contract;
    node('execution-proposed-fields').replaceChildren(...(contract ? Object.entries(words.criteria).flatMap(([key,label]) => {
      const value = contract[key];
      if (!(typeof value === 'string' || Array.isArray(value)) || !value.length) return [];
      const row = document.createElement('div');
      const heading = document.createElement('dt');
      const detail = document.createElement('dd');
      heading.textContent = label;
      detail.textContent = Array.isArray(value) ? value.join('\n') : value;
      row.append(heading,detail);
      return [row];
    }) : []));
    const sources = result?.documents ?? [];
    node('execution-source-record').hidden = !sources.length;
    node('execution-sources').replaceChildren(...sources.map(source => {
      const row = document.createElement('li');
      row.textContent = `${source.name} · SHA-256 ${source.sha256}`;
      return row;
    }));
  }

  async function downloadArtifact(result, artifact, button) {
    const pairing = session;
    button.disabled = true;
    try {
      const blob = await request('export', {id:result.id});
      if (pairing !== session || view?.id !== result.id || !available()) return;
      const body = JSON.parse(await blob.text());
      const content = body.files?.[artifact.name];
      if (typeof content !== 'string' || body.state?.id !== result.id) throw new Error('MISSION_ARTIFACT');
      const bytes = new TextEncoder().encode(content);
      const hash = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
      const digest = [...hash].map(value => value.toString(16).padStart(2,'0')).join('');
      if (digest !== artifact.sha256) throw new Error('MISSION_ARTIFACT');
      if (pairing === session && view?.id === result.id && available()) {
        download(new Blob([bytes], {type:'application/octet-stream'}), artifact.name);
      }
    } catch {
      if (pairing === session && view?.id === result.id && available()) text('execution-artifact-status', words.fileUnavailable);
    } finally { button.disabled = false; }
  }

  function follow(result, key = viewMissionKey ?? missionKey()) {
    view = result;
    viewMissionKey = key;
    previousRun = result.id;
    const panel = node('mission-execution');
    panel.hidden = false;
    panel.dataset.state = result.status;
    status(words.statuses[result.status] ?? result.status);
    text('execution-counts', `${words.actions} ${result.actions ?? 0} · ${words.model} ${result.model_calls ?? 0}`);
    text('execution-proposal', result.proposal ?? '');
    node('execution-understanding').hidden = !result.proposal;
    node('execution-pause').hidden = !activeStates.has(result.status) && !result.worker_active;
    node('execution-resume').hidden = !resumable.has(result.status) || result.worker_active;
    node('execution-cancel').hidden = !['running','ready','paused','interrupted'].includes(result.status) && !approvalStates.has(result.status);
    node('execution-approve').hidden = !approvalStates.has(result.status);
    node('execution-export').disabled = result.worker_active || result.status === 'running' || approvalStates.has(result.status);
    const events = result.events ?? [];
    node('execution-events').replaceChildren(...events.map(item => {
      const li = document.createElement('li');
      const title = item.operation_executed === false ? words.checked : words.events[item.kind] ?? item.kind;
      li.textContent = [title, item.tool, item.artifact, item.disposition,
        item.input_origin && (words.origins[item.input_origin] ?? item.input_origin),
        item.reason ?? item.code].filter(Boolean).join(' · ');
      return li;
    }));
    const latest = events.findLast(item => item.preview);
    text('execution-result', latest?.preview ?? '');
    text('execution-result-origin', (latest && words.origins[latest.input_origin]) || words.rawOutput);
    node('execution-preview').hidden = !latest;
    renderEvidence(result.evidence, result.outcome);
    renderQualification(result);
    const artifacts = result.artifacts ?? [];
    node('execution-delivery').hidden = !artifacts.length;
    node('execution-artifacts').replaceChildren(...artifacts.map(artifact => {
      const li = document.createElement('li');
      if (!result.worker_active && !activeStates.has(result.status) && /^[0-9a-f]{64}$/u.test(artifact.sha256 ?? '')
        && /^[a-zA-Z0-9][a-zA-Z0-9._-]*\.(csv|json|md|txt)$/u.test(artifact.name ?? '')) {
        const file = document.createElement('button');
        file.type = 'button';
        file.className = 'quiet';
        file.textContent = words.downloadFile(artifact.name);
        file.addEventListener('click', () => void downloadArtifact(result, artifact, file));
        li.append(file);
      } else li.textContent = artifact.name;
      return li;
    }));
    if (nativeSetup?.id === result.id) updateNativeSetup(result, nativeSetup);
    updateControls();
    clearTimeout(timer);
    if (session && (result.worker_active || activeStates.has(result.status)
      || (nativeSetup?.id === result.id && nativeSetup.opened && !nativeSetup.canceling))) {
      const epoch = serial;
      const pairing = session;
      timer = setTimeout(async () => {
        try {
          const snap = await request('get', {id:result.id});
          if (serial === epoch && session === pairing && available()) follow(snap);
        } catch (error) {
          if (serial !== epoch || session !== pairing || !available()) return;
          requirePairing(error);
          status(errorMessage(error));
          if (nativeSetup?.id === result.id) showRoute(errorMessage(error), {check:true,cancel:true});
        }
      }, 1200);
    }
  }

  function updateNativeSetup(result, attempt) {
    if (attempt.canceling || missionKey() !== attempt.key) return;
    if (approvalStates.has(result.status)) {
      const url = result.setup_ticket === undefined ? undefined : nativeLink(result.setup_ticket);
      if (url) displayNativeLink(url);
      const message = attempt.opened ? words.nativeWaiting : url ? words.nativeSetup : words.nativeRequired;
      showRoute(message, {check:true,cancel:true});
      return;
    }
    nativeSetup = undefined;
    displayNativeLink();
    const canceled = ['cancelled','superseded','expired','revoked'].includes(result.status);
    showRoute(canceled ? words.statuses[result.status] : words.nativeReturned, {assist:canceled});
    if (attempt.opened && !canceled && !node('my-intelligence').hidden) returnToMission();
  }

  async function refreshNativeSetup({renewTicket = false} = {}) {
    const attempt = nativeSetup;
    if (!available() || !session || !attempt?.id || attempt.canceling || attempt.key !== missionKey()) return;
    const epoch = serial;
    const pairing = session;
    try {
      const result = await request(renewTicket ? 'mission-intelligence-status' : 'get', {id:attempt.id});
      if (epoch === serial && session === pairing && attempt === nativeSetup && !attempt.canceling && available() && attempt.key === missionKey()) {
        checkAmbition(result, currentMission(), attempt.id);
        follow(result);
      }
    } catch (error) {
      if (attempt === nativeSetup && session === pairing && available()) {
        requirePairing(error);
        showRoute(errorMessage(error), {check:true,cancel:true});
      }
    }
  }

  async function prepareNativeSetup() {
    const mission = currentMission();
    if (mission && filesAttached()) { showRoute(words.localFiles); return; }
    if (!mission) {
      displayNativeLink(nativeLink());
      showRoute(words.nativeConfiguration);
      return;
    }
    if (nativeSetup?.key === missionKey(mission)) {
      if (nativeSetup.id && !nativeSetup.preparation) await refreshNativeSetup({renewTicket:true});
      return;
    }
    const command = crypto.randomUUID();
    const pairing = session;
    const commandNamespace = commandScope;
    const body = ambitionBody(mission, previousRun);
    const attempt = {key:missionKey(mission)};
    nativeSetup = attempt;
    const epoch = ++serial;
    clearTimeout(timer);
    queuedAmbition = undefined;
    displayNativeLink();
    showRoute(words.staging, {cancel:true});
    attempt.preparation = (async () => {
      const bytes = new TextEncoder().encode(`frontier-pages-mission-v1:${command}`);
      const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
      attempt.id = 'wf_' + [...digest.slice(0,12)].map(value => value.toString(16).padStart(2,'0')).join('');
      if (attempt.canceling || attempt !== nativeSetup || pairing !== session || !available()) return;
      const result = await request('prepare-intelligence', body, command, pairing, commandNamespace);
      checkAmbition(result, mission, attempt.id);
      return result;
    })();
    try {
      const result = await attempt.preparation;
      if (result && !attempt.canceling && attempt === nativeSetup && pairing === session && epoch === serial && available()) follow(result, attempt.key);
    } catch (error) {
      if (attempt === nativeSetup && !attempt.canceling && pairing === session && available()) {
        requirePairing(error);
        showRoute(errorMessage(error), {check:true,cancel:true});
      }
    } finally {
      attempt.preparation = undefined;
    }
  }

  async function cancelPendingSetup() {
    const attempt = nativeSetup;
    if (!attempt) return true;
    if (!session) return false;
    if (attempt.cancellation) return attempt.cancellation;
    const pairing = session;
    const commandNamespace = commandScope;
    attempt.canceling = true;
    ++serial;
    clearTimeout(timer);
    displayNativeLink();
    attempt.cancellation = (async () => {
      let canceled;
      try {
        await attempt.preparation?.catch(() => {});
        if (!available() || session !== pairing || nativeSetup !== attempt) return false;
        if (attempt.id) canceled = await request('cancel', {id:attempt.id}, crypto.randomUUID(), pairing, commandNamespace);
      } catch (error) {
        if (!['WORKFLOW_NOT_FOUND','MISSION_NOT_FOUND'].includes(error.message)) {
          if (available() && session === pairing && nativeSetup === attempt) {
            requirePairing(error);
            showRoute(words.nativeCancelFailed, {check:true,cancel:true});
          }
          return false;
        }
      }
      if (!available() || session !== pairing || nativeSetup !== attempt) return false;
      nativeSetup = undefined;
      if (canceled) follow(canceled, attempt.key);
      showRoute(!canceled || canceled.status === 'cancelled' ? words.nativeCanceled : words.statuses[canceled.status],
        {assist:Boolean(currentMission())});
      selectedRoute = localSelection?.mode;
      updateControls();
      return true;
    })();
    try { return await attempt.cancellation; }
    finally { attempt.cancellation = undefined; attempt.canceling = false; }
  }

  function clearView({preservePrevious = false} = {}) {
    serial++;
    clearTimeout(timer);
    view = pending = queuedAmbition = viewMissionKey = undefined;
    if (!preservePrevious) previousRun = undefined;
    delete node('mission-execution').dataset.state;
    node('mission-execution').hidden = true;
    for (const id of ['execution-status','execution-counts','execution-result','execution-proposal']) text(id, '');
    node('execution-understanding').hidden = true;
    node('execution-preview').hidden = true;
    node('execution-approve').hidden = true;
    renderEvidence();
    renderQualification();
    node('execution-delivery').hidden = true;
    text('execution-artifact-status', '');
    for (const id of ['execution-events','execution-artifacts']) node(id).replaceChildren();
    updateControls();
  }

  async function activate(ambition, {continuation = false} = {}) {
    if (!available() || currentAmbition() !== ambition || nativeSetup) return;
    onChooseRoute();
    const mission = currentMission();
    if (!mission) return;
    const key = missionKey(mission);
    if (!continuation && view && viewMissionKey === key && view.status !== 'cancelled') return;
    if (selectedRoute === 'api') {
      showSetup();
      if (session) return prepareNativeSetup();
      if (desktop) { pairingPanel.open = true; showRoute(words.companion); }
      return;
    }
    if (!localFilesConsent()) { showSetup(); showRoute(words.chooseFiles); return; }
    if (!session || !ready || setupBusy) {
      queuedAmbition = {ambition,key,continuation};
      return;
    }
    const retry = pending?.key === key ? pending : undefined;
    const command = retry?.command ?? crypto.randomUUID();
    const body = ambitionBody(mission, previousRun, {local:true});
    if (retry && JSON.stringify(retry.body) !== JSON.stringify(body)) {
      status(words.changedSources);
      return;
    }
    const epoch = ++serial;
    clearTimeout(timer);
    pending = {ambition,body,command,key};
    queuedAmbition = undefined;
    view = undefined;
    node('mission-execution').hidden = false;
    delete node('mission-execution').dataset.state;
    for (const id of ['execution-pause','execution-resume','execution-cancel','execution-retry','execution-send-current']) node(id).hidden = true;
    node('execution-export').disabled = true;
    for (const id of ['execution-counts','execution-result','execution-proposal']) text(id, '');
    node('execution-understanding').hidden = true;
    node('execution-preview').hidden = true;
    renderEvidence();
    renderQualification();
    node('execution-delivery').hidden = true;
    text('execution-artifact-status','');
    for (const id of ['execution-events','execution-artifacts']) node(id).replaceChildren();
    status(words.starting);
    try {
      const result = await request('submit', body, command);
      if (serial === epoch && available()) {
        checkAmbition(result, mission);
        pending = undefined;
        follow(result, key);
      }
    } catch (error) {
      if (serial === epoch && available()) {
        requirePairing(error);
        if (error.message === 'MISSION_INTELLIGENCE_REQUIRED') {
          ready = false;
          queuedAmbition = {ambition,key,continuation};
          pending = undefined;
        }
        status(errorMessage(error));
        updateControls();
      }
    }
  }

  function showConnection(result, profile = result) {
    const selection = profile?.selection;
    localSelection = selection;
    ready = typeof result.scope?.model === 'string';
    node('intelligence-local-controls').hidden = !profile;
    node('intelligence-reconnect').hidden = !selection || selection.ready;
    text('intelligence-readiness', selection?.ready ? `${words.verifiedModel} · ${selection.model_label ?? selection.model}`
      : ready ? `${words.configuredModel} · ${result.scope.model}` : selection ? words.savedModel : words.chooseModel);
    updateControls();
  }

  function startWaiting() {
    if (!ready || !queuedAmbition || queuedAmbition.key !== missionKey() || selectedRoute === 'api') return;
    const {ambition,continuation} = queuedAmbition;
    queuedAmbition = undefined;
    returnToMission();
    activate(ambition, {continuation});
  }

  async function intelligenceAction(action, body, {findAndCheck = false} = {}) {
    if (!session || !available() || setupBusy) return;
    const pairing = session;
    const route = selectedRoute;
    let candidate;
    let applied = false;
    setupBusy = true;
    updateControls();
    text('intelligence-readiness', action === 'discover' ? words.findingModels : words.checkingModel);
    if (route === 'local' || route === 'hybrid') showRoute(action === 'discover' ? words.findingModels : words.checkingModel);
    try {
      const result = await request(`intelligence-${action}`, body);
      if (pairing !== session || !available()) return;
      if (action === 'discover') {
        const choices = Array.isArray(result.candidates) ? result.candidates : [];
        const host = result.host ?? {};
        const formatGiB = bytes => Number.isFinite(bytes) && bytes >= 0
          ? new Intl.NumberFormat(language, {maximumFractionDigits: 1}).format(bytes / (1024 ** 3)) : null;
        const memory = formatGiB(host.available_memory_bytes);
        const installed = formatGiB(host.physical_memory_bytes);
        const storage = formatGiB(host.available_workspace_bytes);
        text('intelligence-device', [host.system, memory ? words.memory(memory) : installed && words.installed(installed),
          storage && words.storage(storage)].filter(Boolean).join(' · '));
        node('intelligence-install').hidden = Boolean(choices.length);
        node('intelligence-choice').replaceChildren(...choices.map(choice => {
          const option = document.createElement('option');
          option.value = choice.id;
          option.textContent = [choice.model,choice.label].filter(Boolean).join(' · ');
          return option;
        }));
        node('intelligence-select-form').hidden = !choices.length;
        text('intelligence-readiness', choices.length ? words.modelsFound : words.noModel);
        if (findAndCheck) candidate = choices.find(item => item.selected) ?? (choices.length === 1 ? choices[0] : null);
        if (findAndCheck && route === selectedRoute) {
          showRoute(choices.length ? words.chooseFound : words.noModel);
          if (choices.length && !candidate) node('intelligence-choice').focus();
        }
      } else {
        showConnection(result);
        node('intelligence-install').hidden = true;
        node('intelligence-select-form').hidden = true;
        applied = ready;
        if (ready && route === selectedRoute && route !== 'api') showRoute(route === 'hybrid' ? words.hybridReady : words.localReady, {assist:false});
      }
    } catch (error) {
      if (pairing === session && available()) {
        requirePairing(error);
        text('intelligence-readiness', errorMessage(error));
        if (route === selectedRoute && route !== 'api') showRoute(errorMessage(error));
      }
    } finally {
      setupBusy = false;
      updateControls();
    }
    if (pairing !== session || !available() || route !== selectedRoute) return;
    if (candidate) return intelligenceAction('connect', {id:candidate.id,consent:true,mode:route === 'hybrid' ? 'hybrid' : 'local'});
    if (applied) startWaiting();
  }

  function findLocalIntelligence() {
    const mode = selectedRoute === 'hybrid' ? 'hybrid' : 'local';
    pairingPanel.open = true;
    node('intelligence-hybrid').checked = mode === 'hybrid';
    if (currentMission() && !view) queuedAmbition = {ambition:currentAmbition(),key:missionKey()};
    if (ready && localSelection?.mode === mode) {
      showRoute(mode === 'hybrid' ? words.hybridReady : words.localReady, {assist:false});
      startWaiting();
    } else if (localSelection && localSelection.mode === mode) {
      showRoute(words.checkingModel);
      return intelligenceAction('reconnect',{consent:true});
    } else {
      showRoute(words.findingModels);
      return intelligenceAction('discover',{consent:true},{findAndCheck:true});
    }
  }

  async function chooseIntelligence(route) {
    if (!available() || busyEpoch === serial) return;
    if (route === 'api' && filesAttached()) { showSetup(); showRoute(words.localFiles); return; }
    if (route !== 'api' && nativeSetup && !await cancelPendingSetup()) return;
    if (!available()) return;
    onChooseRoute();
    selectedRoute = route;
    displayNativeLink();
    showSetup();
    if (!desktop) {
      node('intelligence-mobile').hidden = false;
      showRoute(words.desktopOnly);
      node('intelligence-next-title').focus();
    } else if (!session) {
      pairingPanel.open = true;
      showRoute(words.companion);
      node('execution-connect-companion').focus();
    } else if (route === 'api') {
      await prepareNativeSetup();
      if (available() && !node('my-intelligence').hidden) node('intelligence-next-title').focus();
    } else {
      await findLocalIntelligence();
    }
    updateControls();
  }

  node('intelligence-desktop').hidden = !desktop;
  node('intelligence-companion-download').hidden = !desktop;
  node('execution-code-form').hidden = !desktop;
  node('intelligence-mobile').hidden = desktop;
  for (const option of member.querySelectorAll('[data-frontier-connection]')) {
    option.addEventListener('click', () => chooseIntelligence(option.dataset.frontierConnection));
  }
  node('execution-approve').addEventListener('click', () => chooseIntelligence('api'));
  node('intelligence-check-native').addEventListener('click', () =>
    refreshNativeSetup({renewTicket:!node('intelligence-open-native').hasAttribute('href')}));
  node('intelligence-cancel-native').addEventListener('click', cancelPendingSetup);
  node('intelligence-open-native').addEventListener('click', event => {
    if (!available() || !session || nativeSetup?.canceling) { event.preventDefault(); return; }
    if (nativeSetup) {
      nativeSetup.opened = true;
      showRoute(words.nativeWaiting, {check:true,cancel:true});
      void refreshNativeSetup();
    }
  });
  window.addEventListener('focus', () => { if (nativeSetup?.opened) void refreshNativeSetup(); });

  node('intelligence-discover').addEventListener('click', () => intelligenceAction('discover',{consent:true}));
  node('intelligence-reconnect').addEventListener('click', () => intelligenceAction('reconnect',{consent:true}));
  node('intelligence-select-form').addEventListener('submit', event => {
    event.preventDefault();
    intelligenceAction('connect', {id:node('intelligence-choice').value,consent:true,
      mode:node('intelligence-hybrid').checked ? 'hybrid' : 'local'});
  });

  async function pair(body) {
    if (!available() || !desktop || session) return;
    const epoch = ++serial;
    clearTimeout(timer);
    text('execution-connection', words.pairing);
    try {
      const result = await request('pair', body);
      if (epoch !== serial || !available()) {
        request('release', {}, undefined, result.session).catch(() => {});
        return;
      }
      session = result.session;
      commandScope = result.command_scope;
      node('intelligence-select-form').hidden = true;
      const end = Number.isFinite(Date.parse(result.expires_at))
        ? new Intl.DateTimeFormat(language, {dateStyle:'short', timeStyle:'short'}).format(new Date(result.expires_at)) : '';
      text('execution-connection', [words.paired,result.scope.model,end].filter(Boolean).join(' · '));
      showConnection(result, result.intelligence);
      if (nativeSetup?.id) {
        nativeSetup.opened = false;
        await refreshNativeSetup({renewTicket:true});
      } else if (view) {
        const recovered = await request('get', {id:view.id});
        if (epoch === serial && session === result.session && available()) follow(recovered);
      }
      if (epoch !== serial || session !== result.session || !available()) return;
      if (selectedRoute === 'api' && !nativeSetup) await prepareNativeSetup();
      else if (selectedRoute === 'local' || selectedRoute === 'hybrid') await findLocalIntelligence();
      else startWaiting();
    } catch (error) {
      if (epoch === serial && available()) text('execution-connection', body.code && error.message === 'MISSION_PAIRING' ? words.pairInvalid : errorMessage(error));
    }
  }
  node('execution-code-form').addEventListener('submit', event => {
    event.preventDefault();
    const input = node('execution-code');
    const code = input.value.trim();
    input.value = '';
    pairingRequest?.abort();
    void pair({code});
  });
  node('execution-connect-companion').addEventListener('click', async () => {
    if (!available() || !desktop || session || pairingRequest) return;
    const controller = new AbortController();
    pairingRequest = controller;
    text('execution-connection', words.approveCompanion);
    updateControls();
    try {
      const handoff = await connectCompanion(language, controller.signal);
      if (controller.signal.aborted || !available() || session) return;
      if (handoff) await pair(handoff);
      if (!session && available() && !controller.signal.aborted) {
        text('execution-connection', words.companionFallback);
        node('execution-manual-code').open = true;
        node('execution-code').focus();
      }
    } finally {
      if (controller === pairingRequest) pairingRequest = undefined;
      updateControls();
    }
  });

  for (const action of ['pause','resume','cancel','export']) node(`execution-${action}`).addEventListener('click', async () => {
    if (!session || !view || !available() || busyEpoch === serial) return;
    if (action === 'cancel' && nativeSetup?.id === view.id) return cancelPendingSetup();
    const epoch = action === 'export' ? serial : ++serial;
    if (action !== 'export') {
      busyEpoch = epoch;
      clearTimeout(timer);
      updateControls();
    }
    try {
      const result = await request(action, {id:view.id}, action === 'export' ? undefined : crypto.randomUUID());
      if (epoch !== serial || !available()) return;
      if (action === 'export') {
        download(result, 'frontier-execution.json');
      } else follow(result);
    } catch (error) {
      if (epoch === serial && available()) { requirePairing(error); status(errorMessage(error)); }
    }
    finally { if (busyEpoch === epoch) { busyEpoch = undefined; updateControls(); } }
  });

  node('execution-retry').addEventListener('click', () => activate(pending?.ambition));
  node('execution-send-current').addEventListener('click', () => activate(currentAmbition()));
  node('execution-disconnect').addEventListener('click', async () => {
    if (!session || !available() || busyEpoch === serial) return;
    const epoch = ++serial;
    busyEpoch = epoch;
    clearTimeout(timer);
    updateControls();
    try {
      await request('disconnect', {}, crypto.randomUUID());
      if (serial !== epoch || !available()) return;
      session = commandScope = undefined;
      ready = false;
      localSelection = nativeSetup = undefined;
      clearOnboarding();
      node('intelligence-local-controls').hidden = true;
      node('intelligence-select-form').hidden = true;
      clearView();
      node('execution-saved-list').replaceChildren();
      text('execution-connection', words.disconnected);
    } catch (error) { if (epoch === serial && available()) text('execution-connection', errorMessage(error)); }
    finally { if (busyEpoch === epoch) { busyEpoch = undefined; updateControls(); } }
  });
  async function openSaved() {
    if (!session || !available()) return;
    const epoch = serial;
    try {
      const result = await request('list');
      if (serial !== epoch || !available()) return;
      text('execution-results-status', result.missions.length ? '' : words.empty);
      node('execution-saved-list').replaceChildren(...result.missions.map(row => {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'quiet';
        button.textContent = `${row.ambition || row.id} · ${words.statuses[row.status] ?? row.status}`;
        button.addEventListener('click', async () => {
          if (!available() || !session) return;
          if (nativeSetup && nativeSetup.id !== row.id && !await cancelPendingSetup()) return;
          const epoch = ++serial;
          try {
            const recovered = await request('get',{id:row.id});
            if (serial !== epoch || !available()) return;
            if (!nativeSetup || nativeSetup.id !== recovered.id || nativeSetup.key !== missionKey()) onOpen(recovered);
            if (approvalStates.has(recovered.status)) {
              selectedRoute = 'api';
              nativeSetup = {id:recovered.id,key:missionKey()};
            }
            follow(recovered, missionKey());
          } catch (error) { if (epoch === serial && available()) text('execution-results-status', errorMessage(error)); }
        });
        item.append(button);
        return item;
      }));
    } catch (error) {
      if (serial === epoch && available()) { requirePairing(error); text('execution-results-status', errorMessage(error)); }
    }
  }
  node('execution-open-saved').addEventListener('click', openSaved);
  node('execution-recover').addEventListener('click', () => {
    if (!available()) return;
    node('mission-keeper').open = true;
    void openSaved();
  });

  function sealSession() {
    pairingRequest?.abort();
    pairingRequest = undefined;
    if (session) request('release').catch(() => {});
    session = commandScope = undefined;
    ready = false;
    localSelection = nativeSetup = undefined;
    clearOnboarding();
    node('intelligence-local-controls').hidden = true;
    node('intelligence-select-form').hidden = true;
    node('intelligence-select-form').reset();
    node('intelligence-choice').replaceChildren();
    clearView();
    node('execution-code-form').reset();
    node('execution-saved-list').replaceChildren();
    text('execution-connection', '');
    text('execution-results-status', '');
  }
  window.addEventListener('frontier:member-lock', sealSession);
  window.addEventListener('pagehide', sealSession);
  updateControls();
  async function pauseActive(action = 'pause') {
    if (pending || busyEpoch === serial) return false;
    const activeView = view?.worker_active || activeStates.has(view?.status);
    if (!activeView && !(action === 'cancel' && resumable.has(view?.status))) return true;
    if (!session || !available() || !view?.id) return false;
    const epoch = ++serial;
    busyEpoch = epoch;
    clearTimeout(timer);
    updateControls();
    try {
      const next = await request(action, {id:view.id}, crypto.randomUUID());
      if (serial !== epoch || !available()) return false;
      follow(next);
      return !next.worker_active && !activeStates.has(next.status);
    } catch (error) {
      if (serial === epoch && available()) { requirePairing(error); status(errorMessage(error)); }
      return false;
    } finally {
      if (busyEpoch === epoch) { busyEpoch = undefined; updateControls(); }
    }
  }
  return {activate, clearView, updateControls, cancelPendingSetup,
    pauseActive,
    summary() {
      const key = missionKey();
      if (!key) return;
      if (view && viewMissionKey === key) return {status:node('execution-status').textContent,
        nextAction:words.next[view.status] ?? words.nextReview};
      if (pending?.key === key) return {status:node('execution-status').textContent,
        nextAction:words.next.ready};
    },
    hasPreferredRoute: () => selectedRoute === 'api' || Boolean(session && ready),
    hasPendingSetup: () => Boolean(nativeSetup),
    hasActiveWork: (action = 'pause') => Boolean(pending || view?.worker_active || activeStates.has(view?.status)
      || (action === 'cancel' && resumable.has(view?.status))),
    clearWaiting() { queuedAmbition = selectedRoute = undefined; }};
}
