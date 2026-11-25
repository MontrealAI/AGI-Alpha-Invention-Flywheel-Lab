const available = new Set(['available', 'downloadable', 'downloading']);

const modelOptions = language => ({
  expectedInputs: [{type: 'text', languages: [language]}],
  expectedOutputs: [{type: 'text', languages: [language]}],
});

export async function browserModelAvailability(language, runtime = globalThis.LanguageModel) {
  if (!['en', 'fr'].includes(language) || typeof runtime?.availability !== 'function'
      || typeof runtime.create !== 'function') return 'unavailable';
  try {
    const state = await runtime.availability(modelOptions(language));
    return available.has(state) ? state : 'unavailable';
  } catch {
    return 'unavailable';
  }
}

const directions = {
  en: 'Make a useful first pass at the member’s ambition in English. Give a concrete initial result when the supplied information supports one. Otherwise identify the most useful next action and any indispensable missing input. State material assumptions. Keep the response concise. Report only work you actually performed.',
  fr: 'Amorcez l’ambition du membre en français. Donnez un premier résultat concret si les renseignements fournis le permettent. Sinon, indiquez la prochaine action la plus utile et toute donnée indispensable qui manque. Précisez les hypothèses importantes. Répondez brièvement et faites état du travail réellement accompli.',
};

export async function runBrowserStarter({ambition, language, signal, onProgress}, runtime = globalThis.LanguageModel) {
  if (!['en', 'fr'].includes(language) || typeof ambition !== 'string' || !ambition.trim()
      || new TextEncoder().encode(ambition).length > 24 * 1024 || typeof runtime?.create !== 'function') {
    throw new Error('BROWSER_MODEL_INPUT');
  }
  signal?.throwIfAborted();
  // Invoke create in the user gesture so the browser can ask to download its model.
  const session = await runtime.create({
    ...modelOptions(language),
    signal,
    initialPrompts: [{role: 'system', content: directions[language]}],
    monitor(monitor) {
      monitor.addEventListener('downloadprogress', event => {
        if (!signal?.aborted && Number.isFinite(event.loaded) && event.loaded >= 0 && event.loaded <= 1) {
          onProgress?.(event.loaded);
        }
      });
    },
  });
  try {
    signal?.throwIfAborted();
    const response = await session.prompt([{role: 'user', content: ambition}], {signal});
    signal?.throwIfAborted();
    if (typeof response !== 'string' || !response.trim()) throw new Error('BROWSER_MODEL_EMPTY');
    return response.trim().slice(0, 10000);
  } finally {
    session.destroy();
  }
}
