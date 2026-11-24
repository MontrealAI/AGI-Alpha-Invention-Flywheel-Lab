import {downloadJSON} from './frontier-goals.mjs';
import {fingerprint} from './outcome-receipt.mjs';
import {compare, fieldsFromText, freeze, harnessProject, importDraft, kinds, maxBytes, mission,
  promptFor, readJSON, reopen, requalify, retain, run} from './foundry-core.mjs';
import {replayStudy, studyArms} from './foundry-study.mjs';

const id = name => document.getElementById(name);
const root = id('my-intelligence');
const member = id('member');
const fr = document.documentElement.lang === 'fr';

const inventorStatus = fr ? {
  RUNNING:'En cours ou en pause', SELECTED:'Possibilité choisie', SEALED:'Candidat préparé',
  DEVELOPMENT_INCOMPLETE:'Vérification de développement incomplète', ABSTAIN:'Abstention',
} : {
  RUNNING:'Running or paused', SELECTED:'Opportunity selected', SEALED:'Candidate sealed',
  DEVELOPMENT_INCOMPLETE:'Development checks incomplete', ABSTAIN:'Abstained',
};
const learningStages = fr ? {
  audit:'Vérifier la publication', learn:'Entraîner le modèle', invent:'Construire un outil',
} : {
  audit:'Verify release', learn:'Train model', invent:'Construct tool',
};
const activationStages = fr ? {
  construct:'Construire', decide:'Choisir la suite', repair:'Corriger', 'retain-rule':'Retenir une méthode',
  'choose-next':'Choisir un nouvel objectif', original:'Référence initiale', ordinary:'Réemploi ordinaire',
  augmented:'Méthode active', withdrawn:'Méthode retirée',
} : {
  construct:'Construct', decide:'Choose the next action', repair:'Repair', 'retain-rule':'Retain a method',
  'choose-next':'Choose a fresh objective', original:'Original constructor', ordinary:'Ordinary reuse',
  augmented:'Method active', withdrawn:'Method withdrawn',
};
const activationObjectives = fr ? {
  'learning-replay':'Reproduire l’évaluation du modèle', 'local-runner':'Rétablir l’environnement local',
  'inventor-audit':'Reconstituer les preuves d’invention',
} : {
  'learning-replay':'Replay the model evaluation', 'local-runner':'Restore the local runtime',
  'inventor-audit':'Reconstruct the invention evidence',
};
const stageStates = fr ? {
  QUEUED:'En attente', RUNNING:'En cours à l’export', COMPLETE:'Terminé', FAILED:'Échec',
} : {
  QUEUED:'Queued', RUNNING:'Running at export', COMPLETE:'Complete', FAILED:'Failed',
};
const learningOutcomes = fr ? {
  MATCHED_PUBLIC_RELEASE:'Publication publique vérifiée', CANDIDATE:'Candidat à évaluer',
  SEALED:'Outil à évaluer', ABSTAIN:'Abstention', REJECTED:'Refusé',
  DEVELOPMENT_INCOMPLETE:'Développement incomplet',
} : {
  MATCHED_PUBLIC_RELEASE:'Public release verified', CANDIDATE:'Candidate awaiting evaluation',
  SEALED:'Tool awaiting evaluation', ABSTAIN:'Abstained', REJECTED:'Rejected',
  DEVELOPMENT_INCOMPLETE:'Development incomplete',
};
const words = fr ? {
  frozen:'Mission figée. Choisissez comment obtenir un instrument.',
  sealed:'Instrument scellé. Ouvrez maintenant vos cas de vérification.',
  compared:'Cas concordants', rejected:'Au moins un cas a échoué. Examinez les écarts avant de revoir l’instrument.',
  current:'Le contrôle porte sur les cas fournis. L’acceptation indépendante du travail demeure à établir.',
  sample:'Rejeu technique des octets observés dans des reçus NOAA signés.',
  imported:'Intégrité du fichier contrôlée. Rouvrez le jeu de vérification d’origine pour requalifier l’instrument.',
  rechecked:'Les cas d’origine concordent. Utilisez les mêmes conditions pour interpréter les nouveaux résultats.',
  pending:'Calcul terminé. Qualifiez l’instrument avec des cas séparés.',
  checked:'Calcul terminé. Appliquez les limites du jeu de vérification.',
  copied:'Consigne copiée. Choisissez où la transmettre.',
  clipboard:'Sélectionnez et copiez la consigne affichée.',
  saved:'Fichier préparé sur cet appareil.',
  bad:'Vérifiez le format et les limites affichés. L’instrument précédent a été conservé.',
  libraryReady:'Intégrité des fichiers contrôlée. Rouvrez un instrument avec sa grille d’origine.',
  libraryFull:'La bibliothèque de session peut contenir jusqu’à 32 capacités. Retirez des éléments pour en ouvrir d’autres.',
  libraryRemoved:'Capacité retirée de la session.', libraryOpen:'Rouvrir pour vérifier', libraryExport:'Exporter', libraryRemove:'Retirer',
  studyReady:'Les résultats ont été reproduits avec la grille enregistrée.',
  studyKeep:'L’outil de référence a réussi tous les cas. Conservez-le pour l’utilisation courante.',
  studyReview:'Examinez les écarts avant de choisir un outil.',
  studyOpen:'Examiner l’instrument', studyScope:'Durées locales observées. Le coût complet et l’acceptation du travail restent à établir.',
  studyLabels:['Référence conventionnelle','Construction directe','Réemploi ordinaire','Réemploi par noms de sorties'],
  studyFailures:{NO_CANDIDATE:'Aucun instrument valide', PROVIDER_ERROR:'Erreur de connexion ou du modèle',
    INTERRUPTED:'Interrompu', PENDING:'En attente'},
  STUDY:'Le rapport ou la grille diffère du protocole enregistré. Ouvrez les fichiers d’origine.',
  FIELDS:'Utilisez des noms uniques suivis de :integer, :boolean ou :text.',
  MISSION:'Précisez le résultat, la règle, la méthode de référence et les critères d’acceptation.',
  CANDIDATE:'La réponse ne respecte pas le format HARNESS ou les champs de la mission.',
  SUITE:'Les cas doivent correspondre à cette mission et à ses champs. Vérifiez leur référence et leurs types.',
  RECHECK:'Le jeu fourni diffère de la vérification enregistrée. Requalifiez en repartant de la mission.',
  INPUT:'Les entrées comportent des champs manquants, des types différents ou des valeurs hors limites.',
  OUTPUT:'La sortie ne respecte pas le contrat de la mission.',
  EXECUTION:'Le calcul est invalide ou dépasse les limites de l’évaluateur.',
  ASSET:'Le fichier a changé ou sa version doit être requalifiée.',
  FILE:'Ouvrez un fichier JSON de 128 Kio au maximum.',
  JSON:'Collez un objet JSON complet.',
  SHEET:'Au moins un cas de vérification est requis.',
  crypto:'Utilisez la page HTTPS ou l’outil hors ligne pour sceller une mission.',
} : {
  frozen:'Mission frozen. Choose how to obtain an instrument.',
  sealed:'Instrument sealed. Open your verification cases now.',
  compared:'Cases matched', rejected:'At least one case failed. Inspect the differences before revising the instrument.',
  current:'This check covers the supplied cases. Independent acceptance of the work remains outstanding.',
  sample:'Technical replay of byte counts observed in signed NOAA receipts.',
  imported:'File integrity checked. Reopen the original verification sheet to requalify the instrument.',
  rechecked:'The original cases match. Use the same conditions to interpret new results.',
  pending:'Calculation complete. Qualify the instrument with separate cases.',
  checked:'Calculation complete. Apply the limits of the verification sheet.',
  copied:'Prompt copied. Choose where to send it.',
  clipboard:'Select and copy the displayed prompt.',
  saved:'File prepared on this device.',
  bad:'Check the displayed format and limits. The previous instrument has been kept.',
  libraryReady:'File integrity checked. Reopen an instrument with its original case sheet.',
  libraryFull:'This session holds up to 32 capabilities. Remove entries to open more.',
  libraryRemoved:'Capability removed from this session.', libraryOpen:'Reopen for verification', libraryExport:'Export', libraryRemove:'Remove',
  studyReady:'Results reproduced with the registered case sheet.',
  studyKeep:'The conventional incumbent passed every case. Keep it for current use.',
  studyReview:'Review the differences before choosing an instrument.',
  studyOpen:'Inspect instrument', studyScope:'These are local timings. Complete cost and work acceptance require separate evidence.',
  studyLabels:['Conventional incumbent','Direct construction','Ordinary reuse','Reuse by named outputs'],
  studyFailures:{NO_CANDIDATE:'No valid instrument', PROVIDER_ERROR:'Connection or model error',
    INTERRUPTED:'Interrupted', PENDING:'Pending'},
  STUDY:'The report or cases differ from the registered study. Open the original files.',
  FIELDS:'Use unique names followed by :integer, :boolean or :text.',
  MISSION:'Specify the outcome, rule, reference method and acceptance criteria.',
  CANDIDATE:'The reply does not match the HARNESS format or mission fields.',
  SUITE:'The cases must match this mission and its fields. Check their reference and types.',
  RECHECK:'The supplied sheet differs from the saved check. Start from the mission to qualify new cases.',
  INPUT:'Input fields are missing, have the wrong type or fall outside the declared range.',
  OUTPUT:'The output does not meet the mission contract.',
  EXECUTION:'The calculation is invalid or exceeds the evaluator limits.',
  ASSET:'The file changed or its version needs to be requalified.',
  FILE:'Open a JSON file up to 128 KiB.',
  JSON:'Paste a complete JSON object.',
  SHEET:'Enter at least one verification case.',
  crypto:'Use the HTTPS page or the offline tool to seal a mission.',
};

function setup() {
  const get = key => id('foundry-' + key);
  const active = () => !member.hidden;
  const put = (node, value) => { node.textContent = value; };
  const status = value => put(get('status'), value);
  const showJSON = (node, value) => put(node, JSON.stringify(value, null, 2));
  const json = key => readJSON(get(key).value, key === 'response');
  const library = new Map();
  const maximumLibraryItems = 32;
  let task, sealed, suite, saved, publicReplay, checked, generation = 0;
  let busy = false;
  const form = get('form');

  function render() {
    get('handoff').hidden = !task;
    get('verification').hidden = !sealed;
    get('data-permission').hidden = !task;
    get('run').disabled = busy || !sealed || Boolean(saved && !checked);
    get('retain').disabled = busy || !checked || !get('export-consent').checked;
    get('copy').disabled = busy || !task || !get('share').checked;
    get('kit').disabled = busy || !task || !get('share').checked;
    get('study-check').disabled = busy || !globalThis.crypto?.subtle ||
      !get('study-report').files.length || !get('study-cases').files.length;
    for (const name of ['sample','freeze','candidate','verify','case-template','mission-download','project',
      'open','candidate-file','cases','mission-file','library-files','study-report','study-cases','inventor-open','learning-open','activation-open']) {
      const control = get(name);
      if (control) control.disabled = busy || !globalThis.crypto?.subtle;
    }
  }

  function updateLibrary() {
    const items = get('library-items');
    items.replaceChildren();
    for (const [hash, envelope] of library) {
      const asset = envelope.asset;
      const entry = document.createElement('li');
      const title = document.createElement('strong');
      const scope = document.createElement('p');
      const actions = document.createElement('div');
      actions.className = 'mv-actions';
      put(title, asset.mission.objective);
      put(scope, `${asset.runtime} · ${asset.comparison.matched}/${asset.comparison.total} · ${hash.slice(0, 12)}`);
      function button(label, action) {
        const control = document.createElement('button');
        control.type = 'button';
        control.className = 'quiet';
        put(control, label);
        control.addEventListener('click', action);
        actions.append(control);
      }
      button(words.libraryOpen, launch(async alive => {
        if (await openAsset(envelope, alive)) location.hash = 'foundry-verification';
      }));
      button(words.libraryExport, () => {
        if (active()) downloadJSON(envelope, `frontier-capability-${hash.slice(0, 12)}.json`);
      });
      button(words.libraryRemove, () => {
        if (!active() || busy) return;
        library.delete(hash);
        updateLibrary();
        put(get('library-status'), words.libraryRemoved);
        get('library-files').focus();
      });
      entry.append(title, scope, actions);
      items.append(entry);
    }
  }

  function clearStudy() {
    put(get('study-status'), '');
    get('study-outcomes').replaceChildren();
    get('study-outcomes').hidden = true;
  }

  function clear(lock = false) {
    generation++;
    task = sealed = suite = saved = undefined;
    busy = publicReplay = checked = false;
    get('share').checked = get('export-consent').checked = false;
    for (const name of ['prompt','response','inputs','cases','sheet','candidate-file','open','mission-file']) get(name).value = '';
    for (const name of ['mission-hash','seal','comparison','output','receipt']) put(get(name), '');
    status('');
    if (lock) form.reset();
    render();
  }

  function launch(operation) {
    return async event => {
      event?.preventDefault();
      if (!active() || busy) return;
      if (!globalThis.crypto?.subtle) { status(words.crypto); return; }
      const stamp = generation;
      const alive = () => stamp === generation && active();
      busy = true;
      render();
      try { await operation(alive); }
      catch (error) {
        if (alive()) status(Object.hasOwn(words, error.message) ? words[error.message] : words.bad);
      } finally { if (alive()) { busy = false; render(); } }
    };
  }

  async function start(taskValue, alive) {
    const checkedTask = mission(taskValue);
    const hash = await fingerprint(checkedTask);
    if (!alive()) return false;
    task = checkedTask;
    sealed = suite = saved = undefined;
    checked = publicReplay = false;
    get('share').checked = get('export-consent').checked = false;
    for (const name of ['response','cases','sheet','inputs','candidate-file','open']) get(name).value = '';
    for (const name of ['seal','comparison','output','receipt']) put(get(name), '');
    get('prompt').value = promptFor(task);
    put(get('mission-hash'), hash);
    status(words.frozen);
    return true;
  }

  async function applyCandidate(draft, alive) {
    if (!task) return;
    const frozen = await freeze(task, importDraft(draft, task));
    if (!alive()) return;
    sealed = frozen;
    saved = suite = undefined;
    publicReplay = checked = false;
    get('export-consent').checked = false;
    for (const name of ['comparison','output','receipt']) put(get(name), '');
    put(get('seal'), frozen.instrument_sha256);
    status(words.sealed);
  }

  async function acceptCases(sheet, alive) {
    if (!sealed) return;
    const result = saved ? await requalify(saved, sheet) : await compare(sealed, sheet);
    if (!alive()) return;
    checked = result.summary.verdict === 'MATCHED';
    suite = checked ? sheet : undefined;
    get('export-consent').checked = false;
    put(get('comparison'), `${words.compared} ${result.summary.matched}/${result.summary.total}\n` +
      result.summary.reference + '\n' + (checked ? publicReplay ? words.sample :
        saved ? words.rechecked : words.current : words.rejected));
    showJSON(get('receipt'), result.rows);
    status(checked ? (publicReplay ? words.sample : words.current) : words.rejected);
  }

  async function readFile(file, allowFence = false) {
    if (!file || file.size > maxBytes) throw new Error('FILE');
    return readJSON(await file.text(), allowFence);
  }
  const fileValue = (node, allowFence) => readFile(node.files[0], allowFence);

  async function openAsset(envelope, alive) {
    const item = await reopen(envelope);
    if (!alive() || !await start(item.frozen.task, alive)) return false;
    saved = item;
    sealed = item.frozen;
    put(get('seal'), sealed.instrument_sha256);
    put(get('comparison'), words.imported);
    status(words.imported);
    return true;
  }

  form.addEventListener('submit', launch(alive => start({
    schema:kinds.mission, language:fr ? 'fr' : 'en',
    objective:get('objective').value, rule:get('rule').value,
    inputs:fieldsFromText(get('fields').value), outputs:fieldsFromText(get('outputs').value),
    alternative:get('alternative').value, acceptance:get('acceptance').value,
  }, alive)));
  get('mission-file').addEventListener('change', launch(async alive => {
    const data = await fileValue(get('mission-file'));
    if (alive()) await start(data, alive);
  }));
  get('mission-download').addEventListener('click', () => {
    if (task && active() && !busy) downloadJSON(task, 'frontier-mission.json');
  });
  get('project').addEventListener('click', launch(() => {
    if (!task) return;
    downloadJSON(harnessProject(task, sealed), 'frontier-harness-project.json');
    status(words.saved);
  }));
  get('share').addEventListener('change', render);
  get('copy').addEventListener('click', launch(async alive => {
    if (!get('share').checked || !task) return;
    try {
      await navigator.clipboard.writeText(promptFor(task));
      if (alive()) status(words.copied);
    } catch {
      if (alive()) { get('prompt').select(); status(words.clipboard); }
    }
  }));
  get('kit').addEventListener('click', () => {
    if (!active() || busy || !task || !get('share').checked) return;
    const prompt = new Blob([promptFor(task)], {type:'text/plain;charset=UTF-8'});
    const href = URL.createObjectURL(prompt);
    const link = document.createElement('a');
    link.href = href; link.download = 'frontier-mission-prompt.txt'; link.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  });
  get('candidate').addEventListener('click', launch(alive => applyCandidate(json('response'), alive)));
  get('candidate-file').addEventListener('change', launch(async alive => {
    const draft = await fileValue(get('candidate-file'), true);
    if (!alive()) return;
    await applyCandidate(draft, alive);
    if (alive()) get('response').value = JSON.stringify(sealed.instrument, null, 2);
  }));
  get('case-template').addEventListener('click', () => {
    if (!active() || !sealed || busy) return;
    downloadJSON({schema:kinds.confirmation, mission_sha256:sealed.mission_sha256, reference:'', cases:[]},
      'frontier-verification-template.json');
  });
  get('cases').addEventListener('change', launch(async alive => {
    const sheet = await fileValue(get('cases'));
    if (alive()) await acceptCases(sheet, alive);
  }));
  get('verify').addEventListener('click', launch(alive => acceptCases(json('sheet'), alive)));
  get('run').addEventListener('click', launch(() => {
    if (!sealed || (saved && !checked)) return;
    put(get('output'), '');
    showJSON(get('output'), run(sealed, json('inputs')));
    status(checked ? words.checked : words.pending);
  }));
  get('export-consent').addEventListener('change', render);
  get('retain').addEventListener('click', launch(async alive => {
    if (!checked || !suite || !get('export-consent').checked) return;
    const asset = await retain(sealed, suite);
    if (!alive() || !get('export-consent').checked) return;
    downloadJSON(asset, 'frontier-capability.json');
    if (library.size < maximumLibraryItems) {
      library.set(asset.sha256, asset);
      updateLibrary();
    }
    status(words.saved);
  }));
  get('open').addEventListener('change', launch(async alive => {
    const data = await fileValue(get('open'));
    if (alive()) await openAsset(data, alive);
  }));
  get('library-files').addEventListener('change', launch(async alive => {
    const field = get('library-files');
    const message = get('library-status');
    const files = [...field.files];
    field.value = '';
    if (files.length > maximumLibraryItems) { put(message, words.libraryFull); return; }
    const opened = new Map(library);
    try {
      for (const file of files) {
        const envelope = await readFile(file);
        if (!alive()) return;
        await reopen(envelope);
        if (!alive()) return;
        opened.set(envelope.sha256, envelope);
      }
      if (opened.size > maximumLibraryItems) { put(message, words.libraryFull); return; }
      for (const [hash, envelope] of opened) library.set(hash, envelope);
      updateLibrary();
      put(message, words.libraryReady);
    } catch (error) {
      if (alive()) put(message, Object.hasOwn(words, error.message) ? words[error.message] : words.bad);
    }
  }));
  for (const key of ['study-report','study-cases']) {
    get(key).addEventListener('change', () => { clearStudy(); render(); });
  }
  get('inventor-open').addEventListener('change', launch(async alive => {
    const local = get('inventor-local');
    put(local, '');
    try {
      const run = await fileValue(get('inventor-open'));
      if (!alive()) return;
      if (run?.schema !== 'frontier/inventor-run-v1' || typeof run.model !== 'string' || !run.model.trim() || run.model.length > 160 ||
          typeof run.status !== 'string' || !Object.hasOwn(inventorStatus, run.status) ||
          !Array.isArray(run.events) || run.events.length > 64) {
        throw new Error('CHECKPOINT');
      }
      const count = run.events.length;
      put(local, `${run.model} · ${inventorStatus[run.status]} · ${count} ${fr ? 'appels consignés' : 'recorded requests'}. ` +
        (fr ? 'Point de reprise local. Utilisez l’évaluateur pour confirmer le résultat.' :
          'Local checkpoint. Use the evaluator to confirm the result.'));
    } catch {
      if (alive()) put(local, fr ? 'Ouvrez le fichier run.json produit par l’utilitaire.' : 'Open the run.json file produced by the companion.');
    }
  }));
  function clearLearning() {
    if (!get('learning-status')) return;
    put(get('learning-status'), '');
    get('learning-steps').replaceChildren();
    get('learning-steps').hidden = true;
  }
  get('learning-open')?.addEventListener('change', launch(async alive => {
    clearLearning();
    try {
      const snapshot = await fileValue(get('learning-open'));
      if (!alive()) return;
      const hash = value => value === null || (typeof value === 'string' && /^[a-f0-9]{64}$/.test(value));
      if (snapshot?.schema !== 'frontier/learning-status-v1' || snapshot.scope !== 'public-actions-pages' ||
          !['ACTIVE','IDLE'].includes(snapshot.state) || !Number.isSafeInteger(snapshot.observed) || snapshot.observed < 0 ||
          !Number.isSafeInteger(snapshot.observed_at) || snapshot.observed_at < 0 || snapshot.observed_at >= 2 ** 32 ||
          !hash(snapshot.candidate_sha256) || !hash(snapshot.admitted_sha256) ||
          !Array.isArray(snapshot.stages) || snapshot.stages.length > 12 ||
          snapshot.stages.some(row => !row || !Object.hasOwn(learningStages, row.stage) ||
            !Object.hasOwn(stageStates, row.state) || (row.result && !Object.hasOwn(learningOutcomes, row.result.state)))) {
        throw new Error('LEARNING_STATUS');
      }
      const date = new Intl.DateTimeFormat(fr ? 'fr-CA' : 'en-CA', {dateStyle:'medium',timeStyle:'short'});
      const count = snapshot.observed;
      const state = snapshot.state === 'ACTIVE' ? (fr ? 'actif à l’export' : 'active at export') : (fr ? 'au repos' : 'idle');
      const candidate = snapshot.candidate_sha256 ? (fr ? 'Candidat ' : 'Candidate ') + snapshot.candidate_sha256.slice(0, 12) : '';
      const admitted = snapshot.admitted_sha256 ? (fr ? 'Modèle autorisé ' : 'Admitted model ') + snapshot.admitted_sha256.slice(0, 12) : '';
      put(get('learning-status'), [date.format(snapshot.observed_at*1000), state,
        `${count} observations`, candidate, admitted].filter(Boolean).join(' · '));
      const list = get('learning-steps');
      for (const row of snapshot.stages) {
        const item = document.createElement('li');
        const title = document.createElement('strong');
        put(title, learningStages[row.stage]);
        const state = document.createElement('span');
        put(state, row.result ? learningOutcomes[row.result.state] : stageStates[row.state]);
        item.append(title, state);
        list.append(item);
      }
      list.hidden = !snapshot.stages.length;
    } catch {
      if (alive()) put(get('learning-status'), fr ? 'Ouvrez le fichier learning-status.json de l’utilitaire.' :
        'Open the learning-status.json file from the companion.');
    }
  }));
  function clearActivation() {
    if (!get('activation-status')) return;
    put(get('activation-status'), '');
    get('activation-steps').replaceChildren();
    get('activation-steps').hidden = true;
  }
  get('activation-open')?.addEventListener('change', launch(async alive => {
    clearActivation();
    try {
      const snapshot = await fileValue(get('activation-open'));
      if (!alive()) return;
      if (snapshot?.schema !== 'frontier/activation-run-v1' ||
          snapshot.authority?.scope !== 'public-readonly-research' || !Object.hasOwn(activationObjectives,snapshot.objective) ||
          !['ACTIVE','COMPLETE'].includes(snapshot.state) || !Array.isArray(snapshot.journal) || snapshot.journal.length > 9 ||
          snapshot.journal.some(row => !row || !Object.hasOwn(activationStages,row.stage) || !['SEALED','ABSTAIN'].includes(row.state))) {
        throw new Error('ACTIVATION_STATUS');
      }
      const state = snapshot.state === 'COMPLETE' ? (fr ? 'Cycle terminé' : 'Cycle complete') :
        (fr ? 'Cycle actif à l’export' : 'Cycle active at export');
      put(get('activation-status'), `${activationObjectives[snapshot.objective]} · ${state}`);
      const list = get('activation-steps');
      for (const row of snapshot.journal) {
        const step = document.createElement('li');
        const title = document.createElement('strong');
        const note = document.createElement('span');
        put(title,activationStages[row.stage]);
        put(note,row.state === 'SEALED' ? (fr ? 'Proposition consignée' : 'Proposal recorded') :
          (fr ? 'Abstention' : 'Abstained'));
        step.append(title,note);
        list.append(step);
      }
      list.hidden = snapshot.journal.length === 0;
    } catch {
      if (alive()) put(get('activation-status'),fr ? 'Ouvrez le fichier activation-status.json de l’utilitaire.' :
        'Open activation-status.json from the local companion.');
    }
  }));
  get('study-check').addEventListener('click', launch(async alive => {
    clearStudy();
    try {
      const bundleFile = get('study-report').files[0];
      const casesFile = get('study-cases').files[0];
      const cases = await readFile(casesFile);
      const report = await replayStudy(await readFile(bundleFile), cases);
      if (!alive() || bundleFile !== get('study-report').files[0] || casesFile !== get('study-cases').files[0]) return;
      const {reference, outcomes, decision} = report.comparison;
      const result = get('study-outcomes');
      [null, ...studyArms].forEach((arm, index) => {
        const armResult = arm ? outcomes[arm] : null;
        const measure = arm ? armResult.comparison : reference;
        const attempt = arm ? report.attempts[arm] : null;
        const entry = document.createElement('div');
        const term = document.createElement('dt');
        const value = document.createElement('dd');
        put(term, words.studyLabels[index]);
        put(value, measure ? `${measure.matched}/${measure.total}` : words.studyFailures[armResult.status]);
        if (Number.isSafeInteger(attempt?.elapsed_ns)) {
          value.append(' · ' + (attempt.elapsed_ns / 1e9).toLocaleString(fr ? 'fr-CA' : 'en-CA', {maximumFractionDigits:2}) + ' s');
        }
        if (attempt && measure?.verdict === 'MATCHED') {
          const open = document.createElement('button');
          open.type = 'button';
          open.className = 'quiet';
          put(open, words.studyOpen);
          open.addEventListener('click', launch(async stillOpen => {
            if (!await start(report.plan.study.task, stillOpen)) return;
            await applyCandidate(attempt.candidate, stillOpen);
            if (!stillOpen()) return;
            await acceptCases(cases, stillOpen);
            if (stillOpen()) location.hash = 'foundry-verification';
          }));
          value.append(document.createElement('br'), open);
        }
        entry.append(term, value);
        result.append(entry);
      });
      result.hidden = false;
      put(get('study-status'), [words.studyReady, decision === 'KEEP_INCUMBENT' ? words.studyKeep : words.studyReview,
        words.studyScope].join(' '));
    } catch (error) {
      if (alive()) put(get('study-status'), Object.hasOwn(words, error.message) ? words[error.message] : words.bad);
    }
  }));
  get('sample').addEventListener('click', launch(async alive => {
    const example = readJSON(get('public-data').content.textContent);
    if (!await start(example.task, alive)) return;
    await applyCandidate(example.candidate, alive);
    if (!alive()) return;
    publicReplay = true;
    await acceptCases(example.suite, alive);
    if (!alive()) return;
    get('inputs').value = JSON.stringify(example.sample);
    showJSON(get('output'), run(sealed, example.sample));
  }));
  get('clear').addEventListener('click', () => {
    clear(true);
    get('mission').querySelector('summary').focus();
  });
  window.addEventListener('frontier:member-lock', () => {
    library.clear();
    updateLibrary();
    for (const key of ['library-files','study-report','study-cases','inventor-open','learning-open','activation-open']) {
      const control = get(key);
      if (control) control.value = '';
    }
    put(get('library-status'), '');
    put(get('inventor-local'), '');
    clearLearning();
    clearActivation();
    clearStudy();
    clear(true);
  });
  document.querySelectorAll('[data-foundry-start]').forEach(link => link.addEventListener('click', () => {
    if (active() && !task) {
      if (!get('objective').value) get('objective').value = id('goal-text').value;
      get('mission').open = true;
    }
  }));
  render();
}

if (root && member) setup();
