// Node 22+ offline operation. All authority remains with the local operator.
import {readFile, stat, open} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {compare, formulaPrompt, freeze, maxBytes, promptFor, readJSON, reopen, requalify, retain, run} from './foundry-core.mjs';

async function read(path, fence = false) {
  const info = await stat(path);
  if (!info.isFile() || info.size > maxBytes) throw new Error('FILE');
  const handle = await open(path);
  try {
    const data = Buffer.alloc(maxBytes + 1);
    const {bytesRead} = await handle.read(data, 0, data.length);
    return readJSON(new TextDecoder('utf-8', {fatal:true}).decode(data.subarray(0, bytesRead)), fence);
  } finally { await handle.close(); }
}

const print = value => console.log(JSON.stringify(value, null, 2));
const [command,...files] = process.argv.slice(2);
const lengths = {prompt:1, 'formula-prompt':1, seal:2, check:3, retain:3, recheck:2, run:3, demo:0};
try {
  if (!Object.hasOwn(lengths, command) || files.length !== lengths[command]) throw new Error('USAGE');
  if (command === 'demo') {
    const d = await read(fileURLToPath(new URL('./example.json', import.meta.url)));
    const frozen = await freeze(d.task, d.candidate);
    const {summary} = await compare(frozen, d.suite);
    print({summary, result:run(frozen, d.sample)});
    if (summary.verdict !== 'MATCHED') process.exitCode = 2;
  } else if (command === 'prompt' || command === 'formula-prompt') {
    const task = await read(files[0]);
    console.log(command === 'prompt' ? promptFor(task) : formulaPrompt(task));
  } else if (command === 'run' || command === 'recheck') {
    const item = await reopen(await read(files[0]));
    const verified = await requalify(item, await read(files[1]));
    print(command === 'recheck' ? verified : run(item.frozen, await read(files[2])));
  } else {
    const frozen = await freeze(await read(files[0]), await read(files[1], true));
    if (command === 'seal') print(frozen);
    else {
      const sheet = await read(files[2]);
      if (command === 'retain') print(await retain(frozen, sheet));
      else {
        const comparison = await compare(frozen, sheet);
        print(comparison);
        if (comparison.summary.verdict !== 'MATCHED') process.exitCode = 2;
      }
    }
  }
} catch (error) {
  // Do not repeat arbitrary filenames, private input data or model responses in diagnostics.
  const known = ['FILE','JSON','MISSION','CANDIDATE','SUITE','ASSET','RECHECK','INPUT','OUTPUT','EXECUTION','REJECTED'];
  console.error('Foundry: ' + (known.includes(error.message) ? error.message :
    'expected prompt/formula-prompt MISSION | seal MISSION CANDIDATE | check/retain MISSION CANDIDATE CASES | recheck ASSET CASES | run ASSET CASES INPUT | demo'));
  process.exitCode = 2;
}
