import {downloadJSON} from './frontier-goals.mjs';
import {browserModelAvailability, runBrowserStarter} from './frontier-browser-model.mjs';
import {setupExecution} from './frontier-execution.mjs';
import {
  createMission, reviseMission, prepareMission, beginMission, recordMission, interruptMission,
  cancelMission, continueMission, exportMission, importMission, missionPacket, bindMissionRequest,
  addMissionInstruction, checkMissionDocuments, setMissionDocuments, maxDocuments, maxDocumentBytes,
  addMissionArtifacts, removeMissionArtifact,
} from './frontier-mission.mjs';
import {
  createMissionRequest, createMissionPrompt, runLocalMission, validateLocalMissionConfig,
} from './frontier-mission-router.mjs';
import {createAssistedBrief, maximumReturnedBytes, readAssistedReply, renderAssistedWork, workPreview} from './frontier-assisted-work.mjs';
import {inspectReturnedWork, readMissionArtifact, importMissionArtifacts, missionArtifactBytes, maximumArtifacts, maximumArtifactBytes} from './frontier-artifact-exchange.mjs';
import {evaluateMissionFiles} from './frontier-native-work.mjs';
import {selectMissionContext, missionContextLines, missionIntelligencePackage, missionWorkPlan} from './frontier-mission-context.mjs';
import {reviewBatterySources, sourceReviewSchema} from './dpp-source-review.mjs';

const messages = {
  en: {
    ready: 'Mission opened on this device.', waiting: 'Your brief is ready.',
    running: 'Waiting for your local model…', review: 'Work returned for your review.',
    paused: 'Mission paused. Its ambition and completed work are still here.', canceled: 'Mission canceled.',
    choose: 'Choose intelligence to start work on this ambition. You can also use a qualified capability or continue with an assistant.',
    assisted: 'Copy the brief into ChatGPT or another AI you use, then bring its answer back here.',
    localNext: 'Review the local result and its assumptions before using it.',
    error: 'The local model did not return a usable response. Check the running service, model name and connection, or continue with an assisted mission.',
    config: 'Local settings saved for this tab. The first mission request will check the connection.', invalidConfig: 'Enter the exact model name and choose a supported runtime.',
    invalid: 'This structured response does not match the prepared mission or is incomplete. You can keep its content here as unverified work.',
    plainInvalid: 'Paste a response or choose a readable UTF-8 text file of up to 32 KiB.',
    workReview: 'Review the work, then continue from the next useful calculation, source check or test.',
    originalResponse: 'Original assistant response', fileDownload: 'Download original text',
    prepareFirst: 'Enter your ambition. Then you can review a brief for ChatGPT.',
    cancelSetupFailed: 'The companion could not confirm cancellation. Reconnect and cancel the pending approval before replacing this mission.',
    browserSource: 'Browser model draft', browserFirst: 'Enter an ambition to try the browser model.',
    browserStarting: 'Preparing the browser’s model…', browserDownloading: value => `Downloading the browser’s model · ${value}`,
    browserRunning: 'The browser’s model is working on your ambition…', browserCanceled: 'The browser model was canceled. Your ambition is still here.',
    browserUnavailable: 'The browser could not complete this request. Try again or continue with another intelligence option.',
    browserUnsupported: 'This browser has no supported on-device model available here.',
    browserContext: 'This mission exceeds the browser model’s context. Choose a companion model or review an assisted brief.',
    browserUnverified: 'This browser did not pass the on-device model check. Your ambition is ready for another intelligence option.',
    browserWait: 'Finish or cancel the current run and provider setup before starting the browser model.',
    pausedNext: 'Continue when you have the right intelligence or the missing information.',
    canceledNext: 'Open a new mission or resume this one.',
    invalidMission: 'Enter an ambition of up to 24 KiB. Use text you are authorized to process.',
    saved: 'Mission downloaded. It contains your ambition and work.',
    reopened: 'Mission restored. Review its current status before continuing.',
    fileInvalid: 'This file is unreadable, changed or outside the mission format.',
    copy: 'Reviewed brief copied.', select: 'The reviewed brief is selected for copying.',
    copyEarlier: 'An earlier draft was copied. Copy the updated brief before sharing.',
    localSource: 'Local model result', manualSource: 'Assisted result', restoredSource: 'Restored work record', unpublished: 'Verification pending',
    publicReport: 'Read the completed study', publicArtifact: 'Download the verified research tool',
    contextRun: 'Current mission run reference', contextAtlas: 'Public Atlas lead with unverified applicability',
    contextObjective: 'Previous unverified objective', contextAction: 'Previous unverified next action',
    contextWork: 'Previous work to review', evidencePlan:'First useful operation',
    priorOriginal:'Original returned material for this mission', priorFiles:'Files held in this mission',
    contextInstruction: 'Member’s latest instruction',
    nextInstruction: 'Choose how to continue with this instruction.',
    invalidInstruction: 'Enter an instruction of up to 2 KiB.',
    fileInput: 'Use up to eight nonempty UTF-8 text files. The total limit is 96 KiB.',
    localFiles: 'Use these files with your private companion, or remove them to use another intelligence option.',
    fileReady: 'Source files ready. Confirm below to share them with the private companion.',
    fileChanged: 'Continue the mission to use your updated sources.',
    restoreFiles: 'The companion holds these source files for this mission.',
    continueBusy: 'The current operation is still being stopped. Try again after it settles.',
    evidenceGap: 'No public evidence matched this mission’s scope. You can use the brief directly.',
    evidenceUnavailable: 'Public evidence is temporarily unavailable. You can use the brief directly.',
    evidenceHeading: 'Selected public evidence and tools to review',
    openSource: 'Open source',
    openTool: 'Open tool',
    deliverablesMissing: names => `Files still needed · ${names.join(', ')}. Download them from your assistant and add them here.`,
    deliverablesRetained: count => `${count} file${count === 1 ? '' : 's'} retained for review.`,
    deliverablesSnippet: 'The reply contains a code example. Add the actual source file for review or an authorized test.',
    deliverablesReady: 'Add the actual files your assistant produced, or bring them back later.',
    deliverablesInvalid: 'Use supported files or a simple ZIP of supported files. The original and unpacked contents must fit within 256 KiB.',
    archiveInspected:'Archive inspected · exact original retained',
    downloadExact:'Download exact file', nextFromReply:'Proposed by your assistant',
    auditDone:'Verified calculation', auditScope:'FRONTIER Ω performed this calculation locally on the retained input. Its proof does not validate the source’s real-world claims.',
    auditBoundary: (count, total, maxima) => `Recomputed all ${total} shared scores. ${count} change level between maxima ${maxima.join(' and ')}.`,
    auditConcentration: (n, missing, value, total, share) => `Checked ${n} measured days and ${missing} missing days. The highest complete window totals ${value ?? 'unavailable'}${share === null ? '.' : `, ${share}% of the measured total of ${total}.`}`,
    auditChanges: (results,format) => results.map(r=>`${r.series} · ${r.publishedDates.length} quoted days · ${r.unquotedDates.length} without a quote · largest absolute change ${format(r.largestAbsoluteChange,r.series) ?? 'unavailable'}`).join(' · '),
    auditWithheld:'Calculation withheld. Check the format, completeness and source identity shown in the receipt.',
    auditNeedSource:'Add the exact source file named by the calculation request.',
    auditNext:'Download the calculation and source record to reuse or independently check the result.',
    supplySource:'Add the data behind the table or the actual result file to make it possible to check this claim.',
    duplicateReply: 'That exact reply is already in this mission. Bring back a new finding, test or file.',
    useFile: 'Stage for private companion review',
    artifactUnverified: 'Imported file · verification pending',
    removeFile: 'Remove result file',
    fileRemoved: 'Result file removed from this mission.',
    askFiles: 'Ask the assistant for the actual files',
    continueAssistant: 'Continue with ChatGPT',
    reviewSourceClaims: 'Check supplied battery measurements',
    claimReviewScope: 'This check compares quantities and scope labels in the supplied excerpts. It leaves source interpretation and regulatory acceptance for review.',
    claimReviewInvalid: 'This evidence package could not be checked. Review its case, source and observation fields.',
    downloadClaimReview: 'Download check receipt',
    retainClaimReview: 'Keep check receipt with mission',
    claimDecisions: {supported:'Supported by supplied observations',contradicted:'Contradicted',insufficient:'Insufficient',conflicting:'Conflicting'},
    routes: {direct:'Direct answer',capability:'Existing capability',composition:'Capability composition',adaptation:'Adaptation',
      research:'Frontier research',invention:'New invention',continuing:'Continuing investigation',clarification:'Clarification or abstention'},
  },
  fr: {
    ready: 'Mission ouverte sur cet appareil.', waiting: 'Votre résumé est prêt.',
    running: 'En attente de votre modèle local…', review: 'Travail reçu pour examen.',
    paused: 'Mission en pause. Son ambition et le travail accompli sont conservés.', canceled: 'Mission annulée.',
    choose: 'Choisissez une intelligence pour commencer le travail. Vous pouvez aussi utiliser une capacité qualifiée ou poursuivre avec un assistant.',
    assisted: 'Copiez le résumé dans ChatGPT ou une autre IA de votre choix, puis rapportez la réponse ici.',
    localNext: 'Examinez le résultat local et ses hypothèses avant de l’utiliser.',
    error: 'Le modèle local n’a pas fourni de réponse exploitable. Vérifiez le service, le nom du modèle et la connexion, ou poursuivez avec une mission assistée.',
    config: 'Paramètres locaux conservés pour cet onglet. La première requête vérifiera la connexion.', invalidConfig: 'Indiquez le nom exact du modèle et choisissez un environnement pris en charge.',
    invalid: 'Cette réponse structurée ne correspond pas à la mission préparée ou elle est incomplète. Vous pouvez en conserver le contenu ici comme travail à vérifier.',
    plainInvalid: 'Collez une réponse ou choisissez un fichier texte UTF-8 lisible d’au plus 32 Kio.',
    workReview: 'Examinez le travail, puis poursuivez avec le prochain calcul, la prochaine vérification de source ou le prochain essai utile.',
    originalResponse: 'Réponse originale de l’assistant', fileDownload: 'Télécharger le texte original',
    prepareFirst: 'Saisissez votre ambition, puis relisez la consigne à préparer pour ChatGPT.',
    cancelSetupFailed: 'Le compagnon n’a pas pu confirmer l’annulation. Reconnectez-vous et annulez l’approbation en attente avant de remplacer la mission.',
    browserSource: 'Ébauche du modèle du navigateur', browserFirst: 'Saisissez une ambition pour essayer le modèle du navigateur.',
    browserStarting: 'Préparation du modèle du navigateur…', browserDownloading: value => `Téléchargement du modèle du navigateur · ${value}`,
    browserRunning: 'Le modèle du navigateur travaille sur votre ambition…', browserCanceled: 'Le modèle du navigateur a été arrêté. Votre ambition est toujours ici.',
    browserUnavailable: 'Le navigateur n’a pas pu terminer cette demande. Réessayez ou choisissez une autre intelligence.',
    browserUnsupported: 'Ce navigateur ne dispose pas d’un modèle intégré pris en charge ici.',
    browserContext: 'Cette mission dépasse le contexte du modèle intégré. Choisissez un modèle du compagnon ou préparez une mission assistée.',
    browserUnverified: 'Le navigateur n’a pas réussi le test du modèle local. Votre ambition est prête pour une autre intelligence.',
    browserWait: 'Terminez ou annulez l’exécution et la configuration du fournisseur avant de lancer le modèle du navigateur.',
    pausedNext: 'Poursuivez lorsque l’intelligence ou les renseignements nécessaires sont disponibles.',
    canceledNext: 'Ouvrez une nouvelle mission ou reprenez celle-ci.',
    invalidMission: 'Saisissez une ambition d’au plus 24 Kio. Utilisez du texte que vous êtes autorisé à traiter.',
    saved: 'Mission téléchargée. Le fichier contient votre ambition et votre travail.',
    reopened: 'Mission rétablie. Examinez son état avant de poursuivre.',
    fileInvalid: 'Ce fichier est illisible, a été modifié ou ne respecte pas le format de mission.',
    copy: 'Résumé relu copié.', select: 'Le résumé relu est sélectionné pour la copie.',
    copyEarlier: 'Un résumé antérieur a été copié. Copiez le résumé actuel avant de le partager.',
    localSource: 'Résultat du modèle local', manualSource: 'Résultat assisté', restoredSource: 'Travail rétabli', unpublished: 'Vérification à venir',
    publicReport: 'Lire l’étude terminée', publicArtifact: 'Télécharger l’outil de recherche vérifié',
    contextRun: 'Identifiant de l’exécution en cours', contextAtlas: 'Piste publique de l’Atlas dont l’applicabilité reste à vérifier',
    contextObjective: 'Objectif précédent à vérifier', contextAction: 'Prochaine action précédente à vérifier',
    contextWork: 'Travail précédent à examiner', evidencePlan:'Première opération utile',
    priorOriginal:'Travail original rapporté dans cette mission', priorFiles:'Fichiers conservés dans cette mission',
    contextInstruction: 'Dernière consigne du membre',
    nextInstruction: 'Choisissez comment poursuivre avec cette consigne.',
    invalidInstruction: 'Saisissez une consigne d’au plus 2 Kio.',
    fileInput: 'Utilisez au plus huit fichiers texte UTF-8 non vides (96 Kio au total).',
    localFiles: 'Utilisez ces fichiers avec votre compagnon privé ou retirez-les pour choisir une autre intelligence.',
    fileReady: 'Les fichiers sources sont prêts. Confirmez leur transmission au compagnon privé ci-dessous.',
    fileChanged: 'Poursuivez la mission pour utiliser les sources mises à jour.',
    restoreFiles: 'Le compagnon conserve ces fichiers sources pour la mission.',
    continueBusy: 'L’opération en cours s’arrête. Réessayez une fois l’arrêt confirmé.',
    evidenceGap: 'Aucune donnée publique trouvée ne correspond à la portée de la mission. Vous pouvez utiliser le résumé directement.',
    evidenceUnavailable: 'Les données probantes publiques sont temporairement indisponibles. Vous pouvez utiliser le résumé directement.',
    evidenceHeading: 'Données publiques et outils sélectionnés à examiner',
    openSource: 'Ouvrir la source',
    openTool: 'Ouvrir l’outil',
    deliverablesMissing: names => `Fichiers à obtenir · ${names.join(', ')}. Téléchargez-les dans votre assistant, puis ajoutez-les ici.`,
    deliverablesRetained: count => `${count} fichier${count === 1 ? '' : 's'} à examiner.`,
    deliverablesSnippet: 'La réponse contient un exemple de code. Ajoutez le fichier source pour l’examiner ou réaliser un essai autorisé.',
    deliverablesReady: 'Ajoutez les fichiers produits par votre assistant maintenant ou plus tard.',
    deliverablesInvalid: 'Utilisez des fichiers pris en charge ou une archive ZIP simple. L’original et son contenu extrait doivent tenir dans 256 Kio.',
    archiveInspected:'Archive examinée · original exact conservé',
    downloadExact:'Télécharger le fichier exact', nextFromReply:'Proposition de votre assistant',
    auditDone:'Calcul vérifié', auditScope:'FRONTIER Ω a effectué ce calcul localement à partir des données conservées. La preuve ne valide pas les affirmations de la source sur le monde réel.',
    auditBoundary: (count, total, maxima) => `Les ${total} scores communs ont été recalculés. ${count} changent de niveau entre les maximums ${maxima.join(' et ')}.`,
    auditConcentration: (n, missing, value, total, share) => `${n} jours mesurés et ${missing} jours manquants. Le cumul maximal sur une période complète est de ${value ?? 'non disponible'}${share === null ? '.' : `, soit ${share} % du cumul mesuré de ${total}.`}`,
    auditChanges: (results,format) => results.map(r=>`${r.series} · ${r.publishedDates.length} jours avec taux · ${r.unquotedDates.length} sans taux · variation maximale en valeur absolue ${format(r.largestAbsoluteChange,r.series) ?? 'non disponible'}`).join(' · '),
    auditWithheld:'Calcul suspendu. Vérifiez le format, l’exhaustivité et l’identité de la source indiqués dans le relevé.',
    auditNeedSource:'Ajoutez le fichier source exact indiqué dans la demande de calcul.',
    auditNext:'Téléchargez le calcul et les sources pour réutiliser le résultat ou le vérifier indépendamment.',
    supplySource:'Ajoutez les données du tableau ou le fichier de résultats pour pouvoir vérifier cette affirmation.',
    duplicateReply: 'Cette réponse exacte figure déjà dans la mission. Rapportez un nouveau résultat, un essai ou un fichier.',
    useFile: 'Préparer l’examen dans le compagnon privé',
    artifactUnverified: 'Fichier ajouté · vérification à venir',
    removeFile: 'Retirer le fichier livré',
    fileRemoved: 'Fichier livré retiré de la mission.',
    askFiles: 'Demander les fichiers à l’assistant',
    continueAssistant: 'Poursuivre avec ChatGPT',
    reviewSourceClaims: 'Vérifier les mesures de batterie fournies',
    claimReviewScope: 'Ce contrôle compare les valeurs et les portées des extraits fournis. L’interprétation des sources et l’acceptation réglementaire restent à vérifier.',
    claimReviewInvalid: 'Ce dossier ne peut pas être vérifié. Examinez les cas, les sources et les observations.',
    downloadClaimReview: 'Télécharger le relevé de vérification',
    retainClaimReview: 'Conserver le relevé dans la mission',
    claimDecisions: {supported:'Sources fournies à l’appui',contradicted:'Contredit',insufficient:'Insuffisant',conflicting:'Contradictoire'},
    routes: {direct:'Réponse directe',capability:'Capacité existante',composition:'Composition de capacités',adaptation:'Adaptation',
      research:'Recherche de pointe',invention:'Nouvelle invention',continuing:'Enquête à poursuivre',clarification:'Précision ou abstention'},
  },
};

const routes = [
  ['endpoint-screen','#mv-endpoint-run',['Endpoint Evidence Screen','Évaluation Endpoint'],
    ['Select a tested load from authorized same-scope measurements of P90 first-token latency and per-user throughput. Missing results, untested loads and different workload scopes require their own evidence.',
      'Choisir une charge testée selon la latence P90 du premier jeton et le débit par utilisateur, à partir de mesures autorisées et comparables. Les charges non testées et les autres scénarios exigent leurs propres mesures.']],
  ['noaa-archive','#tool-archive',['NOAA Archive Point','Point d’archive NOAA'],
    ['NOAA GFS historical f024 forecast only, with exactly 24 hours from initialization to valid time. It returns 2 m air temperature at an exact native 0.25° grid cell in kelvin. The package runs with Linux, Python 3.12, curl and OpenSSL.',
      'Prévision historique NOAA GFS f024 seulement, avec exactement 24 heures entre l’initialisation et l’heure de validité. Température de l’air à 2 m en kelvins pour une cellule exacte de la grille de 0,25°. Linux, Python 3.12, curl et OpenSSL requis.']],
  ['harness','#foundry-mission',['HARNESS capability construction','Construction d’une capacité HARNESS'],
    ['Define scalar inputs, a deterministic rule and independently held acceptance cases.','Définir des entrées scalaires, une règle déterministe et des cas d’acceptation gardés séparément.']],
  ['scientific-evidence','#foundry-factory-results',['Scientific Truth Engine','Moteur de validation scientifique'],
    ['Inspect qualified source-lineage, scope and historical measurement checks.','Examiner les contrôles qualifiés de provenance, de portée et de mesures historiques.']],
  ['opportunity-capture','#opportunity-capture',['Opportunity Capture','Repérage des possibilités'],
    ['Check verified technology availability and supported productive follow-up.','Vérifier la disponibilité documentée et les suites productives possibles.']],
  ['successor-study','#foundry-study',['Successor comparisons','Comparaison de capacités successeures'],
    ['Inspect independently compared portable capabilities and replay a supported study.','Examiner des capacités portables comparées indépendamment et reproduire une étude prise en charge.']],
];

const node = key => document.getElementById(key);
const text = (key, value) => { node(key).textContent = value ?? ''; };
const show = (key, visible) => { node(key).hidden = !visible; };
const encoder = new TextEncoder();
const browserModelId = 'browser-gemini-nano';

function downloadText(value, filename, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([value], {type}));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function publicRuns() {
  try {
    const entries = JSON.parse(node('mission-public-runs').content.textContent);
    return entries.filter(row => typeof row.ambition === 'string' && typeof row.en === 'string' && typeof row.fr === 'string'
      && /^frontier-[a-z0-9.-]+\.zip$/u.test(row.download)
      && /^https:\/\/github\.com\/MontrealAI\/AGI-Alpha-Invention-Flywheel-Lab\/blob\/[0-9a-f]{40}\/publication\/(universal|mission-executor)\/[a-zA-Z0-9/._-]+\.md$/u.test(row.report)
      && typeof row.capability?.id === 'string' && /^[a-z0-9][a-z0-9-]{1,63}$/u.test(row.capability.id)
      && [row.capability.en, row.capability.fr, row.capability.scopeEn, row.capability.scopeFr]
        .every(value => typeof value === 'string' && value.length > 0 && value.length <= 300));
  } catch { return []; }
}

function publicContext() {
  try { return JSON.parse(node('mission-public-context').content.textContent); }
  catch { return {}; }
}

export function setupMissionConsole(member, shell) {
  const language = document.documentElement.lang === 'fr' ? 'fr' : 'en';
  const words = messages[language];
  const i = language === 'fr' ? 1 : 0;
  const input = node('goal-text');
  const priorRuns = publicRuns();
  const registered = priorRuns.map(({capability, download}) => [capability.id, download,
    [capability.en, capability.fr], [capability.scopeEn, capability.scopeFr]]);
  const available = [...routes, ...registered];
  const capabilities = available.map(([id,, title, scope]) => ({id, title:title[i], scope:scope[i]}));
  const localRuns = new Set();
  const observedFileChecks = new Map();
  const evidenceSources = publicContext();
  let mission, request, connection, activeRequest, atlas, unmatchedWork, serial = 0;
  let entryDocuments, recoveredDocuments, fileSerial = 0, editingAmbition = false;
  let evidenceContext, selectedEvidence, assistedDraft;
  let artifactSerial = 0, nativeKey = '', nativeResults = [];
  let browserCheck = 0;
  const active = () => !member.hidden;
  const files = () => mission ? mission.documents ?? recoveredDocuments ?? [] : entryDocuments ?? [];
  const settings = node('mission-intelligence');

  function showSetup() {
    if (mission) {
      const slot = node('mission-inline-intelligence');
      if (settings.parentElement !== slot) slot.append(settings);
      settings.open = true;
      shell.show(node('frontier-mission-panel'), {remember:true,focus:false});
    } else {
      if (settings.parentElement !== node('intelligence-settings-slot')) node('intelligence-settings-slot').append(settings);
      settings.open = true;
      shell.show(settings, {remember:true});
    }
  }

  window.addEventListener('frontier:member-view', ({detail}) => {
    if (detail === 'my-intelligence' && settings.parentElement !== node('intelligence-settings-slot')) {
      node('intelligence-settings-slot').append(settings);
      settings.open = true;
    }
  });
  const execution = setupExecution(member, language, {
    currentAmbition: () => mission?.ambition,
    currentMission: () => ['canceled','running'].includes(mission?.status) ? undefined : mission,
    localFilesConsent: () => !files().length || node('mission-document-consent').checked,
    filesAttached: () => files().length > 0,
    updateSummary: () => renderHeadline(),
    onChooseRoute() {
      if (mission?.status !== 'waiting' || mission.run?.provider !== 'assisted') return;
      resetRequest();
      mission = continueMission(mission);
      render();
    },
    returnToMission: () => shell.show(node('frontier-mission-panel'), {remember:true}),
    showSetup,
    onOpen({ambition, original_ambition: originalAmbition = ambition, language: missionLanguage, instruction, documents}) {
      stopRequest();
      resetHandoff();
      mission = createMission(originalAmbition, {language:missionLanguage === 'fr' ? 'fr' : missionLanguage === 'en' ? 'en' : language});
      if (originalAmbition !== ambition) mission = reviseMission(mission, ambition);
      if (instruction) mission = addMissionInstruction(mission, instruction);
      recoveredDocuments = Array.isArray(documents) ? documents : undefined;
      entryDocuments = undefined;
      fileSerial++;
      node('mission-document-consent').checked = false;
      node('mission-follow-up').value = '';
      editingAmbition = false;
      atlas = undefined;
      input.value = ambition;
      input.dispatchEvent(new Event('input'));
      render();
      text('mission-document-status', recoveredDocuments?.length ? words.restoreFiles : '');
      shell.show(node('frontier-mission-panel'), {remember:true});
    },
  });

  function currentReport() {
    return mission?.reports.findLast(report => report.revision === mission.revision);
  }

  function resultFiles() {
    return (mission?.workFiles ?? []).filter(file => file.revision === mission.revision);
  }

  function workInspection(report) {
    const original = report?.artifacts?.find(file => file.kind === 'assisted-original' || file.kind === 'assisted-text');
    return inspectReturnedWork(original?.content ?? report?.work, resultFiles());
  }

  function nativeChecks() {
    const inputs = resultFiles();
    const key = JSON.stringify([mission?.id,mission?.revision,inputs.map(file=>[file.name,file.kind,file.sha256])]);
    if (key !== nativeKey) {
      nativeKey = key;
      nativeResults = evaluateMissionFiles(inputs);
    }
    return nativeResults;
  }

  function amount(value, unit) {
    return value === null ? null : [i ? value.replace('.', ',') : value,unit].filter(Boolean).join(' ');
  }

  function auditSummary(result) {
    if (result.disposition !== 'VERIFIED_CALCULATION') return result.reason === 'SOURCE_MISSING' ? words.auditNeedSource : words.auditWithheld;
    if (result.operation === 'decision-boundaries') return words.auditBoundary(result.differingScores,result.comparedScores,result.maxima);
    if (result.operation === 'concentration') {
      const {measuredDays,missingDays,windowTotal,total,percentageOfMeasuredTotal} = result.output;
      const unit = Object.values(result.units ?? {})[0];
      return words.auditConcentration(measuredDays,missingDays,amount(windowTotal,unit),amount(total,unit),amount(percentageOfMeasuredTotal));
    }
    return words.auditChanges(result.output,(value,series)=>amount(value,result.units?.[series]));
  }

  function renderNativeResults() {
    const results = mission ? nativeChecks() : [];
    show('mission-native-result', results.length > 0);
    const verified = results.some(result => result.disposition === 'VERIFIED_CALCULATION');
    text('mission-native-title', verified ? words.auditDone : words.auditWithheld);
    text('mission-native-scope', verified ? words.auditScope : '');
    node('mission-native-list').replaceChildren(...results.map(result => {
      const row = document.createElement('li');
      row.textContent = auditSummary(result);
      if (result.operation === 'decision-boundaries') {
        const scores = result.ranges.map(([start,end])=>start === end ? start : `${start}–${end}`);
        const detail = document.createElement('p');
        detail.textContent = scores.join(', ');
        row.append(detail);
      } else if (result.operation === 'concentration') {
        const detail = document.createElement('p');
        detail.textContent = result.output.maximumWindows.map(dates=>dates.join(' → ')).join(' · ');
        row.append(detail);
      } else if (result.operation === 'successive-changes') {
        const detail = document.createElement('p');
        detail.textContent = result.output.flatMap(series=>series.largestSteps.map(step=>`${series.series} · ${step.from} → ${step.to} · ${amount(step.amount,result.units?.[series.series])}`)).join(' | ');
        row.append(detail);
      }
      return row;
    }));
  }

  node('mission-native-download').addEventListener('click', () => {
    if (!active() || !mission || !nativeChecks().length) return;
    const inputs = resultFiles().map(({name,sha256,bytes}) => ({name,sha256,bytes}));
    downloadJSON({mission:mission.originalAmbition, inputs, calculations:nativeChecks()}, 'frontier-calculation-receipt.json');
  });

  function evidenceBundle(file) {
    if (!/\.json$/iu.test(file.name)) return null;
    const value = JSON.parse(file.content.replace(/^\ufeff/u, ''));
    return value?.schema === sourceReviewSchema ? value : null;
  }

  function claimReviewControls(file, container) {
    const bundle = evidenceBundle(file);
    if (!bundle) return;
    const key = `${mission.id}:${file.revision}:${file.sha256}`;
    const result = observedFileChecks.get(key);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'quiet';
    button.textContent = words.reviewSourceClaims;
    button.addEventListener('click', () => {
      if (!active()) return;
      try {
        const checked = reviewBatterySources(bundle);
        observedFileChecks.set(key, {...checked, inputSha256:file.sha256, evidenceScope:'supplied-observations'});
        text('mission-deliverable-feedback', words.claimReviewScope);
        render();
        const displayed = node('mission-deliverable-list').querySelector(`[data-file-claim-review="${file.sha256}"]`);
        if (displayed) { displayed.closest('details').open = true; displayed.focus(); }
      } catch { text('mission-deliverable-feedback', words.claimReviewInvalid); }
    });
    container.append(button);
    if (!result) return;
    const output = document.createElement('div');
    output.setAttribute('role','status');
    output.tabIndex = -1;
    output.dataset.fileClaimReview = file.sha256;
    const summary = document.createElement('ul');
    summary.replaceChildren(...result.results.map(item => {
      const row = document.createElement('li');
      row.textContent = [item.id, words.claimDecisions[item.decision], item.evidence.join(', ')].filter(Boolean).join(' · ');
      return row;
    }));
    const download = document.createElement('button');
    download.type = 'button';
    download.className = 'quiet';
    download.textContent = words.downloadClaimReview;
    download.addEventListener('click', () => {
      if (active()) downloadJSON(result, 'frontier-source-review.json');
    });
    const retain = document.createElement('button');
    retain.type = 'button';
    retain.className = 'quiet';
    retain.textContent = words.retainClaimReview;
    retain.addEventListener('click', async () => {
      if (!active() || !mission || ['running','canceled'].includes(mission.status)) return;
      const {id,revision} = mission;
      const name = `source-review-${file.sha256.slice(0,12)}.json`;
      try {
        const receipt = await readMissionArtifact(new File([JSON.stringify(result, null, 2) + '\n'], name), revision);
        if (!active() || mission?.id !== id || mission.revision !== revision || ['running','canceled'].includes(mission.status)) return;
        mission = addMissionArtifacts(mission, [receipt]);
        render();
        text('mission-deliverable-feedback', words.deliverablesRetained(mission.workFiles.length));
      } catch {
        if (active() && mission?.id === id && mission.revision === revision) {
          text('mission-deliverable-feedback', words.deliverablesInvalid);
        }
      }
    });
    output.append(summary, download, retain);
    container.append(output);
  }

  function stageArtifact(file) {
    if (file.kind === 'archive') return;
    const name = /\.(txt|md|csv|tsv|json)$/iu.test(file.name) ? file.name : file.name + '.txt';
    try {
      const existing = files().find(source => source.name === name);
      if (existing && existing.text !== file.content) throw Error('ARTIFACT_NAME');
      const sources = existing ? files() : [...files(), {name, text:file.content}];
      changeFiles(sources);
      node('mission-files').open = true;
      node('mission-document-consent').focus();
    } catch { text('mission-deliverable-feedback', words.fileInput); }
  }

  function renderDeliverables(report) {
    const returned = mission?.workFiles ?? [];
    const inspection = workInspection(report);
    const panel = node('mission-deliverables');
    show('mission-deliverables', Boolean(mission));
    if (!mission) panel.open = false;
    const message = inspection.missing.length ? words.deliverablesMissing(inspection.missing)
      : returned.length ? words.deliverablesRetained(returned.length)
      : inspection.sourceSnippet ? words.deliverablesSnippet : words.deliverablesReady;
    text('mission-deliverable-status', mission ? message : '');
    node('mission-deliverable-import').disabled = !mission || ['running','canceled'].includes(mission.status);
    node('mission-deliverable-list').replaceChildren(...returned.map(file => {
      const row = document.createElement('li');
      const record = document.createElement('details');
      const caption = document.createElement('summary');
      caption.textContent = file.name;
      const status = document.createElement('p');
      status.textContent = `${file.kind === 'archive' ? words.archiveInspected : words.artifactUnverified} · ${file.bytes} B`;
      const preview = document.createElement('pre');
      preview.hidden = file.kind === 'archive';
      if (!preview.hidden) preview.textContent = workPreview(file.content);
      const hash = document.createElement('p');
      hash.textContent = 'SHA-256 ' + file.sha256;
      const download = document.createElement('button');
      download.type = 'button';
      download.className = 'quiet';
      download.textContent = words.downloadExact;
      download.addEventListener('click', () => {
        if (active()) downloadText(missionArtifactBytes(file), file.name, 'application/octet-stream');
      });
      record.append(caption, status, preview, hash, download);
      claimReviewControls(file, record);
      if (file.kind !== 'archive' && file.bytes <= maxDocumentBytes && !['running','canceled'].includes(mission.status)) {
        const stage = document.createElement('button');
        stage.type = 'button';
        stage.className = 'quiet';
        stage.textContent = words.useFile;
        stage.addEventListener('click', () => { if (active()) stageArtifact(file); });
        record.append(stage);
      }
      if (mission.status !== 'running') {
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'quiet';
        remove.textContent = words.removeFile;
        remove.addEventListener('click', () => {
          if (!active() || !mission || mission.status === 'running') return;
          mission = removeMissionArtifact(mission, file);
          observedFileChecks.delete(`${mission.id}:${file.revision}:${file.sha256}`);
          render();
          text('mission-deliverable-feedback', words.fileRemoved);
          node('mission-deliverables').querySelector('summary').focus();
        });
        record.append(remove);
      }
      row.append(record);
      return row;
    }));
    return inspection;
  }

  node('mission-deliverable-import').addEventListener('change', async event => {
    const selected = Array.from(event.target.files);
    event.target.value = '';
    if (!active() || !mission || !selected.length || ['running','canceled'].includes(mission.status)) return;
    const ticket = ++artifactSerial;
    const {id, revision} = mission;
    const sameRevision = () => active() && ticket === artifactSerial && mission?.id === id && mission.revision === revision
      && !['running','canceled'].includes(mission.status);
    try {
      if (selected.length > maximumArtifacts || selected.reduce((sum, file) => sum + file.size, 0) > maximumArtifactBytes) throw Error('ARTIFACT_LIMIT');
      const imported = (await Promise.all(selected.map(file => importMissionArtifacts(file, revision)))).flat();
      if (!sameRevision()) return;
      mission = addMissionArtifacts(mission, imported);
      node('mission-deliverables').open = true;
      text('mission-deliverable-feedback', '');
      render();
      if (nativeChecks().length) {
        node('mission-native-result').focus({preventScroll:true});
        node('mission-native-result').scrollIntoView({block:'nearest'});
      }
    } catch { if (sameRevision()) text('mission-deliverable-feedback', words.deliverablesInvalid); }
  });

  function renderFiles() {
    const documents = files();
    const reports = documents.map(source => {
      const row = document.createElement('li');
      row.textContent = source.name;
      return row;
    });
    node('mission-document-list').replaceChildren(...reports);
    show('mission-document-scope', documents.length > 0);
    show('mission-documents-remove', documents.length > 0);
    const report = currentReport();
    show('mission-use-returned', Boolean(report?.provider === 'assisted' && report.work && !documents.length));
  }

  function changeFiles(documents) {
    const next = mission ? setMissionDocuments(mission, documents) : undefined;
    afterPendingSetup(() => {
      if (next && ['running','waiting'].includes(next.status)) {
        stopRequest();
        resetHandoff();
        mission = continueMission(interruptMission(next, next.run.id, 'SOURCE_CHANGED'));
      } else if (next) mission = next;
      else entryDocuments = documents;
      recoveredDocuments = undefined;
      node('mission-document-consent').checked = false;
      render();
      text('mission-document-status', documents.length ? words.fileReady : mission ? words.fileChanged : '');
    });
  }

  node('mission-documents').addEventListener('change', async event => {
    const selected = Array.from(event.target.files);
    event.target.value = '';
    if (!active() || !selected.length) return;
    const ticket = ++fileSerial;
    const id = mission?.id;
    try {
      if (selected.length > maxDocuments || selected.reduce((total, file) => total + file.size, 0) > maxDocumentBytes
        || selected.some(file => !/\.(txt|md|csv|tsv|json)$/iu.test(file.name))) throw new Error('MISSION_DOCUMENTS');
      const decoder = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true});
      const documents = await Promise.all(selected.map(async file => ({name:file.name, text:decoder.decode(await file.arrayBuffer())})));
      if (ticket !== fileSerial || !active() || mission?.id !== id) return;
      // Apply the same validation to files picked before and after activating a mission.
      checkMissionDocuments(documents);
      changeFiles(documents);
    } catch {
      if (ticket === fileSerial && active()) text('mission-document-status', words.fileInput);
    }
  });

  node('mission-documents-remove').addEventListener('click', () => {
    if (!active()) return;
    fileSerial++;
    changeFiles([]);
    node('mission-documents').focus();
  });

  node('mission-use-returned').addEventListener('click', () => {
    const report = currentReport();
    if (!active() || report?.provider !== 'assisted' || !report.work || files().length) return;
    try {
      changeFiles([{name:'returned-assisted-work.md',text:report.work}]);
      node('mission-files').open = true;
      node('mission-document-consent').focus();
    } catch { text('mission-document-status', words.fileInput); }
  });

  function activateWork({preferred, continuation = false} = {}) {
    if (!mission || mission.status === 'running' || mission.status === 'canceled') return;
    if (files().length && !node('mission-document-consent').checked) {
      node('mission-files').open = true;
      showSetup();
      render(words.localFiles);
      return;
    }
    if (!files().length && preferred === 'assisted') { void prepareAssistance(); return; }
    if (!files().length && preferred === browserModelId) { node('intelligence-browser-start').click(); return; }
    if (!files().length && connection && !execution.hasPreferredRoute()) { void runConfiguredModel(); return; }
    if (!files().length && !execution.hasPreferredRoute()) { void prepareAssistance({focus:false}); return; }
    if (!execution.hasPreferredRoute()) showSetup();
    void execution.activate(mission.ambition, {continuation});
  }

  function resetHandoff() {
    artifactSerial++;
    request = undefined;
    evidenceContext = selectedEvidence = assistedDraft = undefined;
    for (const id of ['mission-prompt','mission-reply','mission-import-artifact']) node(id).value = '';
    node('mission-technical').checked = false;
    node('mission-include-history').checked = false;
    text('mission-history-preview', '');
    text('mission-copy-status', '');
    clearCopyFallback();
    resetAssistedImport();
    node('mission-handoff').open = false;
    show('mission-handoff', false);
    show('mission-evidence-context', false);
    node('mission-context-items').replaceChildren();
    updateHandoffControls();
  }

  function updateHandoffControls() {
    const permitted = Boolean(request && active());
    for (const id of ['mission-copy','mission-prompt-download']) node(id).disabled = !permitted;
    show('mission-assistant', permitted);
    show('mission-codex', permitted);
  }

  function renderHeadline(message) {
    if (!mission) return;
    const state = mission.status;
    const report = currentReport();
    const native = state === 'ready' ? execution.summary() : null;
    const observed = localRuns.has(report?.runId);
    const browserReport = observed && report.model === browserModelId;
    const source = report?.provider === 'assisted' ? words.manualSource
      : browserReport ? words.browserSource : observed ? words.localSource : words.restoredSource;
    const labels = [source, observed && !browserReport ? report.model : null, words.unpublished].filter(Boolean);
    const running = state === 'running' && mission.run.model === browserModelId;
    const plan = state === 'waiting' && evidenceContext?.items.length ? missionWorkPlan(evidenceContext, [...selectedEvidence]) : '';
    text('mission-plan', plan);
    show('mission-plan', Boolean(plan));
    text('mission-status', message ?? native?.status
      ?? (nativeChecks().some(result => result.disposition === 'VERIFIED_CALCULATION') ? words.auditDone
        : report && state === 'review' ? labels.join(' · ') : running ? words.browserRunning : words[state]));
    const missing = state === 'review' ? workInspection(report).missing : [];
    const check = nativeChecks().find(result => result.disposition === 'VERIFIED_CALCULATION');
    text('mission-next', native?.nextAction ?? (check ? words.auditNext : missing.length ? words.deliverablesMissing(missing)
      : state === 'canceled' ? words.canceledNext : state === 'paused' ? words.pausedNext
      : state === 'waiting' ? words.assisted : state === 'running' ? words.localNext
      : state === 'ready' && missionPacket(mission).instruction ? words.nextInstruction : report?.nextAction ?? words.choose));
  }

  function render(message) {
    const panel = node('frontier-mission-panel');
    panel.hidden = !mission;
    node('mission-export').disabled = !mission;
    renderNativeResults();
    refreshHistoryPreview();
    show('mission-return', Boolean(mission));
    show('mission-reopen-current', Boolean(mission));
    show('mission-checkpoint', Boolean(mission));
    show('mission-entry', !mission || editingAmbition);
    const filesSlot = node(mission && !editingAmbition ? 'mission-inline-files' : 'mission-entry-files');
    if (node('mission-files').parentElement !== filesSlot) filesSlot.append(node('mission-files'));
    renderFiles();
    show('mission-follow-up-form', Boolean(mission && mission.status !== 'canceled'));
    show('mission-dialogue', Boolean(mission?.turns?.length));
    node('mission-dialogue-list').replaceChildren(...(mission?.turns ?? []).map(turn => {
      const item = document.createElement('li');
      item.textContent = turn.instruction;
      return item;
    }));
    execution.updateControls();
    if (!mission) {
      renderDeliverables();
      text('mission-deliverable-feedback', '');
      delete panel.dataset.state;
      delete panel.dataset.route;
      for (const key of ['mission-ambition','mission-next','mission-status','mission-original','mission-objective','mission-route','mission-work','mission-published-summary']) text(key, '');
      for (const key of ['mission-published-links','mission-capabilities','mission-assumptions']) node(key).replaceChildren();
      node('mission-returned-files').replaceChildren();
      show('mission-returned-files', false);
      return;
    }
    const report = currentReport();
    const state = mission.status;
    const route = report?.route;
    panel.dataset.state = state;
    panel.dataset.route = route ?? '';
    text('mission-ambition', mission.ambition);
    text('mission-original', mission.originalAmbition);
    show('mission-history', mission.originalAmbition !== mission.ambition);
    renderHeadline(message);
    show('mission-understanding', Boolean(report));
    text('mission-route', words.routes[route]);
    text('mission-objective', report?.objective);
    renderAssistedWork(node('mission-work'), report?.work);
    show('mission-work-panel', Boolean(report?.work));
    show('mission-continue-assisted', report?.provider === 'assisted' && state === 'review');
    const inspection = renderDeliverables(report);
    text('mission-continue-assisted', inspection.missing.length ? words.askFiles : words.continueAssistant);
    const files = mission.reports.filter(item => item.revision === mission.revision)
      .flatMap(item => item.artifacts ?? []).filter(item => ['assisted-text','browser-text'].includes(item?.kind) && typeof item.content === 'string');
    show('mission-returned-files', files.length > 0);
    node('mission-returned-files').replaceChildren(...files.map(file => {
      const row = document.createElement('li');
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      const preview = document.createElement('pre');
      const download = document.createElement('button');
      summary.textContent = file.label;
      preview.textContent = file.content;
      download.type = 'button';
      download.className = 'quiet';
      download.textContent = words.fileDownload;
      download.addEventListener('click', () => {
        if (active()) downloadText(file.content, 'frontier-assisted-work.txt');
      });
      details.append(summary, preview, download);
      row.append(details);
      return row;
    }));
    const assumptions = report?.assumptions ?? [];
    show('mission-assumptions-group', assumptions.length > 0);
    node('mission-assumptions').replaceChildren(...assumptions.map(value => {
      const item = document.createElement('li');
      item.textContent = value;
      return item;
    }));
    const picked = available.filter(([id]) => report?.capabilityIds?.includes(id));
    node('mission-capabilities').replaceChildren(...picked.map(([, href, title, scope]) => {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = href;
      link.textContent = title[i];
      if (href.endsWith('.zip')) link.download = '';
      if (href === '#foundry-mission') link.addEventListener('click', () => {
        const value = report.objective;
        if (value.length <= 360 && !node('foundry-objective').value) node('foundry-objective').value = value;
        node('foundry-mission').open = true;
      });
      item.append(link, document.createTextNode(` · ${scope[i]}`));
      return item;
    }));
    const published = priorRuns.filter(row => row.ambition === mission.ambition.trim());
    show('mission-published', published.length > 0);
    text('mission-published-summary', published.map(row => row[language]).join(' '));
    node('mission-published-links').replaceChildren();
    for (const row of published) {
      const label = row.capability[language];
      for (const [href, title] of [[row.report, words.publicReport], [row.download, words.publicArtifact]]) {
        const link = document.createElement('a');
        link.href = href;
        link.textContent = `${title} · ${label}`;
        if (href === row.download) link.download = '';
        node('mission-published-links').append(link);
      }
    }
    show('mission-run-local', Boolean(connection) && state !== 'canceled' && state !== 'running');
    show('mission-pause', state === 'running' || state === 'waiting');
    show('mission-continue', ['paused','canceled','review'].includes(state));
    node('mission-cancel').disabled = state === 'canceled';
    node('mission-prepare').disabled = state === 'running' || state === 'canceled';
    show('mission-prepare', state !== 'waiting' || mission.run?.provider !== 'assisted');
  }

  function stopRequest() {
    serial++;
    activeRequest?.abort();
    activeRequest = undefined;
    browserBusy(false);
  }

  function afterPendingSetup(action, {stopWork = false} = {}) {
    const stopping = stopWork === 'cancel' ? 'cancel' : 'pause';
    if (!execution.hasPendingSetup() && (!stopWork || !execution.hasActiveWork(stopping))) { action(); return; }
    const token = ++serial;
    void (async () => await execution.cancelPendingSetup() && (!stopWork || await execution.pauseActive(stopping)))().then(canceled => {
      if (token !== serial || !active()) return;
      if (canceled) action();
      else render(words.continueBusy);
    });
  }

  function start(ambition, {execute = false, atlasLead} = {}) {
    if (!active()) return false;
    try {
      let updated = mission ? (mission.ambition !== ambition ? reviseMission(mission, ambition) : mission)
        : createMission(ambition, {language});
      if (!mission && entryDocuments) updated = setMissionDocuments(updated, entryDocuments);
      const open = () => {
        if (updated !== mission) {
          stopRequest();
          resetHandoff();
          execution.clearView({preservePrevious:true});
          mission = updated;
        }
        editingAmbition = false;
        entryDocuments = undefined;
        atlas = atlasLead;
        render();
        shell.show(node('frontier-mission-panel'), {remember:true});
        if (execute) activateWork();
        else execution.clearView();
      };
      if (updated !== mission) afterPendingSetup(open, {stopWork:true});
      else open();
      return true;
    } catch {
      text('goal-status', words.invalidMission);
      return false;
    }
  }

  async function requestForMission() {
    const packet = missionPacket(mission);
    const context = [`${words.contextRun}: ${packet.runId}`];
    if (atlas) context.push(`${words.contextAtlas}: ${atlas.title} · ${atlas.evidence} · ${atlas.url}`);
    if (packet.previousReport && mission.run?.provider !== 'assisted') {
      const previous = packet.previousReport;
      context.push(`${words.contextObjective}: ${workPreview(previous.objective,1700)}`);
      context.push(`${words.contextAction}: ${workPreview(previous.nextAction,1700)}`);
      if (previous.work) context.push(`${words.contextWork}: ${workPreview(previous.work,1700)}`);
      const missing = workInspection(previous).missing;
      if (missing.length) context.push(words.deliverablesMissing(missing.slice(0,4)));
    }
    const {missionId, revision, language, originalAmbition, ambition, instruction} = packet;
    if (instruction) context.push(words.contextInstruction, instruction);
    return createMissionRequest({missionId, revision, language, originalAmbition, ambition, context, capabilities});
  }

  function accept(receipt, runId) {
    const route = receipt.route === 'clarify' ? 'clarification' : receipt.route;
    const {objective, nextAction, assumptions, work, capabilityIds, artifacts} = receipt;
    mission = recordMission(mission, runId, {route, objective, nextAction,
      ...(assumptions && {assumptions}), ...(work && {work}), ...(capabilityIds && {capabilityIds}), ...(artifacts && {artifacts})});
    resetHandoff();
    render();
    node('mission-work-panel').open = Boolean(receipt.work && encoder.encode(receipt.work).length <= 1600);
  }

  function revealHandoff(prepared) {
    if (request?.requestId !== prepared.requestId) {
      resetHandoff();
      request = prepared;
      updateAssistedBrief();
      refreshEvidence();
    }
    const handoff = node('mission-handoff');
    handoff.hidden = false;
    handoff.open = true;
  }

  function priorContext(value) {
    const prefixes = ['Excerpt from previous unverified work','Extrait du travail précédent à vérifier',
      ...Object.values(messages).flatMap(labels=>[labels.contextObjective,labels.contextAction,labels.contextWork])];
    return prefixes.some(label=>value.startsWith(`${label}: `));
  }

  function priorMaterial() {
    const prior = currentReport();
    const original = prior?.artifacts?.find(file=>['assisted-text','assisted-original'].includes(file.kind));
    const held = resultFiles().map(file=>`${file.name} · SHA-256 ${file.sha256}`);
    const checks = nativeChecks().filter(result=>result.disposition === 'VERIFIED_CALCULATION');
    return [checks.length ? `${words.auditDone}\n${checks.map(auditSummary).join('\n')}` : null,
      held.length ? `${words.priorFiles}\n${held.join('\n')}` : null,
      original?.content || prior?.work ? `${words.priorOriginal}\n${original?.content ?? prior.work}` : null]
      .filter(Boolean).join('\n\n');
  }

  function refreshHistoryPreview() {
    const preview = node('mission-history-preview');
    const material = request ? priorMaterial() : '';
    if (preview.textContent !== material) {
      preview.textContent = material;
      node('mission-include-history').checked = false;
      clearCopyFallback();
      text('mission-copy-status', '');
    }
    show('mission-history-share', Boolean(material) && !node('mission-prompt').readOnly);
  }

  function updateAssistedBrief() {
    if (!request) return;
    const context = request.context.filter(value => !value.startsWith(`${words.contextRun}: `) && !priorContext(value));
    const prompt = node('mission-prompt');
    prompt.readOnly = node('mission-technical').checked;
    prompt.value = prompt.readOnly ? createMissionPrompt(request)
      : assistedDraft ?? createAssistedBrief(request, context, Boolean(mission.reports.length));
    show('mission-evidence-context', !prompt.readOnly && Boolean(evidenceContext));
    refreshHistoryPreview();
    text('mission-copy-status', '');
    clearCopyFallback();
    updateHandoffControls();
  }

  function renderEvidence() {
    const items = evidenceContext?.items ?? [];
    show('mission-evidence-context', Boolean(request) && !node('mission-technical').checked && Boolean(evidenceContext));
    text('mission-context-status', items.length ? missionWorkPlan(evidenceContext, [...selectedEvidence])
      : evidenceSources?.release ? words.evidenceGap : words.evidenceUnavailable);
    show('mission-context-download', items.length > 0);
    node('mission-context-items').replaceChildren(...items.map(item => {
      const row = document.createElement('li');
      const label = document.createElement('label');
      const include = document.createElement('input');
      include.type = 'checkbox';
      include.checked = selectedEvidence.has(item.id);
      include.addEventListener('change', () => {
        if (include.checked) selectedEvidence.add(item.id);
        else selectedEvidence.delete(item.id);
        clearCopyFallback();
        text('mission-copy-status', '');
        text('mission-context-status', missionWorkPlan(evidenceContext, [...selectedEvidence]));
        renderHeadline();
      });
      label.append(include, document.createTextNode(' ' + item.title));
      const detail = document.createElement('p');
      detail.textContent = [item.fact, item.scope, item.source.date].join(' · ');
      row.append(label, detail);
      const links = new Map([[item.source.url, words.openSource], [item.recordURL, words.openSource],
        [item.artifact?.url, words.openTool]]);
      for (const [href, title] of links) {
        if (!href?.startsWith('https://')) continue;
        const link = document.createElement('a');
        link.href = href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = title;
        row.append(link, document.createTextNode(' '));
      }
      return row;
    }));
  }

  function refreshEvidence() {
    const {ambition, instruction, language:missionLanguage} = missionPacket(mission);
    const requestScope = {ambition, language:missionLanguage, ...evidenceSources};
    const previous = currentReport();
    const previousScope = !instruction && previous?.provider === 'assisted' && previous.work
      ? selectMissionContext({...requestScope, instruction:workPreview(previous.work,2200)}) : null;
    evidenceContext = previousScope?.items.length ? previousScope : selectMissionContext({...requestScope, instruction});
    selectedEvidence = new Set(evidenceContext.items.map(item => item.id));
    renderEvidence();
  }

  function sharedBrief() {
    const prompt = node('mission-prompt');
    if (prompt.readOnly || !evidenceContext) return prompt.value;
    const selected = [...selectedEvidence];
    const rows = missionContextLines(evidenceContext, selected);
    const parts = [prompt.value,`${words.evidencePlan}\n${missionWorkPlan(evidenceContext, selected)}`];
    if (rows.length) parts.push(`${words.evidenceHeading}\n${rows.join('\n\n')}`);
    if (node('mission-include-history').checked) {
      const reviewed = node('mission-history-preview').textContent;
      if (reviewed) parts.push(reviewed);
    }
    return parts.join('\n\n');
  }

  node('mission-include-history').addEventListener('change', () => {
    clearCopyFallback();
    text('mission-copy-status', '');
  });

  node('mission-context-download').addEventListener('click', () => {
    if (!active() || !request || !evidenceContext) return;
    const packet = missionIntelligencePackage(sharedBrief(), evidenceContext, [...selectedEvidence]);
    downloadJSON(packet, 'frontier-reviewed-mission.json');
  });

  async function prepareAssistance({focus = true} = {}) {
    if (!active()) return;
    if (!mission) {
      shell.show(input, {remember:true});
      text('goal-status', words.prepareFirst);
      input.focus();
      return;
    }
    if (files().length) { render(words.localFiles); return; }
    if (node('mission-prepare').disabled) {
      shell.show(node('frontier-mission-panel'), {remember:true});
      return;
    }
    const previous = mission;
    if (execution.hasPendingSetup() && !await execution.cancelPendingSetup()) {
      if (active() && previous === mission) render(words.cancelSetupFailed);
      return;
    }
    if (!active() || previous !== mission) return;
    shell.show(node('frontier-mission-panel'), {remember:true,focus});
    if (settings.parentElement === node('mission-inline-intelligence')) settings.open = false;
    execution.clearWaiting();
    const token = ++serial;
    try {
      if (mission.status !== 'waiting' || mission.run?.provider !== 'assisted' || !mission.request || mission.request.context.some(priorContext)) {
        const queued = prepareMission(mission, {provider:'assisted'});
        mission = queued;
        const prepared = await bindMissionRequest(queued, queued.run.id, await requestForMission());
        if (token !== serial || !active()) return;
        mission = prepared;
      }
      revealHandoff(mission.request);
      render();
      if (focus) node('mission-handoff').querySelector('summary').focus();
    } catch { if (token === serial && active()) render(words.invalidMission); }
  }
  node('mission-prepare').addEventListener('click', prepareAssistance);
  node('mission-continue-assisted').addEventListener('click', prepareAssistance);
  for (const button of member.querySelectorAll('[data-frontier-assisted]')) button.addEventListener('click', prepareAssistance);

  node('mission-technical').addEventListener('change', () => {
    if (node('mission-technical').checked) assistedDraft = node('mission-prompt').value;
    updateAssistedBrief();
  });
  function clearCopyFallback() {
    const fallback = node('mission-copy-fallback');
    fallback.value = '';
    fallback.hidden = true;
  }
  node('mission-prompt').addEventListener('input', () => {
    clearCopyFallback();
    text('mission-copy-status', '');
  });
  node('mission-copy').addEventListener('click', async () => {
    if (!active() || !request) return;
    const token = serial;
    const reviewed = sharedBrief();
    try {
      await navigator.clipboard.writeText(reviewed);
      if (token === serial && active()) {
        clearCopyFallback();
        text('mission-copy-status', sharedBrief() === reviewed ? words.copy : words.copyEarlier);
      }
    } catch {
      if (token !== serial || !active()) return;
      const fallback = node('mission-copy-fallback');
      fallback.value = sharedBrief();
      fallback.hidden = false;
      fallback.focus();
      fallback.select();
      text('mission-copy-status', words.select);
    }
  });
  node('mission-prompt-download').addEventListener('click', () => {
    if (active() && request) downloadText(sharedBrief(), 'frontier-mission-brief.txt');
  });

  function resetAssistedImport() {
    unmatchedWork = undefined;
    show('mission-keep-unverified', false);
    text('mission-handoff-status', '');
  }

  const canImportAssisted = () => active() && request && mission?.request?.requestId === request.requestId
    && mission.status === 'waiting' && mission.run?.provider === 'assisted';

  async function textArtifact(content, kind, label) {
    const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(content))),
      value => value.toString(16).padStart(2, '0')).join('');
    return {label, kind, sha256, content};
  }

  async function keepAssisted(result, filename, token) {
    const label = filename?.replace(/[\u0000-\u001f\u007f]/gu, '').slice(0, 120).trim() || words.originalResponse;
    const artifact = await textArtifact(result.raw, filename ? 'assisted-text' : 'assisted-original', label);
    if (token !== serial || !canImportAssisted()) return;
    if (!filename && mission.reports.some(report => report.revision === mission.revision && report.artifacts?.some(
      file => file.kind === 'assisted-original' && file.sha256 === artifact.sha256))) {
      text('mission-handoff-status', words.duplicateReply);
      return;
    }
    const inspection = inspectReturnedWork(result.raw, resultFiles());
    const proposed = result.work.match(/^#{1,6} +(?:next [^\n]*|prochaine? [^\n]*|suite)\n\s*([^#\n][^\n]*)/imu)?.[1]?.trim();
    const nextAction = inspection.missing.length ? words.deliverablesMissing(inspection.missing)
      : proposed ? `${words.nextFromReply} · ${workPreview(proposed,650)}` : (inspection.hasTable || inspection.sources.length) ? words.supplySource : words.workReview;
    const receipt = result.receipt ?? {route:'continuing', objective:mission.ambition, nextAction};
    const work = workPreview(result.work.trim() ? result.work : result.raw);
    accept({...receipt, work, artifacts:[artifact]}, mission.run.id);
    if (workInspection(currentReport()).missing.length) node('mission-deliverables').open = true;
    const workPanel = node('mission-work-panel');
    const target = workInspection(currentReport()).missing.length ? node('mission-deliverable-import') : workPanel.querySelector('summary');
    if (target.getClientRects().length) {
      target.focus({preventScroll:true});
      target.scrollIntoView({block:'nearest', behavior:'instant'});
    }
  }

  async function importAssisted(raw, filename, token) {
    const result = await readAssistedReply(raw, request);
    if (token !== serial || !canImportAssisted()) return;
    if (result.kind === 'unmatched') {
      unmatchedWork = {result, filename};
      text('mission-handoff-status', words.invalid);
      show('mission-keep-unverified', true);
      node('mission-keep-unverified').focus();
      return;
    }
    await keepAssisted(result, filename, token);
  }

  node('mission-reply').addEventListener('input', () => { serial++; resetAssistedImport(); });
  node('mission-import-reply').addEventListener('click', async () => {
    if (!canImportAssisted()) return;
    const token = ++serial;
    resetAssistedImport();
    try { await importAssisted(node('mission-reply').value, undefined, token); }
    catch { if (token === serial && active()) text('mission-handoff-status', words.plainInvalid); }
  });
  node('mission-keep-unverified').addEventListener('click', async () => {
    if (!canImportAssisted() || !unmatchedWork) return;
    const token = ++serial;
    const {result, filename} = unmatchedWork;
    try { await keepAssisted(result, filename, token); }
    catch { if (token === serial && active()) text('mission-handoff-status', words.plainInvalid); }
  });

  async function returnedText(content) {
    const bytes = encoder.encode(content);
    if (!content.trim() || bytes.length > maximumReturnedBytes) throw new Error('ASSISTED_TEXT');
    const report = {route:'continuing', objective:mission.ambition, nextAction:words.workReview};
    if (bytes.length <= 12 * 1024) return {...report, work:content};
    return {...report, artifacts:[await textArtifact(content, 'browser-text', words.browserSource)]};
  }

  node('mission-import-artifact').addEventListener('change', async event => {
    const control = event.target;
    const file = control.files[0];
    control.value = '';
    if (!file || !canImportAssisted()) return;
    const token = ++serial;
    resetAssistedImport();
    try {
      if (file.size > maximumReturnedBytes) throw new Error('ASSISTED_FILE_SIZE');
      const content = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(await file.arrayBuffer());
      if (token === serial && canImportAssisted()) await importAssisted(content, file.name, token);
    } catch { if (token === serial && active()) text('mission-handoff-status', words.plainInvalid); }
  });

  async function checkBrowserStarter() {
    const check = ++browserCheck;
    const state = await browserModelAvailability(mission?.language ?? language);
    if (check !== browserCheck || !active()) return;
    show('intelligence-browser', true);
    show('intelligence-browser-start', state !== 'unavailable');
    if (state === 'unavailable') text('intelligence-browser-status', words.browserUnsupported);
    else if (node('intelligence-browser-status').textContent === words.browserUnsupported) text('intelligence-browser-status', '');
  }

  function browserBusy(busy) {
    node('intelligence-browser-start').disabled = busy;
    show('intelligence-browser-cancel', busy);
  }

  node('intelligence-browser-start').addEventListener('click', async () => {
    if (!active()) return;
    if (!mission) {
      shell.show(input, {remember:true});
      text('goal-status', words.browserFirst);
      input.focus();
      return;
    }
    if (files().length) { render(words.localFiles); return; }
    if (['canceled','running'].includes(mission.status) || execution.hasActiveWork() || execution.hasPendingSetup()) {
      text('intelligence-browser-status', words.browserWait);
      return;
    }
    execution.clearWaiting();
    resetHandoff();
    const controller = new AbortController();
    const token = ++serial;
    const snapshot = mission;
    activeRequest = controller;
    browserBusy(true);
    text('intelligence-browser-status', words.browserStarting);
    let run;
    try {
      mission = beginMission(mission, {provider:'local', model:browserModelId});
      run = mission.run.id;
      render();
      const packet = missionPacket(snapshot);
      const result = await runBrowserStarter({ambition:snapshot.ambition, language:snapshot.language, signal:controller.signal,
        originalAmbition:packet.originalAmbition, instruction:packet.instruction, previousWork:packet.previousReport?.work,
        onProgress(value) {
          if (token !== serial || !active()) return;
          const message = value < 1 ? words.browserDownloading(new Intl.NumberFormat(language, {style:'percent'}).format(value)) : words.browserStarting;
          if (node('intelligence-browser-status').textContent !== message) text('intelligence-browser-status', message);
        },
        onReady() {
          if (token === serial && active()) text('intelligence-browser-status', words.browserRunning);
        }});
      if (token !== serial || !active()) return;
      const report = await returnedText(result);
      if (token !== serial || !active()) return;
      localRuns.add(run);
      accept(report, run);
      text('intelligence-browser-status', words.review);
      shell.show(node('frontier-mission-panel'), {remember:true});
    } catch (error) {
      if (token !== serial || !active()) return;
      if (run) mission = interruptMission(mission, run, 'BROWSER_MODEL_FAILED');
      const message = error?.message === 'BROWSER_MODEL_UNVERIFIED' ? words.browserUnverified
        : error?.message === 'BROWSER_MODEL_CONTEXT' ? words.browserContext : words.browserUnavailable;
      render(message);
      text('intelligence-browser-status', message);
    } finally {
      if (token === serial) { activeRequest = undefined; browserBusy(false); }
    }
  });

  node('intelligence-browser-cancel').addEventListener('click', () => {
    if (!active() || mission?.status !== 'running' || mission.run.model !== browserModelId) return;
    stopRequest();
    mission = interruptMission(mission, mission.run.id, 'USER_PAUSED');
    render(words.browserCanceled);
    text('intelligence-browser-status', words.browserCanceled);
  });
  window.addEventListener('frontier:member-enter', checkBrowserStarter);
  node('mission-intelligence').addEventListener('toggle', () => {
    if (active() && node('mission-intelligence').open) void checkBrowserStarter();
  });

  node('mission-configure').addEventListener('click', () => {
    if (!active()) return;
    showSetup();
    settings.querySelector('summary').focus();
    void checkBrowserStarter();
  });
  node('mission-connection-form').addEventListener('submit', event => {
    event.preventDefault();
    if (!active()) return;
    try {
      const endpoint = node('mission-endpoint').value;
      connection = validateLocalMissionConfig({endpoint, model:node('mission-model').value.trim(),
        structuredOutput:endpoint.endsWith('/v1/chat/completions')});
      text('mission-connection-status', words.config);
      render();
    } catch { text('mission-connection-status', words.invalidConfig); }
  });
  async function runConfiguredModel() {
    if (!active() || !mission || !connection || ['running','canceled'].includes(mission.status)) return;
    if (files().length) { render(words.localFiles); return; }
    execution.clearWaiting();
    const config = connection;
    const controller = new AbortController();
    const token = ++serial;
    activeRequest = controller;
    resetHandoff();
    let run;
    try {
      mission = beginMission(mission, {provider:'local', model:config.model});
      run = mission.run.id;
      render();
      const localRequest = await requestForMission();
      const attached = await bindMissionRequest(mission, run, localRequest);
      if (token !== serial || !active()) return;
      mission = attached;
      const result = await runLocalMission(localRequest, config, {authorized:true, signal:controller.signal});
      if (token === serial && active()) {
        localRuns.add(run);
        accept(result, run);
      }
    } catch {
      if (token !== serial || !active()) return;
      if (run) mission = interruptMission(mission, run, 'LOCAL_RESPONSE_FAILED');
      render(words.error);
    } finally { if (token === serial) activeRequest = undefined; }
  }
  node('mission-run-local').addEventListener('click', runConfiguredModel);

  const resetRequest = () => { stopRequest(); resetHandoff(); };
  node('mission-pause').addEventListener('click', () => {
    if (!active() || !mission?.run) return;
    resetRequest();
    mission = interruptMission(mission, mission.run.id, 'USER_PAUSED');
    render();
  });
  function continueFromHere(instruction) {
    if (!active() || !mission) return;
    try {
      const next = instruction ? addMissionInstruction(mission, instruction) : continueMission(mission);
      const last = currentReport();
      const preferred = mission.run?.provider === 'assisted' || last?.provider === 'assisted' ? 'assisted' : last?.model;
      afterPendingSetup(() => {
        resetRequest();
        if (next.status === 'running') {
          const stopped = interruptMission(next, next.run.id, 'USER_CONTINUED');
          mission = continueMission(stopped);
        } else mission = next;
        node('mission-follow-up').value = '';
        render();
        activateWork({preferred,continuation:true});
      }, {stopWork:true});
    } catch { render(words.invalidInstruction); }
  }
  node('mission-continue').addEventListener('click', () => continueFromHere());
  node('mission-follow-up-form').addEventListener('submit', event => {
    event.preventDefault();
    const instruction = node('mission-follow-up').value;
    if (instruction.trim()) continueFromHere(instruction);
  });
  node('mission-cancel').addEventListener('click', () => {
    if (!active() || !mission) return;
    afterPendingSetup(() => {
      execution.clearWaiting();
      resetRequest();
      mission = cancelMission(mission);
      render();
    }, {stopWork:'cancel'});
  });
  node('mission-revise').addEventListener('click', () => {
    if (!active() || !mission) return;
    editingAmbition = true;
    render();
    input.focus();
  });
  node('mission-new').addEventListener('click', () => {
    if (!active()) return;
    afterPendingSetup(() => {
      resetRequest();
      mission = atlas = undefined;
      entryDocuments = recoveredDocuments = undefined;
      editingAmbition = false;
      fileSerial++;
      node('mission-follow-up').value = '';
      node('mission-document-status').textContent = '';
      node('mission-document-consent').checked = false;
      node('mission-files').open = false;
      execution.clearView();
      localRuns.clear();
      observedFileChecks.clear();
      input.value = '';
      input.dispatchEvent(new Event('input'));
      render();
      input.focus();
    }, {stopWork:true});
  });
  node('mission-work-download').addEventListener('click', () => {
    const report = currentReport();
    const original = report?.artifacts?.find(file => ['assisted-original','assisted-text'].includes(file.kind));
    const work = original?.content ?? report?.work;
    if (active() && work) downloadText(work, 'frontier-work-for-review.txt');
  });
  async function downloadMission(feedback) {
    if (!active() || !mission) return;
    const snapshot = mission;
    const token = serial;
    try {
      const exported = await exportMission(snapshot);
      if (token !== serial || !active()) return;
      downloadJSON(typeof exported === 'string' ? JSON.parse(exported) : exported, 'frontier-mission.json');
      text(feedback, words.saved);
    } catch { if (token === serial && active()) text(feedback, words.fileInvalid); }
  }
  node('mission-export').addEventListener('click', () => downloadMission('mission-file-status'));
  node('mission-checkpoint').addEventListener('click', () => downloadMission('mission-checkpoint-status'));
  node('mission-restore').addEventListener('click', () => {
    if (active()) node('mission-keeper').open = true;
  });
  node('mission-import').addEventListener('change', async event => {
    const control = event.target;
    const file = control.files[0];
    control.value = '';
    if (!file || !active()) return;
    const attempt = serial;
    try {
      if (file.size > 2*1024*1024) throw new Error('FILE_TOO_LARGE');
      const restored = await importMission(await file.text());
      if (attempt !== serial || !active()) return;
      afterPendingSetup(() => {
        resetRequest();
        localRuns.clear();
        mission = restored;
        nativeKey = '';
        recoveredDocuments = entryDocuments = undefined;
        editingAmbition = false;
        fileSerial++;
        node('mission-document-consent').checked = false;
        node('mission-follow-up').value = '';
        execution.clearView();
        atlas = undefined;
        input.value = mission.ambition;
        input.dispatchEvent(new Event('input'));
        if (mission.status === 'waiting' && mission.request) {
          if (mission.request.context.some(priorContext)) void prepareAssistance({focus:false});
          else revealHandoff(mission.request);
        }
        render(words.reopened);
        text('mission-file-status', words.reopened);
        shell.show(node('frontier-mission-panel'), {remember:true});
        void checkBrowserStarter();
      }, {stopWork:true});
    } catch { if (attempt === serial && active()) text('mission-file-status', words.fileInvalid); }
  });
  window.addEventListener('frontier:member-lock', () => {
    resetRequest();
    mission = atlas = connection = undefined;
    entryDocuments = recoveredDocuments = undefined;
    editingAmbition = false;
    fileSerial++;
    node('mission-follow-up').value = '';
    node('mission-document-status').textContent = '';
    node('mission-document-consent').checked = false;
    node('mission-files').open = false;
    if (settings.parentElement !== node('intelligence-settings-slot')) node('intelligence-settings-slot').append(settings);
    localRuns.clear();
    observedFileChecks.clear();
    browserCheck++;
    show('intelligence-browser', false);
    node('mission-connection-form').reset();
    node('mission-keeper').open = node('mission-intelligence').open = false;
    text('mission-file-status', '');
    text('mission-connection-status', '');
    text('mission-checkpoint-status', '');
    text('intelligence-browser-status', '');
    render();
  });
  render();
  return {start};
}
