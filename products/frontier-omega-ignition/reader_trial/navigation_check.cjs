'use strict';
// Execute the unmodified inline script in a generated packet. This DOM contract
// captures rendered links, snippets and status; browser layout is tested separately.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync(process.argv[2], 'utf8');
class Element {
  constructor() { this.children = []; this.listeners = {}; this.textContent = ''; }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  replaceChildren() { this.children = []; }
  append(...nodes) { this.children.push(...nodes); }
}
const nodes = Object.fromEntries(['pages','query','summary','hits'].map(id => ['#'+id,new Element()]));
nodes['#pages'].textContent = html.match(/<script type="application\/json" id="pages">([\s\S]*?)<\/script>/)[1];
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const doc = {documentElement:{lang:'en'}, querySelector:id=>nodes[id], createElement:()=>new Element()};
vm.runInNewContext(script,{document:doc});
const queries = [
  ['−5.02',[1]], ['-5.02',[1]], ['+5.02',[2]], ['5.02',[]], ['90%',[1]], ['90',[2]],
  ['90.5%',[3]], ['2e-3',[1]], ['2e+3',[2]], ['"x <= 5"',[1]], ['"5 ≤ x"',[2]],
  ['"x ≥ 5"',[3]], ['"x < 5"',[4]], ['measured yield',[1,2,3,4]], ['unknownword',[]]
];
const results = [];
for (const [query, expected] of queries) {
  nodes['#query'].value = query;
  nodes['#query'].listeners.input();
  const links = nodes['#hits'].children.map(article => {
    const [link, snippet] = article.children;
    assert.ok(snippet.textContent.trim());
    assert.match(link.href,/^fixture\.pdf#page=\d+$/);
    return Number(link.href.split('=').pop());
  });
  assert.match(nodes['#summary'].textContent,new RegExp('^'+links.length+' '));
  results.push({query, expected, observed:links, passed:JSON.stringify(links)===JSON.stringify(expected)});
}
console.log(JSON.stringify(results));
