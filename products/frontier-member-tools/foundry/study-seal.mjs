import {createInterface} from 'node:readline';
import {freeze, maxBytes, readJSON} from './foundry-core.mjs';

try {
  let input = '';
  for await (const line of createInterface({input:process.stdin, crlfDelay:Infinity})) {
    input += line + '\n';
    if (input.length > maxBytes) throw new Error('FILE');
  }
  const {task, candidate} = readJSON(input);
  await freeze(task, candidate);
} catch {
  process.exitCode = 2;
}
