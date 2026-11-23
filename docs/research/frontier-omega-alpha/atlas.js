/* The rendered Atlas remains available when JavaScript is disabled. */
const controls = document.getElementById('atlas-controls');
const query = document.getElementById('atlas-query');
const filter = document.getElementById('atlas-state');
const count = document.getElementById('atlas-count');
const normalize = text => text.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
const cards = [...document.querySelectorAll('[data-atlas-record]')].map(node => ({
  node,
  state: node.dataset.state,
  label: node.querySelector('.atlas-card-meta strong').textContent,
  text: normalize(node.textContent),
}));
const states = new Map(cards.map(({state, label}) => [state, label]));
const sorter = new Intl.Collator(document.documentElement.lang);
for (const [state, label] of [...states].sort((a, b) => sorter.compare(a[1], b[1]))) {
  filter.append(new Option(label, state));
}

function update() {
  const terms = normalize(query.value).trim().split(/\s+/).filter(Boolean);
  let visible = 0;
  for (const {node, state, text} of cards) {
    node.hidden = (filter.value !== '' && filter.value !== state) || !terms.every(term => text.includes(term));
    if (!node.hidden) visible++;
  }
  count.textContent = visible ? `${visible} / ${cards.length} · ${count.dataset.label}` : count.dataset.empty;
}

query.addEventListener('input', update);
filter.addEventListener('change', update);
window.addEventListener('hashchange', () => {
  const destination = document.getElementById(location.hash.slice(1));
  const card = destination?.closest('[data-atlas-record]');
  if (card?.hidden) {
    filter.value = '';
    query.value = '';
    update();
    card.scrollIntoView();
  }
});
controls.hidden = false;
update();
