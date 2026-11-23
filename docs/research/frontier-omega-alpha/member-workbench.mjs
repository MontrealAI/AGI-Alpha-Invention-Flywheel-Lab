import {screen, validate} from './endpoint-screen.mjs';
import {fingerprint, freezeScreen, outcome, verifyOutcome} from './outcome-receipt.mjs';
import {downloadJSON, setupGoals} from './frontier-goals.mjs';

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
};

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

function setupRunner() {
  const status = id('mv-run-status');
  const resultArea = id('mv-screen-result');
  const feedback = id('mv-receipt-status');
  const scope = id('mv-plan');
  const consent = id('mv-consent');
  const rights = id('mv-rights');
  const rightsRow = id('mv-rights-row');
  const freeze = id('mv-freeze');
  const run = id('mv-run');
  const save = id('mv-export');
  const keep = id('mv-keep-result');
  const input = id('mv-input');
  const receiptInput = id('mv-import');
  const tool = template('mv-endpoint-manifest');
  const reference = template('mv-endpoint-reference');
  const hasCrypto = Boolean(window.crypto?.subtle);
  const sample = validate(template('mv-endpoint-sample'));
  let current, frozen, result, duration, exportStamp, running = false;
  let generation = 0;
  const active = () => !member.hidden;
  function enable() {
    freeze.disabled = !current || !(rightsRow.hidden || rights.checked) || Boolean(frozen);
    run.disabled = !frozen || running || Boolean(result) || !(rightsRow.hidden || rights.checked);
    save.disabled = !hasCrypto || !consent.checked || !result || !(rightsRow.hidden || rights.checked);
  }
  function clear() {
    generation++;
    exportStamp = undefined;
    current = frozen = result = duration = undefined;
    running = false;
    input.value = receiptInput.value = '';
    consent.checked = rights.checked = false;
    rightsRow.hidden = resultArea.hidden = keep.hidden = true;
    resultArea.replaceChildren();
    status.textContent = feedback.textContent = scope.textContent = '';
    enable();
  }
  function load(document, isPublic) {
    current = validate(document);
    rightsRow.hidden = isPublic;
    scope.textContent = `${words.scoped} · ${current.scope.model} · ${current.scope.workload} · ${current.scope.system}
${current.rows.length} ${words.rows} · ${words.floor} ${current.minimum_tokens_per_s} · ${words.ceiling} ${current.maximum_p90_ttft_ms} · ${words.cutoff} ${current.cutoff}`;
    status.textContent = words.input;
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
      if (token === generation && active()) status.textContent = words.bad;
    }
  });
  rights.addEventListener('change', () => {
    if (!rights.checked) {
      generation++;
      exportStamp = undefined;
      frozen = result = duration = undefined;
      running = false;
      resultArea.hidden = keep.hidden = true;
      resultArea.replaceChildren();
      consent.checked = false;
      status.textContent = words.input;
      feedback.textContent = words.consentCleared;
    }
    enable();
  });
  async function freezeTask() {
    if (!active() || !current || !(rightsRow.hidden || rights.checked)) return false;
    const token = ++generation;
    const approvedInput = current;
    freeze.disabled = true;
    try {
      const plan = hasCrypto ? await freezeScreen(approvedInput, tool, reference) : null;
      if (token !== generation || !active() || !(rightsRow.hidden || rights.checked)) return false;
      frozen = {input: approvedInput, plan};
      status.textContent = words.frozen;
      enable();
      return true;
    } catch {
      if (token === generation && active()) { status.textContent = words.missingCrypto; enable(); }
      return false;
    }
  }
  freeze.addEventListener('click', freezeTask);

  async function runTask() {
    if (!active() || !frozen || running || result) return;
    const token = generation;
    running = true;
    enable();
    const start = performance.now();
    const output = screen(frozen.input);
    const elapsed = Math.round((performance.now() - start) * 1000) / 1000;
    const isExample = frozen.plan?.classification === 'controlled-public-replay';
    try {
      if (isExample && await fingerprint(output) !== reference.result_sha256) throw Error('REFERENCE_MISMATCH');
    } catch {
      if (token === generation && active()) {
        running = false;
        status.textContent = words.referenceError;
        enable();
      }
      return;
    }
    if (token !== generation || !active()) return;
    running = false;
    result = output;
    duration = elapsed;
    const title = result.highest_tested_load === null ? words.noPoint : `${words.highest} · ${result.highest_tested_load}`;
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
    resultArea.replaceChildren(text('h5', title), text('p', isExample ? words.demonstration : words.task),
      text('p', words.abstain), list);
    if (isExample) resultArea.querySelector('h5').after(text('p', words.compared));
    resultArea.hidden = false;
    keep.hidden = !hasCrypto;
    resultArea.scrollIntoView({block: 'start', behavior: 'instant'});
    resultArea.focus({preventScroll: true});
    status.textContent = words.sync;
    enable();
  }
  run.addEventListener('click', runTask);
  async function launchDemo() {
    if (loadPublic() && await freezeTask()) await runTask();
  }
  id('mv-demo').addEventListener('click', launchDemo);
  id('mf-quick-run').addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    void launchDemo();
  });
  keep.addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
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
    feedback.textContent = '';
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
    if (file === receiptInput.files[0] && token === generation && active()) feedback.textContent = message;
  });
  if (!hasCrypto) { receiptInput.disabled = consent.disabled = true; status.textContent = words.missingCrypto; }
  id('mv-clear').addEventListener('click', clear);
  window.addEventListener('frontier:member-lock', clear);
  enable();
  return launchDemo;
}

if (id('member-value')) {
  setupExplorer();
  setupGoals(member, setupRunner());
}
