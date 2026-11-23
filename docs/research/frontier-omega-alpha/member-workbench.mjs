import {screen, validate} from './endpoint-screen.mjs';
import {freezeScreen, outcome, verifyOutcome} from './outcome-receipt.mjs';

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
  badReceipt:'Reçu invalide ou modifié.', exported:'Reçu exporté localement.',
  consentCleared:'Consentement retiré. Aucun nouveau reçu ne sera préparé.',
  missingCrypto:'Le calcul local reste offert. La préparation de reçus nécessite un navigateur en contexte HTTPS sécurisé.',
} : {
  tracked:'briefs shown', empty:'No briefs match.',
  input:'Batch ready to freeze.', bad:'The file does not match the input format. Check dates, measurements and identifiers.',
  frozen:'Task frozen. The batch, thresholds and SQLite comparator are recorded.',
  sync:'Local calculation completed.', scoped:'Configuration', rows:'measurements',
  floor:'minimum tokens/s/user', ceiling:'maximum P90 TTFT (ms)', cutoff:'cutoff',
  highest:'Highest documented load', noPoint:'No documented qualifying point',
  abstain:'Operational adoption remains ABSTAIN.', checked:'Digest matches. Verify origin and the comparator separately.',
  badReceipt:'Invalid or altered receipt.', exported:'Receipt exported locally.',
  consentCleared:'Consent withdrawn. No further receipt will be prepared.',
  missingCrypto:'Local calculation is available. Receipt tools require a browser in a secure HTTPS context.',
};

function setupExplorer() {
  const query = id('mv-query');
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
  const input = id('mv-input');
  const receiptInput = id('mv-import');
  const tool = template('mv-endpoint-manifest');
  const reference = template('mv-endpoint-reference');
  const hasCrypto = Boolean(window.crypto?.subtle);
  let current, frozen, result, duration, exportStamp;
  let generation = 0;
  const active = () => !member.hidden;
  function enable() {
    freeze.disabled = !current || !(rightsRow.hidden || rights.checked) || Boolean(frozen);
    run.disabled = !frozen || Boolean(result) || !(rightsRow.hidden || rights.checked);
    save.disabled = !hasCrypto || !consent.checked || !result || !(rightsRow.hidden || rights.checked);
  }
  function clear() {
    generation++;
    exportStamp = undefined;
    current = frozen = result = duration = undefined;
    input.value = receiptInput.value = '';
    consent.checked = rights.checked = false;
    rightsRow.hidden = resultArea.hidden = true;
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

  id('mv-sample').addEventListener('click', () => {
    if (!active()) return;
    clear();
    load(template('mv-endpoint-sample'), true);
  });
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
      resultArea.hidden = true;
      resultArea.replaceChildren();
      consent.checked = false;
      status.textContent = words.input;
      feedback.textContent = words.consentCleared;
    }
    enable();
  });
  freeze.addEventListener('click', async () => {
    if (!active() || !current || !(rightsRow.hidden || rights.checked)) return;
    const token = ++generation;
    const approvedInput = current;
    freeze.disabled = true;
    try {
      const plan = hasCrypto ? await freezeScreen(approvedInput, tool, reference) : null;
      if (token !== generation || !active() || !(rightsRow.hidden || rights.checked)) return;
      frozen = {input: approvedInput, plan};
      status.textContent = words.frozen;
      enable();
    } catch {
      if (token === generation && active()) { status.textContent = words.missingCrypto; enable(); }
    }
  });

  run.addEventListener('click', () => {
    if (!active() || !frozen) return;
    const start = performance.now();
    result = screen(frozen.input);
    duration = Math.round((performance.now() - start) * 1000) / 1000;
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
    resultArea.replaceChildren(text('h5', title), text('p', words.abstain), list);
    resultArea.hidden = false;
    resultArea.focus();
    status.textContent = words.sync;
    enable();
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
    const url = URL.createObjectURL(new Blob([JSON.stringify(sealed, null, 2)], {type:'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'frontier-outcome-receipt.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    feedback.textContent = words.exported;
    enable();
  });
  receiptInput.addEventListener('change', async () => {
    if (!active()) return;
    const token = generation;
    let correct = false;
    try { correct = await verifyOutcome(await readFile(receiptInput.files[0])); } catch { /* untrusted input */ }
    if (token === generation && active()) feedback.textContent = correct ? words.checked : words.badReceipt;
  });
  if (!hasCrypto) { receiptInput.disabled = consent.disabled = true; status.textContent = words.missingCrypto; }
  id('mv-clear').addEventListener('click', clear);
  window.addEventListener('frontier:member-lock', clear);
  enable();
}

if (id('member-value')) {
  setupExplorer();
  setupRunner();
}
