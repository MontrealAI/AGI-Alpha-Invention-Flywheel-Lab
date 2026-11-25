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

export function setupExecution(member, language, {onOpen, currentAmbition}) {
  const words = copy[language];
  const available = () => !member.hidden;
  let session, commandScope, view, pending, busyEpoch, serial = 0, timer;
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
    return error instanceof TypeError ? words.unreachable : words.refused;
  }

  function updateControls() {
    node('execution-open-saved').disabled = !session;
    node('execution-disconnect').hidden = !session;
    node('execution-send-current').hidden = !session || !currentAmbition() || Boolean(view || pending);
    node('execution-retry').hidden = !session || !pending;
    for (const id of ['execution-pause','execution-resume','execution-cancel','execution-disconnect']) node(id).disabled = busyEpoch === serial;
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
        item.reason ?? item.code].filter(Boolean).join(' · ');
      return li;
    }));
    const latest = result.events.findLast(item => item.preview);
    text('execution-result', latest?.preview ?? '');
    node('execution-result').hidden = !latest;
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
    view = pending = undefined;
    delete node('mission-execution').dataset.state;
    node('mission-execution').hidden = true;
    for (const id of ['execution-status','execution-counts','execution-result','execution-proposal']) text(id, '');
    node('execution-understanding').hidden = true;
    for (const id of ['execution-events','execution-artifacts']) node(id).replaceChildren();
    updateControls();
  }

  async function activate(ambition) {
    if (!available() || !session || typeof ambition !== 'string' || !ambition.trim()) return;
    if (view?.ambition === ambition && (view.worker_active || activeStates.has(view.status))) return;
    const retry = pending?.ambition === ambition ? pending : undefined;
    const command = retry?.command ?? crypto.randomUUID();
    const previous = retry?.previous ?? view?.id;
    const epoch = ++serial;
    clearTimeout(timer);
    pending = {ambition,command,previous};
    view = undefined;
    node('mission-execution').hidden = false;
    delete node('mission-execution').dataset.state;
    for (const id of ['execution-pause','execution-resume','execution-cancel','execution-retry','execution-send-current']) node(id).hidden = true;
    node('execution-export').disabled = true;
    for (const id of ['execution-counts','execution-result','execution-proposal']) text(id, '');
    node('execution-understanding').hidden = true;
    for (const id of ['execution-events','execution-artifacts']) node(id).replaceChildren();
    status(words.starting);
    try {
      const result = await request('submit', previous ? {ambition,language,previous} : {ambition,language}, command);
      if (serial === epoch && available()) { pending = undefined; follow(result); }
    } catch (error) {
      if (serial === epoch && available()) { status(errorMessage(error)); updateControls(); }
    }
  }

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
      const end = new Intl.DateTimeFormat(language, {dateStyle:'short', timeStyle:'short'}).format(new Date(result.expires_at));
      text('execution-connection', `${words.paired} · ${result.scope.model} · ${end}`);
      updateControls();
      if (view) {
        const recovered = await request('get', {id:view.id});
        if (epoch === serial && session === result.session && available()) follow(recovered);
      }
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
    clearView();
    node('execution-code-form').reset();
    node('execution-saved-list').replaceChildren();
    text('execution-connection', '');
    text('execution-results-status', '');
  }
  window.addEventListener('frontier:member-lock', sealSession);
  window.addEventListener('pagehide', sealSession);
  updateControls();
  return {activate, clearView, updateControls};
}
