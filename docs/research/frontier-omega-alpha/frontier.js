import { decryptRelease } from './decrypt.js';

const labels = ['radar', 'opportunity', 'experiment', 'verification', 'compounding', 'archive'];
const language = document.documentElement.lang === 'fr' ? 'fr' : 'en';
const messages = {
  en: {
    ready: 'Choose an access path.',
    offline: 'Protected access is offline on this deployment.',
    wallet_missing: 'Open this page in an Ethereum wallet browser or install a compatible wallet extension.',
    network: 'Switch your wallet to Ethereum mainnet and try again.',
    identity: 'Enter only the first label, using letters, digits or internal hyphens.',
    connecting: 'Connecting to your wallet…',
    signing: 'Review and sign the sign-in message in your wallet.',
    verifying: 'Verifying your wallet and eligibility on Ethereum…',
    refused: 'The wallet request was cancelled.',
    ineligible: 'This wallet does not meet the verified AGI Club or $AGIALPHA access rule.',
    invalid_signature: 'The wallet signature could not be verified. Start a new sign-in.',
    challenge_expired: 'The sign-in request expired. Start a new sign-in.',
    session_required: 'Your session has ended. Sign in again.',
    wallet_changed: 'The wallet account or network changed. Sign in again.',
    verification_unavailable: 'Verification is temporarily unavailable. Protected content remains locked.',
    release_unavailable: 'This research release is unavailable.',
    rate_limit: 'Too many access requests. Try again in a minute.',
    locked: 'The research workspace is locked.',
    loading: 'Opening protected research…',
    empty: 'No released records in this section.',
    select: 'Choose a release to read.',
    sources: 'Sources',
    version: 'version',
    sections: ['Frontier Radar', 'Opportunity Explorer', 'Experiment Lab', 'Verification Room', 'Compounding Ledger', 'Research Archive']
  },
  fr: {
    ready: 'Choisissez un mode d’accès.',
    offline: 'L’accès protégé est hors ligne sur ce site.',
    wallet_missing: 'Ouvrez cette page dans le navigateur d’un portefeuille Ethereum ou installez une extension compatible.',
    network: 'Passez au réseau principal Ethereum dans votre portefeuille, puis réessayez.',
    identity: 'Saisissez uniquement le premier libellé, avec des lettres, des chiffres ou des traits d’union internes.',
    connecting: 'Connexion à votre portefeuille…',
    signing: 'Vérifiez et signez le message de connexion dans votre portefeuille.',
    verifying: 'Vérification de votre portefeuille et de votre admissibilité sur Ethereum…',
    refused: 'La demande au portefeuille a été annulée.',
    ineligible: 'Ce portefeuille ne satisfait à aucun des deux critères d’accès vérifiés.',
    invalid_signature: 'La signature n’a pas pu être vérifiée. Relancez la connexion.',
    challenge_expired: 'La demande de connexion a expiré. Relancez la connexion.',
    session_required: 'Votre session est terminée. Reconnectez-vous.',
    wallet_changed: 'Le compte ou le réseau du portefeuille a changé. Reconnectez-vous.',
    verification_unavailable: 'La vérification est temporairement indisponible. Le contenu reste verrouillé.',
    release_unavailable: 'Cette version de recherche est indisponible.',
    rate_limit: 'Trop de demandes d’accès. Réessayez dans une minute.',
    locked: 'L’espace de recherche est verrouillé.',
    loading: 'Ouverture du contenu protégé…',
    empty: 'Aucun dossier publié dans cette section.',
    select: 'Choisissez une version à consulter.',
    sources: 'Sources',
    version: 'version',
    sections: ['Radar de la frontière', 'Explorateur d’occasions', 'Laboratoire d’expérimentation', 'Salle de vérification', 'Registre des acquis', 'Archives de recherche']
  }
}[language];

const byId = id => document.getElementById(id);
const status = byId('status');
const workspaceStatus = byId('workspace-status');
const connectButtons = Array.from(document.querySelectorAll('[data-connect]'));
const say = (node, key) => { node.textContent = Object.hasOwn(messages, key) ? messages[key] : messages.verification_unavailable; };
let api;
try {
  const config = document.querySelector('meta[name="frontier-api"]').content.trim();
  if (config) {
    const url = new URL(config === 'same-origin' ? location.origin : config);
    const local = url.origin === location.origin && ['localhost', '127.0.0.1'].includes(url.hostname);
    if ((url.protocol === 'https:' || local && url.protocol === 'http:') &&
        url.pathname === '/' && !url.username && !url.password && !url.search && !url.hash) api = url.origin;
  }
} catch {
  // An invalid deployment configuration leaves access offline.
}

let generation = 0;
let openRequest = 0;
let session;
let activeWallet;
let entries = [];
let selectedSection;
let expiryTimer;
let checkTimer;
let checking = false;

async function request(route, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch(api + '/v1/' + route, {
    method: 'POST', headers, body: JSON.stringify(body), credentials: 'omit',
    redirect: 'error', cache: 'no-store', referrerPolicy: 'no-referrer', signal: AbortSignal.timeout(15_000)
  });
  const result = await response.json();
  if (!response.ok) throw Error(result.error);
  return result;
}

function boundEvents(wallet, op) {
  for (const event of ['accountsChanged', 'chainChanged', 'disconnect']) wallet[op]?.(event, walletChanged);
}

function walletChanged() {
  lock('wallet_changed');
}

function revoke(token) {
  if (token) void request('logout', {}, token).catch(() => {});
}

function lock(reason, focus = false) {
  generation++;
  openRequest++;
  clearTimeout(expiryTimer);
  clearInterval(checkTimer);
  if (activeWallet) boundEvents(activeWallet, 'removeListener');
  activeWallet = null;
  revoke(session?.token);
  session = undefined;
  entries = [];
  byId('member').hidden = true;
  for (const id of ['record', 'entries', 'collections', 'workspace-status']) byId(id).replaceChildren();
  connectButtons.forEach(button => { button.disabled = false; });
  say(status, reason);
  if (focus) byId('gate-title').scrollIntoView({ block: 'nearest' });
  if (focus) connectButtons[0].focus({ preventScroll: true });
}

async function recheck(ownGeneration) {
  if (!session || ownGeneration !== generation || checking) return;
  if (Date.now() >= session.expiresAt) return lock('session_required');
  checking = true;
  try {
    await request('session', {}, session.token);
  } catch (error) {
    if (ownGeneration === generation) lock(error.message);
  } finally {
    checking = false;
  }
}

function recordNode(tag, content) {
  const node = document.createElement(tag);
  node.textContent = content;
  return node;
}

function renderSections() {
  byId('collections').replaceChildren(...labels.map((label, index) => {
    const count = entries.filter(entry => entry.section === label).length;
    const button = recordNode('button', messages.sections[index] + ' · ' + count);
    button.type = 'button';
    button.dataset.section = label;
    button.setAttribute('aria-pressed', String(label === selectedSection));
    button.addEventListener('click', () => selectSection(label));
    return button;
  }));
}

function selectSection(section) {
  selectedSection = section;
  openRequest++;
  byId('record').replaceChildren();
  document.querySelectorAll('[data-section]').forEach(button => {
    button.setAttribute('aria-pressed', String(button.dataset.section === section));
  });
  const matching = entries.filter(entry => entry.section === section);
  say(workspaceStatus, matching.length ? 'select' : 'empty');
  byId('entries').replaceChildren(...matching.map(entry => {
    const item = document.createElement('li');
    const label = entry.id + ' · ' + messages.version + ' ' + entry.version;
    const button = recordNode('button', label);
    button.type = 'button';
    button.addEventListener('click', () => void openRelease(entry));
    item.append(button);
    return item;
  }));
}

async function openRelease(entry) {
  if (!session) return;
  const ownGeneration = generation;
  const sequence = ++openRequest;
  byId('record').replaceChildren();
  say(workspaceStatus, 'loading');
  try {
    const { ciphertext, key, record } = await request('open', { id: entry.id, version: entry.version }, session.token);
    const content = record ?? await decryptRelease(ciphertext, key, entry);
    const localized = content?.[language];
    if (content?.section !== entry.section || typeof localized?.title !== 'string' ||
        !Array.isArray(localized.paragraphs) || !localized.paragraphs.every(text => typeof text === 'string')) throw Error('release_unavailable');
    if (generation !== ownGeneration || sequence !== openRequest) return;
    workspaceStatus.textContent = '';
    const body = [recordNode('h3', localized.title), ...localized.paragraphs.map(text => recordNode('p', text))];
    if (Array.isArray(content.sources) && content.sources.length) {
      const list = document.createElement('ul');
      for (const source of content.sources) {
        const url = new URL(source.url);
        if (url.protocol !== 'https:' || url.username || url.password || typeof source[language] !== 'string') continue;
        const item = document.createElement('li');
        const link = recordNode('a', source[language]);
        link.href = url.href;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        item.append(link);
        list.append(item);
      }
      if (list.children.length) body.push(recordNode('p', messages.sources), list);
    }
    byId('record').replaceChildren(...body);
  } catch (error) {
    if (generation !== ownGeneration || sequence !== openRequest) return;
    if (['release_unavailable', 'rate_limit'].includes(error.message)) say(workspaceStatus, error.message);
    else lock(error.message, true);
  }
}

function compatibleEntry(entry) {
  return entry && typeof entry.id === 'string' && /^[a-z0-9][a-z0-9-]{0,79}$/.test(entry.id) &&
    Number.isSafeInteger(entry.version) && entry.version >= 1 && labels.includes(entry.section);
}

async function connect(path) {
  if (!api || !globalThis.isSecureContext || !globalThis.crypto?.subtle) return say(status, 'offline');
  const wallet = globalThis.ethereum;
  if (!wallet?.request) return say(status, 'wallet_missing');
  const label = path === 'club' ? byId('club-label').value.trim().toLowerCase() : null;
  if (path === 'club' && !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)) return say(status, 'identity');
  if (session) lock('locked');
  const ownGeneration = ++generation;
  connectButtons.forEach(button => { button.disabled = true; });
  let provisioned;
  try {
    say(status, 'connecting');
    const [address] = await wallet.request({ method: 'eth_requestAccounts' });
    if (!address) throw Error('wallet_missing');
    if (await wallet.request({ method: 'eth_chainId' }) !== '0x1') throw Error('network');
    if (ownGeneration !== generation) return;
    activeWallet = wallet;
    boundEvents(wallet, 'on');
    const { nonce, message } = await request('challenge', { address, label, language });
    if (ownGeneration !== generation) return;
    const encoded = Array.from(new TextEncoder().encode(message), byte => byte.toString(16).padStart(2, '0')).join('');
    say(status, 'signing');
    const signature = await wallet.request({ method: 'personal_sign', params: ['0x' + encoded, address] });
    if (ownGeneration !== generation) return;
    say(status, 'verifying');
    provisioned = await request('verify', { nonce, signature });
    if (ownGeneration !== generation) return;
    const [current] = await wallet.request({ method: 'eth_accounts' });
    if (current?.toLowerCase() !== address.toLowerCase() ||
        await wallet.request({ method: 'eth_chainId' }) !== '0x1') throw Error('wallet_changed');
    if (!/^[a-f0-9]{64}$/.test(provisioned?.token) || !Number.isSafeInteger(provisioned.expiresAt) ||
        provisioned.expiresAt <= Date.now()) throw Error('session_required');
    const catalog = await request('catalog', {}, provisioned.token);
    if (ownGeneration !== generation) return;
    if (!Array.isArray(catalog.entries) || !catalog.entries.every(compatibleEntry)) throw Error('verification_unavailable');
    if (provisioned.expiresAt <= Date.now()) throw Error('session_required');
    session = provisioned;
    entries = catalog.entries;
    const first = entries[0]?.section ?? labels[0];
    renderSections();
    selectSection(first);
    byId('member').hidden = false;
    byId('workspace-title').focus();
    status.textContent = '';
    expiryTimer = setTimeout(() => lock('session_required'), session.expiresAt - Date.now());
    checkTimer = setInterval(() => void recheck(ownGeneration), 45_000);
  } catch (error) {
    if (ownGeneration === generation) lock(error.code === 4001 ? 'refused' : error.message);
  } finally {
    if (provisioned && session !== provisioned) revoke(provisioned.token);
    if (ownGeneration === generation) connectButtons.forEach(button => { button.disabled = false; });
  }
}

byId('club-form').addEventListener('submit', event => { event.preventDefault(); void connect('club'); });
document.querySelector('[data-connect="token"]').addEventListener('click', () => void connect('token'));
byId('lock').addEventListener('click', () => lock('locked', true));
window.addEventListener('pagehide', () => { if (session || activeWallet) lock('locked'); });
window.addEventListener('focus', () => void recheck(generation));
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') void recheck(generation); });
say(status, api ? 'ready' : 'offline');
