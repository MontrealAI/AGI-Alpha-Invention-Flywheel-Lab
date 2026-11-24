import {open} from 'node:fs/promises';
import {maxBytes, readJSON} from './foundry-core.mjs';
import {constructionPlan, evaluateStudy, registerStudy, replayStudy} from './foundry-study.mjs';

async function read(path) {
  const file = await open(path, 'r');
  try {
    const info = await file.stat();
    if (!info.isFile() || info.size > maxBytes) throw new Error('FILE');
    const buffer = Buffer.alloc(maxBytes + 1);
    const {bytesRead} = await file.read(buffer, 0, buffer.length);
    return readJSON(new TextDecoder('utf-8', {fatal:true}).decode(buffer.subarray(0, bytesRead)));
  } finally { await file.close(); }
}

const actions = {
  register:{arguments:5, run:registerStudy},
  plan:{arguments:1, run:constructionPlan},
  grade:{arguments:3, run:evaluateStudy},
  replay:{arguments:2, run:replayStudy},
};
const [command, ...files] = process.argv.slice(2);
try {
  if (!Object.hasOwn(actions, command) || files.length !== actions[command].arguments) throw new Error('USAGE');
  const result = await actions[command].run(...await Promise.all(files.map(read)));
  const output = JSON.stringify(result);
  if (Buffer.byteLength(output) >= maxBytes) throw new Error('FILE');
  console.log(output);
} catch (error) {
  const codes = ['STUDY','FILE','JSON','MISSION','CANDIDATE','SUITE','ASSET','RECHECK'];
  console.error('Study: ' + (codes.includes(error.message) ? error.message :
    'register SPEC PARENT PARENT_CASES INCUMBENT CASES | plan PLAN | grade PLAN CASES ATTEMPTS | replay REPORT CASES'));
  process.exitCode = 2;
}
