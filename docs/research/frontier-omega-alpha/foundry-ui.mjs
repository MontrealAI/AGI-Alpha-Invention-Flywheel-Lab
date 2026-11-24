import {downloadJSON} from './frontier-goals.mjs';
import {fingerprint} from './outcome-receipt.mjs';
import {candidate, compare, fieldsFromText, freeze, harnessProject, kinds, maxBytes, mission,
  promptFor, readJSON, reopen, requalify, retain, run} from './foundry-core.mjs';

const id = name => document.getElementById(name);
const root = id('my-intelligence');
const member = id('member');
const fr = document.documentElement.lang === 'fr';
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
  let task, sealed, suite, saved, publicReplay, checked, generation = 0;
  let busy = false;
  const controls = root.querySelectorAll('input, textarea, button');
  const form = get('form');

  function render() {
    get('handoff').hidden = !task;
    get('verification').hidden = !sealed;
    get('data-permission').hidden = !task;
    get('run').disabled = busy || !sealed || Boolean(saved && !checked);
    get('retain').disabled = busy || !checked || !get('export-consent').checked;
    get('copy').disabled = busy || !task || !get('share').checked;
    get('kit').disabled = busy || !task || !get('share').checked;
    for (const name of ['sample','freeze','open','candidate','verify','case-template','mission-download','project']) {
      get(name).disabled = busy || !globalThis.crypto?.subtle;
    }
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
    const frozen = await freeze(task, draft);
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

  async function fileValue(node, allowFence = false) {
    const file = node.files[0];
    if (!file || file.size > maxBytes) throw new Error('FILE');
    return readJSON(await file.text(), allowFence);
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
    candidate(draft, task);
    get('response').value = JSON.stringify(draft, null, 2);
    await applyCandidate(draft, alive);
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
    status(words.saved);
  }));
  get('open').addEventListener('change', launch(async alive => {
    const data = await fileValue(get('open'));
    const item = await reopen(data);
    if (!alive() || !await start(item.frozen.task, alive)) return;
    saved = item;
    sealed = item.frozen;
    put(get('seal'), sealed.instrument_sha256);
    put(get('comparison'), words.imported);
    status(words.imported);
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
    get('objective').focus();
  });
  window.addEventListener('frontier:member-lock', () => clear(true));
  document.querySelectorAll('[data-foundry-start]').forEach(link => link.addEventListener('click', () => {
    if (active() && !task) {
      if (!get('objective').value) get('objective').value = id('goal-text').value;
      get('mission').open = true;
    }
  }));
  for (const control of controls) {
    if (!globalThis.crypto?.subtle && control.type === 'file') control.disabled = true;
  }
  render();
}

if (root && member) setup();
