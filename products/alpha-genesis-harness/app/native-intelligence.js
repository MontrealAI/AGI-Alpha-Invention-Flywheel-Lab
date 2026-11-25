/* SPDX-License-Identifier: Apache-2.0 */
(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const currentUrl = new URL(window.location.href);
  if (currentUrl.protocol !== 'http:' || currentUrl.hostname !== '127.0.0.1') return;

  const setupLink = $('native-api-link');
  setupLink.hidden = false;
  const setupAnchor = setupLink.querySelector('a');
  function updateWorkspaceLink() {
    const french = document.documentElement.lang === 'fr';
    setupAnchor.href = '/?setup=intelligence&route=api&lang=' + (french ? 'fr' : 'en');
    setupAnchor.textContent = french ? 'Gérer les fournisseurs de FRONTIER Ω' : 'Manage FRONTIER Ω provider connections';
  }
  new MutationObserver(updateWorkspaceLink).observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
  updateWorkspaceLink();
  if (currentUrl.searchParams.get('setup') !== 'intelligence' || currentUrl.searchParams.get('route') !== 'api') return;

  const strings = {
    fr: {
      title: 'Connectez votre fournisseur d’IA', intro: 'Choisissez un compte, testez un modèle et définissez les limites de cette connexion privée.',
      mission: 'Examinez votre mission', original: 'Ambition d’origine', instruction: 'Instruction de suivi', chooseProfile: 'Connexion vérifiée',
      review: 'Examiner les données et les limites', scopeData: 'Le fournisseur reçoit l’ambition actuelle et celle d’origine, l’instruction affichée ci-dessus et le contexte créé durant cette exécution. Les documents locaux et les résultats des exécutions précédentes restent sur cet appareil.',
      missionConsent: 'J’autorise ce fournisseur pour cette révision de la mission et selon les limites ci-dessus.', approve: 'Autoriser cette mission',
      approved: 'Mission autorisée', approvedDetail: 'Revenez à Mon univers FRONTIER pour poursuivre la même mission avec cette connexion.',
      return: 'Retour à Mon univers FRONTIER', profiles: 'Vos connexions sur cet ordinateur', newProfile: 'Connecter un fournisseur',
      billing: 'Votre fournisseur facture l’utilisation de son API séparément. Pour éviter des frais d’API, revenez à Mon univers FRONTIER et choisissez l’intelligence locale ou le mode assisté.',
      provider: 'Fournisseur', key: 'Clé d’API du projet', organization: 'Identifiant de l’organisation (facultatif)',
      discoveryConsent: 'Je suis autorisé à utiliser cette clé et à demander la liste des modèles accessibles avec ce compte.', discover: 'Découvrir les modèles',
      selectModel: 'Modèle', budget: 'Limite de dépenses pour cette connexion (estimation en USD)',
      inputRate: 'Tarif maximal d’entrée (USD par million de jetons)', outputRate: 'Tarif maximal de sortie (USD par million de jetons)',
      costScope: 'Indiquez les tarifs maximaux actuellement applicables, y compris les jetons de raisonnement et tout autre jeton facturé. Le relais réserve une estimation prudente avant chaque requête. Les règles de facturation du fournisseur s’appliquent.',
      advanced: 'Limites de la connexion', outputLimit: 'Jetons de sortie par requête', requestLimit: 'Requêtes par mission autorisée', expiry: 'Expiration de la connexion en heures',
      inferenceConsent: 'J’autorise un test de connexion potentiellement facturable pour ce modèle. Le relais peut enregistrer cette clé si le test réussit.',
      verify: 'Tester et enregistrer la connexion', startOver: 'Changer de fournisseur ou de clé', workspace: 'Ouvrir l’espace de travail HARNESS',
      projectId: 'Identifiant du projet', projectLabel: 'Nom du projet ou de l’espace de travail',
      openaiProject: 'Saisissez l’identifiant du projet OpenAI qui sera facturé (proj_…). Utilisez une clé standard autorisée pour ce projet.',
      otherProject: 'Indiquez le nom du projet ou de l’espace de travail auquel la clé donne accès. Le relais conserve le nom que vous confirmez.',
      fileProtection: 'La clé est conservée dans un fichier local accessible uniquement à votre compte système. Les autorisations du système de fichiers assurent sa protection.',
      windowsProtection: 'Windows protège la clé enregistrée pour votre compte système (DPAPI).',
      metadata: 'Le fournisseur a répertorié ces modèles. Le test confirme l’accès au modèle sélectionné.',
      partialCatalog: 'La liste affiche la première page du catalogue fourni par le compte.',
      estimate: 'Réservation locale estimée pour ce test', disconnect: 'Retirer la connexion',
      confirmDisconnect: 'Retirer cette clé de cet ordinateur et révoquer son autorisation pour les missions à venir? La clé demeure sous votre contrôle chez le fournisseur.',
      disconnected: 'Connexion retirée. Les prochaines requêtes avec cette autorisation sont bloquées.',
      ready: 'Inférence observée', expired: 'Connexion expirée', limit_reached: 'Limite locale atteinte',
      noProfile: 'Connectez et vérifiez un fournisseur ci-dessous pour autoriser cette mission.', chooseOne: 'Choisir une connexion',
      authenticating: 'Vérification de l’accès et découverte des modèles…', verifying: 'Le test autorisé est en cours…',
      reviewing: 'Lecture de la révision exacte de la mission…', authorizing: 'Autorisation de cette révision…',
      discovered: 'Modèles découverts. Sélectionnez un modèle et autorisez son test de connexion.',
      verified: 'Le modèle a réussi le test. La connexion est enregistrée sur cet ordinateur.',
      revision: 'Révision', expires: 'Autorisation valide jusqu’au', actions: 'Actions locales permises',
      budgetLabel: 'Budget estimé restant du profil', uncertain: 'Si une requête a été envoyée, votre fournisseur peut la facturer.',
      testHistory: 'Tests de connexion interrompus ou échoués', testHistoryScope: 'Le relais conserve les estimations d’utilisation déclarées ou les montants réservés pour les tests inachevés. Vérifiez les frais réels auprès de votre fournisseur.',
      verifyingState: 'Test en cours', failedTest: 'Test échoué', interruptedTest: 'Test interrompu', testAccounted: 'Estimation comptabilisée ou réservée',
      credentialError: 'Le fournisseur a refusé cette clé. Vérifiez qu’elle est active et autorisée pour le projet choisi.',
      permissionError: 'Vérifiez vos autorisations sur le projet et votre accès au modèle chez le fournisseur.',
      projectError: 'Saisissez le projet ou l’espace de travail exact associé à la clé.',
      modelError: 'Le modèle sélectionné ne prend pas en charge cette requête. Essayez un modèle de génération de texte accessible avec ce projet.',
      quotaError: 'Le fournisseur indique une limite d’utilisation, de fréquence ou de dépenses. Consultez les paramètres de ce compte.',
      budgetError: 'La limite de dépenses du relais empêche cette requête. Vérifiez les tarifs et le budget autorisé.',
      connectionError: 'Impossible de joindre le fournisseur. Une requête déjà envoyée peut être facturée.',
      challengeError: 'Le modèle n’a pas réussi le test de connexion. La requête envoyée peut être facturée. Essayez un autre modèle ou vérifiez l’accès du compte.',
      noModels: 'Ce projet ne répertorie aucun modèle utilisable. Vérifiez les droits du projet chez le fournisseur.',
      limitError: 'Vérifiez les tarifs et les limites saisis avant de lancer le test.',
      lockedError: 'Le stockage privé du relais est indisponible. Réessayez après avoir vérifié les autorisations locales.',
      refreshMission: 'Revenez à Mon univers FRONTIER et ouvrez la configuration depuis la mission actuelle.',
      companionError: 'Le relais local ne répond pas. Relancez-le et rouvrez la configuration depuis votre mission.'
    },
    en: {
      projectId: 'Project ID', projectLabel: 'Project or workspace name',
      openaiProject: 'Enter the OpenAI project ID that should receive usage (proj_…). Use a standard key authorized for that project.',
      otherProject: 'Enter the project or workspace this credential belongs to. The companion records the name you confirm.',
      fileProtection: 'The companion saves the key in a local file protected by your operating-system user permissions.',
      windowsProtection: 'Windows protects the saved key for your operating-system account (DPAPI).',
      metadata: 'The provider listed these models. The connection test confirms access to the one you select.',
      partialCatalog: 'This is the first page of the account’s model catalog.', estimate: 'Estimated local reservation for this test', disconnect: 'Remove connection',
      confirmDisconnect: 'Remove the key from this computer and revoke its authority for future missions? You can still manage the key at the provider.',
      disconnected: 'Connection removed. Future requests using this approval are blocked.',
      ready: 'Inference observed', expired: 'Connection expired', limit_reached: 'Local limit reached',
      noProfile: 'Connect and verify a provider below to authorize this mission.', chooseOne: 'Choose a connection',
      authenticating: 'Checking access and discovering models…', verifying: 'Running the authorized connection test…',
      reviewing: 'Checking the exact mission revision…', authorizing: 'Authorizing this revision…',
      discovered: 'Models found. Select a model and authorize its connection test.',
      verified: 'The model passed the test. This computer saved the connection.',
      revision: 'Revision', expires: 'Authorization expires', actions: 'Allowed local actions', budgetLabel: 'Remaining profile budget estimate',
      uncertain: 'Your provider may bill a request that was already sent.',
      verifyingState: 'Test in progress', failedTest: 'Failed test', interruptedTest: 'Interrupted test', testAccounted: 'Estimated usage or reservation',
      credentialError: 'The provider refused this credential. Check that it is active and authorized for the selected project.',
      permissionError: 'Check the provider account’s eligibility, project permissions and model access.',
      projectError: 'Enter the exact project or workspace associated with this credential.',
      modelError: 'The selected model did not accept this request. Try a text-generation model available to this project.',
      quotaError: 'The provider reported a quota, rate or spending limit. Check the account’s usage settings.',
      budgetError: 'The companion’s spending limit blocks this request. Check the current rates and authorized budget.',
      connectionError: 'Could not reach the provider. Your provider may bill a request that was already sent.',
      challengeError: 'The model did not pass the connection test. Your provider may bill the sent request. Try another model or check the account’s access.',
      noModels: 'This project listed no usable models. Check the project’s permissions with the provider.',
      limitError: 'Check your rates and limits before running the test.',
      lockedError: 'The companion’s private storage is unavailable. Check the local permissions and try again.',
      refreshMission: 'Return to My Frontier and reopen setup from the current mission.',
      companionError: 'The local companion did not respond. Restart it and reopen setup from your mission.'
    }
  };
  const errors = {
    INTELLIGENCE_CREDENTIAL: 'credentialError', INTELLIGENCE_PERMISSION: 'permissionError', INTELLIGENCE_PROJECT: 'projectError',
    INTELLIGENCE_MODEL: 'modelError', INTELLIGENCE_QUOTA: 'quotaError', INTELLIGENCE_BUDGET: 'budgetError',
    INTELLIGENCE_CONNECTION: 'connectionError', INTELLIGENCE_VERIFICATION: 'challengeError', INTELLIGENCE_NO_MODELS: 'noModels',
    INTELLIGENCE_LIMITS: 'limitError', INTELLIGENCE_TEST_BUDGET: 'budgetError', INTELLIGENCE_STORAGE: 'lockedError', CHATGPT_STORAGE: 'lockedError',
    INTELLIGENCE_EXPIRED: 'expired', INTELLIGENCE_REVOKED: 'disconnected'
  };
  const original = new Map([...document.querySelectorAll('[data-native-text]')].map(node => [node.dataset.nativeText, node.textContent]));
  const ticketStorage = 'frontier-native-review-ticket-v1';
  const ticketPattern = /^[A-Za-z0-9_-]{43}$/;
  let language = currentUrl.searchParams.get('lang') === 'fr' ? 'fr' : 'en';
  let ticket = new URLSearchParams(currentUrl.hash.slice(1)).get('ticket');
  if (ticketPattern.test(ticket || '')) {
    try { sessionStorage.setItem(ticketStorage, ticket); } catch (_) { /* page memory remains available */ }
  } else {
    try { ticket = sessionStorage.getItem(ticketStorage); } catch (_) { ticket = null; }
  }
  if (!ticketPattern.test(ticket || '')) ticket = null;
  history.replaceState(null, '', currentUrl.pathname + currentUrl.search);
  let nativeToken, status, discovery, mission, review, notice, busy = false;

  function t(key) { return strings[language][key] || original.get(key) || ''; }
  function showNotice(key, isError = false) {
    notice = {key, isError};
    $('native-state').textContent = t(key);
    $('native-state').classList.toggle('native-error', isError);
  }
  function localizedNumber(value, currency = false) {
    return Intl.NumberFormat(language, currency
      ? {style: 'currency', currency: 'USD', maximumFractionDigits: 6}
      : {}).format(value);
  }
  function localDate(value) {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toLocaleString(language) : '';
  }
  function option(value, label) {
    const node = document.createElement('option');
    node.value = value;
    node.textContent = label;
    return node;
  }
  function showProvider() {
    const openai = $('native-provider').value === 'openai';
    $('native-project-label').textContent = t(openai ? 'projectId' : 'projectLabel');
    $('native-project-note').textContent = t(openai ? 'openaiProject' : 'otherProject');
    $('native-organization-panel').hidden = !openai;
  }
  function estimate() {
    const input = $('native-input-rate').value, output = $('native-output-rate').value;
    const dollars = (4224 * Number(input) + Math.min(Number($('native-output-limit').value), 512) * Number(output)) / 1000000;
    $('native-test-estimate').textContent = input && output && Number.isFinite(dollars) ? `${t('estimate')} · ${localizedNumber(dollars, true)}` : '';
  }
  function returnToPages(event) {
    // A browser may disallow closing a directly opened tab. The regular link then remains usable.
    window.close();
    if (window.closed) event.preventDefault();
  }
  function setLanguage(next) {
    language = next;
    document.documentElement.lang = next;
    $('native-language').textContent = next === 'fr' ? 'English' : 'Français';
    $('native-language').lang = next === 'fr' ? 'en' : 'fr';
    document.querySelectorAll('[data-native-text]').forEach(node => { node.textContent = t(node.dataset.nativeText); });
    const landing = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/';
    const destination = landing + (next === 'fr' ? 'fr.html' : '') + '#my-frontier';
    $('native-return').href = destination;
    $('native-authorized-return').href = destination;
    const params = new URL(window.location.href);
    params.searchParams.set('lang', next);
    history.replaceState(null, '', params.pathname + params.search);
    document.title = 'FRONTIER Ω — ' + t('title');
    if (status) renderStatus();
    if (mission) renderMission();
    if (review) renderScope();
    if (notice) showNotice(notice.key, notice.isError);
    showProvider();
    estimate();
  }

  async function request(action, body = {}) {
    if (!nativeToken) {
      const session = await fetch('/api/session', {credentials: 'same-origin', headers: {'X-Harness-Client': 'browser'}, cache: 'no-store'});
      if (!session.ok) throw new Error('native-session');
      nativeToken = (await session.json()).token;
    }
    const response = await fetch('/api/frontier-intelligence/' + action, {
      method: 'POST', cache: 'no-store', credentials: 'same-origin',
      headers: {'X-Harness-Token': nativeToken, 'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    const value = await response.json();
    if (!response.ok) {
      if (value.error?.code === 'TOKEN') nativeToken = null;
      const error = new Error('native-operation');
      error.code = value.error?.code;
      throw error;
    }
    return value;
  }

  async function operation(action, progress, failure = 'companionError') {
    if (busy) return;
    busy = true;
    $('native-intelligence').setAttribute('aria-busy', 'true');
    const controls = [...$('native-intelligence').querySelectorAll('form button, form input, form select, .native-profiles button')];
    controls.forEach(node => { node.disabled = true; });
    if (progress) showNotice(progress);
    try { await action(); }
    catch (error) { showNotice(errors[error.code] || failure, true); }
    finally {
      controls.forEach(node => { node.disabled = false; });
      $('native-intelligence').removeAttribute('aria-busy');
      busy = false;
    }
  }

  function renderStatus() {
    const profiles = status.profiles || [];
    $('native-protection').textContent = t(status.credential_protection === 'windows-dpapi' ? 'windowsProtection' : 'fileProtection');
    $('native-existing').hidden = profiles.length === 0;
    const items = profiles.map(profile => {
      const item = document.createElement('li');
      const name = document.createElement('strong');
      name.textContent = `${profile.label} · ${profile.model}`;
      const detail = document.createElement('p');
      detail.className = 'subtle';
      detail.textContent = `${profile.project} · ${t(profile.state)} · ${localDate(profile.expires_at)}`;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'button text-button';
      button.textContent = t('disconnect');
      button.setAttribute('aria-label', `${t('disconnect')} · ${profile.label} · ${profile.model} · ${profile.project}`);
      button.addEventListener('click', () => {
        if (!window.confirm(t('confirmDisconnect'))) return;
        operation(async () => {
          await request('disconnect', {profile_id: profile.id, consent: true});
          invalidateReview();
          await loadProfiles();
          showNotice('disconnected');
        });
      });
      item.append(name, detail, button);
      return item;
    });
    $('native-profiles').replaceChildren(...items);
    const tests = status.recent_tests || [];
    $('native-history').hidden = tests.length === 0;
    const testNames = {failed: 'failedTest', interrupted: 'interruptedTest', verifying: 'verifyingState'};
    $('native-test-history').replaceChildren(...tests.map(test => {
      const item = document.createElement('li');
      const description = document.createElement('strong');
      const detail = document.createElement('p');
      description.textContent = `${test.label} · ${test.model} · ${t(testNames[test.state])}`;
      detail.className = 'subtle';
      detail.textContent = `${localDate(test.at)} · ${t('testAccounted')} · ${localizedNumber(test.usage.committed + test.usage.reserved, true)}`;
      item.append(description, detail);
      return item;
    }));
    const provider = $('native-provider').value;
    $('native-provider').replaceChildren(...status.providers.map(row => option(row.id, row.label)));
    if (status.providers.some(row => row.id === provider)) $('native-provider').value = provider;
    showProvider();
    if (mission) renderMission();
  }

  function renderMission() {
    $('native-mission').hidden = false;
    $('native-ambition').textContent = mission.ambition;
    $('native-original-panel').hidden = mission.ambition === mission.original_ambition || !mission.original_ambition;
    $('native-original').textContent = mission.original_ambition || '';
    $('native-instruction-panel').hidden = !mission.instruction;
    $('native-instruction').textContent = mission.instruction || '';
    $('native-review-revision').textContent = `${t('revision')} ${mission.revision}`;
    const profiles = status?.profiles?.filter(profile => profile.ready) || [];
    const select = $('native-review-profile');
    const selected = select.value;
    const choices = profiles.map(profile => option(profile.id, `${profile.label} · ${profile.model} · ${profile.project}`));
    if (profiles.length > 1) choices.unshift(option('', t('chooseOne')));
    select.replaceChildren(...choices);
    if (profiles.some(profile => profile.id === selected)) select.value = selected;
    $('native-approve-form').hidden = profiles.length === 0;
  }

  function invalidateReview() {
    review = null;
    $('native-scope').hidden = true;
    $('native-mission-consent').checked = false;
  }

  function renderScope() {
    const listing = $('native-scope-limits');
    const fields = [[t('provider'), `${review.profile.label} · ${review.profile.model}`], [t('projectLabel'), review.profile.project],
      [t('requestLimit'), review.scope.max_turns], [t('outputLimit'), review.scope.max_output_tokens],
      [t('actions'), review.scope.max_actions], [t('expires'), localDate(review.scope.expires_at)]];
    const remaining = review.profile.usage?.estimate?.remaining;
    if (Number.isFinite(remaining)) fields.push([t('budgetLabel'), localizedNumber(remaining, true)]);
    listing.replaceChildren();
    for (const [key, value] of fields) {
      const title = document.createElement('dt');
      const detail = document.createElement('dd');
      title.textContent = key;
      detail.textContent = value ?? '—';
      listing.append(title, detail);
    }
    $('native-scope').hidden = false;
  }

  async function loadProfiles() {
    status = await request('status');
    renderStatus();
  }

  function resetDiscovery() {
    discovery = null;
    $('native-discover-form').hidden = false;
    $('native-verify-form').hidden = true;
    $('native-key').value = '';
    $('native-discovery-consent').checked = false;
    $('native-inference-consent').checked = false;
  }

  document.body.classList.add('native-setup');
  $('native-intelligence').hidden = false;
  $('native-return').addEventListener('click', returnToPages);
  $('native-authorized-return').addEventListener('click', returnToPages);
  $('native-language').addEventListener('click', () => setLanguage(language === 'en' ? 'fr' : 'en'));
  $('native-provider').addEventListener('change', showProvider);
  $('native-review-profile').addEventListener('change', invalidateReview);
  for (const id of ['native-input-rate', 'native-output-rate', 'native-output-limit']) $(id).addEventListener('input', estimate);
  $('native-start-over').addEventListener('click', resetDiscovery);
  $('native-discover-form').addEventListener('submit', event => {
    event.preventDefault();
    const provider = $('native-provider').value;
    const data = {provider, credential: $('native-key').value, project: $('native-project').value.trim(),
      organization: provider === 'openai' ? $('native-organization').value.trim() : '', consent: $('native-discovery-consent').checked};
    $('native-key').value = '';
    operation(async () => {
      discovery = await request('discover', data);
      $('native-model').replaceChildren(...discovery.models.map(model => option(model, model)));
      $('native-metadata').textContent = t('metadata') + (discovery.has_more ? ' ' + t('partialCatalog') : '');
      $('native-discover-form').hidden = true;
      $('native-verify-form').hidden = false;
      showNotice('discovered');
    }, 'authenticating');
  });
  $('native-verify-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!discovery) return;
    operation(async () => {
      const data = {setup_id: discovery.setup_id, model: $('native-model').value, input_rate: $('native-input-rate').value,
        output_rate: $('native-output-rate').value, budget_usd: $('native-budget').value,
        max_output_tokens: Number($('native-output-limit').value), max_turns: Number($('native-request-limit').value),
        expiry_hours: Number($('native-expiry').value), consent: $('native-inference-consent').checked};
      try {
        const result = await request('verify', data);
        resetDiscovery();
        await loadProfiles();
        if (mission && result.profile.ready) $('native-review-profile').value = result.profile.id;
        showNotice(result.state === 'ready' ? 'verified' : result.state);
      } catch (error) {
        if (!['INTELLIGENCE_LIMITS', 'INTELLIGENCE_TEST_BUDGET'].includes(error.code)) {
          resetDiscovery();
          try { await loadProfiles(); } catch (_) { /* report the original connection error */ }
        }
        throw error;
      }
    }, 'verifying');
  });
  $('native-review-details').addEventListener('click', () => {
    const profile = $('native-review-profile').value;
    if (!profile) { $('native-review-profile').focus(); return; }
    invalidateReview();
    operation(async () => {
      review = await request('mission-review', {ticket, profile});
      renderScope();
      showNotice('');
    }, 'reviewing', 'refreshMission');
  });
  $('native-approve-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!review || !ticket) return;
    operation(async () => {
      await request('mission-authorize', {ticket, revision: review.revision,
        profile: $('native-review-profile').value, consent: $('native-mission-consent').checked});
      try { sessionStorage.removeItem(ticketStorage); } catch (_) { /* the permit is single use */ }
      ticket = null;
      $('native-mission').hidden = true;
      $('native-approved').hidden = false;
      $('native-create').hidden = true;
      showNotice('');
    }, 'authorizing', 'refreshMission');
  });

  setLanguage(language);
  $('native-intelligence').focus({preventScroll: true});
  operation(async () => {
    await loadProfiles();
    if (ticket) {
      try {
        mission = await request('mission-review', {ticket});
        renderMission();
        if (!status.profiles.some(profile => profile.ready)) showNotice('noProfile');
      } catch (error) {
        try { sessionStorage.removeItem(ticketStorage); } catch (_) { /* setup can continue without a mission */ }
        ticket = null;
        showNotice('refreshMission', true);
      }
    }
  });
})();
