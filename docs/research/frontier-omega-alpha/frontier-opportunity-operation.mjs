const hub = 'https://huggingface.co';
const kind = 'huggingface-model-inventory';
const commit = /^[a-f0-9]{40}$/u;
const digest = /^[a-f0-9]{64}$/u;
const segment = /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,181}$/u;
const encoder = new TextEncoder();
const decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true});
const maxMetadataBytes = 128 * 1024;

function validPath(value, maxSegments) {
  if (typeof value !== 'string' || value.length > 240) return false;
  const parts = value.split('/');
  return parts.length <= maxSegments && parts.every(part => segment.test(part));
}

export function opportunityOperation(record) {
  const plan = record?.operation;
  if (plan?.kind !== kind || !validPath(plan.repo, 2) || !plan.repo.includes('/')
    || !validPath(plan.filename, 4)) return null;
  const required = plan.requiredFilenames === undefined ? [] : plan.requiredFilenames;
  const comparison = plan.comparisonFilename;
  if (!Array.isArray(required) || required.length > 8
    || !required.every(value => validPath(value, 4))
    || (comparison !== undefined && !validPath(comparison, 4))) return null;
  const fileNames = [plan.filename, ...required, ...(comparison === undefined ? [] : [comparison])];
  if (new Set(fileNames).size !== fileNames.length) return null;
  return {kind, repo: plan.repo, filename: plan.filename, requiredFilenames: [...required],
    ...(comparison === undefined ? {} : {comparisonFilename: comparison})};
}

function requireEvidence(condition, code) {
  if (condition) return;
  throw Object.assign(new Error(code), {code});
}

function decode(bytes) {
  try {
    return decoder.decode(bytes);
  } catch {
    requireEvidence(false, 'source-format');
  }
}

async function readBounded(fetchSource, url, limit, signal) {
  signal?.throwIfAborted();
  const response = await fetchSource(url, {
    method: 'GET', credentials: 'omit', redirect: 'error', referrerPolicy: 'no-referrer',
    mode: 'cors', signal,
  });
  signal?.throwIfAborted();
  if (!response.ok || !response.body || (response.url && response.url !== url)) {
    await response.body?.cancel().catch(() => {});
    requireEvidence(false, 'source-unavailable');
  }
  const length = response.headers.get('content-length');
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    requireEvidence(length === null || Number(length) <= limit, 'source-too-large');
    while (true) {
      const {value, done} = await reader.read();
      signal?.throwIfAborted();
      if (done) break;
      size += value.length;
      requireEvidence(size <= limit, 'source-too-large');
      chunks.push(value);
    }
  } catch (error) {
    await reader.cancel().catch(() => {});
    throw error;
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let start = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, start);
    start += chunk.length;
  }
  return {bytes, headers: response.headers};
}

async function hash(bytes, algorithm = 'SHA-256') {
  const buffer = await globalThis.crypto.subtle.digest(algorithm, bytes);
  return [...new Uint8Array(buffer)].map(byte => byte.toString(16).padStart(2, '0')).join('');
}

async function gitBlobHash(bytes) {
  const header = encoder.encode('blob ' + bytes.length + '\0');
  const blob = new Uint8Array(header.length + bytes.length);
  blob.set(header);
  blob.set(bytes, header.length);
  return hash(blob, 'SHA-1');
}

function modelMetadata(sourceText, repo) {
  let data;
  try {
    data = JSON.parse(sourceText);
  } catch {
    requireEvidence(false, 'source-format');
  }
  requireEvidence(data?.id === repo && commit.test(data.sha ?? '') && Array.isArray(data.siblings),
    'source-identity');
  requireEvidence(data.private === false && data.gated === false && data.disabled === false, 'source-access');
  requireEvidence(typeof data.cardData?.license === 'string'
    && /^[A-Za-z0-9][A-Za-z0-9.+-]{0,60}$/u.test(data.cardData.license), 'source-license');
  return data;
}

async function artifactEvidence(data, filename, fetchSource, signal) {
  const matches = data.siblings.filter(file => file?.rfilename === filename);
  requireEvidence(matches.length === 1, 'artifact-unavailable');
  const entry = matches[0];
  requireEvidence(typeof entry.blobId === 'string' && commit.test(entry.blobId)
    && Number.isSafeInteger(entry.size) && entry.size > 0, 'artifact-identity');
  const base = hub + '/' + data.id;
  const path = data.sha + '/' + filename.split('/').map(encodeURIComponent).join('/');
  const evidenceURL = base + '/raw/' + path;
  const evidence = await readBounded(fetchSource, evidenceURL, entry.lfs ? 1024 : maxMetadataBytes, signal);
  requireEvidence(evidence.headers.get('x-repo-commit') === data.sha, 'artifact-revision');
  requireEvidence(await gitBlobHash(evidence.bytes) === entry.blobId, 'artifact-integrity');
  let sha256;
  let pointer;
  if (entry.lfs) {
    pointer = decode(evidence.bytes);
    const parts = /^version https:\/\/git-lfs\.github\.com\/spec\/v1\noid sha256:([a-f0-9]{64})\nsize ([1-9][0-9]*)\n?$/u.exec(pointer);
    requireEvidence(parts && digest.test(entry.lfs.sha256 ?? '') && entry.lfs.sha256 === parts[1]
      && Number(parts[2]) === entry.lfs.size && entry.lfs.size === entry.size, 'artifact-integrity');
    sha256 = parts[1];
  } else {
    requireEvidence(evidence.bytes.length === entry.size, 'artifact-integrity');
    sha256 = await hash(evidence.bytes);
  }
  return {
    filename, bytes: entry.size, sha256, downloadURL: base + '/resolve/' + path, evidenceURL,
    evidenceBytes: evidence.bytes.length, evidenceSha256: await hash(evidence.bytes),
    gitBlobSha1: entry.blobId, ...(pointer === undefined ? {} : {lfsPointer: pointer}),
  };
}

/** Acquire the public distribution record without downloading weights or invoking a model. */
export async function runOpportunityOperation(input, {fetchSource = globalThis.fetch, now, signal} = {}) {
  const plan = opportunityOperation({operation: input});
  requireEvidence(plan, 'invalid-operation');
  const url = hub + '/api/models/' + plan.repo + '?blobs=true';
  const {bytes, headers} = await readBounded(fetchSource, url, maxMetadataBytes, signal);
  requireEvidence(headers.get('content-type')?.startsWith('application/json'), 'source-format');
  const sourceText = decode(bytes);
  const data = modelMetadata(sourceText, plan.repo);
  const artifacts = await Promise.all([plan.filename, ...plan.requiredFilenames]
    .map(filename => artifactEvidence(data, filename, fetchSource, signal)));
  const alternate = plan.comparisonFilename === undefined ? undefined
    : await artifactEvidence(data, plan.comparisonFilename, fetchSource, signal);
  const totalBytes = artifacts.reduce((sum, file) => sum + file.bytes, 0);
  requireEvidence(Number.isSafeInteger(totalBytes), 'artifact-identity');
  const repoName = data.id.replace('/', '-').toLowerCase();
  const fileLabel = repoName.length > 105
    ? repoName.slice(0, 92) + '-' + (await hash(encoder.encode(data.id))).slice(0, 12)
    : repoName;
  const stem = 'frontier-' + fileLabel + '-' + data.sha.slice(0, 12);
  const source = {url, sha256: await hash(bytes), bytes: bytes.length, filename: stem + '-hub-source.json'};
  signal?.throwIfAborted();
  const manifest = {
    schema: 'frontier/model-distribution-manifest-v1', repo: data.id, revision: data.sha,
    retrievedAt: (now ?? new Date()).toISOString(), declaredLicense: data.cardData.license,
    modelCardURL: hub + '/' + data.id + '/blob/' + data.sha + '/README.md',
    totalBytes, artifacts, source,
    acquiredEvidenceBytes: bytes.length + artifacts.reduce((sum, file) => sum + file.evidenceBytes, 0)
      + (alternate?.evidenceBytes ?? 0),
    ...(alternate === undefined ? {} : {comparison: {...alternate, deltaBytes: alternate.bytes - artifacts[0].bytes}}),
    qualification: {
      distributionMetadata: 'matched-immutable-source',
      weightBytesAcquired: false,
      runtimeCompatibilityTested: false,
      modelQualityTested: false,
    },
  };
  return {...manifest, files: [
    {name: stem + '-deployment-manifest.json', content: JSON.stringify(manifest, null, 2) + '\n'},
    {name: source.filename, content: sourceText},
  ]};
}
