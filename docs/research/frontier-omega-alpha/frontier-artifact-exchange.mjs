export const maximumArtifactBytes = 256 * 1024;
export const maximumArtifacts = 8;

const extensions = new Map([
  ['txt','text'], ['md','text'], ['csv','data'], ['tsv','data'], ['json','data'], ['ipynb','notebook'],
  ['py','source'], ['js','source'], ['mjs','source'], ['ts','source'], ['sql','source'], ['yaml','source'], ['yml','source'], ['zip','archive'],
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
  const text = typeof work === 'string' ? work : '';
  const sources = [...new Set([...text.matchAll(/https:\/\/[^\s<>"\]'`]+/gu)].map(match => match[0]))].slice(0,8);
  return {
    missing: expected.filter(filename => !present.has(filename)),
    sourceSnippet: /^\s{0,3}(?:`{3,}|~{3,})(?:python|py|js|javascript|mjs|typescript|ts|sql|bash|sh|r|julia)\b/imu.test(text),
    sources,
    hasTable: /^\s*\|.+\|\s*\n\s*\|?[ :|-]+\|/mu.test(text),
  };
}

function validJSON(text, notebook) {
  try {
    const data = JSON.parse(text.replace(/^\ufeff/u, ''));
    return !notebook || data && Number.isInteger(data.nbformat) && Array.isArray(data.cells);
  } catch { return false; }
}

export function isMissionArtifact(file) {
  const valid = file && Object.keys(file).length === 6 && typeof file.content === 'string' &&
    file.kind !== undefined && file.kind === kind(file.name) &&
    Number.isSafeInteger(file.revision) && file.revision > 0 &&
    Number.isSafeInteger(file.bytes) && file.bytes > 0 && file.bytes <= maximumArtifactBytes &&
    typeof file.sha256 === 'string' && sha.test(file.sha256);
  if (!valid) return false;
  if (file.kind === 'archive') return file.content.length === 4 * Math.ceil(file.bytes / 3)
    && /^[A-Za-z0-9+/]+={0,2}$/u.test(file.content) && decodeArchive(file.content)?.length === file.bytes;
  return file.content.length <= maximumArtifactBytes && encoder.encode(file.content).length === file.bytes &&
    file.content.trim().length > 0 && !control.test(file.content) &&
    (!(file.kind === 'notebook' || /\.json$/iu.test(file.name)) || validJSON(file.content, file.kind === 'notebook'));
}

async function sha256(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
  return Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('');
}

export async function readMissionArtifact(file, revision) {
  const type = kind(file.name);
  if (!type || type === 'archive' || file.size <= 0 || file.size > maximumArtifactBytes) throw new Error('ARTIFACT_FILE');
  const bytes = await file.arrayBuffer();
  const content = new TextDecoder('utf-8', {fatal:true, ignoreBOM:true}).decode(bytes);
  const artifact = {name:file.name, kind:kind(file.name), bytes:bytes.byteLength, sha256:await sha256(bytes), content, revision};
  if (!isMissionArtifact(artifact)) throw new Error('ARTIFACT_CONTENT');
  return artifact;
}

function decodeArchive(content) {
  try { return Uint8Array.from(atob(content), character => character.charCodeAt(0)); }
  catch { return undefined; }
}

export function missionArtifactBytes(file) {
  return file.kind === 'archive' ? decodeArchive(file.content) : encoder.encode(file.content);
}

function zipRequire(condition) {
  if (!condition) throw new Error('ARTIFACT_ARCHIVE');
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function unpack(bytes, method, size) {
  if (method === 0) { zipRequire(bytes.length === size); return bytes; }
  const output = new Uint8Array(size);
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('deflate-raw')).getReader();
  let filled = 0;
  try {
    while (true) {
      const {done,value} = await stream.read();
      if (done) break;
      zipRequire(filled + value.length <= size);
      output.set(value,filled);
      filled += value.length;
    }
    zipRequire(filled === size);
    return output;
  } finally { await stream.cancel().catch(() => {}); }
}

async function zipEntries(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const short = position => view.getUint16(position,true);
  const long = position => view.getUint32(position,true);
  const decoder = new TextDecoder('utf-8',{fatal:true,ignoreBOM:true});
  let end = bytes.length - 22;
  while (end >= Math.max(0,bytes.length - 65557) && (long(end) !== 0x06054b50 || end + 22 + short(end+20) !== bytes.length)) end--;
  zipRequire(end >= 0 && end >= bytes.length - 65557 && short(end+4) === 0 && short(end+6) === 0);
  const count = short(end+10);
  const start = long(end+16);
  zipRequire(count > 0 && count < maximumArtifacts && short(end+8) === count && start + long(end+12) === end);
  const entries = [], names = new Set(), ranges = [];
  let position = start, combined = bytes.length;
  for (let index = 0; index < count; index++) {
    zipRequire(position + 46 <= end && long(position) === 0x02014b50 && !short(position+34));
    const flags = short(position+8), method = short(position+10), crc = long(position+16);
    const compressed = long(position+20), size = long(position+24), nameLength = short(position+28);
    const after = position + 46 + nameLength + short(position+30) + short(position+32);
    const offset = long(position+42);
    const fileMode = (long(position+38) >>> 16) & 0xf000;
    combined += size;
    zipRequire((flags & ~0x0800) === 0 && (method === 0 || method === 8) && (fileMode === 0 || fileMode === 0x8000)
      && after <= end && nameLength && compressed && size && combined <= maximumArtifactBytes && offset + 30 <= start);
    const original = decoder.decode(bytes.subarray(position+46,position+46+nameLength));
    const parts = original.split('/');
    const filename = parts.at(-1);
    zipRequire(parts.every(part => part && part === part.trim() && part !== '.' && part !== '..' && !/[\\:\u0000-\u001f\u007f]/u.test(part))
      && kind(filename) && kind(filename) !== 'archive' && !names.has(filename.toLowerCase()));
    zipRequire(long(offset) === 0x04034b50 && short(offset+6) === flags && short(offset+8) === method && long(offset+14) === crc
      && long(offset+18) === compressed && long(offset+22) === size && short(offset+26) === nameLength);
    const dataStart = offset + 30 + nameLength + short(offset+28);
    const dataEnd = dataStart + compressed;
    zipRequire(dataEnd <= start && decoder.decode(bytes.subarray(offset+30,offset+30+nameLength)) === original
      && !ranges.some(([left,right]) => offset < right && left < dataEnd));
    names.add(filename.toLowerCase());
    ranges.push([offset,dataEnd]);
    entries.push({filename,method,crc,size,bytes:bytes.subarray(dataStart,dataEnd)});
    position = after;
  }
  zipRequire(position === end);
  return entries;
}

export async function importMissionArtifacts(file, revision) {
  if (kind(file.name) !== 'archive') return [await readMissionArtifact(file, revision)];
  zipRequire(file.size > 0 && file.size <= maximumArtifactBytes);
  const bytes = new Uint8Array(await file.arrayBuffer());
  zipRequire(bytes.length === file.size);
  const results = [];
  for (const item of await zipEntries(bytes)) {
    const data = await unpack(item.bytes,item.method,item.size);
    zipRequire(crc32(data) === item.crc);
    results.push(await readMissionArtifact(new File([data],item.filename),revision));
  }
  const content = btoa(Array.from(bytes, byte => String.fromCharCode(byte)).join(''));
  return [{name:file.name,kind:'archive',bytes:bytes.length,sha256:await sha256(bytes),content,revision},...results];
}

export async function verifyMissionArtifact(file) {
  if (!isMissionArtifact(file) || await sha256(missionArtifactBytes(file)) !== file.sha256) return false;
  if (file.kind !== 'archive') return true;
  try { await importMissionArtifacts(new File([missionArtifactBytes(file)],file.name),file.revision); return true; }
  catch { return false; }
}
