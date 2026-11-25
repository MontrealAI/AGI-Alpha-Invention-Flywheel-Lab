const base = 'http://127.0.0.1:38463/api/frontier-missions/';
const node = id => document.getElementById(id);
const text = (id, value) => { if (node(id).textContent !== value) node(id).textContent = value; };
const activeStates = new Set(['running','ready']);
const resumable = new Set(['paused','interrupted','ready']);
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
    storage: value => `${value} GiB of free workspace storage`,
    modelUnavailable: 'The selected model could not complete the connection check. Make sure it is loaded and try again.',
    settingsBusy: 'Finish checking the model before starting more work.',
    missionActive: 'Pause the active mission before changing models.',
    evidenceStates: {VERIFIED:'Checked against the registered reference', SOURCE_BOUND:'Result from bound inputs, awaiting verification',
      UNVERIFIED:'Unverified', EXECUTED:'Executed', PROPOSED:'Proposed', REJECTED:'Rejected', ABSTAIN:'Evidence unavailable'},
    origins: {AUTHORIZED_MISSION_INPUT:'Authorized mission input', OPERATOR_SUPPLIED_OBSERVATION:'Operator observation',
      OPERATOR_APPROVED_DATASET:'Approved dataset', VERIFIED_EXTERNAL_SOURCE:'Verified external source',
      OPERATOR_PINNED_SOURCE_CAPTURE:'Operator-approved source capture',
      MODEL_DEVELOPMENT_FIXTURE:'Generated development fixture', DEVELOPMENT_FIXTURE:'Development fixture',
      SYNTHETIC_EXAMPLE:'Synthetic example', SIMULATION_OUTPUT:'Simulation output', DERIVED_DATA:'Derived data'},
    rawOutput: 'Tool output without claim acceptance',
    empty: 'This workspace has no saved missions.', actions: 'Actions', model: 'Model calls', checked: 'Scope or prior result checked',
    statuses: {ready:'Ready to execute',running:'Running',paused:'Paused',interrupted:'Interrupted',cancelled:'Canceled',
      complete:'Completed within the registered checks',needs_review:'Awaiting independent evaluation',
      exhausted:'Authorized resources exhausted',revoked:'Authority revoked',expired:'Authority expired',failed:'Execution failed'},
    events: {created:'Mission recorded',model_started:'Model request sent',model_completed:'Model result received',
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
    storage: value => `${value} Gio d’espace de travail libre`,
    modelUnavailable: 'Le modèle sélectionné n’a pas terminé la vérification. Assurez-vous qu’il est chargé et réessayez.',
    settingsBusy: 'Attendez la fin de la vérification du modèle avant de lancer un autre travail.',
    missionActive: 'Suspendez la mission en cours avant de changer de modèle.',
    evidenceStates: {VERIFIED:'Vérifié selon la référence déclarée', SOURCE_BOUND:'Résultat issu des données liées, en attente de vérification',
      UNVERIFIED:'Non vérifié', EXECUTED:'Exécuté', PROPOSED:'Proposé', REJECTED:'Rejeté', ABSTAIN:'Preuves indisponibles'},
    origins: {AUTHORIZED_MISSION_INPUT:'Données de mission autorisées', OPERATOR_SUPPLIED_OBSERVATION:'Observation de l’opérateur',
      OPERATOR_APPROVED_DATASET:'Jeu de données approuvé', VERIFIED_EXTERNAL_SOURCE:'Source externe vérifiée',
      OPERATOR_PINNED_SOURCE_CAPTURE:'Source archivée et approuvée par l’opérateur',
      MODEL_DEVELOPMENT_FIXTURE:'Données d’essai générées', DEVELOPMENT_FIXTURE:'Données d’essai',
      SYNTHETIC_EXAMPLE:'Exemple synthétique', SIMULATION_OUTPUT:'Résultat d’une simulation', DERIVED_DATA:'Données dérivées'},
    rawOutput: 'Sortie de l’outil dont la conclusion reste à valider',
    empty: 'Cet espace ne contient aucune mission enregistrée.', actions: 'Actions', model: 'Appels au modèle', checked: 'Périmètre ou résultat antérieur vérifié',
    statuses: {ready:'Prête à démarrer',running:'En cours',paused:'En pause',interrupted:'Interrompue',cancelled:'Annulée',
      complete:'Terminée selon les contrôles enregistrés',needs_review:'En attente d’une évaluation indépendante',
      exhausted:'Ressources autorisées épuisées',revoked:'Autorisation révoquée',expired:'Autorisation expirée',failed:'Échec de l’exécution'},
    events: {created:'Mission enregistrée',model_started:'Demande envoyée au modèle',model_completed:'Résultat du modèle reçu',
      tool_completed:'Opération de l’outil enregistrée',tool_refused:'Opération refusée',response_refused:'Réponse du modèle refusée',
      paused:'Mise en pause',resumed:'Reprise',cancelled:'Annulation',stopped:'Arrêt',model_error:'Échec de la demande au modèle',
      interruption_recovered:'Interruption enregistrée',model_not_dispatched:'Demande au modèle non envoyée'},
  },
};

export function setupExecution(member, language, {onOpen, currentAmbition, returnToMission}) {
  const words = copy[language];
  const available = () => !member.hidden;
  let session, commandScope, view, pending, busyEpoch, serial = 0, timer;
  let queuedAmbition, ready = false, setupBusy = false;
  const status = message => text('execution-status', message);

  async function request(action, body = {}, command, authorizedSession = session) {
    const headers = {'Content-Type':'application/json'};
    if (action !== 'pair') headers['X-Frontier-Session'] = authorizedSession;
    if (command) headers['X-Frontier-Command'] = `${commandScope}.${command}`;
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
    if (error.message === 'MISSION_INTELLIGENCE_BUSY') return words.settingsBusy;
    if (error.message === 'MISSION_ACTIVE') return words.missionActive;
    if (error.message === 'INTELLIGENCE_BUSY') return words.settingsBusy;
    if (error.message.startsWith('INTELLIGENCE_')) return words.modelUnavailable;
    return error instanceof TypeError ? words.unreachable : words.refused;
  }

  function updateControls() {
    node('execution-open-saved').disabled = !session;
    node('execution-disconnect').hidden = !session;
    node('execution-send-current').hidden = !session || !ready || !currentAmbition() || Boolean(view || pending);
    node('execution-retry').hidden = !session || !ready || !pending;
    node('intelligence-discover').disabled = setupBusy;
    node('intelligence-reconnect').disabled = setupBusy;
    node('intelligence-select-form').querySelector('button').disabled = setupBusy;
    for (const link of member.querySelectorAll('[data-local-intelligence-workbench]')) {
      link.hidden = !session;
      if (session) link.href = new URL('/', base).href;
    }
    for (const id of ['execution-pause','execution-resume','execution-cancel','execution-disconnect']) node(id).disabled = busyEpoch === serial;
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

  function follow(result) {
    view = result;
    const panel = node('mission-execution');
    panel.hidden = false;
    panel.dataset.state = result.status;
    status(words.statuses[result.status] ?? result.status);
    text('execution-counts', `${words.actions} ${result.actions} · ${words.model} ${result.model_calls}`);
    text('execution-proposal', result.proposal ?? '');
    node('execution-understanding').hidden = !result.proposal;
    node('execution-pause').hidden = !activeStates.has(result.status) && !result.worker_active;
    node('execution-resume').hidden = !resumable.has(result.status) || result.worker_active;
    node('execution-cancel').hidden = !['running','ready','paused','interrupted'].includes(result.status);
    node('execution-export').disabled = result.worker_active || result.status === 'running';
    node('execution-events').replaceChildren(...result.events.map(item => {
      const li = document.createElement('li');
      const title = item.operation_executed === false ? words.checked : words.events[item.kind] ?? item.kind;
      li.textContent = [title, item.tool, item.artifact, item.disposition,
        item.input_origin && (words.origins[item.input_origin] ?? item.input_origin),
        item.reason ?? item.code].filter(Boolean).join(' · ');
      return li;
    }));
    const latest = result.events.findLast(item => item.preview);
    text('execution-result', latest?.preview ?? '');
    text('execution-result-origin', (latest && words.origins[latest.input_origin]) || words.rawOutput);
    node('execution-preview').hidden = !latest;
    renderEvidence(result.evidence, result.outcome);
    node('execution-artifacts').replaceChildren(...result.artifacts.map(artifact => {
      const li = document.createElement('li');
      li.textContent = artifact.name;
      return li;
    }));
    updateControls();
    clearTimeout(timer);
    if (session && (result.worker_active || activeStates.has(result.status))) {
      const epoch = serial;
      timer = setTimeout(async () => {
        try {
          const snap = await request('get', {id:result.id});
          if (serial === epoch && available()) follow(snap);
        } catch (error) { if (serial === epoch && available()) status(errorMessage(error)); }
      }, 1200);
    }
  }

  function clearView() {
    serial++;
    clearTimeout(timer);
    view = pending = queuedAmbition = undefined;
    delete node('mission-execution').dataset.state;
    node('mission-execution').hidden = true;
    for (const id of ['execution-status','execution-counts','execution-result','execution-proposal']) text(id, '');
    node('execution-understanding').hidden = true;
    node('execution-preview').hidden = true;
    renderEvidence();
    for (const id of ['execution-events','execution-artifacts']) node(id).replaceChildren();
    updateControls();
  }

  async function activate(ambition) {
    if (!available() || typeof ambition !== 'string' || !ambition.trim()) return;
    if (!session || !ready || setupBusy) {
      queuedAmbition = ambition;
      return;
    }
    if (view?.ambition === ambition && (view.worker_active || activeStates.has(view.status))) return;
    const retry = pending?.ambition === ambition ? pending : undefined;
    const command = retry?.command ?? crypto.randomUUID();
    const previous = retry?.previous ?? view?.id;
    const epoch = ++serial;
    clearTimeout(timer);
    pending = {ambition,command,previous};
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
    for (const id of ['execution-events','execution-artifacts']) node(id).replaceChildren();
    status(words.starting);
    try {
      const result = await request('submit', previous ? {ambition,language,previous} : {ambition,language}, command);
      if (serial === epoch && available()) { pending = undefined; follow(result); }
    } catch (error) {
      if (serial === epoch && available()) {
        if (error.message === 'MISSION_INTELLIGENCE_REQUIRED') {
          ready = false;
          queuedAmbition = ambition;
          pending = undefined;
        }
        status(errorMessage(error));
        updateControls();
      }
    }
  }

  function showConnection(result, profile = result) {
    const selection = profile?.selection;
    ready = typeof result.scope?.model === 'string';
    node('intelligence-local-controls').hidden = !profile;
    node('intelligence-reconnect').hidden = !selection || selection.ready;
    text('intelligence-readiness', selection?.ready ? `${words.verifiedModel} · ${selection.model_label ?? selection.model}`
      : ready ? `${words.configuredModel} · ${result.scope.model}` : selection ? words.savedModel : words.chooseModel);
    updateControls();
  }

  function startWaiting() {
    if (!ready || !queuedAmbition || queuedAmbition !== currentAmbition()) return;
    const ambition = queuedAmbition;
    queuedAmbition = undefined;
    returnToMission();
    activate(ambition);
  }

  async function intelligenceAction(action, body) {
    if (!session || !available() || setupBusy) return;
    const pairing = session;
    let applied = false;
    setupBusy = true;
    updateControls();
    text('intelligence-readiness', action === 'discover' ? words.findingModels : words.checkingModel);
    try {
      const result = await request(`intelligence-${action}`, body);
      if (pairing !== session || !available()) return;
      if (action === 'discover') {
        const choices = Array.isArray(result.candidates) ? result.candidates : [];
        const host = result.host ?? {};
        const formatGiB = bytes => Number.isFinite(bytes) && bytes >= 0
          ? new Intl.NumberFormat(language, {maximumFractionDigits: 1}).format(bytes / (1024 ** 3)) : null;
        const memory = formatGiB(host.available_memory_bytes);
        const storage = formatGiB(host.available_workspace_bytes);
        text('intelligence-device', [host.system, memory && words.memory(memory), storage && words.storage(storage)].filter(Boolean).join(' · '));
        node('intelligence-install').hidden = Boolean(choices.length);
        node('intelligence-choice').replaceChildren(...choices.map(choice => {
          const option = document.createElement('option');
          option.value = choice.id;
          option.textContent = [choice.model,choice.label].filter(Boolean).join(' · ');
          return option;
        }));
        node('intelligence-select-form').hidden = !choices.length;
        text('intelligence-readiness', choices.length ? words.modelsFound : words.noModel);
      } else {
        showConnection(result);
        node('intelligence-install').hidden = true;
        node('intelligence-select-form').hidden = true;
        applied = ready;
      }
    } catch (error) {
      if (pairing === session && available()) text('intelligence-readiness', errorMessage(error));
    } finally {
      setupBusy = false;
      updateControls();
    }
    if (applied && pairing === session && available()) startWaiting();
  }

  node('intelligence-discover').addEventListener('click', () => intelligenceAction('discover',{consent:true}));
  node('intelligence-reconnect').addEventListener('click', () => intelligenceAction('reconnect',{consent:true}));
  node('intelligence-select-form').addEventListener('submit', event => {
    event.preventDefault();
    intelligenceAction('connect', {id:node('intelligence-choice').value,consent:true,
      mode:node('intelligence-hybrid').checked ? 'hybrid' : 'local'});
  });

  node('execution-code-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (!available()) return;
    const input = node('execution-code');
    const code = input.value.trim();
    input.value = '';
    const epoch = ++serial;
    clearTimeout(timer);
    text('execution-connection', words.pairing);
    try {
      const result = await request('pair', {code});
      if (epoch !== serial || !available()) {
        request('release', {}, undefined, result.session).catch(() => {});
        return;
      }
      session = result.session;
      commandScope = result.command_scope;
      node('intelligence-select-form').hidden = true;
      const end = new Intl.DateTimeFormat(language, {dateStyle:'short', timeStyle:'short'}).format(new Date(result.expires_at));
      text('execution-connection', [words.paired,result.scope.model,end].filter(Boolean).join(' · '));
      showConnection(result, result.intelligence);
      if (view) {
        const recovered = await request('get', {id:view.id});
        if (epoch === serial && session === result.session && available()) follow(recovered);
      }
      if (epoch === serial && session === result.session && available()) startWaiting();
    } catch (error) {
      if (epoch === serial && available()) text('execution-connection', error.message === 'MISSION_PAIRING' ? words.pairInvalid : errorMessage(error));
    }
  });

  for (const action of ['pause','resume','cancel','export']) node(`execution-${action}`).addEventListener('click', async () => {
    if (!session || !view || !available() || busyEpoch === serial) return;
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
        const url = URL.createObjectURL(result);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'frontier-execution.json';
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else follow(result);
    } catch (error) { if (epoch === serial && available()) status(errorMessage(error)); }
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
      node('intelligence-local-controls').hidden = true;
      node('intelligence-select-form').hidden = true;
      clearView();
      node('execution-saved-list').replaceChildren();
      text('execution-connection', words.disconnected);
    } catch (error) { if (epoch === serial && available()) text('execution-connection', errorMessage(error)); }
    finally { if (busyEpoch === epoch) { busyEpoch = undefined; updateControls(); } }
  });
  node('execution-open-saved').addEventListener('click', async () => {
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
          const epoch = ++serial;
          try {
            const recovered = await request('get',{id:row.id});
            if (serial !== epoch || !available()) return;
            onOpen(recovered);
            follow(recovered);
          } catch (error) { if (epoch === serial && available()) text('execution-results-status', errorMessage(error)); }
        });
        item.append(button);
        return item;
      }));
    } catch (error) { if (serial === epoch && available()) text('execution-results-status', errorMessage(error)); }
  });

  function sealSession() {
    if (session) request('release').catch(() => {});
    session = commandScope = undefined;
    ready = false;
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
  return {activate, clearView, updateControls, clearWaiting() { queuedAmbition = undefined; }};
}
