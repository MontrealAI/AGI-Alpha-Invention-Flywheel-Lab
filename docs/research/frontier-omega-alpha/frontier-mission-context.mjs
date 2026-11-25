const contextSchema = 'frontier/mission-context-v1';
const packageSchema = 'frontier/mission-intelligence-package-v1';
const repository = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab';
const published = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/';
const sha = /^[a-f0-9]{64}$/u;
const commit = /^[a-f0-9]{40}$/u;
const named = /^[a-z0-9][a-z0-9.-]{0,100}$/u;
const isoDay = /^\d{4}-\d\d-\d\d$/u;
const encoder = new TextEncoder();

const word = {
  en: {
    lead:'Research lead', result:'Reviewed observation', tool:'Qualified tool', limit:'Scope', fit:'Relevance',
    operation:'Operating instructions', record:'Review record', compare:'Prior whole-work comparison',
    sourceDate:'Source date', reviewDate:'Reviewed on', cutoffDate:'Evidence cutoff', asOf:'Available in release', alternative:'Alternative to compare',
    compareScope:'Disjoint conventional cycles and integrated cycles with transition included. This comparison establishes no economic gain.',
    compareFit:'Use comparable conditions and include the full workflow cost.',
    broadFit:'A published candidate to investigate against its incumbent on the same authorized task.',
    observedFit:'The source and measured outcome are available for checking before committing resources.',
    referenceFit:'The published title and version identify a relevant source to read.',
    referenceScope:'The Atlas confirmed source metadata. Applicability and outcomes remain unverified.',
    reported:'Author-reported lead. Independent transfer and complete cost remain unverified.',
    catalogScope:'Public catalogue planning. Imagery, site displacement and site safety require separate evidence.',
    confirmedScope:'The study verifies documentary availability. Actual operation and complete cost remain unverified.',
    observedSource:'The Atlas checked the source identity, title and version.',
  },
  fr: {
    lead:'Piste de recherche', result:'Observation examinée', tool:'Outil qualifié', limit:'Périmètre', fit:'Pertinence',
    operation:'Mode d’emploi', record:'Dossier examiné', compare:'Comparaison antérieure du travail de bout en bout',
    sourceDate:'Date de la source', reviewDate:'Examiné le', cutoffDate:'Date limite des preuves', asOf:'Disponible dans la publication du', alternative:'Méthode de comparaison',
    compareScope:'Cycles classiques distincts et cycles intégrés avec transition. Cette comparaison n’établit aucun gain économique.',
    compareFit:'Comparer des tâches équivalentes en tenant compte de l’ensemble des coûts.',
    broadFit:'Une piste publique à comparer à la meilleure méthode en place sur la même tâche autorisée.',
    observedFit:'La source et le résultat mesuré peuvent être examinés avant d’engager des ressources.',
    referenceFit:'Le titre et la version permettent de retrouver une source pertinente à examiner.',
    referenceScope:'L’Atlas a confirmé les métadonnées de la source. L’applicabilité et les résultats restent à vérifier.',
    reported:'Piste rapportée par les auteurs. Le transfert et le coût complet restent à vérifier indépendamment.',
    catalogScope:'Planification à partir du catalogue public. Les images, les déplacements du terrain et sa sécurité exigent des preuves distinctes.',
    confirmedScope:'L’étude confirme la disponibilité documentée. Le fonctionnement réel et le coût complet restent à vérifier.',
    observedSource:'L’Atlas a vérifié l’identité, le titre et la version de la source.',
  },
};

const frames = {
  discovery: [
    /\b(?:capture|captur\w*|capter|saisir|discover|decouvrir|reperer|find|identify|identifier|leverage|tirer parti|explore|explorer)\b/u,
    /\b(?:exponential|exponentiel\w*|newly (?:possible|attainable|feasible)|recent (?:advances?|technolog\w+)|technological progress|emerging technolog\w*|frontier advances?|nouvelles possibilites|progres technologique\w*|avancees recentes|nouvellement (?:possible|realisable))\b/u,
  ],
  endpoint: [
    /\b(?:endpoint\w*|mlperf|llm|inference|inference locale|service de modele)\b/u,
    /\b(?:p90|ttft|first token|premier jeton)\b/u,
    /\b(?:throughput|debit|tokens per user|jetons par utilisateur)\b/u,
    /\b(?:load|loads|concurrency|charge|concurrence)\b/u,
    /\b(?:test\w*|measur\w*|mesur\w*|benchmark)\b/u,
  ],
  archive: [
    /\b(?:noaa|gfs|grib2)\b/u,
    /\b(?:archive\w*|histor\w*|f024)\b/u,
    /\b(?:temperatur\w*|kelvin|grille|grid)\b/u,
  ],
  game: [
    /\b(?:game theory|theorie des jeux|zero sum|somme nulle)\b/u,
    /\b(?:build|construct\w*|creer|develop\w*|solver|solveur|strategie|strateg\w*|teach\w*|entrain\w*|former|learn\w*|allocat\w*|verif\w*|certif\w*|payoff|gain\w*)\b/u,
  ],
  battery: [
    /\b(?:battery|batterie|batteries)\b/u,
    /\b(?:product passport|passport|passeport|dpp|preuve|evidence|declaration|disclosure)\b/u,
  ],
};

const rejects = {
  discovery: /\b(?:exponential (?:decay|function|fit|growth rate|moving average|backoff)|exponentiel (?:decroissant|mobile)|camera|oscilloscope|plot|tracer)\b/u,
  endpoint: /\b(?:without (?:any )?(?:measurements?|benchmarks?)|sans (?:mesures?|essais?)|(?:certify|certifier|guarantee|garantir) (?:production|uptime|availability|disponibilite))\b/u,
  archive: /\b(?:browser only|navigateur seulement|sans installation|without (?:linux|network)|sans (?:linux|reseau|internet)|live weather|temps reel|observed temperature|temperature observee|station temperature|temperatur\w* de station|interpolat\w*|wind|vent|precipitation\w*|f(?!024\b)\d{3}|(?:6|12|18|36|48|72) (?:h|hours?|heures?))\b/u,
  game: /\b(?:general sum|non zero sum|somme non nulle|positive sum|cooperative games?|jeux cooperatifs|repeated games?|jeux repetes|sequential auctions?|encheres sequentielles)\b/u,
  battery: /\b(?:submit|filing|authorize|legal advice|deposer|soumettre|avis juridique|homologuer)\b/u,
};

// The general exploration package spans industries. An ambition already
// narrowed to a field should receive only individually matched evidence.
const focusedDiscovery = /\b(?:(?:recent advances?|emerging technolog\w*|newly (?:possible|attainable|feasible)|nouvelles possibilites|avancees recentes) (?:in|for|within|dans|en|pour)|focus(?:ed)? on|concentre\w* sur) (?!ai\b|technology\b|technologie\b|ia\b)\w/u;

const intent = /\b(?:verify|verifier|validate|valider|research|recherch\w*|investigat\w*|enquet\w*|review|examin\w*|compare|comparer|check|evaluate|evalu\w*|discover|decouvr\w*|catalog\w*|availability|disponibilite)\b/u;
const ignored = new Set(('their about this these those what which with from please would recent technology technical software report results system research publication review public verify validated compare using supported support evidence study author frontier source ' +
  'leur cette celui aussi pour dans dont avec entre depuis outil etude recherche resultat systeme technique logiciel public preuves source verifier comparer examiner rapport disponible possibilite').split(' '));
const normalize = value => value.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()
  .replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
const terms = value => new Set(normalize(value).split(' ').filter(term => term.length >= 4 && !ignored.has(term)));
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const control = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/u;

function text(value, limit) {
  if (typeof value !== 'string' || control.test(value)) return undefined;
  const line = value.trim().replace(/\s+/gu, ' ');
  return line && encoder.encode(line).length <= limit ? line : undefined;
}

function url(value) {
  if (value !== text(value, 340)) return undefined;
  try {
    const parsed = new URL(value);
    if (parsed.protocol === 'https:' && !parsed.username && !parsed.password && text(parsed.href, 340)) return parsed.href;
  } catch { /* A source or tool without a usable URL adds no brief content. */ }
  return undefined;
}

function date(value) {
  const day = typeof value === 'string' && value.slice(0, 10);
  return day && isoDay.test(day) && Number.isFinite(Date.parse(day))
    && new Date(day).toISOString().slice(0, 10) === day ? day : undefined;
}

function fits(name, query) {
  return frames[name].every(clause => clause.test(query)) && !rejects[name].test(query);
}

function scopedOverlap(words, title) {
  if (!words || typeof title !== 'string') return 0;
  const overlap = [...terms(title)].filter(term => words.has(term));
  return overlap.length >= 2 && overlap.some(term => term.length >= 6) ? overlap.length : 0;
}

function reviewedSource(release, path) {
  return commit.test(release?.source_commit ?? '') ? repository + '/blob/' + release.source_commit + '/' + path : undefined;
}

function item({id, kind, title, fact, scope, relevance, sourceURL, sourceDate, dateBasis = 'sourceDate',
  primaryMetadataSha256, artifact, recordURL, recordSha256}) {
  const source = {url:url(sourceURL), date:date(sourceDate), dateBasis};
  const result = {id, kind, title:text(title, 220), fact:text(fact, 630), scope:text(scope, 410),
    relevance:text(relevance, 210), source};
  if (sha.test(primaryMetadataSha256 ?? '')) source.primaryMetadataSha256 = primaryMetadataSha256;
  const review = url(recordURL);
  if (review && review !== source.url) {
    result.recordURL = review;
    if (sha.test(recordSha256 ?? '')) result.recordSha256 = recordSha256;
  }
  if (artifact) result.artifact = artifact;
  return named.test(id ?? '') && result.title && result.fact && result.scope && result.relevance && source.url && source.date ? result : undefined;
}

function opportunityItem(study, entry, language, broad, release) {
  const words = word[language];
  const content = entry[language];
  const acceptance = entry.acceptance_receipt;
  const operated = ['OPERATING', 'QUALIFIED'].includes(entry.state) && /^discovery\/[A-Z0-9._-]+\.json$/u.test(acceptance ?? '')
    && sha.test(study.receipts?.[acceptance] ?? '') && entry.evidence_stage === 'PUBLIC_CATALOG_METADATA';
  if (entry.action !== 'TEST' || broad && !operated || !operated && entry.state !== 'VERIFIED') return undefined;
  return item({id:entry.id, kind:operated ? 'result' : 'lead', title:content?.title, fact:content?.finding,
    scope:operated ? words.catalogScope : words.confirmedScope, relevance:broad ? words.broadFit : words.observedFit,
    sourceURL:Array.isArray(entry.evidence) ? entry.evidence.find(value => url(value)) : undefined,
    sourceDate:entry.first_party_date_utc,
    recordURL:reviewedSource(release, operated ? 'publication/opportunity/' + acceptance : 'publication/opportunity/REPORT.md'),
    recordSha256:operated ? study.receipts[acceptance] : undefined});
}

function comparison(study, language, release) {
  const observed = study.comparison;
  const times = observed?.whole_work_wall_seconds;
  const accepted = observed?.accepted;
  if (!times || !accepted || ![accepted.conventional, accepted.integrated].every(
    row => Array.isArray(row) && row.length === 2 && row.every(Number.isSafeInteger) && row[0] <= row[1] && row[1] > 0)
    || ![times.conventional_disjoint_cycles, times.integrated_with_transition].every(n => Number.isFinite(n) && n > 0)) return undefined;
  const words = word[language];
  const outcome = field => accepted[field].join('/');
  const seconds = field => new Intl.NumberFormat(language, {maximumFractionDigits:1}).format(times[field]);
  const conventional = outcome('conventional') + ' · ' + seconds('conventional_disjoint_cycles') + ' s';
  const integrated = outcome('integrated') + ' · ' + seconds('integrated_with_transition') + ' s';
  const fact = language === 'fr' ? 'Méthode classique ' + conventional + '. Méthode intégrée ' + integrated + '.'
    : 'Conventional ' + conventional + '. Integrated ' + integrated + '.';
  return item({id:'opportunity-comparison', kind:'result', title:words.compare, fact, scope:words.compareScope,
    relevance:words.compareFit, sourceURL:reviewedSource(release, 'publication/opportunity/REPORT.md'),
    sourceDate:study.atlas_cutoff_utc, dateBasis:'cutoffDate'});
}

function batterySourceStudy(language, release) {
  const filename = 'frontier-battery-source-example.json';
  const digest = release?.universal_mission_sha256?.[filename];
  if (!sha.test(digest ?? '') || !sha.test(release?.universal_mission_sha256?.['dpp-source-review.mjs'] ?? '')) return undefined;
  const fr = language === 'fr';
  return item({id:'battery-source-review', kind:'result',
    title:fr ? 'Passeports de batterie · vérification des données sources' : 'Battery passport source review',
    fact:fr ? 'La Commission a publié les spécifications du registre et les ressources sémantiques. Les deux méthodes expérimentales ont obtenu 14/16, puis 6/6 sur des cas distincts.' :
      'The Commission published registry specifications and semantic resources. Both pilot methods scored 14/16, then 6/6 on fresh cases.',
    scope:fr ? 'Contrôle de mesures issues d’extraits examinés. Gain comparatif et conformité réglementaire à établir.' :
      'Checks measurements from reviewed excerpts. Comparative gain and regulatory acceptance remain unestablished.',
    relevance:fr ? 'Utiliser l’exemple pour examiner ce qu’une source permet d’affirmer sur un modèle précis.' :
      'Use the example to examine what a source supports for a specific product configuration.',
    sourceURL:'https://single-market-economy.ec.europa.eu/news/digital-product-passport-registry-technical-guidance-available-2026-11-16_en',
    sourceDate:'2026-11-16',
    recordURL:reviewedSource(release, 'publication/prove-advantage/DPP.md'),
    artifact:{url:published+filename,sha256:digest,version:'1.0.0',rights:'Synthetic fixture under the repository license',
      instructions:fr ? 'Ajouter le JSON aux fichiers de la mission et vérifier les mesures fournies.' :
        'Add the JSON to this mission’s result files and check the supplied measurements.'}});
}

const tools = {
  endpoint: {
    en:['Endpoint Evidence Screen','Select the highest measured concurrency meeting declared P90 first-token latency and per-user throughput limits.','Requires measurements on one workload, model and hardware setup. Operational adoption remains outside the qualified scope.','Both measures and tested load are requested.'],
    fr:['Évaluation Endpoint','Sélectionner la concurrence mesurée la plus élevée qui respecte les limites de latence P90 du premier jeton et de débit par utilisateur.','Exige des mesures pour une seule tâche, un seul modèle et une seule configuration. L’adoption opérationnelle dépasse le périmètre qualifié.','La tâche demande les deux mesures et une charge testée.'],
    instructions:'node endpoint-cli.mjs sample.json',
    guide:'products/frontier-member-tools/ENDPOINT.md',
    id:'endpoint-evidence-screen',
  },
  archive: {
    en:['NOAA Archive Point','Extract 2 m air temperature in kelvin at an exact NOAA GFS native 0.25° grid point.','Historical f024 forecast only, valid 24 hours after initialization. Linux, Python 3.12, curl and OpenSSL.','The requested historical source and quantity fit this forecast retrieval scope.'],
    fr:['Point d’archive NOAA','Extraire en kelvins la température de l’air à 2 m pour un point exact de la grille NOAA GFS à 0,25°.','Prévision historique f024 valide 24 heures après l’initialisation. Linux, Python 3.12, curl et OpenSSL.','La source historique et la variable demandées cadrent avec cette extraction de prévision.'],
    instructions:'python3 archive-query.py --help',
    guide:null,
    id:'noaa-archive-point',
  },
};

function toolItem(key, language, member, release) {
  if (member?.schema !== 'frontier/public-member-value-v1' || member.publication !== 'public-file') return undefined;
  const definition = tools[key];
  const manifest = member?.capabilities?.[key];
  if (manifest?.id !== definition.id || manifest.schema !== 'frontier/portable-capability-v1'
    || !named.test(manifest.version ?? '') || manifest.download !== definition.id + '-' + manifest.version + '.zip'
    || !sha.test(manifest.sha256 ?? '') || release?.public_capability_sha256?.[manifest.download] !== manifest.sha256) return undefined;
  const rights = text(manifest.rights, 180);
  if (!rights) return undefined;
  const [title, fact, scope, relevance] = definition[language];
  const brief = (Array.isArray(member.briefs) ? member.briefs : []).find(entry => entry.tool === key);
  return item({id:definition.id, kind:'tool', title, fact, scope, relevance, sourceURL:manifest.source,
    sourceDate:brief?.observed_at ?? member.updated_at, dateBasis:brief ? 'reviewDate' : 'asOf',
    recordURL:definition.guide ? reviewedSource(release, definition.guide) : undefined,
    artifact:{url:published + manifest.download, sha256:manifest.sha256, version:manifest.version,
      rights, instructions:definition.instructions}});
}

function gameItem(language, release) {
  const name = 'frontier-game-theory-1.0.0.zip';
  const digest = release?.universal_mission_sha256?.[name];
  if (!sha.test(digest ?? '')) return undefined;
  const fr = language === 'fr';
  return item({id:'strategic-allocation', kind:'tool',
    title:fr ? 'Vérificateur d’allocation stratégique' : 'Strategic allocation verifier',
    fact:fr ? 'Calcule et vérifie des bornes de gains pour une allocation stratégique à somme nulle avec scénarios de gains cachés.'
      : 'Construct and independently check exact payoff bounds for zero-sum allocation with declared hidden payoff scenarios.',
    scope:fr ? 'Budgets entiers finis, enjeux additifs et allocations simultanées. Peut servir à vérifier des exemples d’entraînement.'
      : 'Finite integer budgets, additive lane weights and simultaneous allocation. Can check examples for a strategic reasoning model.',
    relevance:fr ? 'Ce solveur peut fournir un contrôle mathématique pour la tâche stratégique demandée.'
      : 'This solver can supply a mathematical check for the requested strategic task.',
    sourceURL:reviewedSource(release, 'publication/universal/game-theory/START.md'), sourceDate:release.content_updated_at,
    dateBasis:'asOf',
    artifact:{url:published + name, sha256:digest, version:'1.0.0',
      rights:fr ? 'Distribution publique pour la portée de recherche publiée.' : 'Public distribution for the published research scope.',
      instructions:'python -I -S verify.py EXAMPLE.json EXAMPLE-CERTIFICATE.json'}});
}

function atlasLead(entry, language, broad, release) {
  if (entry.state !== 'discovered') return undefined;
  const words = word[language];
  const reviewed = entry.editorial?.at(-1);
  const editorial = reviewed?.record;
  const primary = Object.values(entry.sources ?? {}).filter(Array.isArray).map(versions => versions.at(-1))
    .find(source => source?.decision === 'test' && sha.test(source.primary_sha256 ?? ''));
  if (editorial?.evidence === 'author-reported') {
    const content = editorial[language];
    const alternative = editorial.assessment?.[language]?.alternative;
    const scope = alternative ? words.reported + ' ' + words.alternative + ' · ' + alternative : words.reported;
    return item({id:entry.id, kind:'lead', title:content?.title, fact:content?.signal, scope,
      relevance:broad ? words.broadFit : words.referenceFit, sourceURL:primary?.url ?? editorial.sources?.[0]?.url,
      sourceDate:primary?.source_date ?? reviewed.observed_at ?? editorial.date,
      dateBasis:primary ? 'sourceDate' : 'reviewDate', primaryMetadataSha256:primary?.primary_sha256,
      recordURL:published + (language === 'fr' ? 'fr.html' : '') + '#' + entry.id});
  }
  if (!broad && primary) {
    return item({id:entry.id, kind:'lead', title:primary.title, fact:words.observedSource,
      scope:words.referenceScope, relevance:words.referenceFit, sourceURL:primary.url, sourceDate:primary.source_date,
      primaryMetadataSha256:primary.primary_sha256});
  }
  return undefined;
}

function recent(item, release) {
  const latest = date(release?.content_updated_at);
  if (!latest) return false;
  const elapsed = Date.parse(latest) - Date.parse(item.source.date);
  return elapsed >= 0 && elapsed <= 35 * 86400 * 1000;
}

/** Select from the released public evidence. The ambition and private work stay on this device. */
export function selectMissionContext({ambition, instruction, language = 'en', atlas, opportunity, memberValue, release} = {}) {
  language = language === 'fr' ? 'fr' : 'en';
  const query = typeof ambition === 'string' && ambition.trim()
    ? normalize(typeof instruction === 'string' && instruction.trim() ? instruction : ambition) : '';
  const items = [];
  if (query) {
    for (const key of Object.keys(tools)) if (fits(key, query)) items.push(toolItem(key, language, memberValue, release));
    if (fits('game', query)) items.push(gameItem(language, release));
    const broad = fits('discovery', query) && !focusedDiscovery.test(query);
    if (broad || fits('battery', query)) items.push(batterySourceStudy(language, release));
    const researchTerms = intent.test(query) ? terms(query) : null;
    if (opportunity?.schema === 'frontier/opportunity-capture-v1' && Array.isArray(opportunity.opportunities)) {
      const opportunities = opportunity.opportunities.filter(record)
        .filter(entry => broad || scopedOverlap(researchTerms, entry[language]?.title))
        .map(entry => opportunityItem(opportunity, entry, language, broad, release))
        .filter(entry => entry && (!broad || recent(entry, release)));
      items.push(...opportunities.slice(0, broad ? 1 : 2));
      if (broad) items.push(comparison(opportunity, language, release));
    }
    if (atlas?.schema === 'frontier-omega-alpha/atlas-ledger-v1' && Array.isArray(atlas.records)) {
      const leads = atlas.records.filter(record).map(entry => atlasLead(entry, language, broad, release))
        .filter(entry => entry && (broad ? recent(entry, release) : scopedOverlap(researchTerms, entry.title)))
        .sort((a, b) => Number(Boolean(b.source.primaryMetadataSha256)) - Number(Boolean(a.source.primaryMetadataSha256))
          || b.source.date.localeCompare(a.source.date) || a.id.localeCompare(b.id));
      items.push(...leads.slice(0, broad ? 1 : 2));
    }
  }
  const selected = items.filter(Boolean).slice(0, 3);
  return {schema:contextSchema, language, items:selected, gap:selected.length ? null : 'NO_APPLICABLE_PUBLIC_EVIDENCE'};
}

function selectedItems(context, ids) {
  return context.items.filter(entry => ids === undefined || ids.includes(entry.id));
}

export function missionContextLines(context, selectedIds) {
  const words = word[context.language];
  return selectedItems(context, selectedIds).map(entry => {
    const row = [words[entry.kind] + ' · ' + entry.title, entry.fact, words.limit + ' · ' + entry.scope,
      words[entry.source.dateBasis] + ' · ' + entry.source.date + ' · ' + entry.source.url];
    if (entry.recordURL) row.push(words.record + ' · ' + entry.recordURL);
    if (entry.recordSha256) row.push('SHA-256 ' + entry.recordSha256);
    if (entry.artifact) row.push(words.operation + ' · ' + entry.artifact.instructions + ' · ' + entry.artifact.url,
      'SHA-256 ' + entry.artifact.sha256);
    return row.join('\n');
  }).filter(line => encoder.encode(line).length <= 2048);
}

/** Export the member-reviewed text and selected public items. */
export function missionIntelligencePackage(brief, context, selectedIds) {
  return {schema:packageSchema, language:context.language, brief,
    context:structuredClone(selectedItems(context, selectedIds))};
}
