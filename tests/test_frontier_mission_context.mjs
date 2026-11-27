import assert from 'node:assert/strict';
import {test} from 'node:test';
import {missionContextLines, missionIntelligencePackage, missionIntent, selectMissionContext}
  from '../docs/research/frontier-omega-alpha/frontier-mission-context.mjs';

const gitRevision = '1'.repeat(40);
const source = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/' + gitRevision;
const release = {
  schema:'frontier-omega-alpha/atlas-release-v1', source_commit:gitRevision, content_updated_at:'2026-11-25T19:56:15Z',
  public_capability_sha256:{'endpoint-evidence-screen-1.0.0.zip':'b'.repeat(64), 'noaa-archive-point-1.0.0.zip':'a'.repeat(64)},
  universal_mission_sha256:{'frontier-game-theory-1.0.0.zip':'c'.repeat(64)},
};

function manifest(name) {
  const filename = name + '-1.0.0.zip';
  return {schema:'frontier/portable-capability-v1', id:name, version:'1.0.0', download:filename, source,
    rights:'Public use of the pinned package. Original sources retain their rights.', sha256:release.public_capability_sha256[filename]};
}

const memberValue = {
  schema:'frontier/public-member-value-v1', publication:'public-file', updated_at:release.content_updated_at,
  capabilities:{endpoint:manifest('endpoint-evidence-screen'), archive:manifest('noaa-archive-point')},
  briefs:[{tool:'endpoint', observed_at:'2026-11-23T16:36:07Z'}],
};
const prospective = {
  id:'test-radar', state:'OPERATING', action:'TEST', acceptance_receipt:'discovery/RADAR-CONTROL.json',
  evidence_stage:'PUBLIC_CATALOG_METADATA',
  first_party_date_utc:'2026-11-06', evidence:['https://nisar-docs.asf.alaska.edu/availability-overview/'],
  en:{title:'NISAR radar catalogue', finding:'Two separate catalogue shortlists were accepted.', next:'Catalogue planning only. Site measurements require separate validation.'},
  fr:{title:'Catalogue radar NISAR', finding:'Deux listes de données distinctes ont été acceptées.', next:'Planification à partir du catalogue. Les mesures exigent une validation distincte.'},
};
const opportunity = {
  schema:'frontier/opportunity-capture-v1',
  atlas_cutoff_utc:'2026-11-24T23:59:59Z', receipts:{'discovery/RADAR-CONTROL.json':'e'.repeat(64)},
  opportunities:[prospective, {...prospective, id:'unqualified-radar', state:'BLOCKED'},
    {...prospective, id:'outdated-radar', first_party_date_utc:'2026-09-01'}],
  comparison:{accepted:{conventional:[4,4], integrated:[4,4]},
    whole_work_wall_seconds:{conventional_disjoint_cycles:137.135, integrated_with_transition:265.154}},
};

const sourceUrl = 'https://arxiv.org/abs/2611.21152v2';
const record = {
  id:'shift-repofactory', state:'discovered',
  editorial:[{observed_at:'2026-11-23T20:03:08Z', record:{evidence:'author-reported', date:'2026-11-23',
    en:{title:'Training environment evolution', signal:'The authors compared evolved and fixed training environments.'},
    fr:{title:'Évolution des environnements d’apprentissage', signal:'Les auteurs comparent des environnements évolutifs et fixes.'},
    assessment:{en:{alternative:'Ordinary Harbor environment construction.'}, fr:{alternative:'Construction classique des environnements Harbor.'}},
    sources:[{url:'https://arxiv.org/abs/2611.21152'}]}}],
  sources:{'arxiv:2611.21152':[{decision:'test', url:sourceUrl, source_date:'2026-11-17', primary_sha256:'f'.repeat(64)}]},
};
const atlas = {schema:'frontier-omega-alpha/atlas-ledger-v1', records:[record,
  {...record, state:'falsified', id:'falsified-lead'}, {...record, id:'dated-lead',
    sources:{'arxiv:2611.21152':[{decision:'test', url:sourceUrl, source_date:'2026-09-17', primary_sha256:'f'.repeat(64)}]}}]};
const sources = {release, memberValue, opportunity, atlas};
const choose = (ambition, options = {}) => selectMissionContext({ambition, ...sources, ...options});

test('exact ambition uses public observed limits, conventional baseline, and a dated lead in either language', () => {
  for (const [ambition, language] of [['CAPTURE THE EXPONENTIAL','en'], ['Capter le progrès exponentiel','fr']]) {
    const context = choose(ambition, {language});
    assert.equal(context.gap, null);
    assert.deepEqual(context.items.map(item => item.id), ['test-radar','shift-repofactory','opportunity-comparison']);
    assert.equal(context.items[0].kind, 'result');
    assert.match(context.items[0].recordURL, /\/discovery\/RADAR-CONTROL\.json$/u);
    assert.equal(context.items[0].recordSha256, 'e'.repeat(64));
    assert.match(context.items[2].fact, /4\/4.*137[.,]1.*4\/4.*265[.,]2/u);
    assert.equal(context.items[1].kind, 'lead');
    assert.deepEqual(context.items[1].source, {date:'2026-11-17', dateBasis:'sourceDate', url:sourceUrl,
      primaryMetadataSha256:'f'.repeat(64)});
    assert.ok(missionContextLines(context).every(line => Buffer.byteLength(line) <= 2048));
  }
});

test('irrelevant ambitions, narrower follow-up and absent releases keep the ordinary brief short', () => {
  for (const ambition of ['', 'Find a good soup recipe', 'Capture the exponential decay with an oscilloscope',
    'Verify the latest commercial recipe for Windows and Chrome', 'Configure an LLM endpoint',
    'Screen a measured LLM endpoint test load using P90', 'Explore recent advances in structural ceramics',
    'CAPTURE THE EXPONENTIAL. Focus on riverbank restoration.']) {
    assert.equal(choose(ambition).gap, 'NO_APPLICABLE_PUBLIC_EVIDENCE', ambition);
  }
  assert.deepEqual(choose('CAPTURE THE EXPONENTIAL', {instruction:'Investigate supermarket food prices'}).items, []);
  assert.deepEqual(selectMissionContext({ambition:'CAPTURE THE EXPONENTIAL'}).items, []);
});

test('scope-qualified route carries runnable exact bytes, and refuses measured-scope mismatches', () => {
  const objective = 'Find the highest tested LLM endpoint load meeting first token P90 and throughput for measured rows';
  const context = choose(objective);
  const [item] = context.items;
  assert.equal(item.id, 'endpoint-evidence-screen');
  assert.equal(item.kind, 'tool');
  assert.match(item.artifact.url, /endpoint-evidence-screen-1\.0\.0\.zip$/u);
  assert.equal(item.artifact.sha256, 'b'.repeat(64));
  assert.equal(item.source.date, '2026-11-23');
  assert.match(missionContextLines(context)[0], /node endpoint-cli\.mjs sample\.json/u);
  assert.match(missionContextLines(context)[0], /SHA-256 b{64}/u);
  assert.deepEqual(choose(objective + ' without measurements').items, []);
  assert.deepEqual(choose(objective, {release:{...release, public_capability_sha256:{}}}).items, []);
  assert.equal(choose('Calculer la température NOAA GFS historique f024 sur la grille native', {language:'fr'}).items[0].id, 'noaa-archive-point');
  assert.deepEqual(choose('Calculer la température NOAA GFS historique f048 sur la grille native').items, []);
  assert.deepEqual(choose('Find the observed NOAA station temperature historical archive').items, []);
  assert.deepEqual(choose('Find the NOAA GFS forecast temperature in real time').items, []);
});

test('specialized game research gets the scoped solver reference and excludes incompatible game classes', () => {
  const [item] = choose('Build frontier AI LLM for Game Theory.').items;
  assert.equal(item.id, 'strategic-allocation');
  assert.match(item.scope, /Finite integer budgets/u);
  assert.equal(item.artifact.sha256, 'c'.repeat(64));
  assert.equal(choose('Former un modèle de théorie des jeux', {language:'fr'}).items[0].id, 'strategic-allocation');
  assert.deepEqual(choose('Build a solver for general sum game theory with arbitrary payoff').items, []);
});

test('sharing selection and package projection exclude unselected entries and private metadata', () => {
  const context = choose('CAPTURE THE EXPONENTIAL');
  assert.deepEqual(missionContextLines(context, []), []);
  const selected = missionContextLines(context, ['test-radar']);
  assert.equal(selected.length, 1);
  assert.match(selected[0], /\/discovery\/RADAR-CONTROL\.json/u);
  assert.doesNotMatch(selected[0], /Training environment/u);
  const output = missionIntelligencePackage('Reviewed text', context, ['shift-repofactory']);
  assert.deepEqual(output.context.map(item => item.id), ['shift-repofactory']);
  assert.deepEqual(Object.keys(output), ['schema','language','brief','context']);
  assert.equal(output.brief, 'Reviewed text');
  output.context[0].source.url = 'invalid';
  assert.equal(context.items[1].source.url, sourceUrl);
});

test('battery source review requires both released artifacts and omits inapplicable filing requests', () => {
  const manifest = {...release, universal_mission_sha256:{...release.universal_mission_sha256,
    'dpp-source-review.mjs':'d'.repeat(64), 'frontier-battery-source-example.json':'e'.repeat(64)}};
  const search = (ambition, source) => selectMissionContext({ambition, release:source}).items;
  const inputs = 'Check the battery passport weight against its source';
  assert.equal(search(inputs, release).length, 0);
  assert.equal(search(inputs, manifest)[0].artifact.sha256, 'e'.repeat(64));
  assert.equal(search('Submit a battery passport', manifest).length, 0);
  assert.equal(search('CAPTURE THE EXPONENTIAL', manifest).length, 0);
});


test('open-ended technology activation finds applicable research while grounded work does not force a domain', () => {
  for (const [ambition, language] of [
    ['Activate Frontier AI','en'], ['Build a frontier capability.','en'], ['Capture the exponential of AI progrees.','en'],
    ['Put cutting-edge intelligence to work','en'], ['Mobiliser l’IA de pointe','fr'], ['Concevoir une capacité de pointe','fr'],
  ]) {
    const found = choose(ambition,{language});
    assert.ok(found.items.some(item => item.id === 'test-radar'), ambition);
    assert.ok(!found.items.some(item => item.id === 'battery-source-review'), ambition);
  }
  for (const ambition of ['Activate the Frontier mailbox', 'Find the exponential function',
    'Find exponential decay of a sample', 'Build frontier intelligence to calibrate NIRSpec wavelength',
    'Vérifier les précipitations mesurées et calculer le cumul quotidien']) {
    assert.deepEqual(choose(ambition).items, [], ambition);
  }
});

test('frontier exploration finds dated evidence across unfamiliar wording and both languages', () => {
  for (const [ambition, language] of [
    ['Surfing the Frontier of AI', 'en'], ['Surfer à la frontière de l’IA', 'fr'],
    ['Show me which doors just opened in machine intelligence', 'en'],
    ['Que puis-je accomplir aujourd’hui grâce aux percées de l’intelligence artificielle ?', 'fr'],
  ]) {
    const context = choose(ambition, {language, atlas:{...atlas, records:[...atlas.records,
      {...record, id:'recently-mentioned-without-source-date', sources:{}}]}});
    assert.equal(missionIntent(ambition), 'explore', ambition);
    assert.equal(context.items[0].id, 'shift-repofactory', ambition);
    assert.ok(!context.items.some(item => item.id === 'recently-mentioned-without-source-date'), ambition);
  }
});

test('narrow goals and routine work keep broad acquisition out of the mission', () => {
  for (const ambition of ['Translate this article about frontier AI into Spanish', 'Translate this sentence into French',
    'Traduis cet article sur l’IA de pointe en espagnol', 'Translate this scanned document into Spanish', 'Integrate e to the 2x']) {
    assert.equal(missionIntent(ambition), 'ordinary', ambition);
    assert.deepEqual(choose(ambition).items, [], ambition);
  }
  for (const ambition of ['Build a local summarizer with the newest LLM',
    'Créer un outil de suivi des commandes avec l’IA de pointe',
    'Explore recent advances in artificial intelligence for coral restoration',
    'Prepare a reproducible local workflow for extracting text and tables from scanned documents without sharing them',
    'Préparer un processus local pour extraire le texte et les tableaux de documents numérisés',
    'Set up a local coding assistant']) {
    assert.equal(missionIntent(ambition), 'focused', ambition);
    assert.deepEqual(choose(ambition).items, [], ambition);
  }
  const ambition = 'Construire un LLM de pointe pour la théorie des jeux';
  assert.equal(missionIntent(ambition), 'focused');
  assert.deepEqual(choose(ambition, {language:'fr'}).items.map(item => item.id), ['strategic-allocation']);
  assert.equal(missionIntent('Activate Frontier AI', 'Translate this sentence into French'), 'ordinary');
});

test('focused evidence can match a shared mechanism when the member uses different terms', () => {
  for (const [ambition, language] of [['Compare learning environments for tool-using agents', 'en'],
    ['Comparer les bancs d’entraînement pour les agents', 'fr']]) {
    const context = choose(ambition, {language});
    assert.equal(missionIntent(ambition), 'focused', ambition);
    assert.deepEqual(context.items.map(item => item.id), ['shift-repofactory', 'dated-lead'], ambition);
    assert.ok(context.items.every(item => item.kind === 'lead'), ambition);
  }
});
