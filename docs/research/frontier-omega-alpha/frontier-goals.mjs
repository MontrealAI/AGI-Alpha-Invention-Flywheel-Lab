const vocabulary = {
  screening: /\b(?:endpoints?|sqlite|latency|latence|ttft|throughput|token throughput|charge admissible|debit de jetons)\b/u,
  archive: /\b(?:noaa|ncar|gfs|grib|forecast temperatures?|weather forecasts?|archiv\w* (?:forecasts?|meteo)|previsions? (?:meteo|historiques?|noaa))\b/u,
  reconstruction: /\b(?:missing (?:measurements?|observations?)|measurements? reconstruction|mesures? manquantes?|multiband|multibande|gaussian process|processus gaussien)\b/u,
  resilience: /\b(?:fink|alerce|broker|fallback|source (?:failure|outage)|repli|panne du fournisseur)\b/u,
  catalog: /\b(?:prusa|core one|alpha 1|catalog(?:ue)? eligibility|historical availability|date de lancement)\b/u,
  maintenance: /\b(?:qwen|gguf|harness adapter|adaptateur|schema validator|schema validation|validateur de schema)\b/u,
  training: /\b(?:repofactory|training environments?|environnements? d entrainement)\b/u,
  workflow: /\b(?:anys1|workflow (?:optimization|automation)|automatiser un processus)\b/u,
};

const presets = {
  endpoint: {screening: 8},
  archive: {archive: 8},
  workflow: {resilience: 6, workflow: 5, maintenance: 4},
  verify: {catalog: 6, evidence: 4},
  discover: {workflow: 6, training: 6, evidence: 4},
  build: {training: 6, workflow: 5},
};

const ignored = new Set(('about again also analyze and best build can check compare comparison could develop evidence find for from good have help how improve into intelligence need new now only our plan possible program provide real research result review said some test than that the their then these they this tool under use users using validate value want was what when which will with workflow would your ' +
  'afin aider ainsi analyser aussi avons avec cette changer choisir comme comment comparer construire dans demande depuis doit elle encore faire mieux mon nous notre obtenir outil peut pour pourquoi prends preuve quel quelle recherche rendre serait sont suis sur tester tout trouver utiliser vers veux votre vous').split(' '));
const normalize = value => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
  .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const terms = value => new Set(normalize(value).split(' ').filter(term => term.length >= 3 && !ignored.has(term)));

function actionFor(record, context) {
  const operating = /\b(?:production|operational|operationnel\w*|deploy\w*|deploi\w*|live traffic|real traffic|real workload|trafic reel|charge reelle|sla|slo)\b/u;
  const browserOnly = /\b(?:browser only|in (?:the|my) browser|no (?:install|installation)|dans (?:le|mon) navigateur|sans installation)\b/u;
  const offline = /\b(?:offline|hors ligne|sans (?:internet|reseau))\b/u;
  if (record.tool === 'endpoint' && !operating.test(context)) return 'demo';
  if (record.tool === 'archive' && !browserOnly.test(context) && !offline.test(context)) return 'tool';
  return 'review';
}

export function rankOpportunities(records, goal) {
  const query = normalize(goal.text || '');
  const requestedVersion = goal.text?.match(/\b\d{4}\.\d{4,5}(?:v\d+)?\b/iu)?.[0].toLowerCase();
  const outcome = Object.entries(vocabulary).filter(([, pattern]) => pattern.test(query)).map(([key]) => key);
  const queryTerms = terms(query);
  const preferences = Object.hasOwn(presets, goal.preset) ? presets[goal.preset] : {};
  const ranks = [];
  for (const record of records) {
    const matchesVersion = requestedVersion
      && (record.version === requestedVersion || record.version.split('v')[0] === requestedVersion);
    if (requestedVersion && !matchesVersion) continue;
    const titleTerms = terms(record.title);
    const summaryTerms = terms(record.subject);
    const lexical = [...queryTerms].reduce((score, term) =>
      score + (titleTerms.has(term) ? 5 : summaryTerms.has(term) ? 1 : 0), 0);
    const topic = outcome.includes(record.outcome) ? 12 : 0;
    const suggested = preferences[record.outcome] || 0;
    if (!matchesVersion && !topic && !suggested && lexical < 5) continue;
    const score = (matchesVersion ? 100 : 0) + topic + suggested + lexical;
    const maturity = record.state === 'discovered' ? 0 : 1;
    ranks.push({record, score, maturity, action: actionFor(record, query)});
  }
  return ranks.sort((a, b) => b.score - a.score || b.maturity - a.maturity
    || b.record.observed.localeCompare(a.record.observed) || a.record.id.localeCompare(b.record.id));
}

export function reviewSaved(pin, current) {
  if (!current || pin.id !== current.id) return 'missing';
  return pin.version === current.version && pin.review === current.review ? 'current' : 'revised';
}

const schema = 'frontier/saved-goal-v1';
function exact(value, keys) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}

export function readSavedGoal(value) {
  if (!exact(value, ['schema', 'goal', 'pin']) || value.schema !== schema) throw Error('INVALID_GOAL');
  const {goal, pin} = value;
  if (!(exact(goal, ['text']) && typeof goal.text === 'string' && goal.text.trim() && goal.text.length <= 200)
    && !(exact(goal, ['preset']) && Object.hasOwn(presets, goal.preset))) throw Error('INVALID_GOAL');
  if (pin !== null && !(exact(pin, ['id', 'version', 'review'])
    && typeof pin.id === 'string' && /^[a-z0-9][a-z0-9.-]{0,100}$/u.test(pin.id)
    && typeof pin.version === 'string' && /^[a-zA-Z0-9._-]{1,100}$/u.test(pin.version)
    && typeof pin.review === 'string' && /^[a-f0-9]{64}$/u.test(pin.review))) throw Error('INVALID_GOAL');
  return {goal, pin};
}

export function downloadJSON(value, filename) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function readBrief(card) {
  const source = card.querySelector('.mv-source-date');
  const fields = Object.fromEntries([...card.querySelectorAll('[data-field]')].map(field => [field.dataset.field, field.textContent]));
  return {
    id: card.id.slice('decision-'.length),
    title: card.querySelector('h4').textContent,
    subject: [fields.change, fields.possibility, fields.missing_move].join(' '),
    evidence: card.querySelector('.packet-meta').textContent,
    state: card.dataset.evidence,
    verdict: card.dataset.action,
    outcome: card.dataset.outcome,
    observed: card.dataset.observed,
    tool: source.dataset.tool,
    review: source.dataset.review,
    version: source.querySelector('code').textContent,
    url: card.querySelector('[data-decision-source]').href,
    fields,
  };
}

const labels = {
  en: {
    empty: 'Enter a goal or choose one of the suggested goals.',
    missing: 'There is no sufficiently specific match in the current evidence. Name a concrete claim, tool or measurement, or start with the public example.',
    saved: 'Goal downloaded. Reopen it here on a later visit to check the evidence again.',
    invalid: 'This file could not be opened. Choose a goal file downloaded from My Frontier.',
    current: 'The saved recommendation matches today’s evidence.',
    revised: 'The saved recommendation has changed. Review the current evidence before acting.',
    gone: 'The saved evidence is unavailable in this release. Recheck its source before acting.',
    reranked: 'A different record now ranks first for this goal.',
    demo: ['Run the public demo', 'Endpoint Evidence Screen · local demonstration. Operational adoption remains ABSTAIN.'],
    tool: ['Open NOAA quick start', 'NOAA Archive Point · qualified Linux package with an independent signed reference.'],
    review: ['Open the decision brief', 'Follow the evidence and the strongest alternative before choosing a tool.'],
    prerequisite: 'This archive package needs the qualified Linux setup and the public NOAA origin for a new query.',
    abstain: 'The current evidence supports a bounded benchmark screen. A real operating decision still requires authorized requirements and independent custody.',
  },
  fr: {
    empty: 'Saisissez un objectif ou choisissez une des suggestions.',
    missing: 'Les preuves actuelles ne donnent pas de correspondance assez précise. Nommez une affirmation, un outil ou une mesure, ou essayez l’exemple public.',
    saved: 'Objectif téléchargé. Rouvrez-le lors d’une prochaine visite pour vérifier les preuves à jour.',
    invalid: 'Impossible d’ouvrir ce fichier. Choisissez un fichier d’objectif téléchargé depuis Ma frontière.',
    current: 'La recommandation sauvegardée concorde avec les preuves actuelles.',
    revised: 'La recommandation sauvegardée a changé. Consultez les preuves à jour avant d’agir.',
    gone: 'Les preuves sauvegardées sont absentes de cette édition. Vérifiez leur source avant d’agir.',
    reranked: 'Une autre fiche est maintenant la plus pertinente pour cet objectif.',
    demo: ['Lancer la démonstration', 'Évaluation Endpoint · démonstration locale. L’adoption opérationnelle reste en abstention.'],
    tool: ['Consulter le guide NOAA', 'Point d’archive NOAA · outil Linux qualifié avec référence indépendante signée.'],
    review: ['Ouvrir le dossier décisionnel', 'Examinez les preuves et la meilleure solution de rechange avant de choisir un outil.'],
    prerequisite: 'Cet outil nécessite l’environnement Linux qualifié et le site public de la NOAA pour une nouvelle requête.',
    abstain: 'Les preuves permettent une évaluation de banc d’essai. Une décision opérationnelle nécessite des exigences autorisées et une garde indépendante.',
  },
};

export function setupGoals(member, launchDemo) {
  const id = key => document.getElementById(key);
  const words = labels[document.documentElement.lang] || labels.en;
  const form = id('goal-form');
  const input = id('goal-text');
  const submit = id('goal-submit');
  const status = id('goal-status');
  const result = id('goal-result');
  const title = id('goal-result-title');
  const proof = id('goal-proof');
  const action = id('goal-action');
  const available = id('goal-available');
  const save = id('goal-export');
  const open = id('goal-import');
  const chips = [...form.querySelectorAll('[data-goal]')];
  const records = [...member.querySelectorAll('[data-mv-record]')].map(readBrief);
  const byId = new Map(records.map(record => [record.id, record]));
  let state, generation = 0;
  const active = () => !member.hidden;

  function display(goal, prior) {
    const [match] = rankOpportunities(records, goal);
    const record = match?.record;
    const pin = record ? {id: record.id, version: record.version, review: record.review} : null;
    state = {schema, goal, pin};
    save.disabled = false;
    result.hidden = !match;
    for (const chip of chips) chip.setAttribute('aria-pressed', String(chip.dataset.goal === goal.preset));
    const descriptions = [];
    if (prior) {
      const current = byId.get(prior.id);
      const state = reviewSaved(prior, current);
      descriptions.push(words[state === 'missing' ? 'gone' : state]);
      if (current && prior.version !== current.version) descriptions.push(prior.version + ' → ' + current.version);
      if (record && record.id !== prior.id) descriptions.push(words.reranked);
    }
    if (!match) descriptions.push(words.missing);
    status.textContent = descriptions.join(' ');
    if (!match) return;
    result.dataset.record = record.id;
    result.dataset.action = match.action;
    title.textContent = record.title;
    id('goal-evidence-state').textContent = record.evidence + ' · ' + record.observed.slice(0, 10);
    for (const fact of result.querySelectorAll('[data-goal-fact]')) fact.textContent = record.fields[fact.dataset.goalFact];
    proof.href = '#decision-' + record.id;
    id('goal-source').href = record.url;
    const [verb, detail] = words[match.action];
    action.textContent = verb;
    action.href = match.action === 'demo' ? '#mv-endpoint-run' : match.action === 'tool' ? '#tool-archive' : proof.hash;
    available.textContent = match.action === 'review' && record.tool
      ? words[record.tool === 'endpoint' ? 'abstain' : 'prerequisite'] : detail;
    title.focus();
  }

  function clear() {
    generation++;
    state = undefined;
    result.hidden = save.disabled = true;
    status.textContent = '';
    for (const chip of chips) chip.setAttribute('aria-pressed', 'false');
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!active()) return;
    generation++;
    const query = input.value.trim();
    if (query) display({text: query});
    else status.textContent = words.empty;
  });
  input.addEventListener('input', clear);
  for (const chip of chips) chip.addEventListener('click', () => {
    if (!active()) return;
    generation++;
    input.value = '';
    display({preset: chip.dataset.goal});
  });
  action.addEventListener('click', event => {
    if (!active() || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (result.dataset.action === 'demo') {
      event.preventDefault();
      void launchDemo();
    } else if (result.dataset.action === 'review') {
      event.preventDefault();
      proof.click();
    } else {
      const card = id('tool-archive');
      const details = card.querySelector('.mf-instructions');
      details.open = true;
      details.querySelector('summary').focus({preventScroll: true});
    }
  });
  save.addEventListener('click', () => {
    if (!active() || !state) return;
    downloadJSON(state, 'frontier-goal.json');
    status.textContent = words.saved;
  });
  open.addEventListener('change', async () => {
    if (!active()) return;
    const file = open.files[0];
    open.value = '';
    if (!file) return;
    const token = ++generation;
    try {
      if (file.size > 8192) throw Error('INVALID_GOAL');
      const {goal, pin} = readSavedGoal(JSON.parse(await file.text()));
      if (token !== generation || !active()) return;
      input.value = goal.text || '';
      display(goal, pin);
    } catch {
      if (token === generation && active()) status.textContent = words.invalid;
    }
  });
  window.addEventListener('frontier:member-lock', () => {
    clear();
    form.reset();
    open.value = '';
    id('goal-keeper').open = false;
  });
  submit.disabled = false;
}
