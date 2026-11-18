'use strict';
const pages = JSON.parse(document.querySelector('#pages').textContent);
const query = document.querySelector('#query');
const hits = document.querySelector('#hits');
const summary = document.querySelector('#summary');

// Keep scientific literals intact. Numeric queries must not silently match the
// opposite sign, a fractional prefix, a different exponent or a percent.
function tokens(text) {
  const normalized = text.normalize('NFC').toLowerCase()
    .replaceAll('−','-').replaceAll('<=','≤').replaceAll('>=','≥').replaceAll('!=','≠');
  const pattern = /[+\-]?(?:\p{Nd}+(?:[.,]\p{Nd}+)*|[.,]\p{Nd}+)(?:e[+\-]?\p{Nd}+)?(?:[ \u00a0\u202f]?[%‰])?|[\p{L}\p{M}]+[\p{L}\p{M}\p{Nd}]*|[\p{Sm}+\-^*/()[\]{}%‰]/gu;
  return (normalized.match(pattern) || []).map(token => token.replace(/[ \u00a0\u202f]/g,''));
}
const index = pages.map(text => {
  const lines = text.split('\n');
  const lineTokens = lines.map(tokens);
  const ordered = lineTokens.flat();
  return {lines, lineTokens, ordered, unique:new Set(ordered)};
});

function phraseStart(ordered, terms) {
  return ordered.findIndex((first, start) =>
    first === terms[0] && terms.every((term, offset) => ordered[start + offset] === term));
}

query.addEventListener('input', () => {
  hits.replaceChildren();
  const value = query.value.trim();
  const phrase = /^"([\s\S]*)"$/.exec(value) || /^«([\s\S]*)»$/.exec(value);
  const terms = tokens(phrase ? phrase[1] : value);
  if (!terms.length) { summary.textContent = ''; return; }
  let count = 0;
  index.forEach((page, number) => {
    if (!terms.every(term => page.unique.has(term))) return;
    let best;
    if (phrase) {
      const start = phraseStart(page.ordered, terms);
      if (start < 0) return;
      let end = 0;
      best = page.lineTokens.findIndex(line => { end += line.length; return start < end; });
    } else {
      const scores = page.lineTokens.map(line => terms.filter(term => line.includes(term)).length);
      best = scores.indexOf(Math.max(...scores));
    }
    count++;
    const article = document.createElement('article');
    const link = document.createElement('a');
    const sample = document.createElement('pre');
    link.href = pdf+'#page='+(number+1);
    link.textContent = label+' '+(number+1);
    sample.textContent = page.lines.slice(Math.max(0,best-1),best+3).join('\n');
    article.append(link,sample);
    hits.append(article);
  });
  summary.textContent = document.documentElement.lang === 'fr' ?
    count+' page(s) trouvée(s).' : count+' matching page(s).';
});
