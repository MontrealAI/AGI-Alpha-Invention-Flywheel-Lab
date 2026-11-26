import {readFileSync} from 'node:fs';
import {basename} from 'node:path';
import {createHash} from 'node:crypto';
import {evaluateMissionFiles} from './frontier-native-work.mjs';
function artifact(name,content){return {name,content,kind:'data',sha256:createHash('sha256').update(content).digest('hex')}}
const plan=artifact('plan.json',readFileSync(process.argv[2],'utf8'));
const source=artifact(basename(process.argv[3]),readFileSync(process.argv[3],'utf8'));
console.log(JSON.stringify(evaluateMissionFiles([plan,source])));
