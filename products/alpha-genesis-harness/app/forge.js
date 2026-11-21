/* SPDX-License-Identifier: Apache-2.0 */
(() => {
  'use strict';
  const view = document.getElementById('view-forge');
  if (!view) return;
  const node = key => document.getElementById('forge-' + key);
  const labels = {
    intro: ['Build a tool that recovers an exact result from readings that may contain errors. Qualify it on fresh cases before reuse.',
      'Construisez un outil qui tire un résultat exact de mesures susceptibles de contenir des erreurs. Qualifiez-le sur de nouveaux cas avant de le réutiliser.'],
    mission: ['Investigation', 'Enquête'], refresh: ['Refresh', 'Actualiser'],
    objective: ['What measurement do you need to establish?', 'Quelle grandeur devez-vous établir?'],
    model: ['Local model', 'Modèle local'], connect: ['Connect a model', 'Connecter un modèle'],
    inherit: ['Try a compatible qualified tool first.', 'Essayer d’abord un outil compatible et qualifié.'],
    launch: ['Start investigation', 'Lancer l’enquête'], history: ['Reopen an investigation', 'Rouvrir une enquête'],
    pause: ['Pause', 'Mettre en pause'], resume: ['Resume', 'Reprendre'], cancel: ['Cancel', 'Annuler'],
    bundle: ['Download executable tool', 'Télécharger l’outil exécutable'],
    export: ['Export run evidence', 'Exporter les preuves de l’enquête'],
    details: ['Checks, model route and usage', 'Contrôles, connexion au modèle et utilisation'],
    registry: ['Qualified tools', 'Outils qualifiés'], tool: ['Retained tool', 'Outil conservé'],
    input: ['New readings (JSON)', 'Nouvelles mesures (JSON)'], reuse: ['Run and verify', 'Exécuter et vérifier'],
    scope: ['Qualification covers the registered synthetic telemetry tasks. Frontier-model parity and economic benefit require separate evidence.',
      'La qualification couvre les tâches de télémétrie synthétique enregistrées. L’équivalence avec un modèle de pointe et le bénéfice économique exigent des preuves distinctes.'],
    private: ['Open the private HARNESS connector to launch a run.', 'Ouvrez le connecteur privé HARNESS pour lancer une enquête.'],
    linux: ['Execution requires Linux with libseccomp.so.2.', 'L’exécution requiert Linux avec libseccomp.so.2.'],
    selectModel: ['Choose a local model', 'Choisir un modèle local'],
    selectRun: ['Choose a saved investigation', 'Choisir une enquête enregistrée'],
    selectTool: ['Choose a qualified tool', 'Choisir un outil qualifié'],
    noModel: ['Connect a local llama.cpp or Ollama model to begin.', 'Connectez un modèle local llama.cpp ou Ollama pour commencer.'],
    checked: ['verified checks', 'contrôles réussis'], calls: ['model calls', 'appels au modèle'],
    ready: ['Ready', 'Prêt'], running: ['In progress', 'En cours'],
    paused: ['Paused', 'En pause'], interrupted: ['Interrupted', 'Interrompu'],
    complete: ['Verified on fresh cases', 'Vérifié sur de nouveaux cas'],
    exhausted: ['Attempts exhausted', 'Tentatives épuisées'],
    needs_review: ['Candidate failed qualification', 'Qualification du candidat échouée'],
    cancelled: ['Cancelled', 'Annulé'], failed: ['Failed', 'Échec'],
    integrity_error: ['Integrity check failed', 'Contrôle d’intégrité échoué'],
    route_proposed: ['Proposed mechanism', 'Mécanisme proposé'],
    tool_completed: ['Candidate saved', 'Candidat enregistré'],
    tool_refused: ['Candidate refused', 'Candidat refusé'], response_refused: ['Response refused', 'Réponse refusée'],
    forge_frozen: ['Candidate sealed for fresh tests', 'Candidat scellé pour les nouveaux tests'],
    inherited: ['Reused a qualified tool', 'Outil qualifié réutilisé'],
    model_error: ['Model request failed', 'Échec de la requête au modèle'],
    error: ['The connector could not complete the action. Check the selected mission and model connection.',
      'Le connecteur n’a pas pu terminer l’action. Vérifiez la mission et la connexion au modèle.'],
    inputError: ['Enter valid JSON readings.', 'Saisissez des mesures en JSON valide.'],
    expired: ['The connector session expired. Refresh to reconnect.', 'La session du connecteur a expiré. Actualisez pour vous reconnecter.'],
    reused: ['Fresh result verified', 'Nouveau résultat vérifié'], rejected: ['Fresh result rejected', 'Nouveau résultat rejeté'],
    determined: ['Determined', 'Déterminé'], ambiguous: ['Ambiguous', 'Ambigu'], inconsistent: ['Inconsistent', 'Incompatible'],
    unknownCost: ['Complete cost unknown', 'Coût complet inconnu'],
  };
  const t = key => labels[key]?.[Number(document.documentElement.lang === 'fr')] || key;
  const active = () => !view.classList.contains('hidden');
  const local = location.protocol === 'http:' && location.hostname === '127.0.0.1';
  const terminal = new Set(['complete', 'needs_review', 'exhausted', 'failed', 'cancelled']);
  const activity = new Set(['route_proposed', 'tool_completed', 'tool_refused', 'response_refused',
    'forge_frozen', 'inherited', 'model_error']);
  let token, run, models = [], runs = [], tools = [], available = false, busy = false, timer, notice;
  let freshResult;

  function option(select, value, label) {
    const item = document.createElement('option');
    item.value = value;
    item.textContent = label;
    select.append(item);
  }

  function renderSelect(select, placeholder, options, selected) {
    select.replaceChildren();
    option(select, '', t(placeholder));
    for (const item of options) option(select, item.id, item.label || item.objective || item.id);
    select.value = selected || '';
    select.disabled = !options.length || busy;
  }

  function render() {
    view.querySelectorAll('[data-forge]').forEach(item => { item.textContent = t(item.dataset.forge); });
    node('notice').textContent = notice ? t(notice) : '';
    renderSelect(node('model'), 'selectModel', models, node('model').value);
    renderSelect(node('history'), 'selectRun', runs, run?.id);
    renderSelect(node('tool'), 'selectTool', tools, node('tool').value);
    node('launch').disabled = !available || !node('model').value || busy;
    node('reuse').disabled = !available || !node('tool').value || busy;
    node('run').classList.toggle('hidden', !run);
    node('output').classList.toggle('hidden', !freshResult);
    if (freshResult) {
      const verdict = freshResult.actual?.status ? t(freshResult.actual.status) : '';
      node('output').textContent = (freshResult.passed ? t('reused') : t('rejected')) + '\n' +
        [verdict, freshResult.actual?.value, freshResult.error].filter(Boolean).join(' · ');
    }
    if (!run) return;
    const status = run.worker_active && run.status === 'ready' ? 'running' : run.status;
    node('run-title').textContent = run.objective;
    node('status').textContent = t(status);
    const checks = run.verification?.checks || [];
    const sealed = run.forge?.results;
    const total = sealed && Object.values(sealed).flat().length ? Object.values(sealed).flat() : checks;
    node('progress').textContent = run.model_calls + ' ' + t('calls') + ' · ' +
        total.filter(item => item.passed).length + '/' + total.length + ' ' + t('checked') +
        ' · ' + t('unknownCost');
    node('pause').disabled = busy || status !== 'running';
    node('resume').disabled = busy || !['ready', 'paused', 'interrupted'].includes(status);
    node('cancel').disabled = busy || terminal.has(status);
    node('bundle').disabled = busy || status !== 'complete' || run.forge?.retired;
    node('export').disabled = busy || !terminal.has(status);
    node('activity').replaceChildren();
    for (const event of run.events.filter(event => activity.has(event.kind)).slice(-8)) {
      const item = document.createElement('li');
      const detail = event.detail;
      item.textContent = t(event.kind) + ' · ' +
        (detail.summary || detail.reason || detail.code || detail.sha256 ||
         detail.artifact?.sha256 || detail.outcome?.sha256 || '').slice(0, 400);
      node('activity').append(item);
    }
    node('details').textContent = JSON.stringify({
      checks: run.verification, model_route: run.roles, usage: run.request_costs,
      candidate: run.forge?.frozen_artifact, cohorts: run.forge?.commitments,
    }, null, 2);
  }

  async function request(path, data) {
    if (!local) throw new Error('private');
    if (!token) {
      const session = await fetch('/api/session', {headers: {'X-Harness-Client': 'browser'}, cache: 'no-store'});
      if (!session.ok) throw new Error('private');
      token = (await session.json()).token;
    }
    const options = {headers: {'X-Harness-Token': token}, cache: 'no-store', credentials: 'same-origin'};
    if (data !== undefined) {
      options.method = 'POST';
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(data);
    }
    const response = await fetch(path, options);
    if (response.status === 403) {
      token = undefined;
      throw new Error('expired');
    }
    if (!response.ok) throw new Error('error');
    return path.endsWith('/bundle') ? response.blob() : response.json();
  }

  async function records() {
    const [history, registry] = await Promise.all([
      request('/api/forge/list', {}), request('/api/forge/registry', {}),
    ]);
    runs = history.runs.slice().reverse();
    tools = registry.capabilities.map(item => ({id: item.id, label: item.objective + ' · ' + item.version.slice(0, 10)}));
  }

  async function refresh() {
    if (!active()) return;
    await operate(async () => {
      const [scope, connector] = await Promise.all([request('/api/forge/status'), request('/api/status')]);
      available = scope.available;
      models = connector.providers.filter(provider => provider.ready && provider.local)
        .flatMap(provider => provider.models.map(model => ({
          id: provider.id + '/' + model, label: provider.label + ' · ' + model,
          route: {provider: provider.id, model},
        })));
      notice = !available ? 'linux' : models.length ? '' : 'noModel';
      await records();
      if (run) run = await request('/api/forge/get', {run_id: run.id});
    });
  }

  function schedule() {
    clearTimeout(timer);
    if (!active() || !run || terminal.has(run.status) || (run.status === 'paused' && !run.worker_active)) return;
    timer = setTimeout(() => operate(async () => {
      run = await request('/api/forge/get', {run_id: run.id});
      if (terminal.has(run.status)) await records();
    }), 1500);
  }

  async function operate(operation) {
    if (busy) return;
    busy = true;
    render();
    try {
      await operation();
    } catch (error) {
      notice = ['private', 'expired', 'inputError'].includes(error.message) ? error.message : 'error';
    } finally {
      busy = false;
      render();
      schedule();
    }
  }

  function download(blob, name) {
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.href = url;
    link.download = name;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 3000);
  }

  node('form').addEventListener('submit', event => {
    event.preventDefault();
    const selection = models.find(model => model.id === node('model').value);
    if (!selection) return;
    operate(async () => {
      run = await request('/api/forge/create', {...selection.route, objective: node('objective').value,
        language: document.documentElement.lang === 'fr' ? 'fr' : 'en', reuse: node('inherit').checked});
      await records();
      run = await request('/api/forge/start', {run_id: run.id});
    });
  });
  node('reuse-form').addEventListener('submit', event => {
    event.preventDefault();
    const id = node('tool').value;
    operate(async () => {
      let input;
      try { input = JSON.parse(node('input').value); } catch (_) { throw new Error('inputError'); }
      freshResult = await request('/api/forge/reuse', {run_id: id, input});
    });
  });
  node('model').addEventListener('change', render);
  node('tool').addEventListener('change', render);
  node('history').addEventListener('change', () => {
    const id = node('history').value;
    operate(async () => { run = id ? await request('/api/forge/get', {run_id: id}) : null; });
  });
  node('refresh').addEventListener('click', refresh);
  node('connect').addEventListener('click', () => document.querySelector('[data-view="intelligence"]')?.click());
  for (const action of ['pause', 'resume', 'cancel', 'bundle', 'export']) {
    node(action).addEventListener('click', () => operate(async () => {
      const result = await request('/api/forge/' + action, {run_id: run.id});
      if (action === 'bundle') download(result, 'CAPABILITY-FORGE-' + run.id + '.zip');
      else if (action === 'export') download(new Blob([JSON.stringify(result, null, 2)], {type: 'application/json'}),
        'CAPABILITY-FORGE-' + run.id + '.json');
      else run = result;
    }));
  }
  new MutationObserver(render).observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
  new MutationObserver(() => { if (active()) refresh(); else clearTimeout(timer); })
    .observe(view, {attributes: true, attributeFilter: ['class']});
  render();
})();
