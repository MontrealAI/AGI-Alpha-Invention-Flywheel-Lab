export const maximumArtifactBytes = 256 * 1024;
export const maximumArtifacts = 8;

const extensions = new Map([
  ['txt','text'], ['md','text'], ['csv','data'], ['tsv','data'], ['json','data'], ['ipynb','notebook'],
  ['py','source'], ['js','source'], ['mjs','source'], ['ts','source'], ['sql','source'], ['yaml','source'], ['yml','source'],
]);
const encoder = new TextEncoder();
const control = /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u;
const name = /^[^\s./\\:][^/\\:\u0000-\u001f\u007f]{0,175}\.[a-z0-9]{1,6}$/iu;
const sha = /^[a-f0-9]{64}$/u;

function kind(filename) {
  if (typeof filename !== 'string' || !name.test(filename) ||
      /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])\.|[\u202a-\u202e\u2066-\u2069]/iu.test(filename)) return undefined;
  return extensions.get(filename.slice(filename.lastIndexOf('.') + 1).toLowerCase());
}

export function artifactReferences(work) {
  if (typeof work !== 'string') return [];
  const found = new Set();
  for (const match of work.matchAll(/(?:sandbox:\/mnt\/data\/|(?<![\p{L}\p{N}:/.-])\/mnt\/data\/)([^\s<>"')`]+)/gu)) {
    try {
      const parts = match[1].replace(/[.,;]+$/u, '').split('/').map(part => decodeURIComponent(part));
      const filename = parts.at(-1);
      if (kind(filename) && parts.every(part => part && !['.','..'].includes(part) && !/[\/\\]/u.test(part))) {
        found.add(filename);
      }
    } catch { /* An incomplete path cannot identify a file. */ }
    if (found.size >= maximumArtifacts) break;
  }
  return [...found];
}

export function inspectReturnedWork(work, artifacts = []) {
  const expected = artifactReferences(work);
  const present = new Set(artifacts.map(file => file.name));
  return {
    missing: expected.filter(filename => !present.has(filename)),
    sourceSnippet: typeof work === 'string' && /^\s{0,3}(?:`{3,}|~{3,})(?:python|py|js|javascript|mjs|typescript|ts|sql|bash|sh|r|julia)\b/imu.test(work),
  };
}

function validJSON(text, notebook) {
  try {
    const data = JSON.parse(text.replace(/^\ufeff/u, ''));
    return !notebook || data && Number.isInteger(data.nbformat) && Array.isArray(data.cells);
  } catch { return false; }
}

export function isMissionArtifact(file) {
  return file && Object.keys(file).length === 6 && typeof file.content === 'string' &&
    file.kind !== undefined && file.kind === kind(file.name) &&
    Number.isSafeInteger(file.revision) && file.revision > 0 &&
    Number.isSafeInteger(file.bytes) && file.bytes > 0 && file.bytes <= maximumArtifactBytes &&
    file.content.length <= maximumArtifactBytes && encoder.encode(file.content).length === file.bytes &&
    file.content.trim().length > 0 && !control.test(file.content) &&
    typeof file.sha256 === 'string' && sha.test(file.sha256) &&
    (!(file.kind === 'notebook' || /\.json$/iu.test(file.name)) || validJSON(file.content, file.kind === 'notebook'));
}

async function sha256(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('');
}

export async function readMissionArtifact(file, revision) {
  if (!kind(file.name) || file.size <= 0 || file.size > maximumArtifactBytes) throw new Error('ARTIFACT_FILE');
  const bytes = await file.arrayBuffer();
  const content = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(bytes);
  const artifact = {name:file.name, kind:kind(file.name), bytes:bytes.byteLength, sha256:await sha256(bytes), content, revision};
  if (!isMissionArtifact(artifact)) throw new Error('ARTIFACT_CONTENT');
  return artifact;
}

export async function verifyMissionArtifact(file) {
  return isMissionArtifact(file) && await sha256(encoder.encode(file.content)) === file.sha256;
}
