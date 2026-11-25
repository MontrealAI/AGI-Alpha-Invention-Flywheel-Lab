import {screen, validate} from './endpoint-screen.mjs';
import {fingerprint, freezeScreen, outcome, verifyOutcome} from './outcome-receipt.mjs';
import {downloadJSON, setupGoals} from './frontier-goals.mjs';
import {setupMissionConsole} from './frontier-mission-ui.mjs';

const id = key => document.getElementById(key);
const member = id('member');
const fr = document.documentElement.lang === 'fr';
const words = fr ? {
  tracked:'dossiers affichés', empty:'Aucun dossier ne correspond.',
  input:'Lot prêt à figer.', bad:'Le fichier ne respecte pas le format prévu. Vérifiez les dates, les mesures et les identifiants.',
  frozen:'Tâche figée. Le lot, les seuils et le comparateur SQLite sont enregistrés.',
  sync:'Calcul local terminé.', scoped:'Configuration', rows:'mesures',
  floor:'débit minimal (jetons/s/utilisateur)', ceiling:'latence P90 maximale (ms)', cutoff:'date limite',
  highest:'Charge maximale documentée', noPoint:'Aucun point documenté admissible',
  abstain:'Adoption opérationnelle en abstention.', checked:'Empreinte cohérente. Vérifiez séparément l’origine et le comparateur.',
  compared:'Concorde avec le résultat indépendant de SQLite pour cet exemple public.',
  referenceError:'Écart avec la référence SQLite figée. Le reçu pour l’exemple public est indisponible.',
  badReceipt:'Reçu invalide ou modifié.', exported:'Reçu exporté localement.',
  consentCleared:'Consentement retiré. Aucun nouveau reçu ne sera préparé.',
  demonstration:'Démonstration publique terminée.', task:'Analyse locale terminée. L’acceptation indépendante reste à établir.',
  missingCrypto:'Le calcul local reste offert. La préparation de reçus nécessite un navigateur en contexte HTTPS sécurisé.',
  working:'Évaluation locale en cours…', interrupted:'L’évaluation a été interrompue. Relancez-la ou ouvrez un lot autorisé.',
  scopeLabel:'Conditions et mesures du banc d’essai', comparison:'Référence SQLite et données figées',
  measures:'utilisateurs simultanés', scopedResult:'Charge testée admissible', verdict:'Décision opérationnelle',
  original:'Publication officielle MLPerf', next:'Préparez un lot autorisé pour évaluer votre propre configuration.',
} : {
  tracked:'briefs shown', empty:'No briefs match.',
  input:'Batch ready to freeze.', bad:'The file does not match the input format. Check dates, measurements and identifiers.',
  frozen:'Task frozen. The batch, thresholds and SQLite comparator are recorded.',
  sync:'Local calculation completed.', scoped:'Configuration', rows:'measurements',
  floor:'minimum tokens/s/user', ceiling:'maximum P90 TTFT (ms)', cutoff:'cutoff',
  highest:'Highest documented load', noPoint:'No documented qualifying point',
  abstain:'Operational adoption remains ABSTAIN.', checked:'Digest matches. Verify origin and the comparator separately.',
  compared:'Matches the independently computed SQLite result for this public example.',
  referenceError:'The result differs from the frozen SQLite reference. A public example receipt is unavailable.',
  badReceipt:'Invalid or altered receipt.', exported:'Receipt exported locally.',
  consentCleared:'Consent withdrawn. No further receipt will be prepared.',
  demonstration:'Public demonstration completed.', task:'Local screen completed. Independent acceptance is outstanding.',
  missingCrypto:'Local calculation is available. Receipt tools require a browser in a secure HTTPS context.',
  working:'Running the local screen…', interrupted:'The screen was interrupted. Run it again or open an authorized batch.',
  scopeLabel:'Benchmark conditions and measurements', comparison:'SQLite reference and frozen inputs',
  measures:'concurrent users', scopedResult:'Qualifying tested load', verdict:'Operating decision',
  original:'Official MLPerf submission', next:'Prepare an authorized batch to screen your own configuration.',
};

function setupShell() {
  const views = [...member.querySelectorAll('[data-member-view]')];
  const destinations = [...member.querySelectorAll('.mf-destinations a, .mf-intelligence-link')];
  const home = id('my-frontier');
  function show(target = home, {focus = true, remember = false} = {}) {
    if (member.hidden) return;
    const within = member.contains(target);
    const view = within ? target.closest('[data-member-view]') || home : null;
    member.toggleAttribute('data-public-view', !view);
    for (const section of views) section.hidden = section !== view;
    for (const link of destinations) {
      const destination = view?.id === 'mv-earlier' ? 'my-intelligence' : view?.id;
      if (destination && link.hash === `#${destination}`) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    }
    window.dispatchEvent(new CustomEvent('frontier:member-view', {detail:view?.id}));
    if (remember && location.hash !== `#${target.id}`) history.pushState(null, '', `#${target.id}`);
    if (!focus) return;
    const label = view && id(view.getAttribute('aria-labelledby'));
    const node = target === view || target === member ? label : target.querySelector('h2, h3, h4') || target;
    if (!node.hasAttribute('tabindex')) node.tabIndex = -1;
    node.focus({preventScroll: true});
    if (target === view || target === member) window.scrollTo({top: 0, behavior:'instant'});
    else target.scrollIntoView({block:'start', behavior:'instant'});
  }
  function fragmentTarget() {
    return id(location.hash.slice(1));
  }
  document.addEventListener('click', event => {
    if (member.hidden || event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest('a[href^="#"]');
    if (!link || !(member.contains(link) || link.id === 'member-nav')) return;
    const target = id(link.hash.slice(1));
    if (!target) return;
    event.preventDefault();
    // A decision or tool link can open an already focused disclosure.
    const control = target.querySelector('details[open] summary');
    const preserveFocus = control === document.activeElement;
    show(target, {remember: true, focus: !preserveFocus});
    if (preserveFocus) target.scrollIntoView({block:'start', behavior:'instant'});
  });
  window.addEventListener('hashchange', () => show(fragmentTarget() || home));
  window.addEventListener('frontier:member-enter', () => {
    history.replaceState(null, '', '#my-frontier');
    show(home, {focus:false});
  });
  window.addEventListener('frontier:member-lock', () => {
    member.removeAttribute('data-public-view');
    if (fragmentTarget() && member.contains(fragmentTarget())) history.replaceState(null, '', '#access');
    for (const section of views) section.hidden = section !== home;
    for (const link of destinations) link.removeAttribute('aria-current');
  });
  function step(index) {
    member.querySelectorAll('.mf-steps li').forEach((item, position) => {
      item.toggleAttribute('data-complete', position < index);
      if (position === index) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
  }
  return {show, step};
}

function setupExplorer() {
  const query = id('mv-query');
  const order = id('mv-order');
  const grid = id('mv-records');
  const filters = [...document.querySelectorAll('[data-mv-filter]')];
  const normalize = value => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  const cards = [...document.querySelectorAll('[data-mv-record]')].map(card => [card, normalize(card.textContent)]);
  function update() {
    const terms = normalize(query.value).trim().split(/\s+/u).filter(Boolean);
    let count = 0;
    for (const [element, content] of cards) {
      element.hidden = !terms.every(t => content.includes(t))
        || filters.some(filter => filter.value && filter.value !== element.dataset[filter.dataset.mvFilter]);
      if (!element.hidden) count++;
    }
    id('mv-filter-status').textContent = count ? `${count} / ${cards.length} · ${words.tracked}` : words.empty;
  }
  query.addEventListener('input', update);
  for (const select of filters) select.addEventListener('change', update);
  order.addEventListener('change', () => {
    const sorted = order.value === 'newest'
      ? [...cards].sort(([a], [b]) => b.dataset.observed.localeCompare(a.dataset.observed)) : cards;
    grid.append(...sorted.map(([card]) => card));
  });
  window.addEventListener('frontier:member-lock', () => {
    query.value = order.value = '';
    for (const select of filters) select.value = '';
    order.selectedIndex = 0;
    grid.append(...cards.map(([card]) => card));
    update();
  });
  for (const link of member.querySelectorAll('[data-mv-open]')) {
    link.addEventListener('click', event => {
      if (member.hidden || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const card = id(link.hash.slice(1));
      const details = card?.querySelector('details');
      if (!details) return;
      query.value = '';
      for (const select of filters) select.value = '';
      update();
      details.open = true;
      details.querySelector('summary').focus({preventScroll: true});
    });
  }
  id('mv-filters').hidden = false;
  update();
}

function template(key) {
  return JSON.parse(id(key).content.textContent);
}

function text(tag, value) {
  const node = document.createElement(tag);
  node.textContent = value;
  return node;
}

async function readFile(file) {
  if (!file || file.size > 256_000) throw Error('INPUT_FILE');
  return JSON.parse(await file.text());
}

function setupRunner(shell) {
  const status = id('mv-run-status');
  const toolStatus = id('mv-tool-status');
  const resultArea = id('mv-screen-result');
  const resultPanel = id('mf-outcome');
  const resultLink = id('mf-current-result');
  const noResult = id('mf-result-empty');
  const feedback = id('mv-export-status');
  const receiptFeedback = id('mv-receipt-status');
  const scope = id('mv-plan');
  const consent = id('mv-consent');
  const rights = id('mv-rights');
  const rightsRow = id('mv-rights-row');
  const freeze = id('mv-freeze');
  const run = id('mv-run');
  const save = id('mv-export');
  const keep = id('mv-keep-result');
  const keepControls = id('mf-keep-controls');
  const demo = id('mv-demo');
  const input = id('mv-input');
  const receiptInput = id('mv-import');
  const tool = template('mv-endpoint-manifest');
  const reference = template('mv-endpoint-reference');
  const hasCrypto = Boolean(window.crypto?.subtle);
  const sample = validate(template('mv-endpoint-sample'));
  let current, frozen, result, duration, exportStamp, running = false, preparing = false;
  let generation = 0;
  const active = () => !member.hidden;
  function tell(message) {
    status.textContent = toolStatus.textContent = message;
  }
  function enable() {
    const busy = running || preparing;
    freeze.disabled = !current || busy || !(rightsRow.hidden || rights.checked) || Boolean(frozen);
    run.disabled = !frozen || busy || Boolean(result) || !(rightsRow.hidden || rights.checked);
    demo.disabled = busy;
    const goalAction = id('goal-action');
    if (busy) goalAction.setAttribute('aria-busy', 'true');
    else goalAction.removeAttribute('aria-busy');
    save.disabled = !hasCrypto || !consent.checked || !result || !(rightsRow.hidden || rights.checked);
  }
  function clearResult() {
    exportStamp = undefined;
    frozen = result = duration = undefined;
    preparing = running = false;
    consent.checked = false;
    resultPanel.hidden = resultArea.hidden = keep.hidden = keepControls.hidden = resultLink.hidden = true;
    noResult.hidden = false;
    resultArea.replaceChildren();
    feedback.textContent = '';
  }
  function clear() {
    generation++;
    clearResult();
    current = undefined;
    input.value = receiptInput.value = '';
    rights.checked = false;
    rightsRow.hidden = true;
    receiptFeedback.textContent = scope.textContent = '';
    tell('');
    enable();
  }
  function load(document, isPublic) {
    current = validate(document);
    rightsRow.hidden = isPublic;
    scope.textContent = `${words.scoped} · ${current.scope.model} · ${current.scope.workload} · ${current.scope.system}
${current.rows.length} ${words.rows} · ${words.floor} ${current.minimum_tokens_per_s} · ${words.ceiling} ${current.maximum_p90_ttft_ms} · ${words.cutoff} ${current.cutoff}`;
    tell(words.input);
    enable();
  }

  function loadPublic() {
    if (!active()) return false;
    clear();
    load(sample, true);
    return true;
  }
  id('mv-sample').addEventListener('click',loadPublic);
  input.addEventListener('change', async () => {
    if (!active()) return;
    const file = input.files[0];
    clear();
    const token = generation;
    try {
      const incoming = await readFile(file);
      if (token === generation && active()) load(incoming, false);
    } catch {
      if (token === generation && active()) tell(words.bad);
    }
  });
  rights.addEventListener('change', () => {
    if (!rights.checked) {
      generation++;
      clearResult();
      tell(words.input);
      feedback.textContent = words.consentCleared;
    }
    enable();
  });
  async function freezeTask() {
    if (!active() || !current || preparing || running || !(rightsRow.hidden || rights.checked)) return false;
    const token = ++generation;
    const approvedInput = current;
    preparing = true;
    enable();
    try {
      const plan = hasCrypto ? await freezeScreen(approvedInput, tool, reference) : null;
      if (token !== generation || !active() || !(rightsRow.hidden || rights.checked)) return false;
      frozen = {input: approvedInput, plan};
      tell(words.frozen);
      return true;
    } catch {
      if (token === generation && active()) tell(words.interrupted);
      return false;
    } finally {
      if (token === generation && active()) { preparing = false; enable(); }
    }
  }
  freeze.addEventListener('click', freezeTask);

  async function runTask() {
    if (!active() || !frozen || running || result) return false;
    const token = generation;
    running = true;
    enable();
    tell(words.working);
    const isExample = frozen.plan?.classification === 'controlled-public-replay';
    let output, elapsed;
    try {
      const start = performance.now();
      output = screen(frozen.input);
      elapsed = Math.round((performance.now() - start) * 1000) / 1000;
      if (isExample && await fingerprint(output) !== reference.result_sha256) throw Error('REFERENCE_MISMATCH');
    } catch (error) {
      if (token === generation && active()) {
        running = false;
        tell(error.message === 'REFERENCE_MISMATCH' ? words.referenceError : words.interrupted);
        if (!status.closest('[data-member-view]').hidden) shell.show(status);
        enable();
      }
      return false;
    }
    if (token !== generation || !active()) return false;
    running = false;
    result = output;
    duration = elapsed;
    const totals = new Map();
    for (const row of result.rows) totals.set(row.disposition, (totals.get(row.disposition) ?? 0) + 1);
    const labels = fr ? {
      qualified:'Admissible', 'above-ceiling':'Au-dessus du plafond', 'below-threshold':'Sous le seuil',
      'missing-measurement':'Mesure absente', 'missing-publication-date':'Date absente', 'not-yet-documented':'Non documenté à la date limite'
    } : {
      qualified:'Qualifying', 'above-ceiling':'Above ceiling', 'below-threshold':'Below floor',
      'missing-measurement':'Missing measurement', 'missing-publication-date':'Missing date', 'not-yet-documented':'After cutoff'
    };
    const list = document.createElement('ul');
    for (const [reason, count] of totals) list.append(text('li', `${labels[reason]} · ${count}`));
    const metric = document.createElement('div');
    metric.className = 'mf-result-metric';
    metric.append(text('span', words.scopedResult));
    if (result.highest_tested_load !== null) {
      metric.append(text('strong', result.highest_tested_load), text('span', words.measures));
    } else metric.append(text('p', words.noPoint));
    const finding = document.createElement('div');
    finding.className = 'mf-result-finding';
    const decision = text('p', `${words.verdict} · ABSTAIN`);
    decision.className = 'mf-result-verdict';
    finding.append(text('h4', isExample ? words.demonstration : words.task), decision,
      text('p', isExample ? words.compared : words.abstain), text('p', words.next));
    const inspect = document.createElement('details');
    const scopeText = text('p', scope.textContent);
    scopeText.className = 'mv-plan';
    inspect.append(text('summary', words.scopeLabel), scopeText);
    const measured = frozen.input.rows.find(row => row.id === result.evidence_id);
    if (measured) inspect.append(text('p', fr
      ? `Mesure admissible · ${measured.tokens_per_s} jetons/s/utilisateur · latence P90 ${measured.p90_ttft_ms} ms`
      : `Qualifying measurement · ${measured.tokens_per_s} tokens/s/user · P90 TTFT ${measured.p90_ttft_ms} ms`));
    inspect.append(list);
    if (isExample) {
      const source = text('a', words.comparison);
      source.href = tool.source;
      const original = text('a', words.original);
      original.href = sample.source;
      const links = document.createElement('p');
      links.className = 'mv-links';
      links.append(source, original);
      inspect.append(links);
    }
    resultArea.replaceChildren(metric, finding, inspect);
    resultArea.hidden = resultPanel.hidden = resultLink.hidden = false;
    noResult.hidden = true;
    keep.hidden = !hasCrypto;
    shell.step(4);
    if (!member.hasAttribute('data-public-view')) shell.show(resultPanel, {remember:true});
    tell(words.sync);
    enable();
    return true;
  }
  run.addEventListener('click', runTask);
  async function launchDemo() {
    if (preparing || running || !active()) return false;
    shell.show(id('my-frontier'), {focus:false, remember:true});
    shell.step(3);
    if (loadPublic() && await freezeTask()) return runTask();
    return false;
  }
  demo.addEventListener('click', launchDemo);
  keep.addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    keepControls.hidden = false;
    consent.focus();
  });

  consent.addEventListener('change', () => {
    exportStamp = undefined;
    feedback.textContent = consent.checked ? '' : words.consentCleared;
    enable();
  });
  save.addEventListener('click', async () => {
    if (!active() || !frozen?.plan || !result || !consent.checked) return;
    const stamp = Symbol('explicit consent');
    exportStamp = stamp;
    save.disabled = true;
    let sealed;
    try {
      sealed = await outcome(frozen.plan, result, duration, reference, consent.checked);
    } catch {
      if (exportStamp === stamp && active()) {
        feedback.textContent = words.badReceipt;
        enable();
      }
      return;
    }
    if (exportStamp !== stamp || !active() || !consent.checked) return;
    downloadJSON(sealed, 'frontier-outcome-receipt.json');
    feedback.textContent = words.exported;
    enable();
  });
  receiptInput.addEventListener('change', async () => {
    if (!active()) return;
    const token = generation;
    const file = receiptInput.files[0];
    receiptFeedback.textContent = '';
    let message = words.badReceipt;
    try {
      const saved = await readFile(file);
      if (await verifyOutcome(saved)) {
        const {receipt} = saved;
        if (receipt.plan.classification === 'controlled-public-replay') {
          const plan = await freezeScreen(sample, tool, reference);
          const sameScope = ['artifact_sha256', 'input_sha256', 'scope_sha256', 'limits_sha256']
            .every(key => plan[key] === receipt.plan[key]);
          if (sameScope && receipt.result_sha256 === reference.result_sha256
              && receipt.recorded_highest_load === reference.highest_tested_load) message = words.compared;
        } else message = words.checked;
      }
    } catch { /* untrusted input */ }
    if (file === receiptInput.files[0] && token === generation && active()) receiptFeedback.textContent = message;
  });
  if (!hasCrypto) { receiptInput.disabled = consent.disabled = true; tell(words.missingCrypto); }
  id('mv-clear').addEventListener('click', clear);
  window.addEventListener('frontier:member-lock', clear);
  enable();
  return {launchDemo, clear};
}

if (id('member-value')) {
  const shell = setupShell();
  setupExplorer();
  const mission = setupMissionConsole(member, shell);
  setupGoals(member, setupRunner(shell), shell, mission);
}
