/* SPDX-License-Identifier: Apache-2.0 */
(() => {
  'use strict';
  const root = document.getElementById('workshop');
  if (!root) return;
  const el = id => document.getElementById('workshop-' + id);
  const copy = {
    title: ['The instrument workshop', 'L’atelier des instruments'],
    intro: ['Give an ambition a testable outcome. Build an instrument, inspect the checks and take the result with you.', 'Donnez à votre ambition un résultat vérifiable. Construisez un instrument, examinez les essais et emportez le résultat.'],
    mission: ['Mission', 'Mission'], bench: ['Workbench', 'Atelier'], evidence: ['Evidence', 'Preuves'],
    ambition: ['What would you like to make possible?', 'Qu’aimeriez-vous rendre possible?'],
    business: ['Create a new business', 'Créer une entreprise'],
    access: ['Make an inaccessible service possible', 'Rendre possible un service inaccessible'],
    expertise: ['Turn expertise into a new capability', 'Transformer une expertise en nouvelle capacité'],
    shared: ['Address a challenge affecting many people', 'Relever un défi qui touche beaucoup de personnes'],
    contract: ['What should the instrument do?', 'Que doit faire l’instrument?'],
    custom: ['Use my own input and output', 'Utiliser mes propres entrées et résultats'],
    foundry: ['Instrument Foundry · defect or sensor drift', 'Fonderie d’instruments · défaut ou dérive du capteur'],
    contrast: ['Source-grounded check · WCAG text contrast', 'Vérification avec sources · contraste du texte selon les WCAG'],
    arrangement: ['Shared design · cost, consent and liquidity', 'Conception partagée · coût, consentement et liquidités'],
    model: ['Model connection', 'Connexion au modèle'], noModel: ['Choose a connected model', 'Choisissez un modèle connecté'],
    details: ['Mission details and independent checks', 'Détails de la mission et essais indépendants'],
    context: ['Who benefits, what can you use and what limits matter?', 'Qui en bénéficie, de quoi disposez-vous et quelles limites comptent?'],
    cases: ['Independent input and output examples (JSON)', 'Exemples indépendants d’entrées et de résultats (JSON)'],
    casesHelp: ['Describe the input and output fields above. Supply separate examples here. Their answers stay outside the model request.', 'Décrivez les champs d’entrée et de sortie ci-dessus. Fournissez des exemples distincts ici. Leurs réponses restent hors de la requête au modèle.'],
    loop: ['Optional approach', 'Approche facultative'], chooseLoop: ['Use the shortest useful route', 'Choisir la voie utile la plus directe'],
    compass: ['Counterexample Compass', 'Boussole des contre-exemples'],
    escape: ['Constraint Escape', 'Redéfinition des contraintes'], proof: ['Proof Factory', 'Fabrique de preuves'],
    successor: ['Successor Engine', 'Moteur de succession'], surplus: ['Positive-Sum Multiplier', 'Multiplicateur à somme positive'],
    start: ['Build and test', 'Construire et tester'], save: ['Save draft', 'Enregistrer le brouillon'],
    connect: ['Model connection settings', 'Paramètres de connexion au modèle'],
    history: ['Reopen a saved mission', 'Rouvrir une mission enregistrée'],
    pause: ['Pause', 'Mettre en pause'], resume: ['Resume', 'Reprendre'], cancel: ['Cancel', 'Annuler'],
    fresh: ['Prepare a fresh logger mission', 'Préparer une nouvelle mission de calibration'],
    export: ['Download instrument and proof', 'Télécharger l’instrument et les preuves'],
    offline: ['Offline', 'Hors ligne'], manual: ['Open the manual workspace', 'Ouvrir l’espace de travail manuel'],
    local: ['Local model', 'Modèle local'], api: ['Configured API', 'API configurée'],
    connected: ['Private connector', 'Connecteur privé'], checking: ['Checking the connector…', 'Vérification du connecteur…'],
    static: ['Drafts stay in this browser. Open the downloadable application for private model execution.', 'Les brouillons restent dans ce navigateur. Ouvrez l’application téléchargeable pour exécuter un modèle en privé.'],
    download: ['Downloadable editions', 'Éditions téléchargeables'],
    unavailable: ['The connector is unavailable. Open the downloaded application again to reconnect.', 'Le connecteur est indisponible. Rouvrez l’application téléchargée pour vous reconnecter.'],
    noConnection: ['Connect an installed local model or choose a configured service.', 'Connectez un modèle installé ou choisissez un service configuré.'],
    localBoundary: ['The local model receives your ambition, contract, candidate instrument and repair feedback. Independent test answers stay in the connector.', 'Le modèle local reçoit votre ambition, le contrat, l’instrument candidat et les retours de correction. Les réponses aux essais indépendants restent dans le connecteur.'],
    apiBoundary: ['The selected provider receives your ambition, contract, candidate instrument and repair feedback. Provider terms and charges may apply.', 'Le fournisseur reçoit votre ambition, le contrat, l’instrument candidat et les retours de correction. Les conditions et les frais du fournisseur peuvent s’appliquer.'],
    consentLocal: ['Send these mission details to the selected local model.', 'Transmettre ces détails de mission au modèle local sélectionné.'],
    consentAPI: ['Send these mission details to the selected API and use its configured allowance.', 'Transmettre ces détails de mission à l’API sélectionnée et utiliser l’allocation configurée.'],
    consentMissing: ['Choose a model and confirm the data transfer.', 'Choisissez un modèle et confirmez le transfert des données.'],
    saved: ['Draft saved in this browser.', 'Brouillon enregistré dans ce navigateur.'],
    storage: ['Browser storage is unavailable. Copy your draft before closing this page.', 'Le stockage du navigateur est indisponible. Copiez votre brouillon avant de fermer la page.'],
    inputError: ['Enter valid JSON examples and describe their contract in Mission details.', 'Saisissez des exemples JSON valides et décrivez leur contrat dans les détails de la mission.'],
    empty: ['Register or reopen a mission to see its checked work.', 'Enregistrez ou rouvrez une mission pour voir les travaux vérifiés.'],
    docket: ['Decision', 'Décision'], uncertainty: ['Question that could change the decision', 'Question qui pourrait changer la décision'],
    routes: ['Routes to compare', 'Voies à comparer'], version: ['Mission revision', 'Révision de la mission'],
    artifacts: ['Runnable artifacts', 'Artefacts exécutables'], graph: ['Mission graph', 'Graphe de la mission'],
    pending: ['No instrument has been produced yet.', 'Aucun instrument n’a encore été produit.'],
    activity: ['Actual activity', 'Activité réelle'], checks: ['Independent checks', 'Essais indépendants'],
    source: ['Sources and versions', 'Sources et versions'], limits: ['Scope and limitations', 'Portée et limites'],
    costs: ['Model usage and costs', 'Utilisation et coûts du modèle'],
    costUnknown: ['Total economic cost is unknown.', 'Le coût économique total est inconnu.'],
    noUsage: ['No model request has been sent.', 'Aucune requête n’a été envoyée au modèle.'],
    proofDebt: ['Evidence still missing', 'Preuves encore manquantes'],
    failed: ['Failed', 'Échec'], passed: ['Passed', 'Réussi'], open: ['Open', 'En cours'],
    rejected: ['Needs a different route or repair', 'Nouvelle voie ou correction requise'],
    admitted: ['Qualified for these checks', 'Qualifié pour ces essais'],
    revoked: ['Revoked', 'Révoqué'], stale: ['Dependencies changed', 'Les dépendances ont changé'],
    ready: ['Ready', 'Prêt'], running: ['Running', 'En cours'], paused: ['Paused', 'En pause'],
    complete: ['Complete', 'Terminé'], cancelled: ['Cancelled', 'Annulé'], exhausted: ['Attempt limit reached', 'Limite de tentatives atteinte'],
    needs_review: ['Needs review', 'À examiner'], interrupted: ['Interrupted', 'Interrompu'],
    downloadReady: ['Download ready. The archive includes replay instructions.', 'Téléchargement prêt. L’archive contient les instructions de reproduction.'],
    next: ['You can download and replay the checks or start a fresh mission.', 'Vous pouvez télécharger et reproduire les essais ou démarrer une nouvelle mission.'],
    repair: ['Inspect the failed checks before starting a new run.', 'Examinez les essais échoués avant de lancer une nouvelle exécution.'],
    wait: ['The local connector records construction and verification as work completes.', 'Le connecteur local consigne la construction et la vérification au fil de l’exécution.'],
    recover: ['A request may have reached the model. Resume explicitly to permit another attempt.', 'Une requête a pu atteindre le modèle. Reprenez explicitement pour autoriser une nouvelle tentative.'],
    freshReady: ['A fresh test set will check this artifact on logger handoff conditions.', 'Un nouveau jeu d’essais vérifiera cet artefact dans les conditions de remise en service du capteur.'],
    freshGoal: ['Requalify the instrument for a cold-chain logger handoff.', 'Requalifier l’instrument pour la remise en service d’un capteur de chaîne du froid.'],
    conflict: ['This mission changed. Reopen its latest revision and try again.', 'Cette mission a changé. Rouvrez sa dernière révision et réessayez.'],
    refused: ['The connector declined the request. Check the selected mission and connection.', 'Le connecteur a refusé la demande. Vérifiez la mission et la connexion sélectionnées.'],
    incomplete: ['An interrupted operation may still be settling. Inspect the current mission before retrying.', 'Une opération interrompue peut encore être en cours de traitement. Examinez la mission avant de réessayer.'],
    settingsOffline: ['Open the downloaded application to manage a model connection.', 'Ouvrez l’application téléchargée pour gérer une connexion au modèle.'],
    case_count: ['checks accepted', 'essais réussis'], exception: ['Exception', 'Exception'],
    foundry_hint: ['Three sensor formats. Test whether an independent reference can separate a product defect from drift.', 'Trois formats de capteurs. Testez si une référence indépendante peut distinguer un défaut de la dérive.'],
    contrast_hint: ['Check threshold and exception claims using a pinned W3C criterion and independent cases.', 'Vérifiez les seuils et les exceptions avec une version précise du critère du W3C et des cas indépendants.'],
    arrangement_hint: ['Compare shared and separate work under hypothetical complete costs, outside options and cash available today.', 'Comparez les travaux partagés et séparés selon des coûts complets hypothétiques, les options de repli et les liquidités actuelles.'],
    custom_hint: ['Describe a small instrument you could use, then supply independently chosen test examples.', 'Décrivez un petit instrument qui vous serait utile, puis fournissez des exemples d’essai choisis indépendamment.'],
    original: ['Original result', 'Résultat original'],
  };
  const ideas = {
    business: ['Help a small business decide what it can deliver reliably to its first customers. ', 'Aider une petite entreprise à décider ce qu’elle peut livrer de façon fiable à ses premiers clients. '],
    access: ['Make a service reachable for people currently excluded by a practical barrier. ', 'Rendre un service accessible aux personnes actuellement exclues par un obstacle concret. '],
    expertise: ['Turn a decision an expert makes repeatedly into an instrument others can test and use. ', 'Transformer une décision récurrente d’expert en un instrument que d’autres peuvent tester et utiliser. '],
    shared: ['Help several groups solve a shared problem while meeting their individual requirements. ', 'Aider plusieurs groupes à résoudre un problème commun tout en respectant leurs besoins propres. '],
  };
  const vocabulary = {
    goal: 'objectif', uncertainty: 'incertitude', claim: 'affirmation', gate: 'critère', permission: 'permission',
    tool: 'outil', alternative: 'option', source: 'source', artifact: 'artefact', observation: 'observation',
    cost: 'coût', capability: 'capacité', conditions: 'conditionne', tests: 'teste', addresses: 'traite',
    requires: 'exige', pursues: 'poursuit', depends_on: 'dépend de', constructed_by: 'construit par',
    supports: 'appuie', contradicts: 'contredit', incurs: 'entraîne', can_inherit: 'peut hériter de',
    created: 'Mission enregistrée', model_queued: 'Modèle en attente', model_started: 'Requête au modèle',
    model_progress: 'Réponse en cours', model_completed: 'Réponse reçue', route_proposed: 'Voie proposée',
    tool_completed: 'Outil exécuté', tool_refused: 'Outil refusé', verification: 'Vérification',
    response_refused: 'Réponse refusée', model_error: 'Erreur du modèle', admission_refused: 'Connexion refusée',
    late_result_discarded: 'Résultat tardif écarté', model_not_dispatched: 'Requête non envoyée',
    inherited: 'Artefact hérité', critique: 'Critique', finished: 'Terminé', stopped: 'Arrêté',
    paused: 'Mis en pause', resumed: 'Repris', cancelled: 'Annulé', revoked: 'Révoqué',
    interruption_recovered: 'Reprise après interruption',
  };
  const factText = new Map([
    ['Could the same reading be a product defect or a sensor offset?', 'Une même lecture peut-elle signaler un défaut du produit ou un décalage du capteur?'],
    ['Does a low ratio violate the criterion, or is the exception actually applicable?', 'Un faible rapport enfreint-il le critère ou l’exception s’applique-t-elle?'],
    ['Will each participant prefer the route, and can work start with available cash?', 'Chaque participant préférera-t-il cette option et les liquidités permettent-elles de commencer?'],
    ['Does the new instrument satisfy the independently supplied examples?', 'Le nouvel instrument satisfait-il les exemples fournis indépendamment?'],
    ['Use one raw sample', 'Utiliser une seule lecture brute'],
    ['Use ordinary regression with qualified checks', 'Appliquer une régression classique avec des contrôles qualifiés'],
    ['Build three adapters independently', 'Construire trois adaptateurs séparément'],
    ['Share an instrument after qualifying each adapter', 'Partager un instrument après avoir qualifié chaque adaptateur'],
    ['Stop or gather a physical reference', 'Arrêter ou obtenir une référence physique'],
    ['Review the official criterion directly', 'Examiner directement le critère officiel'],
    ['Use a contrast checker plus manual exception review', 'Utiliser un vérificateur de contraste avec examen manuel des exceptions'],
    ['Construct a claim-and-exception decision instrument', 'Construire un outil de décision pour les affirmations et exceptions'],
    ['Request a missing measurement', 'Demander la mesure manquante'],
    ['Build separately', 'Construire séparément'],
    ['Share a core and qualify separate adapters', 'Partager un noyau et qualifier des adaptateurs distincts'],
    ['Stage or change the offer', 'Échelonner ou modifier l’offre'],
    ['Wait or stop', 'Attendre ou arrêter'],
    ['Use an existing tool', 'Utiliser un outil existant'],
    ['Construct a bounded instrument', 'Construire un instrument à portée limitée'],
    ['Gather missing evidence', 'Recueillir les preuves manquantes'],
    ['The constructed instrument meets the declared scope and checks.', 'L’instrument construit respecte la portée et les essais déclarés.'],
    ['Construct a declarative instrument', 'Construire un instrument déclaratif'],
    ['Synthetic readings. Requires traceable physical references, a qualified operating range and a stable affine regime in the field. A single midpoint cannot exclude every nonlinear or time-varying response.', 'Lectures synthétiques. Sur le terrain, il faut des références physiques traçables, une plage qualifiée et un régime affine stable. Un seul point médian ne peut exclure toute non-linéarité ou variation temporelle.'],
    ['Checks supplied measurements and human-classified exceptions for one pinned criterion. It does not classify page content, measure pixels or certify a site.', 'Vérifie les mesures et les exceptions classées par un humain pour un critère précis. La classification du contenu, la mesure des pixels et la certification du site sont hors de sa portée.'],
    ['Hypothetical input only. Include development, inference, tools, verification, failed work, acquisition, delivery, maintenance, refunds and obligations as applicable. Assumes the independent cost and alternative inputs are complete; this is not a financial ledger or market validation.', 'Données hypothétiques. Incluez le développement, l’inférence, les outils, la vérification, les échecs, l’acquisition, la livraison, la maintenance, les remboursements et les obligations, selon le cas. Les coûts et options fournis sont supposés complets.'],
    ['Operator-authored cases and source descriptions. External validity has not been inferred.', 'Cas et descriptions de sources fournis par l’opérateur. La validité externe reste à établir.'],
  ]);
  const key = 'alpha-genesis-workshop-v1';
  const terminal = new Set(['complete', 'cancelled', 'failed', 'exhausted', 'needs_review']);
  const loopback = location.protocol === 'http:' && location.hostname === '127.0.0.1';
  let token = null, providers = [], mission = null, chosen = null, inheritance = null, inProgress = false;
  let selectedView = 'mission', operation = 0, poll = null, initialize = null, connection = loopback ? 'checking' : 'static';
  let pending = null, published = null;
  const french = () => document.documentElement.lang === 'fr';
  const t = id => copy[id]?.[Number(french())] ?? id;
  const fact = value => french() ? (factText.get(value) ?? value) : value;
  const word = value => french() ? (vocabulary[value] ?? value.replaceAll('_', ' ')) : value.replaceAll('_', ' ');
  function node(type, value, css) {
    const element = document.createElement(type);
    if (value !== undefined) element.textContent = value;
    if (css) element.className = css;
    return element;
  }
  function section(parent, title, description) {
    const box = node('section', undefined, 'workshop-card');
    box.append(node('h3', t(title)));
    if (description) box.append(node('p', description, 'subtle'));
    parent.append(box);
    return box;
  }
  function detail(parent, title, value) {
    const box = node('details', undefined, 'workshop-detail');
    box.append(node('summary', title), node('pre', JSON.stringify(value, null, 2)));
    parent.append(box);
  }
  function stored() {
    try { return JSON.parse(localStorage.getItem(key)) ?? {}; } catch { return {}; }
  }
  function store(value) {
    try { localStorage.setItem(key, JSON.stringify({...stored(), ...value})); return true; } catch { return false; }
  }
  function report(code) {
    el('message').textContent = code ? t(code) : '';
  }
  function reportError(error) {
    report(error.code === 'WORKSHOP_CONFLICT' ? 'conflict' :
      error.code === 'WORKSHOP_STALE' ? 'stale' :
      error.code === 'WORKSHOP_CONSENT' ? 'consentMissing' :
      error.code === 'WORKFLOW_BUSY' ? 'incomplete' :
      !token ? 'unavailable' : 'refused');
  }
  function route() {
    return providers.find(p => p.key === el('model').value);
  }
  function renderSetup() {
    const provider = route();
    el('mode').textContent = t(provider ? (provider.local ? 'local' : 'api') : token ? 'connected' : 'offline');
    el('connection').textContent = t(provider ? (provider.local ? 'localBoundary' : 'apiBoundary') : token ? 'noConnection' : connection);
    if (connection === 'static') {
      const link = node('a', t('download'));
      const releases = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/releases';
      link.href = published ? releases + '/tag/alpha-genesis-harness-v' + window.HarnessEngine.VERSION + '-rc-' + published.slice(0, 12) : releases;
      el('connection').append(' ', link);
      if (published) el('connection').append(' · ' + t('version') + ' ' + published.slice(0, 12));
    }
    el('model').disabled = !token || !providers.length || inProgress;
    el('history').disabled = inProgress;
    el('protocol').textContent = t(el('family').value + '_hint');
    el('cases-row').hidden = el('family').value !== 'custom';
    el('start').disabled = !token || !provider || inProgress || Boolean(mission?.worker_active);
    el('consent-row').hidden = !provider;
    el('consent-text').textContent = t(provider?.local ? 'consentLocal' : 'consentAPI');
    el('connect').textContent = t(loopback ? 'connect' : 'manual');
  }
  function language() {
    root.querySelectorAll('[data-workshop]').forEach(n => { n.textContent = t(n.dataset.workshop); });
    el('views').setAttribute('aria-label', french() ? 'Vues de l’atelier' : 'Workshop views');
    el('invitations').setAttribute('aria-label', french() ? 'Invitations de mission' : 'Mission invitations');
    if (el('model').options[0]) el('model').options[0].textContent = t('noModel');
    if (el('history').options[0]) el('history').options[0].textContent = t('history');
    renderSetup();
    render();
  }
  function panel(view) {
    selectedView = view;
    root.querySelectorAll('[data-workshop-view]').forEach(button => {
      const active = button.dataset.workshopView === view;
      button.setAttribute('aria-pressed', String(active));
      document.getElementById(button.getAttribute('aria-controls')).hidden = !active;
    });
    render();
  }
  function render() {
    const summary = el('summary');
    const actions = el('actions');
    actions.hidden = !mission;
    if (!mission) {
      summary.replaceChildren();
      el('bench').replaceChildren(node('p', t('empty'), 'subtle'));
      el('evidence').replaceChildren(node('p', t('empty'), 'subtle'));
      return;
    }
    const m = mission, docket = m.docket;
    const active = m.worker_active || m.status === 'running';
    const resume = ['paused', 'interrupted', 'ready'].includes(m.status) && !m.worker_active;
    el('pause').disabled = !active || inProgress || !token;
    el('cancel').disabled = terminal.has(m.status) || inProgress || !token;
    el('resume').disabled = !resume || !docket.current || inProgress || !token;
    el('export').disabled = active || inProgress || !token;
    el('fresh').hidden = docket.status !== 'admitted' || m.family !== 'foundry' || m.fresh;
    el('fresh').disabled = !token || inProgress;
    // Polling should not announce identical text through the live region.
    const summaryKey = [m.revision, m.worker_active, docket.status, french()].join('/');
    if (summary.dataset.rendered !== summaryKey) {
      summary.dataset.rendered = summaryKey;
      summary.replaceChildren();
      const box = section(summary, 'docket', m.objective);
      box.append(node('p', t(docket.status) + ' · ' + t(m.status), 'workshop-decision'));
      box.append(node('p', docket.accepted + ' / ' + docket.planned + ' ' + t('case_count')));
      box.append(node('h4', t('uncertainty')), node('p', fact(m.uncertainty)));
      const proposed = m.events.filter(e => e.kind === 'route_proposed').at(-1);
      if (proposed) {
        box.append(node('h4', word('route_proposed')), node('p', proposed.detail.summary, 'subtle'));
      }
      const routeList = node('ul');
      m.routes.forEach(value => routeList.append(node('li', fact(value))));
      const list = node('details', undefined, 'workshop-detail');
      list.append(node('summary', t('routes')), routeList);
      box.append(list, node('p', t(m.recovery_notice ? 'recover' : docket.status === 'admitted' ? 'next' : terminal.has(m.status) ? 'repair' : 'wait'), 'bounded-details'));
    }
    if (selectedView === 'bench') renderBench(m);
    if (selectedView === 'evidence') renderEvidence(m);
  }
  function renderBench(m) {
    const target = el('bench');
    const renderKey = [m.revision, m.docket.status, french()].join('/');
    if (target.dataset.rendered === renderKey) return;
    target.dataset.rendered = renderKey;
    target.replaceChildren();
    const artifacts = section(target, 'artifacts');
    const fileRows = Object.entries(m.artifacts);
    if (!fileRows.length) artifacts.append(node('p', t('pending'), 'subtle'));
    else {
      const files = node('ul');
      for (const [name, record] of fileRows) files.append(node('li', name + ' · ' + record.sha256.slice(0, 16)));
      artifacts.append(files);
    }
    const graph = section(target, 'graph');
    const nodes = new Map(m.graph.nodes.map(row => [row.id, row]));
    const links = node('ul', undefined, 'workshop-links');
    for (const edge of m.graph.edges) {
      const a = nodes.get(edge.from), b = nodes.get(edge.to);
      links.append(node('li', word(a.kind) + ' · ' + fact(a.title) + ' → ' + word(edge.type) + ' → ' + fact(b.title)));
    }
    graph.append(links);
  }
  function renderEvidence(m) {
    const target = el('evidence');
    const renderKey = [m.revision, m.docket.status, french()].join('/');
    if (target.dataset.rendered === renderKey) return;
    target.dataset.rendered = renderKey;
    target.replaceChildren();
    const tests = section(target, 'checks', m.docket.accepted + ' / ' + m.docket.planned + ' ' + t('case_count'));
    const gap = m.docket.planned - m.docket.accepted;
    if (gap || !m.docket.current) tests.append(node('p', t('proofDebt') + (gap ? ' · ' + gap : ' · ' + t('stale')), 'bounded-details'));
    for (const check of m.checks) detail(tests, check.id + ' · ' + t(check.passed ? 'passed' : 'failed'), check);
    const provenance = section(target, 'source');
    const sources = node('ul');
    for (const source of m.sources) {
      const link = node('a', source.title);
      if (/^https:\/\//u.test(source.url)) link.href = source.url;
      const item = node('li'); item.append(link); sources.append(item);
    }
    if (m.sources.length) provenance.append(sources);
    provenance.append(node('p', t('version') + ' · ' + m.revision, 'workshop-hash'));
    detail(provenance, t('version'), {contract: m.contract_sha256, ...m.source_sha256});
    section(target, 'limits', fact(m.limits));
    const costs = section(target, 'costs', t(m.requests.length ? 'costUnknown' : 'noUsage'));
    for (const call of m.requests) detail(costs, call.provider + ' · ' + call.model, call);
    const activity = section(target, 'activity');
    for (const event of m.events.slice().reverse()) {
      const timestamp = new Date(event.at).toLocaleTimeString(french() ? 'fr-CA' : 'en-CA');
      detail(activity, timestamp + ' · ' + word(event.kind), event.detail);
    }
  }
  async function request(action, payload) {
    if (!token) throw new Error('Disconnected');
    const response = await fetch('/api/workshop/' + action, {
      method: 'POST', cache: 'no-store', credentials: 'omit',
      headers: {'Content-Type': 'application/json', 'X-Harness-Token': token}, body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const reply = await response.json().catch(() => ({}));
      if (reply.error?.code === 'TOKEN') {
        token = null; connection = 'unavailable'; renderSetup();
      }
      throw Object.assign(new Error('Connector request failed'), {code: reply.error?.code});
    }
    return action === 'bundle' ? response.blob() : response.json();
  }
  async function history() {
    const data = await request('list', {});
    const picker = el('history');
    picker.replaceChildren(node('option', t('history')));
    picker.options[0].value = '';
    for (const row of data.missions) {
      const option = node('option', row.objective);
      option.value = row.id;
      picker.append(option);
    }
    if (chosen) picker.value = chosen;
    el('reopen').hidden = !data.missions.length;
  }
  function setMission(value) {
    mission = value;
    if (value) {
      chosen = value.id;
      el('history').value = chosen;
      store({chosen});
    } else {
      delete el('summary').dataset.rendered;
      delete el('bench').dataset.rendered;
      delete el('evidence').dataset.rendered;
    }
    renderSetup();
    render();
    clearTimeout(poll);
    if (value && (value.worker_active || value.status === 'running') && token) {
      poll = setTimeout(() => refresh(value.id), 1400);
    }
  }
  async function refresh(id) {
    const issued = operation;
    try {
      const state = await request('get', {run_id: id});
      if (issued === operation && chosen === id) setMission(state);
    } catch (error) {
      if (issued === operation && chosen === id) reportError(error);
    }
  }
  function config() {
    if (!loopback || initialize) return initialize;
    initialize = (async () => {
      try {
        const response = await fetch('/api/session', {headers: {'X-Harness-Client': 'browser'}, credentials: 'omit', cache: 'no-store'});
        if (!response.ok) throw new Error('Session refused');
        const session = await response.json();
        const status = await fetch('/api/status', {headers: {'X-Harness-Token': session.token}, credentials: 'omit', cache: 'no-store'});
        if (!status.ok) throw new Error('Connector unavailable');
        token = session.token;
        connection = 'connected';
        const prior = el('model').value;
        providers = (await status.json()).providers.filter(p => p.ready).flatMap(p => p.models.map(model => ({
          provider: p.id, model, local: p.local === true, label: p.label, key: JSON.stringify([p.id, model]),
        })));
        const picker = el('model');
        picker.replaceChildren(node('option', t('noModel')));
        picker.options[0].value = '';
        for (const p of providers) {
          const option = node('option', p.label + ' · ' + p.model);
          option.value = p.key;
          picker.append(option);
        }
        if (providers.some(p => p.key === prior)) picker.value = prior;
        else el('consent').checked = false;
        await history();
        if (chosen) await refresh(chosen);
      } catch {
        token = null; providers = []; connection = 'unavailable';
      }
      renderSetup();
    })().finally(() => { initialize = null; });
    return initialize;
  }
  function draft() {
    return {objective: el('ambition').value, family: el('family').value, context: el('context').value,
      casesText: el('cases').value, loop: el('loop').value === 'successor' ? '' : el('loop').value};
  }
  function requestIdentity() {
    return Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, '0')).join('');
  }
  el('form').addEventListener('submit', async event => {
    event.preventDefault();
    const p = route();
    if (inProgress || !p || !el('consent').checked) { report('consentMissing'); return; }
    const d = draft();
    const input = {objective: d.objective, family: d.family, context: d.context,
      provider: p.provider, model: p.model, consent: p.local ? 'local' : 'authenticated_api', loop: el('loop').value};
    if (input.family === 'custom') {
      try {
        input.cases = JSON.parse(d.casesText);
        if (!Array.isArray(input.cases) || !d.context.trim()) throw new Error();
      } catch {
        el('details').open = true;
        el('cases').focus();
        report('inputError');
        return;
      }
    }
    if (inheritance) { input.inherit = inheritance; input.fresh = true; }
    const signature = JSON.stringify(input);
    if (pending?.signature !== signature) pending = {signature, id: requestIdentity()};
    input.request_id = pending.id;
    inProgress = true; operation += 1; renderSetup(); report();
    try {
      const value = await request('register', input);
      setMission(value);
      el('consent').checked = false;
      if (value.status === 'ready' && !value.worker_active) {
        setMission(await request('start', {run_id: value.id, revision: value.revision}));
      }
      pending = null;
      inheritance = null;
      el('loop').querySelector('option[value="successor"]').disabled = true;
      if (el('loop').value === 'successor') el('loop').value = '';
      await history();
    } catch (error) {
      reportError(error);
      if (chosen) await refresh(chosen);
    } finally {
      inProgress = false; renderSetup(); render();
    }
  });
  async function act(action) {
    if (!mission || inProgress) return;
    inProgress = true; operation += 1; renderSetup(); render(); report();
    const current = mission;
    try {
      const response = await request(action, {run_id: current.id, revision: current.revision});
      if (action === 'bundle') {
        const url = URL.createObjectURL(response);
        const a = node('a');
        a.href = url;
        a.download = 'ALPHA-GENESIS-' + current.id + '.zip';
        document.body.append(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 3000);
        report('downloadReady');
      } else {
        setMission(response);
      }
    } catch (error) {
      reportError(error);
      await refresh(current.id);
    } finally {
      inProgress = false; renderSetup(); render();
    }
  }
  for (const action of ['pause', 'resume', 'cancel']) el(action).addEventListener('click', () => act(action));
  el('export').addEventListener('click', () => act('bundle'));
  el('fresh').addEventListener('click', () => {
    inheritance = mission.id;
    el('family').value = 'foundry';
    el('loop').querySelector('option[value="successor"]').disabled = false;
    el('loop').value = 'successor';
    el('ambition').value = t('freshGoal');
    el('context').value = '';
    el('ambition').focus();
    renderSetup();
    report('freshReady');
  });
  el('history').addEventListener('change', () => {
    if (!el('history').value || inProgress) return;
    chosen = el('history').value;
    operation += 1;
    clearTimeout(poll);
    inheritance = null;
    el('loop').value = '';
    el('loop').querySelector('option[value="successor"]').disabled = true;
    report();
    refresh(chosen);
  });
  el('family').addEventListener('change', () => {
    inheritance = null;
    el('loop').querySelector('option[value="successor"]').disabled = true;
    if (el('loop').value === 'successor') el('loop').value = '';
    renderSetup();
  });
  el('model').addEventListener('change', () => { el('consent').checked = false; renderSetup(); });
  el('save').addEventListener('click', () => report(store({draft: draft()}) ? 'saved' : 'storage'));
  el('connect').addEventListener('click', () => document.querySelector('[data-view="intelligence"]')?.click());
  root.querySelectorAll('[data-workshop-idea]').forEach(button => button.addEventListener('click', () => {
    if (!el('ambition').value.trim()) el('ambition').value = ideas[button.dataset.workshopIdea][Number(french())];
    el('ambition').focus();
  }));
  root.querySelectorAll('[data-workshop-view]').forEach(button => button.addEventListener('click', () => panel(button.dataset.workshopView)));
  const initial = stored();
  if (initial.draft) {
    el('ambition').value = initial.draft.objective || '';
    if ([...el('family').options].some(o => o.value === initial.draft.family)) el('family').value = initial.draft.family;
    el('context').value = initial.draft.context || '';
    el('cases').value = initial.draft.casesText || '';
    if ([...el('loop').options].some(o => !o.disabled && o.value === initial.draft.loop)) el('loop').value = initial.draft.loop;
  }
  if (typeof initial.chosen === 'string' && /^wf_[a-f0-9]{24}$/u.test(initial.chosen)) chosen = initial.chosen;
  new MutationObserver(language).observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
  new MutationObserver(() => { if (!document.getElementById('view-start').classList.contains('hidden')) config(); })
    .observe(document.getElementById('view-start'), {attributes: true, attributeFilter: ['class']});
  language();
  config();
  if (location.protocol === 'https:' && location.pathname.endsWith('/harness/')) {
    fetch('preview-manifest.json', {credentials: 'omit', cache: 'no-store'})
      .then(response => response.ok ? response.json() : null)
      .then(manifest => {
        if (manifest?.schema === 'alpha-genesis-harness-public-preview/v1' &&
            /^[0-9a-f]{40}$/u.test(manifest.source_revision) && window.HarnessEngine?.VERSION) {
          published = manifest.source_revision;
          renderSetup();
        }
      }).catch(() => {});
  }
})();
